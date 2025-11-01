#!/usr/bin/env python3
"""Sync Slack users and channels to database."""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
import structlog

from database import init_db
from slack.client import SlackClient
from slack.ingest import SlackIngestor

# Configure logging
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ]
)

logger = structlog.get_logger(__name__)

# Load environment
load_dotenv()


def sync_users(slack_client: SlackClient, ingestor: SlackIngestor):
    """Sync all users from Slack to database.

    Args:
        slack_client: Slack API client
        ingestor: Slack ingestor
    """
    logger.info("syncing_users_started")

    try:
        # Fetch all users from Slack
        users = slack_client.list_users()

        logger.info("users_fetched_from_slack", count=len(users))

        # Ingest users into database
        count = ingestor.bulk_ingest_users(users)

        logger.info("users_sync_completed", total=len(users), ingested=count)

        return count

    except Exception as e:
        logger.error("users_sync_failed", error=str(e))
        raise


def sync_channels(slack_client: SlackClient, ingestor: SlackIngestor):
    """Sync all channels from Slack to database.

    Args:
        slack_client: Slack API client
        ingestor: Slack ingestor
    """
    logger.info("syncing_channels_started")

    try:
        # Fetch all channels from Slack
        channels = slack_client.list_channels(exclude_archived=False)

        logger.info("channels_fetched_from_slack", count=len(channels))

        # Ingest channels into database
        count = ingestor.bulk_ingest_channels(channels)

        logger.info("channels_sync_completed", total=len(channels), ingested=count)

        return count

    except Exception as e:
        logger.error("channels_sync_failed", error=str(e))
        raise


def main():
    """Main entry point."""
    logger.info("slack_metadata_sync_started")

    # Get configuration from environment
    bot_token = os.getenv("SLACK_BOT_TOKEN")
    if not bot_token:
        logger.error("SLACK_BOT_TOKEN not found in environment")
        sys.exit(1)

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL not found in environment")
        sys.exit(1)

    # Initialize database
    db = init_db(database_url=database_url)
    logger.info("database_connected")

    # Initialize Slack client
    slack_client = SlackClient(bot_token=bot_token)

    # Create ingestor
    with db.session() as session:
        ingestor = SlackIngestor(session)

        # Sync users
        users_count = sync_users(slack_client, ingestor)

        # Sync channels
        channels_count = sync_channels(slack_client, ingestor)

    logger.info(
        "slack_metadata_sync_completed",
        users=users_count,
        channels=channels_count,
    )


if __name__ == "__main__":
    main()
