"""Slack API client with rate limiting and retry logic."""

import time
from typing import Optional, Dict, List, Any
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import structlog

logger = structlog.get_logger(__name__)


class SlackClient:
    """Wrapper around Slack WebClient with rate limiting and retries."""

    def __init__(self, bot_token: str, max_retries: int = 3, retry_delay: float = 1.0):
        """Initialize Slack client.

        Args:
            bot_token: Slack bot OAuth token (xoxb-...)
            max_retries: Maximum number of retry attempts
            retry_delay: Initial delay between retries (exponential backoff)
        """
        self.client = WebClient(token=bot_token)
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        logger.info("slack_client_initialized")

    def _retry_with_backoff(self, func, *args, **kwargs) -> Any:
        """Execute function with exponential backoff retry logic.

        Args:
            func: Function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Function result

        Raises:
            SlackApiError: If all retries fail
        """
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)

            except SlackApiError as e:
                last_exception = e

                # Don't retry on certain errors
                if e.response["error"] in ["invalid_auth", "account_inactive", "token_revoked"]:
                    logger.error(
                        "slack_api_error_no_retry",
                        error=e.response["error"],
                        attempt=attempt + 1,
                    )
                    raise

                # Handle rate limiting
                if e.response["error"] == "rate_limited":
                    retry_after = int(e.response.get("headers", {}).get("Retry-After", self.retry_delay))
                    logger.warning(
                        "slack_rate_limited",
                        retry_after=retry_after,
                        attempt=attempt + 1,
                    )
                    time.sleep(retry_after)
                    continue

                # Exponential backoff for other errors
                delay = self.retry_delay * (2**attempt)
                logger.warning(
                    "slack_api_error_retry",
                    error=e.response["error"],
                    attempt=attempt + 1,
                    max_retries=self.max_retries,
                    delay=delay,
                )
                time.sleep(delay)

        # All retries failed
        logger.error(
            "slack_api_error_max_retries",
            error=last_exception.response["error"] if last_exception else "unknown",
        )
        raise last_exception

    def post_message(
        self,
        channel: str,
        text: str,
        thread_ts: Optional[str] = None,
        blocks: Optional[List[Dict]] = None,
    ) -> Dict:
        """Post a message to a channel.

        Args:
            channel: Channel ID (e.g., "C123456")
            text: Message text
            thread_ts: Thread timestamp for replies
            blocks: Rich message blocks

        Returns:
            API response with message details
        """
        logger.info(
            "posting_slack_message",
            channel=channel,
            thread_ts=thread_ts,
            has_blocks=bool(blocks),
        )

        response = self._retry_with_backoff(
            self.client.chat_postMessage,
            channel=channel,
            text=text,
            thread_ts=thread_ts,
            blocks=blocks,
        )

        return response.data

    def get_user_info(self, user_id: str) -> Dict:
        """Get user information.

        Args:
            user_id: User ID (e.g., "U123456")

        Returns:
            User information dictionary
        """
        response = self._retry_with_backoff(
            self.client.users_info,
            user=user_id,
        )

        return response.data["user"]

    def get_channel_info(self, channel_id: str) -> Dict:
        """Get channel information.

        Args:
            channel_id: Channel ID (e.g., "C123456")

        Returns:
            Channel information dictionary
        """
        response = self._retry_with_backoff(
            self.client.conversations_info,
            channel=channel_id,
        )

        return response.data["channel"]

    def list_users(self, limit: int = 200) -> List[Dict]:
        """List all users in the workspace.

        Args:
            limit: Number of users to fetch per page

        Returns:
            List of user dictionaries
        """
        logger.info("listing_slack_users", limit=limit)

        users = []
        cursor = None

        while True:
            response = self._retry_with_backoff(
                self.client.users_list,
                limit=limit,
                cursor=cursor,
            )

            users.extend(response.data["members"])

            cursor = response.data.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

        logger.info("slack_users_listed", count=len(users))
        return users

    def list_channels(self, limit: int = 200, exclude_archived: bool = False) -> List[Dict]:
        """List all channels the bot can access.

        Args:
            limit: Number of channels to fetch per page
            exclude_archived: Exclude archived channels

        Returns:
            List of channel dictionaries
        """
        logger.info("listing_slack_channels", limit=limit, exclude_archived=exclude_archived)

        channels = []
        cursor = None

        while True:
            response = self._retry_with_backoff(
                self.client.conversations_list,
                limit=limit,
                exclude_archived=exclude_archived,
                types="public_channel,private_channel",
                cursor=cursor,
            )

            channels.extend(response.data["channels"])

            cursor = response.data.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

        logger.info("slack_channels_listed", count=len(channels))
        return channels

    def get_conversation_history(
        self,
        channel_id: str,
        limit: int = 100,
        oldest: Optional[str] = None,
        latest: Optional[str] = None,
    ) -> List[Dict]:
        """Get conversation history from a channel.

        Args:
            channel_id: Channel ID
            limit: Number of messages to fetch per page
            oldest: Oldest timestamp to fetch
            latest: Latest timestamp to fetch

        Returns:
            List of message dictionaries
        """
        logger.info(
            "fetching_conversation_history",
            channel=channel_id,
            limit=limit,
            oldest=oldest,
            latest=latest,
        )

        messages = []
        cursor = None

        while True:
            response = self._retry_with_backoff(
                self.client.conversations_history,
                channel=channel_id,
                limit=limit,
                oldest=oldest,
                latest=latest,
                cursor=cursor,
            )

            messages.extend(response.data["messages"])

            cursor = response.data.get("response_metadata", {}).get("next_cursor")
            if not cursor or not response.data.get("has_more"):
                break

        logger.info("conversation_history_fetched", channel=channel_id, count=len(messages))
        return messages

    def get_thread_replies(self, channel_id: str, thread_ts: str, limit: int = 100) -> List[Dict]:
        """Get all replies in a thread.

        Args:
            channel_id: Channel ID
            thread_ts: Thread parent timestamp
            limit: Number of messages to fetch per page

        Returns:
            List of message dictionaries (including parent)
        """
        logger.info(
            "fetching_thread_replies",
            channel=channel_id,
            thread_ts=thread_ts,
            limit=limit,
        )

        messages = []
        cursor = None

        while True:
            response = self._retry_with_backoff(
                self.client.conversations_replies,
                channel=channel_id,
                ts=thread_ts,
                limit=limit,
                cursor=cursor,
            )

            messages.extend(response.data["messages"])

            cursor = response.data.get("response_metadata", {}).get("next_cursor")
            if not cursor or not response.data.get("has_more"):
                break

        logger.info("thread_replies_fetched", channel=channel_id, count=len(messages))
        return messages

    def add_reaction(self, channel_id: str, timestamp: str, reaction: str) -> Dict:
        """Add a reaction to a message.

        Args:
            channel_id: Channel ID
            timestamp: Message timestamp
            reaction: Reaction emoji name (e.g., "thumbsup")

        Returns:
            API response
        """
        response = self._retry_with_backoff(
            self.client.reactions_add,
            channel=channel_id,
            timestamp=timestamp,
            name=reaction,
        )

        return response.data

    def get_permalink(self, channel_id: str, message_ts: str) -> str:
        """Get permanent link to a message.

        Args:
            channel_id: Channel ID
            message_ts: Message timestamp

        Returns:
            Permalink URL
        """
        response = self._retry_with_backoff(
            self.client.chat_getPermalink,
            channel=channel_id,
            message_ts=message_ts,
        )

        return response.data["permalink"]
