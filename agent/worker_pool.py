"""Worker pool with bounded concurrency for agent processing."""

import threading
import time
import signal
from typing import Optional, Callable, Any
from dataclasses import dataclass
import structlog

from agent.event_processor import EventProcessor
from database.models import Event
from database.connection import DatabaseConnection

logger = structlog.get_logger(__name__)


@dataclass
class WorkerStats:
    """Statistics for a single worker."""

    worker_id: str
    events_processed: int = 0
    events_failed: int = 0
    last_event_at: Optional[float] = None
    is_running: bool = False


class Worker(threading.Thread):
    """Individual worker that processes events from the queue."""

    def __init__(
        self,
        worker_id: str,
        db_connection: DatabaseConnection,
        process_func: Callable[[Event], None],
        poll_interval: float = 1.0,
    ):
        """Initialize worker.

        Args:
            worker_id: Unique worker identifier
            db_connection: Database connection
            process_func: Function to process events
            poll_interval: Seconds to wait between polling for events
        """
        super().__init__(name=worker_id, daemon=True)
        self.worker_id = worker_id
        self.db_connection = db_connection
        self.process_func = process_func
        self.poll_interval = poll_interval

        self._stop_event = threading.Event()
        self.stats = WorkerStats(worker_id=worker_id)

        logger.info("worker_initialized", worker_id=worker_id)

    def run(self):
        """Main worker loop."""
        self.stats.is_running = True
        logger.info("worker_started", worker_id=self.worker_id)

        while not self._stop_event.is_set():
            try:
                # Get a new database session for this iteration
                with self.db_connection.session() as session:
                    processor = EventProcessor(session, worker_id=self.worker_id)

                    # Try to claim an event
                    event = processor.claim_event()

                    if event:
                        # Process the event
                        self.stats.last_event_at = time.time()
                        self._process_event(event, processor)
                    else:
                        # No events available, wait before polling again
                        time.sleep(self.poll_interval)

            except Exception as e:
                logger.error(
                    "worker_iteration_error",
                    worker_id=self.worker_id,
                    error=str(e),
                )
                time.sleep(self.poll_interval)

        self.stats.is_running = False
        logger.info(
            "worker_stopped",
            worker_id=self.worker_id,
            events_processed=self.stats.events_processed,
            events_failed=self.stats.events_failed,
        )

    def _process_event(self, event: Event, processor: EventProcessor):
        """Process a single event.

        Args:
            event: Event to process
            processor: Event processor for updating status
        """
        start_time = time.time()

        try:
            logger.info(
                "event_processing_started",
                worker_id=self.worker_id,
                event_id=event.id,
                event_type=event.event_type,
            )

            # Call the processing function
            self.process_func(event)

            # Mark as completed
            processor.complete_event(event)
            self.stats.events_processed += 1

            duration = time.time() - start_time
            logger.info(
                "event_processing_completed",
                worker_id=self.worker_id,
                event_id=event.id,
                event_type=event.event_type,
                duration=duration,
            )

        except Exception as e:
            # Mark as failed
            error_message = f"{type(e).__name__}: {str(e)}"
            processor.fail_event(event, error_message)
            self.stats.events_failed += 1

            duration = time.time() - start_time
            logger.error(
                "event_processing_failed",
                worker_id=self.worker_id,
                event_id=event.id,
                event_type=event.event_type,
                duration=duration,
                error=error_message,
            )

    def stop(self):
        """Signal worker to stop."""
        logger.info("worker_stopping", worker_id=self.worker_id)
        self._stop_event.set()

    def is_healthy(self) -> bool:
        """Check if worker is healthy.

        Returns:
            True if worker is running and responsive
        """
        if not self.stats.is_running:
            return False

        # Check if worker has been idle for too long (e.g., 10 minutes)
        if self.stats.last_event_at:
            idle_time = time.time() - self.stats.last_event_at
            if idle_time > 600:  # 10 minutes
                logger.warning(
                    "worker_idle",
                    worker_id=self.worker_id,
                    idle_seconds=idle_time,
                )

        return True


class WorkerPool:
    """Pool of workers with bounded concurrency."""

    def __init__(
        self,
        size: int,
        db_connection: DatabaseConnection,
        process_func: Callable[[Event], None],
        poll_interval: float = 1.0,
    ):
        """Initialize worker pool.

        Args:
            size: Number of workers in the pool
            db_connection: Database connection
            process_func: Function to process events
            poll_interval: Seconds to wait between polling for events
        """
        self.size = size
        self.db_connection = db_connection
        self.process_func = process_func
        self.poll_interval = poll_interval

        self.workers = []
        self._shutdown_requested = False

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        logger.info("worker_pool_initialized", pool_size=size)

    def start(self):
        """Start all workers in the pool."""
        if self.workers:
            logger.warning("worker_pool_already_started")
            return

        logger.info("worker_pool_starting", pool_size=self.size)

        for i in range(self.size):
            worker = Worker(
                worker_id=f"worker-{i}",
                db_connection=self.db_connection,
                process_func=self.process_func,
                poll_interval=self.poll_interval,
            )
            self.workers.append(worker)
            worker.start()

        logger.info("worker_pool_started", pool_size=self.size)

    def stop(self, timeout: float = 30.0):
        """Stop all workers gracefully.

        Args:
            timeout: Maximum seconds to wait for workers to stop
        """
        if not self.workers:
            return

        logger.info("worker_pool_stopping", pool_size=len(self.workers))

        # Signal all workers to stop
        for worker in self.workers:
            worker.stop()

        # Wait for all workers to finish
        start_time = time.time()
        for worker in self.workers:
            remaining_time = max(0, timeout - (time.time() - start_time))
            worker.join(timeout=remaining_time)

            if worker.is_alive():
                logger.warning(
                    "worker_did_not_stop",
                    worker_id=worker.worker_id,
                )

        self.workers.clear()
        logger.info("worker_pool_stopped")

    def get_stats(self) -> dict:
        """Get statistics for all workers.

        Returns:
            Dictionary with worker statistics
        """
        stats = {
            "pool_size": self.size,
            "workers_running": sum(1 for w in self.workers if w.stats.is_running),
            "total_events_processed": sum(w.stats.events_processed for w in self.workers),
            "total_events_failed": sum(w.stats.events_failed for w in self.workers),
            "workers": [
                {
                    "worker_id": w.worker_id,
                    "is_running": w.stats.is_running,
                    "events_processed": w.stats.events_processed,
                    "events_failed": w.stats.events_failed,
                    "last_event_at": w.stats.last_event_at,
                }
                for w in self.workers
            ],
        }

        return stats

    def health_check(self) -> bool:
        """Check if worker pool is healthy.

        Returns:
            True if all workers are healthy
        """
        if not self.workers:
            return False

        return all(worker.is_healthy() for worker in self.workers)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        signal_name = signal.Signals(signum).name
        logger.info("shutdown_signal_received", signal=signal_name)

        if not self._shutdown_requested:
            self._shutdown_requested = True
            self.stop()

    def run_forever(self):
        """Run the worker pool until shutdown is requested.

        This method blocks until a shutdown signal is received.
        """
        logger.info("worker_pool_running")

        try:
            while not self._shutdown_requested:
                time.sleep(1)

                # Periodically log statistics
                if int(time.time()) % 60 == 0:  # Every minute
                    stats = self.get_stats()
                    logger.info("worker_pool_stats", **stats)

        except KeyboardInterrupt:
            logger.info("keyboard_interrupt_received")

        finally:
            self.stop()
