"""
HubSpot Marketing Connector
===========================

Fetches marketing data from HubSpot including:
- Email campaigns
- Forms and submissions
- Landing pages
- Traffic analytics
- Contact lifecycle stages

Setup Instructions:
1. Log in to your HubSpot account
2. Go to Settings > Integrations > Private Apps
3. Create a new private app with required scopes:
   - marketing.read
   - contacts.read
   - forms.read
   - content.read
4. Copy the access token

Required environment variables:
- HUBSPOT_API_KEY (Private App access token)
- HUBSPOT_PORTAL_ID (optional)

Documentation: https://developers.hubspot.com/docs/api/overview
"""

from datetime import date, datetime, timedelta
from typing import Optional
import aiohttp
import structlog

from .base import BaseConnector, CampaignData, MetricData
from ..config import HubSpotConfig

logger = structlog.get_logger(__name__)


class HubSpotConnector(BaseConnector):
    """Connector for HubSpot Marketing API"""

    BASE_URL = "https://api.hubapi.com"

    def __init__(self, config: HubSpotConfig):
        super().__init__(config)

    @property
    def source_name(self) -> str:
        return "HubSpot"

    def _get_headers(self) -> dict:
        """Get headers for API requests"""
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

    async def test_connection(self) -> bool:
        """Test the connection to HubSpot API"""
        if not self.is_configured:
            return False

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.BASE_URL}/account-info/v3/api-usage/daily",
                    headers=self._get_headers()
                ) as response:
                    return response.status == 200
        except Exception as e:
            self.logger.error("HubSpot connection test failed", error=str(e))
            return False

    async def fetch_campaigns(
        self,
        start_date: date,
        end_date: date
    ) -> list[CampaignData]:
        """Fetch email campaign data"""
        if not self.is_configured:
            self.logger.warning("HubSpot not configured, returning empty data")
            return []

        try:
            campaigns = []

            # Fetch email campaigns
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.BASE_URL}/marketing/v3/emails",
                    headers=self._get_headers(),
                    params={
                        "limit": 100,
                        "after": start_date.isoformat(),
                    }
                ) as response:
                    if response.status != 200:
                        self.logger.error("Failed to fetch HubSpot campaigns", status=response.status)
                        return []

                    data = await response.json()

                    for email in data.get("results", []):
                        # Get email statistics
                        email_id = email.get("id")
                        stats = await self._fetch_email_stats(email_id)

                        sent = stats.get("sent", 0)
                        opened = stats.get("open", 0)
                        clicked = stats.get("click", 0)

                        campaigns.append(CampaignData(
                            campaign_id=str(email_id),
                            campaign_name=email.get("name", "Unknown"),
                            status=email.get("state", "UNKNOWN"),
                            impressions=sent,  # Using sent as impressions for email
                            clicks=clicked,
                            spend=0,  # HubSpot doesn't track spend per email
                            conversions=stats.get("reply", 0),
                            cost_per_conversion=0,
                            ctr=(clicked / sent * 100) if sent > 0 else 0,
                            date_range_start=start_date,
                            date_range_end=end_date,
                            source=self.source_name,
                            additional_metrics={
                                "opens": opened,
                                "open_rate": (opened / sent * 100) if sent > 0 else 0,
                                "bounces": stats.get("bounce", 0),
                                "unsubscribes": stats.get("unsubscribed", 0),
                            }
                        ))

            return campaigns

        except Exception as e:
            self.logger.error("Failed to fetch HubSpot campaigns", error=str(e))
            return []

    async def _fetch_email_stats(self, email_id: str) -> dict:
        """Fetch statistics for a specific email"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.BASE_URL}/marketing-emails/v1/emails/{email_id}/statistics",
                    headers=self._get_headers()
                ) as response:
                    if response.status != 200:
                        return {}
                    return await response.json()
        except Exception:
            return {}

    async def fetch_metrics(
        self,
        metric_names: list[str],
        start_date: date,
        end_date: date
    ) -> list[MetricData]:
        """Fetch marketing metrics"""
        if not self.is_configured:
            return []

        metrics = []

        # Map metrics to appropriate fetchers
        if any(m in metric_names for m in ["contacts", "new_contacts", "subscribers"]):
            contact_metrics = await self._fetch_contact_metrics(start_date, end_date)
            metrics.extend(contact_metrics)

        if any(m in metric_names for m in ["form_submissions", "forms"]):
            form_metrics = await self._fetch_form_metrics(start_date, end_date)
            metrics.extend(form_metrics)

        if any(m in metric_names for m in ["website_visits", "page_views"]):
            traffic_metrics = await self._fetch_traffic_metrics(start_date, end_date)
            metrics.extend(traffic_metrics)

        return metrics

    async def _fetch_contact_metrics(
        self,
        start_date: date,
        end_date: date
    ) -> list[MetricData]:
        """Fetch contact-related metrics"""
        try:
            # Get contacts created in date range
            start_timestamp = int(datetime.combine(start_date, datetime.min.time()).timestamp() * 1000)
            end_timestamp = int(datetime.combine(end_date, datetime.max.time()).timestamp() * 1000)

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.BASE_URL}/crm/v3/objects/contacts/search",
                    headers=self._get_headers(),
                    json={
                        "filterGroups": [{
                            "filters": [{
                                "propertyName": "createdate",
                                "operator": "BETWEEN",
                                "highValue": str(end_timestamp),
                                "value": str(start_timestamp),
                            }]
                        }],
                        "limit": 0,
                    }
                ) as response:
                    if response.status != 200:
                        return []

                    data = await response.json()
                    total = data.get("total", 0)

                    return [
                        MetricData(
                            date=end_date,
                            value=float(total),
                            metric_name="new_contacts",
                            source=self.source_name,
                        )
                    ]

        except Exception as e:
            self.logger.error("Failed to fetch contact metrics", error=str(e))
            return []

    async def _fetch_form_metrics(
        self,
        start_date: date,
        end_date: date
    ) -> list[MetricData]:
        """Fetch form submission metrics"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.BASE_URL}/marketing/v3/forms",
                    headers=self._get_headers(),
                ) as response:
                    if response.status != 200:
                        return []

                    data = await response.json()
                    forms = data.get("results", [])

                    total_submissions = 0
                    for form in forms:
                        # Get submissions for each form
                        form_guid = form.get("id")
                        submissions = await self._fetch_form_submissions(form_guid, start_date, end_date)
                        total_submissions += submissions

                    return [
                        MetricData(
                            date=end_date,
                            value=float(total_submissions),
                            metric_name="form_submissions",
                            source=self.source_name,
                        )
                    ]

        except Exception as e:
            self.logger.error("Failed to fetch form metrics", error=str(e))
            return []

    async def _fetch_form_submissions(
        self,
        form_guid: str,
        start_date: date,
        end_date: date
    ) -> int:
        """Fetch submission count for a form"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.BASE_URL}/form-integrations/v1/submissions/forms/{form_guid}",
                    headers=self._get_headers(),
                    params={
                        "limit": 1,
                    }
                ) as response:
                    if response.status != 200:
                        return 0

                    data = await response.json()
                    return len(data.get("results", []))

        except Exception:
            return 0

    async def _fetch_traffic_metrics(
        self,
        start_date: date,
        end_date: date
    ) -> list[MetricData]:
        """Fetch website traffic metrics"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.BASE_URL}/analytics/v2/reports/totals/summarize/daily",
                    headers=self._get_headers(),
                    params={
                        "start": start_date.isoformat(),
                        "end": end_date.isoformat(),
                    }
                ) as response:
                    if response.status != 200:
                        return []

                    data = await response.json()
                    totals = data.get("totals", {})

                    metrics = []
                    if "visits" in totals:
                        metrics.append(MetricData(
                            date=end_date,
                            value=float(totals["visits"]),
                            metric_name="website_visits",
                            source=self.source_name,
                        ))
                    if "pageviews" in totals:
                        metrics.append(MetricData(
                            date=end_date,
                            value=float(totals["pageviews"]),
                            metric_name="page_views",
                            source=self.source_name,
                        ))

                    return metrics

        except Exception as e:
            self.logger.error("Failed to fetch traffic metrics", error=str(e))
            return []

    async def fetch_lifecycle_stages(self) -> list[dict]:
        """Fetch contact counts by lifecycle stage"""
        try:
            stages = [
                "subscriber", "lead", "marketingqualifiedlead",
                "salesqualifiedlead", "opportunity", "customer",
                "evangelist", "other"
            ]

            stage_counts = []

            async with aiohttp.ClientSession() as session:
                for stage in stages:
                    async with session.post(
                        f"{self.BASE_URL}/crm/v3/objects/contacts/search",
                        headers=self._get_headers(),
                        json={
                            "filterGroups": [{
                                "filters": [{
                                    "propertyName": "lifecyclestage",
                                    "operator": "EQ",
                                    "value": stage,
                                }]
                            }],
                            "limit": 0,
                        }
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            stage_counts.append({
                                "stage": stage.replace("qualifiedlead", " Qualified Lead").title(),
                                "count": data.get("total", 0),
                            })

            return stage_counts

        except Exception as e:
            self.logger.error("Failed to fetch lifecycle stages", error=str(e))
            return []

    async def fetch_recent_conversions(self, limit: int = 20) -> list[dict]:
        """Fetch recent form conversions"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.BASE_URL}/form-integrations/v1/submissions",
                    headers=self._get_headers(),
                    params={"limit": limit}
                ) as response:
                    if response.status != 200:
                        return []

                    data = await response.json()
                    return data.get("results", [])

        except Exception as e:
            self.logger.error("Failed to fetch recent conversions", error=str(e))
            return []

    async def get_summary(self, start_date: date, end_date: date) -> dict:
        """Get HubSpot marketing summary"""
        campaigns = await self.fetch_campaigns(start_date, end_date)
        lifecycle = await self.fetch_lifecycle_stages()

        total_sent = sum(c.impressions for c in campaigns)
        total_clicks = sum(c.clicks for c in campaigns)

        return {
            "source": self.source_name,
            "date_range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "total_campaigns": len(campaigns),
            "total_emails_sent": total_sent,
            "total_clicks": total_clicks,
            "avg_ctr": (total_clicks / total_sent * 100) if total_sent > 0 else 0,
            "lifecycle_stages": lifecycle,
        }
