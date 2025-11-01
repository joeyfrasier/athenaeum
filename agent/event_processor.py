"""Event processor with atomic claiming for exactly-once processing."""

import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text
import structlog

from database.models import Event

logger = structlog.get_logger(__name__)


class EventProcessor:
    """Processes events with exactly-once semantics using PostgreSQL-backed claiming."""

    def __init__(
        self,
        session: Session,
        worker_id: str,
        visibility_timeout: int = 300,  # 5 minutes
        max_retry_count: int = 3,
    ):
        """Initialize event processor.

        Args:
            session: Database session
            worker_id: Unique worker identifier
            visibility_timeout: Seconds before a processing event becomes visible again
            max_retry_count: Maximum number of retries for failed events
        """
        self.session = session
        self.worker_id = worker_id
        self.visibility_timeout = visibility_timeout
        self.max_retry_count = max_retry_count

        logger.info(
            "event_processor_initialized",
            worker_id=worker_id,
            visibility_timeout=visibility_timeout,
            max_retry_count=max_retry_count,
        )

    def claim_event(self) -> Optional[Event]:
        """Atomically claim a pending event for processing.

        Uses PostgreSQL's FOR UPDATE SKIP LOCKED to ensure exactly-once claiming
        even under high concurrency.

        Returns:
            Event if claimed, None if no events available
        """
        try:
            # Use raw SQL for atomic operation with SKIP LOCKED
            query = text(
                """
                UPDATE events
                SET status = 'processing',
                    claimed_by = :worker_id,
                    visibility_timeout = NOW() + INTERVAL ':timeout seconds'
                WHERE id = (
                    SELECT id FROM events
                    WHERE (status = 'pending' OR (status = 'processing' AND visibility_timeout < NOW()))
                      AND retry_count < :max_retry_count
                    ORDER BY created_at ASC
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING *
            """
            )

            result = self.session.execute(
                query,
                {
                    "worker_id": self.worker_id,
                    "timeout": self.visibility_timeout,
                    "max_retry_count": self.max_retry_count,
                },
            )

            row = result.fetchone()

            if row:
                # Convert row to Event object
                event = self.session.query(Event).filter(Event.id == row.id).first()

                logger.info(
                    "event_claimed",
                    event_id=event.id,
                    event_type=event.event_type,
                    worker_id=self.worker_id,
                    retry_count=event.retry_count,
                )

                self.session.commit()
                return event
            else:
                logger.debug("no_events_available", worker_id=self.worker_id)
                return None

        except Exception as e:
            self.session.rollback()
            logger.error(
                "event_claim_failed",
                worker_id=self.worker_id,
                error=str(e),
            )
            return None

    def complete_event(self, event: Event) -> bool:
        """Mark event as completed.

        Args:
            event: Event to mark as completed

        Returns:
            True if successful, False otherwise
        """
        try:
            event.status = "completed"
            event.processed_at = datetime.utcnow()
            event.visibility_timeout = None
            self.session.commit()

            logger.info(
                "event_completed",
                event_id=event.id,
                event_type=event.event_type,
                worker_id=self.worker_id,
                retry_count=event.retry_count,
                processing_duration=(event.processed_at - event.created_at).total_seconds(),
            )

            return True

        except Exception as e:
            self.session.rollback()
            logger.error(
                "event_completion_failed",
                event_id=event.id,
                worker_id=self.worker_id,
                error=str(e),
            )
            return False

    def fail_event(self, event: Event, error_message: str) -> bool:
        """Mark event as failed and increment retry count.

        Args:
            event: Event to mark as failed
            error_message: Error message describing the failure

        Returns:
            True if successful, False otherwise
        """
        try:
            event.retry_count += 1
            event.error_message = error_message

            if event.retry_count >= self.max_retry_count:
                # Max retries reached, mark as permanently failed
                event.status = "failed"
                event.processed_at = datetime.utcnow()
                event.visibility_timeout = None

                logger.error(
                    "event_failed_permanently",
                    event_id=event.id,
                    event_type=event.event_type,
                    worker_id=self.worker_id,
                    retry_count=event.retry_count,
                    error=error_message,
                )
            else:
                # Set back to pending with exponential backoff visibility timeout
                event.status = "pending"
                backoff_seconds = min(300, 2 ** event.retry_count * 10)  # Max 5 minutes
                event.visibility_timeout = datetime.utcnow() + timedelta(seconds=backoff_seconds)

                logger.warning(
                    "event_failed_will_retry",
                    event_id=event.id,
                    event_type=event.event_type,
                    worker_id=self.worker_id,
                    retry_count=event.retry_count,
                    next_retry_at=event.visibility_timeout.isoformat(),
                    error=error_message,
                )

            self.session.commit()
            return True

        except Exception as e:
            self.session.rollback()
            logger.error(
                "event_failure_update_failed",
                event_id=event.id,
                worker_id=self.worker_id,
                error=str(e),
            )
            return False

    def insert_event(self, event_type: str, payload: Dict[str, Any]) -> Optional[int]:
        """Insert a new event into the queue.

        Args:
            event_type: Type of event (e.g., "app_mention", "message")
            payload: Event payload as dictionary

        Returns:
            Event ID if successful, None otherwise
        """
        try:
            event = Event(
                event_type=event_type,
                payload=payload,
                status="pending",
            )

            self.session.add(event)
            self.session.commit()

            logger.info(
                "event_inserted",
                event_id=event.id,
                event_type=event_type,
            )

            return event.id

        except Exception as e:
            self.session.rollback()
            logger.error(
                "event_insertion_failed",
                event_type=event_type,
                error=str(e),
            )
            return None

    def get_event(self, event_id: int) -> Optional[Event]:
        """Get event by ID.

        Args:
            event_id: Event ID

        Returns:
            Event if found, None otherwise
        """
        try:
            return self.session.query(Event).filter(Event.id == event_id).first()
        except Exception as e:
            logger.error(
                "event_retrieval_failed",
                event_id=event_id,
                error=str(e),
            )
            return None

    def get_queue_depth(self) -> int:
        """Get number of pending events in the queue.

        Returns:
            Number of pending events
        """
        try:
            count = self.session.query(Event).filter(Event.status == "pending").count()
            return count
        except Exception as e:
            logger.error("queue_depth_query_failed", error=str(e))
            return -1

    def get_processing_count(self) -> int:
        """Get number of events currently being processed.

        Returns:
            Number of processing events
        """
        try:
            count = (
                self.session.query(Event)
                .filter(
                    Event.status == "processing",
                    Event.visibility_timeout > datetime.utcnow(),
                )
                .count()
            )
            return count
        except Exception as e:
            logger.error("processing_count_query_failed", error=str(e))
            return -1

    def get_queue_stats(self) -> Dict[str, int]:
        """Get queue statistics.

        Returns:
            Dictionary with queue statistics
        """
        try:
            result = self.session.query(
                Event.status,
                text("COUNT(*) as count"),
            ).group_by(Event.status).all()

            stats = {row.status: row.count for row in result}

            # Add expired processing events (need retry)
            expired = (
                self.session.query(Event)
                .filter(
                    Event.status == "processing",
                    Event.visibility_timeout < datetime.utcnow(),
                )
                .count()
            )
            stats["expired_processing"] = expired

            return stats

        except Exception as e:
            logger.error("queue_stats_query_failed", error=str(e))
            return {}


class EventProcessingError(Exception):
    """Base exception for event processing errors."""

    pass


class EventClaimError(EventProcessingError):
    """Error claiming an event."""

    pass


class EventProcessError(EventProcessingError):
    """Error processing an event."""

    pass
