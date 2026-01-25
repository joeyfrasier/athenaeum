"""
Marketing Dashboard Configuration
=================================

Easy configuration for all marketing data sources.
Set credentials via environment variables or .env file.
"""

import os
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class GoogleAdsConfig:
    """Google Ads API Configuration"""
    developer_token: str = field(default_factory=lambda: os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", ""))
    client_id: str = field(default_factory=lambda: os.getenv("GOOGLE_ADS_CLIENT_ID", ""))
    client_secret: str = field(default_factory=lambda: os.getenv("GOOGLE_ADS_CLIENT_SECRET", ""))
    refresh_token: str = field(default_factory=lambda: os.getenv("GOOGLE_ADS_REFRESH_TOKEN", ""))
    customer_id: str = field(default_factory=lambda: os.getenv("GOOGLE_ADS_CUSTOMER_ID", ""))
    login_customer_id: str = field(default_factory=lambda: os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID", ""))

    @property
    def is_configured(self) -> bool:
        return all([self.developer_token, self.client_id, self.client_secret,
                   self.refresh_token, self.customer_id])


@dataclass
class LinkedInAdsConfig:
    """LinkedIn Ads API Configuration"""
    access_token: str = field(default_factory=lambda: os.getenv("LINKEDIN_ADS_ACCESS_TOKEN", ""))
    account_id: str = field(default_factory=lambda: os.getenv("LINKEDIN_ADS_ACCOUNT_ID", ""))

    @property
    def is_configured(self) -> bool:
        return all([self.access_token, self.account_id])


@dataclass
class AttioConfig:
    """Attio CRM API Configuration"""
    api_key: str = field(default_factory=lambda: os.getenv("ATTIO_API_KEY", ""))
    workspace_id: str = field(default_factory=lambda: os.getenv("ATTIO_WORKSPACE_ID", ""))

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)


@dataclass
class HubSpotConfig:
    """HubSpot Marketing API Configuration"""
    api_key: str = field(default_factory=lambda: os.getenv("HUBSPOT_API_KEY", ""))
    portal_id: str = field(default_factory=lambda: os.getenv("HUBSPOT_PORTAL_ID", ""))

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)


@dataclass
class LLMTrackingConfig:
    """LLM Search Results Tracking Configuration"""
    # OpenAI for generating test queries
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))

    # Anthropic for generating test queries
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))

    # Perplexity for AI search tracking
    perplexity_api_key: str = field(default_factory=lambda: os.getenv("PERPLEXITY_API_KEY", ""))

    # Keywords to track
    tracked_keywords: list = field(default_factory=lambda: [
        "freelance management system",
        "freelancer management software",
        "contingent workforce management",
        "contractor management platform",
        "freelancer payment solution",
        "FMS software",
        "manage freelancers",
        "hire freelancers globally",
        "freelancer onboarding software",
        "worksuite alternatives",
        "best freelance management tools",
    ])

    # Competitors to track
    competitors: list = field(default_factory=lambda: [
        "Deel",
        "Remote.com",
        "Fiverr Enterprise",
        "Upwork Enterprise",
        "Toptal",
        "Papaya Global",
        "Worksome",
        "Stoke Talent",
    ])

    @property
    def is_configured(self) -> bool:
        return any([self.openai_api_key, self.anthropic_api_key, self.perplexity_api_key])


@dataclass
class MarketingConfig:
    """Master configuration for all marketing integrations"""
    google_ads: GoogleAdsConfig = field(default_factory=GoogleAdsConfig)
    linkedin_ads: LinkedInAdsConfig = field(default_factory=LinkedInAdsConfig)
    attio: AttioConfig = field(default_factory=AttioConfig)
    hubspot: HubSpotConfig = field(default_factory=HubSpotConfig)
    llm_tracking: LLMTrackingConfig = field(default_factory=LLMTrackingConfig)

    # Dashboard settings
    demo_mode: bool = field(default_factory=lambda: os.getenv("MARKETING_DEMO_MODE", "true").lower() == "true")
    refresh_interval_minutes: int = field(default_factory=lambda: int(os.getenv("MARKETING_REFRESH_INTERVAL", "15")))

    def get_status(self) -> dict:
        """Get configuration status for all integrations"""
        return {
            "google_ads": self.google_ads.is_configured,
            "linkedin_ads": self.linkedin_ads.is_configured,
            "attio": self.attio.is_configured,
            "hubspot": self.hubspot.is_configured,
            "llm_tracking": self.llm_tracking.is_configured,
            "demo_mode": self.demo_mode,
        }


# Global configuration instance
_config: Optional[MarketingConfig] = None


def get_config() -> MarketingConfig:
    """Get the marketing configuration singleton"""
    global _config
    if _config is None:
        _config = MarketingConfig()
    return _config


def reset_config() -> None:
    """Reset configuration (useful for testing)"""
    global _config
    _config = None
