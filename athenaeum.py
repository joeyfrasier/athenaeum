#!/usr/bin/env python3
"""Athenaeum - Production AI Agent System

Main entry point for the Athenaeum agent system.
Integrates Slack, Claude, and database components.
"""

import sys
import signal
import structlog
from typing import Optional

from agent.config import get_config
from agent.llm_client import ClaudeClient
from agent.core import AthenaeumAgent
from agent.event_processor import EventProcessor
from agent.worker_pool import WorkerPool
from database.connection import DatabaseConnection
from slack.client import SlackClient
from slack.socket_handler import SocketModeHandler

logger = structlog.get_logger(__name__)

# Global state for graceful shutdown
_shutdown_requested = False
_worker_pool: Optional[WorkerPool] = None
_socket_handler: Optional[SocketModeHandler] = None


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    global _shutdown_requested
    logger.info("shutdown_signal_received", signal=signum)
    _shutdown_requested = True

    # Stop worker pool
    if _worker_pool:
        _worker_pool.stop()

    # Stop socket handler
    if _socket_handler:
        _socket_handler.stop()


def setup_logging(log_level: str = "INFO"):
    """Configure structured logging.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def main():
    """Main entry point for Athenaeum."""
    global _worker_pool, _socket_handler

    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Load configuration
        config = get_config()
        setup_logging(config.log_level)

        logger.info("athenaeum_starting", version="0.3.0")
        config.log_configuration()

        # Validate configuration
        if not config.validate():
            logger.error("configuration_invalid")
            sys.exit(1)

        # Initialize database connection
        logger.info("initializing_database_connection")
        db_connection = DatabaseConnection(
            database_url=config.database_url,
            pool_size=config.worker_pool_size * 2,  # 2 connections per worker
        )

        # Test database connection
        if not db_connection.check_health():
            logger.error("database_health_check_failed")
            sys.exit(1)

        logger.info("database_connection_ready")

        # Initialize Slack clients
        logger.info("initializing_slack_clients")
        slack_client = SlackClient(bot_token=config.slack_bot_token)

        # Get bot user ID for context
        bot_info = slack_client.client.auth_test()
        bot_user_id = bot_info.data.get("user_id")
        logger.info("slack_bot_authenticated", bot_user_id=bot_user_id)

        # Initialize Claude client
        logger.info("initializing_claude_client")
        claude_client = ClaudeClient(
            api_key=config.anthropic_api_key,
            model=config.claude_model,
            default_max_tokens=config.claude_max_tokens,
        )

        # Create agent processing function
        def process_event_with_agent(event):
            """Process event with agent (for worker pool)."""
            with db_connection.session() as session:
                agent = AthenaeumAgent(
                    claude_client=claude_client,
                    slack_client=slack_client,
                    db_session=session,
                    prompt_dir="prompts",
                    bot_user_id=bot_user_id,
                )
                return agent.process_event(event)

        # Initialize worker pool
        logger.info("initializing_worker_pool", workers=config.worker_pool_size)
        _worker_pool = WorkerPool(
            size=config.worker_pool_size,
            db_connection=db_connection,
            process_func=process_event_with_agent,
            visibility_timeout=config.event_visibility_timeout,
            max_retries=config.max_retry_count,
        )

        # Start worker pool
        logger.info("starting_worker_pool")
        _worker_pool.start()

        # Initialize Slack Socket Mode handler
        logger.info("initializing_slack_socket_handler")

        def handle_slack_event(event_data: dict):
            """Handle Slack events by queueing them."""
            with db_connection.session() as session:
                processor = EventProcessor(session, visibility_timeout=config.event_visibility_timeout)

                # Determine event type
                event_type = event_data.get("type", "unknown")
                if event_type == "app_mention":
                    event_type = "slack_app_mention"
                elif event_type == "message":
                    event_type = "slack_message"
                else:
                    event_type = f"slack_{event_type}"

                # Queue event for processing
                event = processor.create_event(
                    event_type=event_type,
                    payload=event_data,
                )

                logger.info(
                    "event_queued",
                    event_id=event.id,
                    event_type=event_type,
                )

        _socket_handler = SocketModeHandler(
            app_token=config.slack_app_token,
            bot_token=config.slack_bot_token,
            event_callback=handle_slack_event,
        )

        # Start Socket Mode handler
        logger.info("starting_slack_socket_handler")
        _socket_handler.start()

        logger.info(
            "athenaeum_ready",
            message="🏛️ Athenaeum is ready! Listening for Slack messages...",
        )

        # Keep main thread alive
        while not _shutdown_requested:
            signal.pause()

    except KeyboardInterrupt:
        logger.info("keyboard_interrupt_received")
    except Exception as e:
        logger.error("athenaeum_error", error=str(e), exc_info=True)
        sys.exit(1)
    finally:
        logger.info("athenaeum_shutdown_complete")


if __name__ == "__main__":
    main()
