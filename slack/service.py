"""Slack integration service - runs Socket Mode handler and ingestion."""

import signal
import time
from typing import Optional
import structlog

from database import DatabaseConnection
from slack.client import SlackClient
from slack.socket_handler import SocketModeHandler
from slack.ingest import SlackIngestor
from agent.event_processor import EventProcessor

logger = structlog.get_logger(__name__)


class SlackService:
    """Slack integration service that handles real-time events."""

    def __init__(
        self,
        app_token: str,
        bot_token: str,
        db_connection: DatabaseConnection,
    ):
        """Initialize Slack service.

        Args:
            app_token: Slack app-level token (xapp-...)
            bot_token: Slack bot OAuth token (xoxb-...)
            db_connection: Database connection
        """
        self.app_token = app_token
        self.bot_token = bot_token
        self.db_connection = db_connection

        # Initialize components
        self.slack_client = SlackClient(bot_token=bot_token)
        self.socket_handler: Optional[SocketModeHandler] = None

        self._running = False
        self._shutdown_requested = False

        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        logger.info("slack_service_initialized")

    def _handle_event(self, event: dict):
        """Handle incoming Slack event.

        Args:
            event: Slack event data
        """
        event_type = event.get("type")
        event_subtype = event.get("subtype")

        logger.info(
            "handling_slack_event",
            event_type=event_type,
            subtype=event_subtype,
        )

        try:
            with self.db_connection.session() as session:
                ingestor = SlackIngestor(session, event_processor=EventProcessor(session, "slack-service"))

                # Handle different event types
                if event_type == "app_mention":
                    self._handle_app_mention(event, ingestor)

                elif event_type == "message":
                    self._handle_message(event, ingestor)

                elif event_type == "reaction_added":
                    self._handle_reaction_added(event, ingestor)

                elif event_type == "reaction_removed":
                    self._handle_reaction_removed(event, ingestor)

                elif event_type == "user_change":
                    self._handle_user_change(event, ingestor)

                elif event_type in ["channel_created", "channel_deleted", "channel_archive", "channel_unarchive"]:
                    self._handle_channel_event(event, ingestor)

                else:
                    logger.debug("unhandled_event_type", event_type=event_type)

        except Exception as e:
            logger.error(
                "event_handling_error",
                event_type=event_type,
                error=str(e),
            )

    def _handle_app_mention(self, event: dict, ingestor: SlackIngestor):
        """Handle app_mention event.

        Args:
            event: Event data
            ingestor: Slack ingestor
        """
        channel = event.get("channel")
        ts = event.get("ts")

        logger.info("handling_app_mention", channel=channel, ts=ts)

        # Ingest the message (will also queue for agent processing)
        ingestor.ingest_message(event, channel)

    def _handle_message(self, event: dict, ingestor: SlackIngestor):
        """Handle message event.

        Args:
            event: Event data
            ingestor: Slack ingestor
        """
        channel = event.get("channel")
        subtype = event.get("subtype")

        # Skip certain subtypes
        if subtype in ["bot_message", "channel_join", "channel_leave"]:
            logger.debug("skipping_message_subtype", subtype=subtype)
            return

        # Ingest the message
        ingestor.ingest_message(event, channel)

    def _handle_reaction_added(self, event: dict, ingestor: SlackIngestor):
        """Handle reaction_added event.

        Args:
            event: Event data
            ingestor: Slack ingestor
        """
        ingestor.ingest_reaction(event)

    def _handle_reaction_removed(self, event: dict, ingestor: SlackIngestor):
        """Handle reaction_removed event.

        Args:
            event: Event data
            ingestor: Slack ingestor
        """
        ingestor.remove_reaction(event)

    def _handle_user_change(self, event: dict, ingestor: SlackIngestor):
        """Handle user_change event.

        Args:
            event: Event data
            ingestor: Slack ingestor
        """
        user_data = event.get("user", {})
        if user_data:
            ingestor.ingest_user(user_data)

    def _handle_channel_event(self, event: dict, ingestor: SlackIngestor):
        """Handle channel creation/deletion/archive events.

        Args:
            event: Event data
            ingestor: Slack ingestor
        """
        channel_data = event.get("channel", {})
        if channel_data:
            ingestor.ingest_channel(channel_data)

    def start(self):
        """Start the Slack service."""
        if self._running:
            logger.warning("slack_service_already_running")
            return

        logger.info("slack_service_starting")

        # Initialize Socket Mode handler
        self.socket_handler = SocketModeHandler(
            app_token=self.app_token,
            event_handler=self._handle_event,
            auto_reconnect=True,
        )

        # Start Socket Mode connection
        self.socket_handler.start()
        self._running = True

        logger.info("slack_service_started")

    def stop(self):
        """Stop the Slack service."""
        if not self._running:
            logger.warning("slack_service_not_running")
            return

        logger.info("slack_service_stopping")

        # Stop Socket Mode handler
        if self.socket_handler:
            self.socket_handler.stop()
            self.socket_handler = None

        self._running = False

        logger.info("slack_service_stopped")

    def is_running(self) -> bool:
        """Check if service is running.

        Returns:
            True if running, False otherwise
        """
        return self._running and (self.socket_handler is not None) and self.socket_handler.is_connected()

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        signal_name = signal.Signals(signum).name
        logger.info("shutdown_signal_received", signal=signal_name)

        if not self._shutdown_requested:
            self._shutdown_requested = True
            self.stop()

    def run_forever(self):
        """Run the service until shutdown is requested.

        This method blocks until a shutdown signal is received.
        """
        logger.info("slack_service_running")

        try:
            while not self._shutdown_requested:
                time.sleep(1)

                # Log status every minute
                if int(time.time()) % 60 == 0:
                    logger.info(
                        "slack_service_status",
                        is_running=self.is_running(),
                        is_connected=self.socket_handler.is_connected() if self.socket_handler else False,
                    )

        except KeyboardInterrupt:
            logger.info("keyboard_interrupt_received")

        finally:
            self.stop()
