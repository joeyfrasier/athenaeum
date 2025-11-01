"""Agent core logic for processing events and generating responses."""

import os
from datetime import datetime
from typing import Dict, Optional
from jinja2 import Environment, FileSystemLoader
import structlog

from agent.llm_client import ClaudeClient
from agent.context import ConversationContext
from slack.client import SlackClient
from database.models import Event

logger = structlog.get_logger(__name__)


class AthenaeumAgent:
    """Core agent that processes events and generates intelligent responses."""

    def __init__(
        self,
        claude_client: ClaudeClient,
        slack_client: SlackClient,
        db_session,
        prompt_dir: str = "prompts",
        bot_user_id: Optional[str] = None,
    ):
        """Initialize Athenaeum agent.

        Args:
            claude_client: Claude API client
            slack_client: Slack API client
            db_session: Database session
            prompt_dir: Directory containing Jinja2 prompt templates
            bot_user_id: Bot's Slack user ID for context
        """
        self.claude = claude_client
        self.slack = slack_client
        self.session = db_session
        self.bot_user_id = bot_user_id

        # Initialize conversation context manager
        self.context_manager = ConversationContext(db_session)

        # Set up Jinja2 environment for prompt templates
        self.jinja_env = Environment(
            loader=FileSystemLoader(prompt_dir), trim_blocks=True, lstrip_blocks=True
        )

        logger.info("athenaeum_agent_initialized", prompt_dir=prompt_dir)

    def process_event(self, event: Event) -> Dict:
        """Process an event and generate appropriate response.

        Args:
            event: Event to process

        Returns:
            Processing result with status and metadata
        """
        logger.info(
            "processing_event",
            event_id=event.id,
            event_type=event.event_type,
        )

        try:
            # Route to appropriate handler based on event type
            if event.event_type == "slack_message":
                return self._handle_slack_message(event)
            elif event.event_type == "slack_app_mention":
                return self._handle_app_mention(event)
            else:
                logger.warning("unknown_event_type", event_type=event.event_type)
                return {"status": "skipped", "reason": "unknown_event_type"}

        except Exception as e:
            logger.error(
                "event_processing_error",
                event_id=event.id,
                error=str(e),
                exc_info=True,
            )
            return {"status": "failed", "error": str(e)}

    def _handle_slack_message(self, event: Event) -> Dict:
        """Handle a Slack message event.

        Args:
            event: Slack message event

        Returns:
            Processing result
        """
        payload = event.payload
        channel_id = payload.get("channel")
        user_id = payload.get("user")
        text = payload.get("text", "")
        thread_ts = payload.get("thread_ts")
        message_ts = payload.get("ts")

        # Skip bot's own messages
        if user_id == self.bot_user_id:
            logger.debug("skipping_bot_message", event_id=event.id)
            return {"status": "skipped", "reason": "bot_message"}

        logger.info(
            "handling_slack_message",
            event_id=event.id,
            channel_id=channel_id,
            user_id=user_id,
            is_thread=bool(thread_ts),
        )

        # Get conversation context
        context = self.context_manager.get_thread_context(
            channel_id=channel_id,
            thread_ts=thread_ts,
            include_channel_context=not bool(thread_ts),
        )

        # Generate response
        response = self._generate_response(
            user_message=text,
            context=context,
            user_id=user_id,
        )

        # Post response to Slack
        slack_response = self.slack.post_message(
            channel=channel_id,
            text=response["content"],
            thread_ts=thread_ts or message_ts,  # Reply in thread
        )

        logger.info(
            "slack_response_posted",
            event_id=event.id,
            response_ts=slack_response.get("ts"),
            tokens_used=response.get("usage", {}).get("output_tokens", 0),
        )

        return {
            "status": "completed",
            "response_ts": slack_response.get("ts"),
            "tokens_used": response.get("usage"),
        }

    def _handle_app_mention(self, event: Event) -> Dict:
        """Handle an app mention event.

        Args:
            event: App mention event

        Returns:
            Processing result
        """
        # App mentions are similar to regular messages
        # Just route to the message handler
        return self._handle_slack_message(event)

    def _generate_response(
        self, user_message: str, context: Dict, user_id: str
    ) -> Dict:
        """Generate an intelligent response using Claude.

        Args:
            user_message: The user's message
            context: Conversation context
            user_id: Slack user ID of the requester

        Returns:
            Response dictionary with content and metadata
        """
        logger.info(
            "generating_response",
            user_id=user_id,
            channel=context.get("channel_name"),
            is_thread=context.get("is_thread"),
        )

        # Get user information
        user_context = self.context_manager.get_user_context(user_id)

        # Render system prompt
        system_prompt = self._render_system_prompt(context, user_context)

        # Format conversation history for Claude
        claude_messages = []

        if context.get("conversation_history"):
            # Convert conversation history to Claude format
            claude_messages = self.context_manager.format_for_claude(
                context["conversation_history"], bot_user_id=self.bot_user_id
            )

        # Add current user message
        claude_messages.append({"role": "user", "content": user_message})

        # Generate response from Claude
        response = self.claude.generate(
            system_prompt=system_prompt,
            messages=claude_messages,
            temperature=0.7,
        )

        logger.info(
            "response_generated",
            user_id=user_id,
            input_tokens=response.get("usage", {}).get("input_tokens", 0),
            output_tokens=response.get("usage", {}).get("output_tokens", 0),
        )

        return response

    def _render_system_prompt(self, context: Dict, user_context: Dict) -> str:
        """Render the system prompt template.

        Args:
            context: Conversation context
            user_context: User information

        Returns:
            Rendered system prompt
        """
        template = self.jinja_env.get_template("system.jinja2")

        template_vars = {
            "user_name": user_context.get("real_name", "Unknown User"),
            "user_email": user_context.get("email", ""),
            "channel_name": context.get("channel_name", "unknown"),
            "current_date": datetime.now().strftime("%Y-%m-%d"),
            "is_thread": context.get("is_thread", False),
            "thread_context": self._summarize_thread(context.get("conversation_history", [])),
            "is_dm": context.get("channel_name", "").startswith("D"),
        }

        return template.render(**template_vars)

    def _summarize_thread(self, conversation_history: list) -> str:
        """Create a brief summary of the thread context.

        Args:
            conversation_history: List of previous messages

        Returns:
            Thread context summary
        """
        if not conversation_history:
            return "This is a new conversation."

        message_count = len(conversation_history)
        participants = set()

        for msg in conversation_history:
            if not msg.get("is_bot"):
                participants.add(msg.get("user_name", "Unknown"))

        participant_list = ", ".join(sorted(participants))

        return f"Thread with {message_count} messages. Participants: {participant_list}"

    def process_with_streaming(self, event: Event, callback=None) -> Dict:
        """Process event with streaming response.

        Args:
            event: Event to process
            callback: Optional callback for each streamed chunk

        Returns:
            Processing result
        """
        payload = event.payload
        channel_id = payload.get("channel")
        user_id = payload.get("user")
        text = payload.get("text", "")
        thread_ts = payload.get("thread_ts")
        message_ts = payload.get("ts")

        # Skip bot's own messages
        if user_id == self.bot_user_id:
            return {"status": "skipped", "reason": "bot_message"}

        logger.info(
            "handling_slack_message_streaming",
            event_id=event.id,
            channel_id=channel_id,
        )

        # Get conversation context
        context = self.context_manager.get_thread_context(
            channel_id=channel_id,
            thread_ts=thread_ts,
            include_channel_context=not bool(thread_ts),
        )

        # Get user information
        user_context = self.context_manager.get_user_context(user_id)

        # Render system prompt
        system_prompt = self._render_system_prompt(context, user_context)

        # Format messages
        claude_messages = []
        if context.get("conversation_history"):
            claude_messages = self.context_manager.format_for_claude(
                context["conversation_history"], bot_user_id=self.bot_user_id
            )
        claude_messages.append({"role": "user", "content": text})

        # Stream response
        full_response = []
        for chunk in self.claude.generate_streaming(
            system_prompt=system_prompt, messages=claude_messages, temperature=0.7
        ):
            full_response.append(chunk)
            if callback:
                callback(chunk)

        # Post complete response to Slack
        complete_text = "".join(full_response)
        slack_response = self.slack.post_message(
            channel=channel_id, text=complete_text, thread_ts=thread_ts or message_ts
        )

        logger.info(
            "streaming_response_complete",
            event_id=event.id,
            response_ts=slack_response.get("ts"),
        )

        return {
            "status": "completed",
            "response_ts": slack_response.get("ts"),
            "streaming": True,
        }
