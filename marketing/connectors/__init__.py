"""
Marketing Data Connectors
=========================

Connectors for fetching data from various marketing platforms:
- Google Ads
- LinkedIn Ads
- Attio CRM
- HubSpot Marketing
"""

from .google_ads import GoogleAdsConnector
from .linkedin_ads import LinkedInAdsConnector
from .attio import AttioConnector
from .hubspot import HubSpotConnector

__all__ = [
    "GoogleAdsConnector",
    "LinkedInAdsConnector",
    "AttioConnector",
    "HubSpotConnector",
]
