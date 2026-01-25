"""
LinkedIn Ads Connector
======================

Fetches campaign and performance data from LinkedIn Marketing API.

Setup Instructions:
1. Create a LinkedIn App at https://www.linkedin.com/developers/
2. Request access to the Marketing Developer Platform
3. Add the required OAuth scopes: r_ads, r_ads_reporting
4. Generate an access token using OAuth 2.0 flow

Required environment variables:
- LINKEDIN_ADS_ACCESS_TOKEN
- LINKEDIN_ADS_ACCOUNT_ID

Documentation: https://learn.microsoft.com/en-us/linkedin/marketing/
"""

from datetime import date, datetime
from typing import Optional
import aiohttp
import structlog

from .base import BaseConnector, CampaignData, MetricData
from ..config import LinkedInAdsConfig

logger = structlog.get_logger(__name__)


class LinkedInAdsConnector(BaseConnector):
    """Connector for LinkedIn Marketing API"""

    BASE_URL = "https://api.linkedin.com/rest"
    API_VERSION = "202401"

    def __init__(self, config: LinkedInAdsConfig):
        super().__init__(config)

    @property
    def source_name(self) -> str:
        return "LinkedIn Ads"

    def _get_headers(self) -> dict:
        """Get headers for API requests"""
        return {
            "Authorization": f"Bearer {self.config.access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "LinkedIn-Version": self.API_VERSION,
            "Content-Type": "application/json",
        }

    async def test_connection(self) -> bool:
        """Test the connection to LinkedIn Ads API"""
        if not self.is_configured:
            return False

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.BASE_URL}/adAccounts/{self.config.account_id}",
                    headers=self._get_headers()
                ) as response:
                    return response.status == 200
        except Exception as e:
            self.logger.error("LinkedIn Ads connection test failed", error=str(e))
            return False

    async def fetch_campaigns(
        self,
        start_date: date,
        end_date: date
    ) -> list[CampaignData]:
        """Fetch campaign performance data"""
        if not self.is_configured:
            self.logger.warning("LinkedIn Ads not configured, returning empty data")
            return []

        try:
            # First, get campaign list
            campaigns_data = await self._fetch_campaign_list()

            # Then get analytics for each campaign
            campaign_ids = [c["id"] for c in campaigns_data]
            if not campaign_ids:
                return []

            analytics = await self._fetch_campaign_analytics(campaign_ids, start_date, end_date)

            campaigns = []
            for campaign in campaigns_data:
                campaign_id = campaign["id"]
                stats = analytics.get(campaign_id, {})

                impressions = stats.get("impressions", 0)
                clicks = stats.get("clicks", 0)
                spend = stats.get("costInLocalCurrency", 0)
                conversions = stats.get("externalWebsiteConversions", 0)

                campaigns.append(CampaignData(
                    campaign_id=str(campaign_id),
                    campaign_name=campaign.get("name", "Unknown"),
                    status=campaign.get("status", "UNKNOWN"),
                    impressions=impressions,
                    clicks=clicks,
                    spend=spend,
                    conversions=conversions,
                    cost_per_conversion=spend / conversions if conversions > 0 else 0,
                    ctr=(clicks / impressions * 100) if impressions > 0 else 0,
                    date_range_start=start_date,
                    date_range_end=end_date,
                    source=self.source_name,
                    additional_metrics={
                        "leads": stats.get("oneClickLeads", 0),
                        "engagement_rate": stats.get("engagementRate", 0),
                        "video_views": stats.get("videoViews", 0),
                    }
                ))

            return campaigns

        except Exception as e:
            self.logger.error("Failed to fetch LinkedIn Ads campaigns", error=str(e))
            return []

    async def _fetch_campaign_list(self) -> list[dict]:
        """Fetch list of campaigns"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.BASE_URL}/adAccounts/{self.config.account_id}/adCampaigns",
                    headers=self._get_headers(),
                    params={"q": "search", "count": 100}
                ) as response:
                    if response.status != 200:
                        self.logger.error("Failed to fetch campaign list", status=response.status)
                        return []

                    data = await response.json()
                    return data.get("elements", [])

        except Exception as e:
            self.logger.error("Error fetching campaign list", error=str(e))
            return []

    async def _fetch_campaign_analytics(
        self,
        campaign_ids: list[str],
        start_date: date,
        end_date: date
    ) -> dict:
        """Fetch analytics for campaigns"""
        try:
            # Build campaign URN list
            campaign_urns = [f"urn:li:sponsoredCampaign:{cid}" for cid in campaign_ids]

            params = {
                "q": "analytics",
                "pivot": "CAMPAIGN",
                "dateRange.start.day": start_date.day,
                "dateRange.start.month": start_date.month,
                "dateRange.start.year": start_date.year,
                "dateRange.end.day": end_date.day,
                "dateRange.end.month": end_date.month,
                "dateRange.end.year": end_date.year,
                "timeGranularity": "ALL",
                "campaigns": ",".join(campaign_urns),
                "fields": "impressions,clicks,costInLocalCurrency,externalWebsiteConversions,oneClickLeads,engagementRate,videoViews",
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.BASE_URL}/adAnalytics",
                    headers=self._get_headers(),
                    params=params
                ) as response:
                    if response.status != 200:
                        self.logger.error("Failed to fetch analytics", status=response.status)
                        return {}

                    data = await response.json()
                    analytics = {}

                    for element in data.get("elements", []):
                        # Extract campaign ID from URN
                        pivot_value = element.get("pivotValue", "")
                        if "sponsoredCampaign:" in pivot_value:
                            campaign_id = pivot_value.split(":")[-1]
                            analytics[campaign_id] = element

                    return analytics

        except Exception as e:
            self.logger.error("Error fetching analytics", error=str(e))
            return {}

    async def fetch_metrics(
        self,
        metric_names: list[str],
        start_date: date,
        end_date: date
    ) -> list[MetricData]:
        """Fetch daily metrics"""
        if not self.is_configured:
            return []

        try:
            params = {
                "q": "analytics",
                "pivot": "ACCOUNT",
                "dateRange.start.day": start_date.day,
                "dateRange.start.month": start_date.month,
                "dateRange.start.year": start_date.year,
                "dateRange.end.day": end_date.day,
                "dateRange.end.month": end_date.month,
                "dateRange.end.year": end_date.year,
                "timeGranularity": "DAILY",
                "accounts": f"urn:li:sponsoredAccount:{self.config.account_id}",
                "fields": ",".join(metric_names),
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.BASE_URL}/adAnalytics",
                    headers=self._get_headers(),
                    params=params
                ) as response:
                    if response.status != 200:
                        return []

                    data = await response.json()
                    metrics = []

                    for element in data.get("elements", []):
                        date_range = element.get("dateRange", {})
                        start = date_range.get("start", {})
                        metric_date = date(start.get("year", 1), start.get("month", 1), start.get("day", 1))

                        for metric_name in metric_names:
                            value = element.get(metric_name, 0)
                            metrics.append(MetricData(
                                date=metric_date,
                                value=float(value),
                                metric_name=metric_name,
                                source=self.source_name,
                            ))

                    return metrics

        except Exception as e:
            self.logger.error("Failed to fetch LinkedIn metrics", error=str(e))
            return []

    async def fetch_audience_insights(self) -> dict:
        """Fetch audience insights for the account"""
        if not self.is_configured:
            return {}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.BASE_URL}/adAccounts/{self.config.account_id}/targetingFacets",
                    headers=self._get_headers()
                ) as response:
                    if response.status != 200:
                        return {}

                    return await response.json()

        except Exception as e:
            self.logger.error("Failed to fetch audience insights", error=str(e))
            return {}
