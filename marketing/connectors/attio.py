"""
Attio CRM Connector
===================

Fetches contact, deal, and pipeline data from Attio CRM.

Setup Instructions:
1. Log in to your Attio workspace
2. Go to Settings > Integrations > API
3. Generate a new API key with the required scopes

Required environment variables:
- ATTIO_API_KEY
- ATTIO_WORKSPACE_ID (optional)

Documentation: https://developers.attio.com/
"""

from datetime import date, datetime
from typing import Optional
import aiohttp
import structlog

from .base import BaseConnector, MetricData
from ..config import AttioConfig

logger = structlog.get_logger(__name__)


class AttioConnector(BaseConnector):
    """Connector for Attio CRM API"""

    BASE_URL = "https://api.attio.com/v2"

    def __init__(self, config: AttioConfig):
        super().__init__(config)

    @property
    def source_name(self) -> str:
        return "Attio CRM"

    def _get_headers(self) -> dict:
        """Get headers for API requests"""
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

    async def test_connection(self) -> bool:
        """Test the connection to Attio API"""
        if not self.is_configured:
            return False

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.BASE_URL}/objects",
                    headers=self._get_headers()
                ) as response:
                    return response.status == 200
        except Exception as e:
            self.logger.error("Attio connection test failed", error=str(e))
            return False

    async def fetch_campaigns(self, start_date: date, end_date: date) -> list:
        """Attio doesn't have campaigns - return empty list"""
        return []

    async def fetch_metrics(
        self,
        metric_names: list[str],
        start_date: date,
        end_date: date
    ) -> list[MetricData]:
        """Fetch CRM metrics"""
        if not self.is_configured:
            return []

        metrics = []

        # Fetch various counts based on requested metrics
        if "contacts" in metric_names or "new_contacts" in metric_names:
            contacts = await self.fetch_contacts_count(start_date, end_date)
            metrics.append(MetricData(
                date=end_date,
                value=float(contacts),
                metric_name="contacts",
                source=self.source_name,
            ))

        if "companies" in metric_names or "new_companies" in metric_names:
            companies = await self.fetch_companies_count(start_date, end_date)
            metrics.append(MetricData(
                date=end_date,
                value=float(companies),
                metric_name="companies",
                source=self.source_name,
            ))

        if "deals" in metric_names or "new_deals" in metric_names:
            deals = await self.fetch_deals_summary(start_date, end_date)
            metrics.append(MetricData(
                date=end_date,
                value=float(deals.get("count", 0)),
                metric_name="deals",
                source=self.source_name,
            ))
            metrics.append(MetricData(
                date=end_date,
                value=float(deals.get("total_value", 0)),
                metric_name="deal_value",
                source=self.source_name,
            ))

        return metrics

    async def fetch_contacts_count(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> int:
        """Fetch count of contacts"""
        try:
            filter_query = {}
            if start_date and end_date:
                filter_query = {
                    "filter": {
                        "created_at": {
                            "$gte": start_date.isoformat(),
                            "$lte": end_date.isoformat(),
                        }
                    }
                }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.BASE_URL}/objects/people/records/query",
                    headers=self._get_headers(),
                    json=filter_query
                ) as response:
                    if response.status != 200:
                        return 0

                    data = await response.json()
                    return len(data.get("data", []))

        except Exception as e:
            self.logger.error("Failed to fetch contacts count", error=str(e))
            return 0

    async def fetch_companies_count(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> int:
        """Fetch count of companies"""
        try:
            filter_query = {}
            if start_date and end_date:
                filter_query = {
                    "filter": {
                        "created_at": {
                            "$gte": start_date.isoformat(),
                            "$lte": end_date.isoformat(),
                        }
                    }
                }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.BASE_URL}/objects/companies/records/query",
                    headers=self._get_headers(),
                    json=filter_query
                ) as response:
                    if response.status != 200:
                        return 0

                    data = await response.json()
                    return len(data.get("data", []))

        except Exception as e:
            self.logger.error("Failed to fetch companies count", error=str(e))
            return 0

    async def fetch_deals_summary(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> dict:
        """Fetch deals summary with total value"""
        try:
            filter_query = {}
            if start_date and end_date:
                filter_query = {
                    "filter": {
                        "created_at": {
                            "$gte": start_date.isoformat(),
                            "$lte": end_date.isoformat(),
                        }
                    }
                }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.BASE_URL}/objects/deals/records/query",
                    headers=self._get_headers(),
                    json=filter_query
                ) as response:
                    if response.status != 200:
                        return {"count": 0, "total_value": 0}

                    data = await response.json()
                    deals = data.get("data", [])

                    total_value = 0
                    for deal in deals:
                        values = deal.get("values", {})
                        # Try to get deal value from common field names
                        for field in ["value", "amount", "deal_value"]:
                            if field in values:
                                val = values[field]
                                if isinstance(val, list) and val:
                                    total_value += float(val[0].get("value", 0) or 0)
                                elif isinstance(val, (int, float)):
                                    total_value += float(val)

                    return {
                        "count": len(deals),
                        "total_value": total_value,
                    }

        except Exception as e:
            self.logger.error("Failed to fetch deals summary", error=str(e))
            return {"count": 0, "total_value": 0}

    async def fetch_pipeline_stages(self) -> list[dict]:
        """Fetch pipeline stages with deal counts"""
        try:
            # First get the pipeline/status attribute
            async with aiohttp.ClientSession() as session:
                # Get all deals
                async with session.post(
                    f"{self.BASE_URL}/objects/deals/records/query",
                    headers=self._get_headers(),
                    json={}
                ) as response:
                    if response.status != 200:
                        return []

                    data = await response.json()
                    deals = data.get("data", [])

                    # Count deals by stage
                    stage_counts = {}
                    for deal in deals:
                        values = deal.get("values", {})
                        stage = values.get("stage", [{}])
                        if isinstance(stage, list) and stage:
                            stage_name = stage[0].get("option", {}).get("title", "Unknown")
                        else:
                            stage_name = "Unknown"

                        stage_counts[stage_name] = stage_counts.get(stage_name, 0) + 1

                    return [
                        {"stage": stage, "count": count}
                        for stage, count in stage_counts.items()
                    ]

        except Exception as e:
            self.logger.error("Failed to fetch pipeline stages", error=str(e))
            return []

    async def fetch_recent_activity(self, limit: int = 20) -> list[dict]:
        """Fetch recent CRM activity"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.BASE_URL}/notes",
                    headers=self._get_headers(),
                    params={"limit": limit}
                ) as response:
                    if response.status != 200:
                        return []

                    data = await response.json()
                    return data.get("data", [])

        except Exception as e:
            self.logger.error("Failed to fetch recent activity", error=str(e))
            return []

    async def get_summary(self, start_date: date, end_date: date) -> dict:
        """Get CRM summary"""
        contacts = await self.fetch_contacts_count(start_date, end_date)
        companies = await self.fetch_companies_count(start_date, end_date)
        deals = await self.fetch_deals_summary(start_date, end_date)
        pipeline = await self.fetch_pipeline_stages()

        return {
            "source": self.source_name,
            "date_range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "new_contacts": contacts,
            "new_companies": companies,
            "new_deals": deals["count"],
            "deal_value": deals["total_value"],
            "pipeline_stages": pipeline,
        }
