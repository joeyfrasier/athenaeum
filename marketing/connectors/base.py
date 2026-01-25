"""
Base connector class for all marketing data sources
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, date
from typing import Any, Optional
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class MetricData:
    """Standard metric data structure"""
    date: date
    value: float
    metric_name: str
    source: str
    dimensions: dict = None

    def __post_init__(self):
        if self.dimensions is None:
            self.dimensions = {}


@dataclass
class CampaignData:
    """Campaign performance data"""
    campaign_id: str
    campaign_name: str
    status: str
    impressions: int
    clicks: int
    spend: float
    conversions: int
    cost_per_conversion: float
    ctr: float
    date_range_start: date
    date_range_end: date
    source: str
    additional_metrics: dict = None

    def __post_init__(self):
        if self.additional_metrics is None:
            self.additional_metrics = {}


class BaseConnector(ABC):
    """Base class for all marketing data connectors"""

    def __init__(self, config: Any):
        self.config = config
        self.logger = logger.bind(connector=self.__class__.__name__)

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Return the name of the data source"""
        pass

    @property
    def is_configured(self) -> bool:
        """Check if the connector is properly configured"""
        return self.config.is_configured

    @abstractmethod
    async def test_connection(self) -> bool:
        """Test the connection to the data source"""
        pass

    @abstractmethod
    async def fetch_campaigns(
        self,
        start_date: date,
        end_date: date
    ) -> list[CampaignData]:
        """Fetch campaign data for the given date range"""
        pass

    @abstractmethod
    async def fetch_metrics(
        self,
        metric_names: list[str],
        start_date: date,
        end_date: date
    ) -> list[MetricData]:
        """Fetch specific metrics for the given date range"""
        pass

    async def get_summary(
        self,
        start_date: date,
        end_date: date
    ) -> dict:
        """Get a summary of key metrics"""
        campaigns = await self.fetch_campaigns(start_date, end_date)

        total_impressions = sum(c.impressions for c in campaigns)
        total_clicks = sum(c.clicks for c in campaigns)
        total_spend = sum(c.spend for c in campaigns)
        total_conversions = sum(c.conversions for c in campaigns)

        return {
            "source": self.source_name,
            "date_range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "total_campaigns": len(campaigns),
            "active_campaigns": len([c for c in campaigns if c.status == "ENABLED"]),
            "total_impressions": total_impressions,
            "total_clicks": total_clicks,
            "total_spend": total_spend,
            "total_conversions": total_conversions,
            "avg_ctr": (total_clicks / total_impressions * 100) if total_impressions > 0 else 0,
            "avg_cpc": (total_spend / total_clicks) if total_clicks > 0 else 0,
            "cost_per_conversion": (total_spend / total_conversions) if total_conversions > 0 else 0,
        }
