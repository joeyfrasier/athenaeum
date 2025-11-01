"""Slack integration package for Athenaeum."""

from slack.client import SlackClient
from slack.socket_handler import SocketModeHandler
from slack.ingest import SlackIngestor

__all__ = [
    "SlackClient",
    "SocketModeHandler",
    "SlackIngestor",
]
