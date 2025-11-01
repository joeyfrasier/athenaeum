"""Slack Socket Mode handler for real-time event reception."""

import asyncio
from typing import Callable, Optional
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.socket_mode.request import SocketModeRequest
import structlog

logger = structlog.get_logger(__name__)


class SocketModeHandler:
    """Handles Slack Socket Mode connections for real-time events."""

    def __init__(
        self,
        app_token: str,
        event_handler: Callable[[dict], None],
        auto_reconnect: bool = True,
    ):
        """Initialize Socket Mode handler.

        Args:
            app_token: Slack app-level token (xapp-...)
            event_handler: Callback function to handle events
            auto_reconnect: Automatically reconnect on disconnect
        """
        self.app_token = app_token
        self.event_handler = event_handler
        self.auto_reconnect = auto_reconnect

        self.client: Optional[SocketModeClient] = None
        self._running = False

        logger.info("socket_mode_handler_initialized", auto_reconnect=auto_reconnect)

    def start(self):
        """Start Socket Mode connection."""
        if self._running:
            logger.warning("socket_mode_already_running")
            return

        logger.info("socket_mode_starting")

        # Create Socket Mode client
        self.client = SocketModeClient(
            app_token=self.app_token,
            auto_reconnect_enabled=self.auto_reconnect,
        )

        # Register event handlers
        self.client.socket_mode_request_listeners.append(self._handle_socket_mode_request)

        # Start connection
        self.client.connect()
        self._running = True

        logger.info("socket_mode_started")

    def stop(self):
        """Stop Socket Mode connection."""
        if not self._running:
            logger.warning("socket_mode_not_running")
            return

        logger.info("socket_mode_stopping")

        if self.client:
            self.client.close()
            self.client = None

        self._running = False

        logger.info("socket_mode_stopped")

    def is_connected(self) -> bool:
        """Check if Socket Mode is connected.

        Returns:
            True if connected, False otherwise
        """
        return self._running and self.client is not None and self.client.is_connected()

    def _handle_socket_mode_request(self, client: SocketModeClient, req: SocketModeRequest):
        """Handle incoming Socket Mode requests.

        Args:
            client: Socket Mode client
            req: Socket Mode request
        """
        try:
            # Acknowledge the request immediately
            response = SocketModeResponse(envelope_id=req.envelope_id)
            client.send_socket_mode_response(response)

            # Process based on request type
            if req.type == "events_api":
                self._handle_events_api(req.payload)
            elif req.type == "interactive":
                self._handle_interactive(req.payload)
            elif req.type == "slash_commands":
                self._handle_slash_command(req.payload)
            else:
                logger.debug("unknown_socket_mode_request_type", type=req.type)

        except Exception as e:
            logger.error(
                "socket_mode_request_handler_error",
                error=str(e),
                request_type=req.type,
            )

    def _handle_events_api(self, payload: dict):
        """Handle Events API payloads.

        Args:
            payload: Event payload
        """
        event = payload.get("event", {})
        event_type = event.get("type")

        logger.info(
            "slack_event_received",
            event_type=event_type,
            event_subtype=event.get("subtype"),
        )

        try:
            # Call the event handler
            self.event_handler(event)

        except Exception as e:
            logger.error(
                "event_handler_error",
                event_type=event_type,
                error=str(e),
            )

    def _handle_interactive(self, payload: dict):
        """Handle interactive payloads (buttons, menus, etc.).

        Args:
            payload: Interactive payload
        """
        logger.info("slack_interactive_received", type=payload.get("type"))
        # TODO: Implement interactive handling in Phase 3

    def _handle_slash_command(self, payload: dict):
        """Handle slash command payloads.

        Args:
            payload: Slash command payload
        """
        logger.info("slack_slash_command_received", command=payload.get("command"))
        # TODO: Implement slash command handling in Phase 3


class AsyncSocketModeHandler:
    """Async version of Socket Mode handler for use with asyncio."""

    def __init__(
        self,
        app_token: str,
        event_handler: Callable[[dict], asyncio.coroutine],
        auto_reconnect: bool = True,
    ):
        """Initialize async Socket Mode handler.

        Args:
            app_token: Slack app-level token (xapp-...)
            event_handler: Async callback function to handle events
            auto_reconnect: Automatically reconnect on disconnect
        """
        self.app_token = app_token
        self.event_handler = event_handler
        self.auto_reconnect = auto_reconnect

        self.client: Optional[SocketModeClient] = None
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        logger.info("async_socket_mode_handler_initialized", auto_reconnect=auto_reconnect)

    async def start(self):
        """Start Socket Mode connection asynchronously."""
        if self._running:
            logger.warning("async_socket_mode_already_running")
            return

        logger.info("async_socket_mode_starting")

        self._loop = asyncio.get_event_loop()

        # Create Socket Mode client
        self.client = SocketModeClient(
            app_token=self.app_token,
            auto_reconnect_enabled=self.auto_reconnect,
        )

        # Register event handlers
        self.client.socket_mode_request_listeners.append(self._handle_socket_mode_request)

        # Start connection in executor (blocking operation)
        await self._loop.run_in_executor(None, self.client.connect)
        self._running = True

        logger.info("async_socket_mode_started")

    async def stop(self):
        """Stop Socket Mode connection asynchronously."""
        if not self._running:
            logger.warning("async_socket_mode_not_running")
            return

        logger.info("async_socket_mode_stopping")

        if self.client and self._loop:
            await self._loop.run_in_executor(None, self.client.close)
            self.client = None

        self._running = False

        logger.info("async_socket_mode_stopped")

    def is_connected(self) -> bool:
        """Check if Socket Mode is connected.

        Returns:
            True if connected, False otherwise
        """
        return self._running and self.client is not None and self.client.is_connected()

    def _handle_socket_mode_request(self, client: SocketModeClient, req: SocketModeRequest):
        """Handle incoming Socket Mode requests.

        Args:
            client: Socket Mode client
            req: Socket Mode request
        """
        try:
            # Acknowledge the request immediately
            response = SocketModeResponse(envelope_id=req.envelope_id)
            client.send_socket_mode_response(response)

            # Process based on request type
            if req.type == "events_api":
                # Schedule async event handling
                if self._loop:
                    asyncio.run_coroutine_threadsafe(
                        self._handle_events_api(req.payload),
                        self._loop,
                    )
            else:
                logger.debug("unknown_async_socket_mode_request_type", type=req.type)

        except Exception as e:
            logger.error(
                "async_socket_mode_request_handler_error",
                error=str(e),
                request_type=req.type,
            )

    async def _handle_events_api(self, payload: dict):
        """Handle Events API payloads asynchronously.

        Args:
            payload: Event payload
        """
        event = payload.get("event", {})
        event_type = event.get("type")

        logger.info(
            "async_slack_event_received",
            event_type=event_type,
            event_subtype=event.get("subtype"),
        )

        try:
            # Call the async event handler
            await self.event_handler(event)

        except Exception as e:
            logger.error(
                "async_event_handler_error",
                event_type=event_type,
                error=str(e),
            )
