"""Conversation context retrieval and formatting."""

from datetime import datetime, timedelta
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_
import structlog

from database.models import SlackMessage, SlackUser, SlackChannel

logger = structlog.get_logger(__name__)


class ConversationContext:
    """Manages conversation context retrieval and formatting."""

    def __init__(self, session: Session, max_history_messages: int = 50):
        """Initialize conversation context manager.

        Args:
            session: Database session
            max_history_messages: Maximum number of historical messages to retrieve
        """
        self.session = session
        self.max_history_messages = max_history_messages

    def get_thread_context(
        self,
        channel_id: str,
        thread_ts: Optional[str] = None,
        include_channel_context: bool = True,
    ) -> Dict:
        """Get full context for a conversation thread.

        Args:
            channel_id: Slack channel ID
            thread_ts: Thread timestamp (None for channel messages)
            include_channel_context: Include recent channel messages for context

        Returns:
            Dictionary with conversation history, users, and metadata
        """
        logger.info(
            "retrieving_thread_context",
            channel_id=channel_id,
            thread_ts=thread_ts,
            include_channel_context=include_channel_context,
        )

        # Get thread messages
        thread_messages = self._get_thread_messages(channel_id, thread_ts)

        # Get channel information
        channel = self._get_channel_info(channel_id)

        # Optionally get recent channel messages for broader context
        channel_messages = []
        if include_channel_context and not thread_ts:
            channel_messages = self._get_recent_channel_messages(
                channel_id, limit=self.max_history_messages
            )

        # Get all unique user IDs
        user_ids = set()
        for msg in thread_messages + channel_messages:
            if msg.user_id:
                user_ids.add(msg.user_id)

        # Fetch user information
        users = self._get_users_info(list(user_ids))
        user_map = {user.user_id: user for user in users}

        # Format conversation history
        conversation_history = self._format_conversation_history(
            thread_messages if thread_ts else channel_messages, user_map
        )

        context = {
            "channel_id": channel_id,
            "channel_name": channel.name if channel else "unknown",
            "thread_ts": thread_ts,
            "is_thread": bool(thread_ts),
            "conversation_history": conversation_history,
            "message_count": len(thread_messages) if thread_ts else len(channel_messages),
            "users": {uid: self._user_to_dict(user_map[uid]) for uid in user_ids if uid in user_map},
        }

        logger.info(
            "thread_context_retrieved",
            channel_id=channel_id,
            message_count=context["message_count"],
            user_count=len(context["users"]),
        )

        return context

    def _get_thread_messages(self, channel_id: str, thread_ts: Optional[str]) -> List[SlackMessage]:
        """Get all messages in a thread.

        Args:
            channel_id: Channel ID
            thread_ts: Thread timestamp

        Returns:
            List of messages ordered by timestamp
        """
        if not thread_ts:
            return []

        query = (
            select(SlackMessage)
            .where(
                and_(
                    SlackMessage.channel_id == channel_id,
                    or_(
                        SlackMessage.ts == thread_ts,
                        SlackMessage.thread_ts == thread_ts,
                    ),
                )
            )
            .order_by(SlackMessage.created_at.asc())
            .limit(self.max_history_messages)
        )

        result = self.session.execute(query)
        messages = result.scalars().all()

        logger.debug(
            "thread_messages_fetched",
            channel_id=channel_id,
            thread_ts=thread_ts,
            count=len(messages),
        )

        return messages

    def _get_recent_channel_messages(
        self, channel_id: str, limit: int = 50, max_age_hours: int = 24
    ) -> List[SlackMessage]:
        """Get recent messages from a channel.

        Args:
            channel_id: Channel ID
            limit: Maximum number of messages
            max_age_hours: Maximum age in hours

        Returns:
            List of recent messages
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)

        query = (
            select(SlackMessage)
            .where(
                and_(
                    SlackMessage.channel_id == channel_id,
                    SlackMessage.created_at >= cutoff_time,
                    SlackMessage.thread_ts.is_(None),  # Only top-level messages
                )
            )
            .order_by(SlackMessage.created_at.desc())
            .limit(limit)
        )

        result = self.session.execute(query)
        messages = result.scalars().all()

        # Return in chronological order
        messages = list(reversed(messages))

        logger.debug(
            "recent_channel_messages_fetched",
            channel_id=channel_id,
            count=len(messages),
        )

        return messages

    def _get_channel_info(self, channel_id: str) -> Optional[SlackChannel]:
        """Get channel information.

        Args:
            channel_id: Channel ID

        Returns:
            Channel object or None
        """
        query = select(SlackChannel).where(SlackChannel.channel_id == channel_id)
        result = self.session.execute(query)
        return result.scalar_one_or_none()

    def _get_users_info(self, user_ids: List[str]) -> List[SlackUser]:
        """Get information for multiple users.

        Args:
            user_ids: List of user IDs

        Returns:
            List of user objects
        """
        if not user_ids:
            return []

        query = select(SlackUser).where(SlackUser.user_id.in_(user_ids))
        result = self.session.execute(query)
        return result.scalars().all()

    def _format_conversation_history(
        self, messages: List[SlackMessage], user_map: Dict[str, SlackUser]
    ) -> List[Dict]:
        """Format messages for LLM consumption.

        Args:
            messages: List of Slack messages
            user_map: Map of user_id to SlackUser

        Returns:
            List of formatted message dictionaries
        """
        formatted = []

        for msg in messages:
            user = user_map.get(msg.user_id)
            formatted.append(
                {
                    "user_id": msg.user_id,
                    "user_name": user.real_name if user else "Unknown User",
                    "user_display_name": user.display_name if user else "Unknown",
                    "text": msg.text or "",
                    "timestamp": msg.created_at.isoformat(),
                    "ts": msg.ts,
                    "is_bot": user.is_bot if user else False,
                }
            )

        return formatted

    def _user_to_dict(self, user: SlackUser) -> Dict:
        """Convert SlackUser to dictionary.

        Args:
            user: SlackUser object

        Returns:
            User information dictionary
        """
        return {
            "user_id": user.user_id,
            "real_name": user.real_name,
            "display_name": user.display_name,
            "email": user.email,
            "is_bot": user.is_bot,
            "is_admin": user.is_admin,
        }

    def format_for_claude(
        self, conversation_history: List[Dict], bot_user_id: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """Format conversation history for Claude API.

        Args:
            conversation_history: List of formatted messages
            bot_user_id: Bot's user ID to identify bot messages

        Returns:
            List of messages in Claude API format
        """
        claude_messages = []

        for msg in conversation_history:
            # Determine role based on whether this is a bot message
            role = "assistant" if msg.get("user_id") == bot_user_id else "user"

            # Format content with user name for clarity
            content = msg["text"]
            if role == "user" and not msg.get("is_bot"):
                # Prefix user messages with their name for context
                content = f"{msg['user_name']}: {content}"

            claude_messages.append({"role": role, "content": content})

        return claude_messages

    def get_user_context(self, user_id: str) -> Dict:
        """Get detailed context about a specific user.

        Args:
            user_id: Slack user ID

        Returns:
            User context dictionary
        """
        query = select(SlackUser).where(SlackUser.user_id == user_id)
        result = self.session.execute(query)
        user = result.scalar_one_or_none()

        if not user:
            logger.warning("user_not_found", user_id=user_id)
            return {"user_id": user_id, "found": False}

        return {
            "user_id": user.user_id,
            "real_name": user.real_name,
            "display_name": user.display_name,
            "email": user.email,
            "is_bot": user.is_bot,
            "is_admin": user.is_admin,
            "found": True,
        }
