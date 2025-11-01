"""Configuration management for production agent system."""

import os
from typing import Optional, List
from dataclasses import dataclass, field
from dotenv import load_dotenv
import structlog

logger = structlog.get_logger(__name__)

# Load environment variables
load_dotenv()


@dataclass
class Config:
    """Configuration for production agent system."""

    # Database
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL", "postgresql://tsdbadmin:password@localhost:5432/tsdb"
        )
    )

    # Slack
    slack_app_token: str = field(default_factory=lambda: os.getenv("SLACK_APP_TOKEN", ""))
    slack_bot_token: str = field(default_factory=lambda: os.getenv("SLACK_BOT_TOKEN", ""))

    # AI/LLM
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    claude_model: str = field(
        default_factory=lambda: os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")
    )
    claude_max_tokens: int = field(
        default_factory=lambda: int(os.getenv("CLAUDE_MAX_TOKENS", "4096"))
    )
    claude_temperature: float = field(
        default_factory=lambda: float(os.getenv("CLAUDE_TEMPERATURE", "0.7"))
    )
    max_conversation_history: int = field(
        default_factory=lambda: int(os.getenv("MAX_CONVERSATION_HISTORY", "50"))
    )

    # GitHub
    github_token: str = field(default_factory=lambda: os.getenv("GITHUB_TOKEN", ""))
    github_org: Optional[str] = field(default_factory=lambda: os.getenv("GITHUB_ORG"))

    # Worker Pool
    worker_pool_size: int = field(default_factory=lambda: int(os.getenv("WORKER_POOL_SIZE", "5")))
    event_visibility_timeout: int = field(
        default_factory=lambda: int(os.getenv("EVENT_VISIBILITY_TIMEOUT", "300"))
    )
    max_retry_count: int = field(default_factory=lambda: int(os.getenv("MAX_RETRY_COUNT", "3")))

    # Agent Configuration
    company_name: str = field(default_factory=lambda: os.getenv("COMPANY_NAME", "Your Company"))
    domain_areas: List[str] = field(
        default_factory=lambda: os.getenv("DOMAIN_AREAS", "Python,Databases,APIs").split(",")
    )

    # MCP Servers
    slack_mcp_url: str = field(
        default_factory=lambda: os.getenv("SLACK_MCP_URL", "http://localhost:3001/mcp")
    )
    docs_mcp_url: str = field(
        default_factory=lambda: os.getenv("DOCS_MCP_URL", "http://localhost:3002/mcp")
    )
    github_mcp_url: str = field(default_factory=lambda: os.getenv("GITHUB_MCP_URL", "stdio"))

    # Observability
    logfire_token: Optional[str] = field(default_factory=lambda: os.getenv("LOGFIRE_TOKEN"))
    logfire_project_name: Optional[str] = field(
        default_factory=lambda: os.getenv("LOGFIRE_PROJECT_NAME")
    )

    # Environment
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    def validate(self) -> bool:
        """Validate configuration.

        Returns:
            True if configuration is valid
        """
        errors = []

        if not self.slack_app_token:
            errors.append("SLACK_APP_TOKEN is required")

        if not self.slack_bot_token:
            errors.append("SLACK_BOT_TOKEN is required")

        if not self.anthropic_api_key:
            errors.append("ANTHROPIC_API_KEY is required")

        if self.worker_pool_size < 1:
            errors.append("WORKER_POOL_SIZE must be at least 1")

        if errors:
            for error in errors:
                logger.error("config_validation_error", error=error)
            return False

        logger.info("config_validated")
        return True

    def log_configuration(self):
        """Log configuration (with secrets masked)."""
        config_dict = {
            "database_url": self._mask_secret(self.database_url),
            "slack_app_token": self._mask_secret(self.slack_app_token),
            "slack_bot_token": self._mask_secret(self.slack_bot_token),
            "anthropic_api_key": self._mask_secret(self.anthropic_api_key),
            "openai_api_key": self._mask_secret(self.openai_api_key),
            "claude_model": self.claude_model,
            "claude_max_tokens": self.claude_max_tokens,
            "claude_temperature": self.claude_temperature,
            "max_conversation_history": self.max_conversation_history,
            "github_token": self._mask_secret(self.github_token),
            "github_org": self.github_org,
            "worker_pool_size": self.worker_pool_size,
            "event_visibility_timeout": self.event_visibility_timeout,
            "max_retry_count": self.max_retry_count,
            "company_name": self.company_name,
            "domain_areas": self.domain_areas,
            "environment": self.environment,
            "log_level": self.log_level,
        }

        logger.info("configuration_loaded", **config_dict)

    @staticmethod
    def _mask_secret(value: str) -> str:
        """Mask secret values for logging.

        Args:
            value: Secret value

        Returns:
            Masked value (first 4 chars + ***)
        """
        if not value:
            return ""
        if len(value) <= 4:
            return "***"
        return f"{value[:4]}***"


# Global configuration instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get global configuration instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def init_config(**kwargs) -> Config:
    """Initialize global configuration with custom values.

    Args:
        **kwargs: Configuration overrides

    Returns:
        Configuration instance
    """
    global _config
    _config = Config(**kwargs)
    return _config
