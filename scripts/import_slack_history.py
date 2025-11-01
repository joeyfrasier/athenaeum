#!/usr/bin/env python3
"""Import historical Slack messages to database."""

import os
import sys
import time
from pathlib import Path
from typing import Optional

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


def import_channel_history(
    channel_id: str,
    slack_client: SlackClient,
    ingestor: SlackIngestor,
    oldest: Optional[str] = None,
    latest: Optional[str] = None,
    batch_size: int = 100,
):
    """Import message history for a channel.

    Args:
        channel_id: Channel ID to import
        slack_client: Slack API client
        ingestor: Slack ingestor
        oldest: Oldest timestamp to fetch (optional)
        latest: Latest timestamp to fetch (optional)
        batch_size: Number of messages to fetch per batch

    Returns:
        Number of messages imported
    """
    logger.info(
        "importing_channel_history",
        channel=channel_id,
        oldest=oldest,
        latest=latest,
    )

    try:
        # Fetch conversation history
        messages = slack_client.get_conversation_history(
            channel_id=channel_id,
            limit=batch_size,
            oldest=oldest,
            latest=latest,
        )

        if not messages:
            logger.info("no_messages_found", channel=channel_id)
            return 0

        # Ingest messages
        count = ingestor.bulk_ingest_messages(messages, channel_id)

        logger.info(
            "channel_history_imported",
            channel=channel_id,
            messages=count,
        )

        return count

    except Exception as e:
        logger.error(
            "channel_history_import_failed",
            channel=channel_id,
            error=str(e),
        )
        raise


def import_all_channels_history(
    slack_client: SlackClient,
    ingestor: SlackIngestor,
    oldest: Optional[str] = None,
    latest: Optional[str] = None,
    include_archived: bool = False,
    rate_limit_delay: float = 1.0,
):
    """Import message history for all accessible channels.

    Args:
        slack_client: Slack API client
        ingestor: Slack ingestor
        oldest: Oldest timestamp to fetch (optional)
        latest: Latest timestamp to fetch (optional)
        include_archived: Include archived channels
        rate_limit_delay: Delay between channel imports (seconds)

    Returns:
        Dictionary with import statistics
    """
    logger.info("importing_all_channels_history_started")

    # Fetch all channels
    channels = slack_client.list_channels(exclude_archived=not include_archived)
    logger.info("channels_fetched", count=len(channels))

    stats = {
        "total_channels": len(channels),
        "processed_channels": 0,
        "total_messages": 0,
        "failed_channels": [],
    }

    for channel in channels:
        channel_id = channel["id"]
        channel_name = channel.get("name", "unknown")

        logger.info(
            "importing_channel",
            channel_id=channel_id,
            channel_name=channel_name,
            progress=f"{stats['processed_channels'] + 1}/{stats['total_channels']}",
        )

        try:
            # Import channel history
            count = import_channel_history(
                channel_id=channel_id,
                slack_client=slack_client,
                ingestor=ingestor,
                oldest=oldest,
                latest=latest,
            )

            stats["processed_channels"] += 1
            stats["total_messages"] += count

            # Rate limiting delay
            if stats["processed_channels"] < stats["total_channels"]:
                time.sleep(rate_limit_delay)

        except Exception as e:
            logger.error(
                "channel_import_failed",
                channel_id=channel_id,
                channel_name=channel_name,
                error=str(e),
            )
            stats["failed_channels"].append(
                {
                    "channel_id": channel_id,
                    "channel_name": channel_name,
                    "error": str(e),
                }
            )

    logger.info(
        "all_channels_history_import_completed",
        processed=stats["processed_channels"],
        total=stats["total_channels"],
        messages=stats["total_messages"],
        failed=len(stats["failed_channels"]),
    )

    return stats


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Import Slack message history")
    parser.add_argument(
        "--channel",
        help="Specific channel ID to import (imports all if not specified)",
    )
    parser.add_argument(
        "--oldest",
        help="Oldest timestamp to fetch (Unix timestamp)",
    )
    parser.add_argument(
        "--latest",
        help="Latest timestamp to fetch (Unix timestamp)",
    )
    parser.add_argument(
        "--include-archived",
        action="store_true",
        help="Include archived channels",
    )
    parser.add_argument(
        "--rate-limit-delay",
        type=float,
        default=1.0,
        help="Delay between channel imports (seconds, default: 1.0)",
    )

    args = parser.parse_args()

    logger.info("slack_history_import_started", args=vars(args))

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

        if args.channel:
            # Import specific channel
            count = import_channel_history(
                channel_id=args.channel,
                slack_client=slack_client,
                ingestor=ingestor,
                oldest=args.oldest,
                latest=args.latest,
            )

            logger.info("import_completed", channel=args.channel, messages=count)
        else:
            # Import all channels
            stats = import_all_channels_history(
                slack_client=slack_client,
                ingestor=ingestor,
                oldest=args.oldest,
                latest=args.latest,
                include_archived=args.include_archived,
                rate_limit_delay=args.rate_limit_delay,
            )

            logger.info("import_completed", **stats)

            if stats["failed_channels"]:
                logger.warning("failed_channels", channels=stats["failed_channels"])


if __name__ == "__main__":
    main()
