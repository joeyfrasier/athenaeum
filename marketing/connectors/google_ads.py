"""
Google Ads Connector
====================

Fetches campaign and performance data from Google Ads API.

Setup Instructions:
1. Create a Google Ads API project in Google Cloud Console
2. Enable the Google Ads API
3. Create OAuth 2.0 credentials
4. Generate a refresh token using the OAuth flow
5. Get your developer token from Google Ads Manager account

Required environment variables:
- GOOGLE_ADS_DEVELOPER_TOKEN
- GOOGLE_ADS_CLIENT_ID
- GOOGLE_ADS_CLIENT_SECRET
- GOOGLE_ADS_REFRESH_TOKEN
- GOOGLE_ADS_CUSTOMER_ID
- GOOGLE_ADS_LOGIN_CUSTOMER_ID (optional, for MCC accounts)

Documentation: https://developers.google.com/google-ads/api/docs/start
"""

from datetime import date
from typing import Optional
import aiohttp
import structlog

from .base import BaseConnector, CampaignData, MetricData
from ..config import GoogleAdsConfig

logger = structlog.get_logger(__name__)


class GoogleAdsConnector(BaseConnector):
    """Connector for Google Ads API"""

    def __init__(self, config: GoogleAdsConfig):
        super().__init__(config)
        self._access_token: Optional[str] = None
        self._token_expiry: Optional[float] = None

    @property
    def source_name(self) -> str:
        return "Google Ads"

    async def _refresh_access_token(self) -> str:
        """Refresh the OAuth access token"""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": self.config.client_id,
                    "client_secret": self.config.client_secret,
                    "refresh_token": self.config.refresh_token,
                    "grant_type": "refresh_token",
                }
            ) as response:
                if response.status != 200:
                    raise Exception(f"Failed to refresh token: {await response.text()}")
                data = await response.json()
                self._access_token = data["access_token"]
                return self._access_token

    async def _get_headers(self) -> dict:
        """Get headers for API requests"""
        if not self._access_token:
            await self._refresh_access_token()

        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "developer-token": self.config.developer_token,
            "Content-Type": "application/json",
        }
        if self.config.login_customer_id:
            headers["login-customer-id"] = self.config.login_customer_id
        return headers

    async def test_connection(self) -> bool:
        """Test the connection to Google Ads API"""
        if not self.is_configured:
            return False

        try:
            headers = await self._get_headers()
            customer_id = self.config.customer_id.replace("-", "")

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"https://googleads.googleapis.com/v18/customers/{customer_id}/googleAds:searchStream",
                    headers=headers,
                    json={
                        "query": "SELECT customer.id FROM customer LIMIT 1"
                    }
                ) as response:
                    return response.status == 200
        except Exception as e:
            self.logger.error("Google Ads connection test failed", error=str(e))
            return False

    async def fetch_campaigns(
        self,
        start_date: date,
        end_date: date
    ) -> list[CampaignData]:
        """Fetch campaign performance data"""
        if not self.is_configured:
            self.logger.warning("Google Ads not configured, returning empty data")
            return []

        try:
            headers = await self._get_headers()
            customer_id = self.config.customer_id.replace("-", "")

            query = f"""
                SELECT
                    campaign.id,
                    campaign.name,
                    campaign.status,
                    metrics.impressions,
                    metrics.clicks,
                    metrics.cost_micros,
                    metrics.conversions,
                    metrics.cost_per_conversion,
                    metrics.ctr
                FROM campaign
                WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
                ORDER BY metrics.impressions DESC
            """

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"https://googleads.googleapis.com/v18/customers/{customer_id}/googleAds:searchStream",
                    headers=headers,
                    json={"query": query}
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        self.logger.error("Google Ads API error", status=response.status, error=error_text)
                        return []

                    data = await response.json()
                    campaigns = []

                    for batch in data:
                        for result in batch.get("results", []):
                            campaign = result.get("campaign", {})
                            metrics = result.get("metrics", {})

                            campaigns.append(CampaignData(
                                campaign_id=str(campaign.get("id", "")),
                                campaign_name=campaign.get("name", "Unknown"),
                                status=campaign.get("status", "UNKNOWN"),
                                impressions=int(metrics.get("impressions", 0)),
                                clicks=int(metrics.get("clicks", 0)),
                                spend=float(metrics.get("costMicros", 0)) / 1_000_000,
                                conversions=int(float(metrics.get("conversions", 0))),
                                cost_per_conversion=float(metrics.get("costPerConversion", 0)) / 1_000_000,
                                ctr=float(metrics.get("ctr", 0)) * 100,
                                date_range_start=start_date,
                                date_range_end=end_date,
                                source=self.source_name,
                            ))

                    return campaigns

        except Exception as e:
            self.logger.error("Failed to fetch Google Ads campaigns", error=str(e))
            return []

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
            headers = await self._get_headers()
            customer_id = self.config.customer_id.replace("-", "")

            # Map friendly names to Google Ads fields
            field_mapping = {
                "impressions": "metrics.impressions",
                "clicks": "metrics.clicks",
                "spend": "metrics.cost_micros",
                "conversions": "metrics.conversions",
                "ctr": "metrics.ctr",
            }

            selected_fields = [field_mapping.get(m, f"metrics.{m}") for m in metric_names]

            query = f"""
                SELECT
                    segments.date,
                    {", ".join(selected_fields)}
                FROM customer
                WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
                ORDER BY segments.date
            """

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"https://googleads.googleapis.com/v18/customers/{customer_id}/googleAds:searchStream",
                    headers=headers,
                    json={"query": query}
                ) as response:
                    if response.status != 200:
                        return []

                    data = await response.json()
                    metrics = []

                    for batch in data:
                        for result in batch.get("results", []):
                            segments = result.get("segments", {})
                            metric_data = result.get("metrics", {})
                            result_date = date.fromisoformat(segments.get("date", str(start_date)))

                            for metric_name in metric_names:
                                value = metric_data.get(metric_name, 0)
                                if metric_name == "spend":
                                    value = float(metric_data.get("costMicros", 0)) / 1_000_000

                                metrics.append(MetricData(
                                    date=result_date,
                                    value=float(value),
                                    metric_name=metric_name,
                                    source=self.source_name,
                                ))

                    return metrics

        except Exception as e:
            self.logger.error("Failed to fetch Google Ads metrics", error=str(e))
            return []

    async def fetch_search_terms(
        self,
        start_date: date,
        end_date: date,
        limit: int = 100
    ) -> list[dict]:
        """Fetch top search terms"""
        if not self.is_configured:
            return []

        try:
            headers = await self._get_headers()
            customer_id = self.config.customer_id.replace("-", "")

            query = f"""
                SELECT
                    search_term_view.search_term,
                    metrics.impressions,
                    metrics.clicks,
                    metrics.cost_micros,
                    metrics.conversions
                FROM search_term_view
                WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
                ORDER BY metrics.impressions DESC
                LIMIT {limit}
            """

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"https://googleads.googleapis.com/v18/customers/{customer_id}/googleAds:searchStream",
                    headers=headers,
                    json={"query": query}
                ) as response:
                    if response.status != 200:
                        return []

                    data = await response.json()
                    search_terms = []

                    for batch in data:
                        for result in batch.get("results", []):
                            stv = result.get("searchTermView", {})
                            metrics = result.get("metrics", {})

                            search_terms.append({
                                "search_term": stv.get("searchTerm", ""),
                                "impressions": int(metrics.get("impressions", 0)),
                                "clicks": int(metrics.get("clicks", 0)),
                                "spend": float(metrics.get("costMicros", 0)) / 1_000_000,
                                "conversions": int(float(metrics.get("conversions", 0))),
                            })

                    return search_terms

        except Exception as e:
            self.logger.error("Failed to fetch search terms", error=str(e))
            return []
