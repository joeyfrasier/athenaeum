"""Slack message ingestion pipeline."""

from datetime import datetime
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import structlog

from database.models import SlackMessage, SlackUser, SlackChannel, SlackReaction
from agent.event_processor import EventProcessor

logger = structlog.get_logger(__name__)


class SlackIngestor:
    """Ingests Slack messages and metadata into TimescaleDB."""

    def __init__(self, session: Session, event_processor: Optional[EventProcessor] = None):
        """Initialize Slack ingestor.

        Args:
            session: Database session
            event_processor: Optional event processor to queue events
        """
        self.session = session
        self.event_processor = event_processor

        logger.info("slack_ingestor_initialized")

    def ingest_user(self, user_data: dict) -> SlackUser:
        """Ingest or update a Slack user.

        Args:
            user_data: User data from Slack API

        Returns:
            SlackUser object
        """
        user_id = user_data["id"]

        # Check if user exists
        user = self.session.query(SlackUser).filter(SlackUser.user_id == user_id).first()

        if user:
            # Update existing user
            user.name = user_data.get("name", user.name)
            user.real_name = user_data.get("real_name")
            user.email = user_data.get("profile", {}).get("email")
            user.is_bot = user_data.get("is_bot", False)
            user.is_deleted = user_data.get("deleted", False)
            user.timezone = user_data.get("tz")
            user.avatar_url = user_data.get("profile", {}).get("image_72")
            user.metadata = user_data
            user.updated_at = datetime.utcnow()

            logger.info("slack_user_updated", user_id=user_id, name=user.name)
        else:
            # Create new user
            user = SlackUser(
                user_id=user_id,
                name=user_data.get("name", "Unknown"),
                real_name=user_data.get("real_name"),
                email=user_data.get("profile", {}).get("email"),
                is_bot=user_data.get("is_bot", False),
                is_deleted=user_data.get("deleted", False),
                timezone=user_data.get("tz"),
                avatar_url=user_data.get("profile", {}).get("image_72"),
                metadata=user_data,
            )
            self.session.add(user)

            logger.info("slack_user_created", user_id=user_id, name=user.name)

        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            # Fetch existing user
            user = self.session.query(SlackUser).filter(SlackUser.user_id == user_id).first()

        return user

    def ingest_channel(self, channel_data: dict) -> SlackChannel:
        """Ingest or update a Slack channel.

        Args:
            channel_data: Channel data from Slack API

        Returns:
            SlackChannel object
        """
        channel_id = channel_data["id"]

        # Check if channel exists
        channel = self.session.query(SlackChannel).filter(SlackChannel.channel_id == channel_id).first()

        if channel:
            # Update existing channel
            channel.name = channel_data.get("name", channel.name)
            channel.is_private = channel_data.get("is_private", channel.is_private)
            channel.is_archived = channel_data.get("is_archived", False)
            channel.topic = channel_data.get("topic", {}).get("value")
            channel.purpose = channel_data.get("purpose", {}).get("value")
            channel.member_count = channel_data.get("num_members", 0)
            channel.metadata = channel_data
            channel.updated_at = datetime.utcnow()

            logger.info("slack_channel_updated", channel_id=channel_id, name=channel.name)
        else:
            # Create new channel
            channel = SlackChannel(
                channel_id=channel_id,
                name=channel_data.get("name", "Unknown"),
                is_private=channel_data.get("is_private", False),
                is_archived=channel_data.get("is_archived", False),
                topic=channel_data.get("topic", {}).get("value"),
                purpose=channel_data.get("purpose", {}).get("value"),
                member_count=channel_data.get("num_members", 0),
                metadata=channel_data,
            )
            self.session.add(channel)

            logger.info("slack_channel_created", channel_id=channel_id, name=channel.name)

        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            # Fetch existing channel
            channel = self.session.query(SlackChannel).filter(SlackChannel.channel_id == channel_id).first()

        return channel

    def ingest_message(self, message_data: dict, channel_id: str) -> Optional[SlackMessage]:
        """Ingest a Slack message.

        Args:
            message_data: Message data from Slack API
            channel_id: Channel ID where message was posted

        Returns:
            SlackMessage object or None if message should be skipped
        """
        ts = message_data.get("ts")
        if not ts:
            logger.warning("message_missing_timestamp", channel=channel_id)
            return None

        # Skip bot messages from other bots (optional, based on your needs)
        # if message_data.get("bot_id") and not message_data.get("user"):
        #     logger.debug("skipping_bot_message", ts=ts, channel=channel_id)
        #     return None

        # Check if message already exists
        existing = (
            self.session.query(SlackMessage)
            .filter(SlackMessage.channel_id == channel_id, SlackMessage.ts == ts)
            .first()
        )

        if existing:
            # Update if edited
            if message_data.get("edited"):
                existing.text = message_data.get("text")
                existing.edited_ts = message_data.get("edited", {}).get("ts")
                existing.metadata = message_data
                existing.updated_at = datetime.utcnow()

                logger.info("slack_message_updated", channel=channel_id, ts=ts)
                self.session.commit()

            return existing

        # Create new message
        message = SlackMessage(
            channel_id=channel_id,
            ts=ts,
            user_id=message_data.get("user"),
            text=message_data.get("text"),
            thread_ts=message_data.get("thread_ts"),
            subtype=message_data.get("subtype"),
            is_bot_message=bool(message_data.get("bot_id")),
            attachments=message_data.get("attachments"),
            files=message_data.get("files"),
            metadata=message_data,
            created_at=datetime.fromtimestamp(float(ts)),
        )

        self.session.add(message)

        try:
            self.session.commit()
            logger.info(
                "slack_message_ingested",
                channel=channel_id,
                ts=ts,
                user=message.user_id,
                is_thread=bool(message.thread_ts),
            )

            # Queue event for agent processing if it's an app_mention
            if self.event_processor and message_data.get("type") == "app_mention":
                self.event_processor.insert_event(
                    event_type="app_mention",
                    payload={
                        "channel": channel_id,
                        "ts": ts,
                        "user": message.user_id,
                        "text": message.text,
                        "thread_ts": message.thread_ts,
                    },
                )

        except IntegrityError as e:
            self.session.rollback()
            logger.warning(
                "slack_message_already_exists",
                channel=channel_id,
                ts=ts,
                error=str(e),
            )
            # Fetch existing message
            message = (
                self.session.query(SlackMessage)
                .filter(SlackMessage.channel_id == channel_id, SlackMessage.ts == ts)
                .first()
            )

        return message

    def ingest_reaction(self, reaction_data: dict) -> Optional[SlackReaction]:
        """Ingest a Slack reaction.

        Args:
            reaction_data: Reaction data from Slack API

        Returns:
            SlackReaction object or None if failed
        """
        channel_id = reaction_data.get("item", {}).get("channel")
        message_ts = reaction_data.get("item", {}).get("ts")
        user_id = reaction_data.get("user")
        reaction = reaction_data.get("reaction")

        if not all([channel_id, message_ts, user_id, reaction]):
            logger.warning("reaction_missing_fields", data=reaction_data)
            return None

        # Check if reaction already exists
        existing = (
            self.session.query(SlackReaction)
            .filter(
                SlackReaction.channel_id == channel_id,
                SlackReaction.message_ts == message_ts,
                SlackReaction.user_id == user_id,
                SlackReaction.reaction == reaction,
            )
            .first()
        )

        if existing:
            logger.debug("reaction_already_exists", channel=channel_id, ts=message_ts, reaction=reaction)
            return existing

        # Create new reaction
        reaction_obj = SlackReaction(
            channel_id=channel_id,
            message_ts=message_ts,
            user_id=user_id,
            reaction=reaction,
        )

        self.session.add(reaction_obj)

        try:
            self.session.commit()
            logger.info(
                "slack_reaction_ingested",
                channel=channel_id,
                ts=message_ts,
                user=user_id,
                reaction=reaction,
            )
        except IntegrityError:
            self.session.rollback()
            logger.warning(
                "slack_reaction_already_exists",
                channel=channel_id,
                ts=message_ts,
                reaction=reaction,
            )
            # Fetch existing reaction
            reaction_obj = (
                self.session.query(SlackReaction)
                .filter(
                    SlackReaction.channel_id == channel_id,
                    SlackReaction.message_ts == message_ts,
                    SlackReaction.user_id == user_id,
                    SlackReaction.reaction == reaction,
                )
                .first()
            )

        return reaction_obj

    def remove_reaction(self, reaction_data: dict) -> bool:
        """Remove a Slack reaction.

        Args:
            reaction_data: Reaction removal data from Slack API

        Returns:
            True if removed, False otherwise
        """
        channel_id = reaction_data.get("item", {}).get("channel")
        message_ts = reaction_data.get("item", {}).get("ts")
        user_id = reaction_data.get("user")
        reaction = reaction_data.get("reaction")

        if not all([channel_id, message_ts, user_id, reaction]):
            logger.warning("reaction_removal_missing_fields", data=reaction_data)
            return False

        # Find and delete reaction
        reaction_obj = (
            self.session.query(SlackReaction)
            .filter(
                SlackReaction.channel_id == channel_id,
                SlackReaction.message_ts == message_ts,
                SlackReaction.user_id == user_id,
                SlackReaction.reaction == reaction,
            )
            .first()
        )

        if reaction_obj:
            self.session.delete(reaction_obj)
            self.session.commit()

            logger.info(
                "slack_reaction_removed",
                channel=channel_id,
                ts=message_ts,
                user=user_id,
                reaction=reaction,
            )
            return True

        logger.debug("reaction_not_found_for_removal", channel=channel_id, ts=message_ts, reaction=reaction)
        return False

    def bulk_ingest_users(self, users_data: List[dict]) -> int:
        """Bulk ingest multiple users.

        Args:
            users_data: List of user data dictionaries

        Returns:
            Number of users ingested
        """
        count = 0
        for user_data in users_data:
            try:
                self.ingest_user(user_data)
                count += 1
            except Exception as e:
                logger.error("user_ingest_error", user_id=user_data.get("id"), error=str(e))

        logger.info("bulk_user_ingest_complete", count=count, total=len(users_data))
        return count

    def bulk_ingest_channels(self, channels_data: List[dict]) -> int:
        """Bulk ingest multiple channels.

        Args:
            channels_data: List of channel data dictionaries

        Returns:
            Number of channels ingested
        """
        count = 0
        for channel_data in channels_data:
            try:
                self.ingest_channel(channel_data)
                count += 1
            except Exception as e:
                logger.error("channel_ingest_error", channel_id=channel_data.get("id"), error=str(e))

        logger.info("bulk_channel_ingest_complete", count=count, total=len(channels_data))
        return count

    def bulk_ingest_messages(self, messages_data: List[dict], channel_id: str) -> int:
        """Bulk ingest multiple messages.

        Args:
            messages_data: List of message data dictionaries
            channel_id: Channel ID for all messages

        Returns:
            Number of messages ingested
        """
        count = 0
        for message_data in messages_data:
            try:
                if self.ingest_message(message_data, channel_id):
                    count += 1
            except Exception as e:
                logger.error(
                    "message_ingest_error",
                    channel=channel_id,
                    ts=message_data.get("ts"),
                    error=str(e),
                )

        logger.info("bulk_message_ingest_complete", channel=channel_id, count=count, total=len(messages_data))
        return count
