"""Claude API client with retry logic and streaming support."""

import time
from typing import Optional, Dict, List, Any, Iterator
from anthropic import Anthropic, APIError, RateLimitError, APIConnectionError
import structlog

logger = structlog.get_logger(__name__)


class ClaudeClient:
    """Wrapper around Anthropic Claude API with rate limiting and retries."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-5-sonnet-20241022",
        max_retries: int = 3,
        retry_delay: float = 1.0,
        default_max_tokens: int = 4096,
    ):
        """Initialize Claude client.

        Args:
            api_key: Anthropic API key
            model: Claude model to use
            max_retries: Maximum number of retry attempts
            retry_delay: Initial delay between retries (exponential backoff)
            default_max_tokens: Default max tokens for responses
        """
        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.default_max_tokens = default_max_tokens

        logger.info(
            "claude_client_initialized",
            model=model,
            max_retries=max_retries,
        )

    def _retry_with_backoff(self, func, *args, **kwargs) -> Any:
        """Execute function with exponential backoff retry logic.

        Args:
            func: Function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Function result

        Raises:
            APIError: If all retries fail
        """
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)

            except RateLimitError as e:
                last_exception = e

                # Handle rate limiting with retry-after header
                retry_after = getattr(e, "retry_after", None) or self.retry_delay * (2**attempt)
                logger.warning(
                    "claude_rate_limited",
                    retry_after=retry_after,
                    attempt=attempt + 1,
                    max_retries=self.max_retries,
                )
                time.sleep(retry_after)
                continue

            except APIConnectionError as e:
                last_exception = e

                # Retry on connection errors
                delay = self.retry_delay * (2**attempt)
                logger.warning(
                    "claude_connection_error",
                    error=str(e),
                    attempt=attempt + 1,
                    max_retries=self.max_retries,
                    delay=delay,
                )
                time.sleep(delay)
                continue

            except APIError as e:
                last_exception = e

                # Don't retry on authentication errors
                if e.status_code in [401, 403]:
                    logger.error(
                        "claude_auth_error",
                        status_code=e.status_code,
                        error=str(e),
                    )
                    raise

                # Exponential backoff for other errors
                delay = self.retry_delay * (2**attempt)
                logger.warning(
                    "claude_api_error_retry",
                    status_code=e.status_code,
                    error=str(e),
                    attempt=attempt + 1,
                    max_retries=self.max_retries,
                    delay=delay,
                )
                time.sleep(delay)

        # All retries failed
        logger.error(
            "claude_api_error_max_retries",
            error=str(last_exception) if last_exception else "unknown",
        )
        raise last_exception

    def generate(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: float = 1.0,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """Generate a completion from Claude.

        Args:
            system_prompt: System prompt for context
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            stream: Whether to stream the response

        Returns:
            Response dict with content, usage, and metadata
        """
        max_tokens = max_tokens or self.default_max_tokens

        logger.info(
            "claude_generate_request",
            model=self.model,
            message_count=len(messages),
            max_tokens=max_tokens,
            temperature=temperature,
            stream=stream,
        )

        def _make_request():
            return self.client.messages.create(
                model=self.model,
                system=system_prompt,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=stream,
            )

        response = self._retry_with_backoff(_make_request)

        if stream:
            # For streaming, return the stream object directly
            return {"stream": response}

        # Extract response data
        content = response.content[0].text if response.content else ""
        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }

        logger.info(
            "claude_generate_success",
            model=self.model,
            input_tokens=usage["input_tokens"],
            output_tokens=usage["output_tokens"],
            stop_reason=response.stop_reason,
        )

        return {
            "content": content,
            "usage": usage,
            "stop_reason": response.stop_reason,
            "model": response.model,
        }

    def generate_streaming(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: float = 1.0,
    ) -> Iterator[str]:
        """Generate a streaming completion from Claude.

        Args:
            system_prompt: System prompt for context
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)

        Yields:
            Content chunks as they arrive
        """
        max_tokens = max_tokens or self.default_max_tokens

        logger.info(
            "claude_streaming_request",
            model=self.model,
            message_count=len(messages),
            max_tokens=max_tokens,
        )

        def _make_request():
            return self.client.messages.stream(
                model=self.model,
                system=system_prompt,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )

        stream = self._retry_with_backoff(_make_request)

        total_tokens = {"input": 0, "output": 0}

        with stream as message_stream:
            for text in message_stream.text_stream:
                yield text

            # Log final usage
            final_message = message_stream.get_final_message()
            total_tokens["input"] = final_message.usage.input_tokens
            total_tokens["output"] = final_message.usage.output_tokens

        logger.info(
            "claude_streaming_complete",
            model=self.model,
            input_tokens=total_tokens["input"],
            output_tokens=total_tokens["output"],
        )

    def count_tokens(self, text: str) -> int:
        """Estimate token count for text.

        Args:
            text: Text to count tokens for

        Returns:
            Estimated token count
        """
        # Anthropic's rough approximation: ~4 characters per token
        # For more accurate counting, use tiktoken or Anthropic's beta API
        return len(text) // 4

    def format_messages(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> List[Dict[str, str]]:
        """Format messages for Claude API.

        Args:
            user_message: Current user message
            conversation_history: Previous messages in conversation

        Returns:
            Formatted message list for Claude API
        """
        messages = []

        # Add conversation history if provided
        if conversation_history:
            messages.extend(conversation_history)

        # Add current user message
        messages.append({"role": "user", "content": user_message})

        return messages
