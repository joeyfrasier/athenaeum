"""
Demo Data Generator
===================

Generates realistic sample data for the marketing dashboard
when real integrations are not configured (demo mode).
"""

import random
from datetime import datetime, date, timedelta
from dataclasses import dataclass
from typing import Optional

from .connectors.base import CampaignData, MetricData


def generate_date_range(start_date: date, end_date: date) -> list[date]:
    """Generate a list of dates between start and end"""
    dates = []
    current = start_date
    while current <= end_date:
        dates.append(current)
        current += timedelta(days=1)
    return dates


def generate_google_ads_campaigns(
    start_date: date,
    end_date: date,
    num_campaigns: int = 8
) -> list[CampaignData]:
    """Generate sample Google Ads campaign data"""
    campaign_names = [
        "Freelancer Management - Search",
        "FMS Enterprise - Display",
        "Contractor Payment Solution",
        "Global Workforce - Remarketing",
        "Worksuite Brand - Search",
        "Competitor Conquest - Search",
        "Free Trial - Performance Max",
        "HR Tech - Display Network",
        "Remote Workforce Solutions",
        "Freelance Platform - Video",
    ]

    campaigns = []
    for i in range(min(num_campaigns, len(campaign_names))):
        impressions = random.randint(50000, 500000)
        ctr = random.uniform(1.5, 4.5)
        clicks = int(impressions * ctr / 100)
        cpc = random.uniform(2.5, 8.0)
        spend = clicks * cpc
        conversion_rate = random.uniform(2.0, 8.0)
        conversions = int(clicks * conversion_rate / 100)

        campaigns.append(CampaignData(
            campaign_id=str(1000 + i),
            campaign_name=campaign_names[i],
            status="ENABLED" if random.random() > 0.2 else "PAUSED",
            impressions=impressions,
            clicks=clicks,
            spend=round(spend, 2),
            conversions=conversions,
            cost_per_conversion=round(spend / conversions, 2) if conversions > 0 else 0,
            ctr=round(ctr, 2),
            date_range_start=start_date,
            date_range_end=end_date,
            source="Google Ads",
        ))

    return campaigns


def generate_linkedin_ads_campaigns(
    start_date: date,
    end_date: date,
    num_campaigns: int = 6
) -> list[CampaignData]:
    """Generate sample LinkedIn Ads campaign data"""
    campaign_names = [
        "Enterprise Decision Makers",
        "HR Leaders - Sponsored Content",
        "CFO Targeting - Conversation Ads",
        "Freelance Economy Whitepaper",
        "Case Study Promotion",
        "Webinar - Future of Work",
        "Product Launch - InMail",
        "Thought Leadership - Articles",
    ]

    campaigns = []
    for i in range(min(num_campaigns, len(campaign_names))):
        impressions = random.randint(20000, 150000)
        ctr = random.uniform(0.3, 1.2)
        clicks = int(impressions * ctr / 100)
        cpc = random.uniform(5.0, 15.0)
        spend = clicks * cpc
        conversion_rate = random.uniform(3.0, 10.0)
        conversions = int(clicks * conversion_rate / 100)
        leads = int(conversions * random.uniform(0.3, 0.6))

        campaigns.append(CampaignData(
            campaign_id=str(2000 + i),
            campaign_name=campaign_names[i],
            status="ENABLED" if random.random() > 0.15 else "PAUSED",
            impressions=impressions,
            clicks=clicks,
            spend=round(spend, 2),
            conversions=conversions,
            cost_per_conversion=round(spend / conversions, 2) if conversions > 0 else 0,
            ctr=round(ctr, 2),
            date_range_start=start_date,
            date_range_end=end_date,
            source="LinkedIn Ads",
            additional_metrics={
                "leads": leads,
                "engagement_rate": round(random.uniform(2.0, 6.0), 2),
                "video_views": random.randint(0, 10000) if "Video" in campaign_names[i] else 0,
            }
        ))

    return campaigns


def generate_daily_metrics(
    start_date: date,
    end_date: date,
    base_users: int = 50000,
    base_revenue: float = 25000.0,
    growth_rate: float = 0.02
) -> tuple[list[MetricData], list[MetricData]]:
    """Generate daily users and revenue metrics with realistic patterns"""
    dates = generate_date_range(start_date, end_date)

    users_data = []
    revenue_data = []

    current_users = base_users
    current_revenue = base_revenue

    for i, d in enumerate(dates):
        # Add weekly pattern (weekends lower)
        day_of_week = d.weekday()
        weekend_factor = 0.6 if day_of_week >= 5 else 1.0

        # Add some randomness
        daily_variance = random.uniform(0.85, 1.15)

        # Growth trend
        trend_factor = 1 + (growth_rate * i / len(dates))

        users = int(current_users * weekend_factor * daily_variance * trend_factor)
        revenue = current_revenue * weekend_factor * daily_variance * trend_factor

        users_data.append(MetricData(
            date=d,
            value=float(users),
            metric_name="users",
            source="aggregate",
        ))

        revenue_data.append(MetricData(
            date=d,
            value=round(revenue, 2),
            metric_name="revenue",
            source="aggregate",
        ))

    return users_data, revenue_data


def generate_traffic_sources() -> list[dict]:
    """Generate traffic source distribution"""
    sources = [
        {"name": "Organic Search", "value": random.randint(35, 45), "color": "#0088FE"},
        {"name": "Direct", "value": random.randint(20, 30), "color": "#B8442E"},
        {"name": "Referral", "value": random.randint(10, 18), "color": "#D4A84B"},
        {"name": "Paid Search", "value": random.randint(10, 15), "color": "#6CB043"},
        {"name": "Social", "value": random.randint(5, 12), "color": "#8884d8"},
        {"name": "Email", "value": random.randint(3, 8), "color": "#82ca9d"},
    ]

    # Normalize to 100%
    total = sum(s["value"] for s in sources)
    for source in sources:
        source["percentage"] = round(source["value"] / total * 100, 1)

    return sources


def generate_attio_crm_data(
    start_date: date,
    end_date: date
) -> dict:
    """Generate sample Attio CRM data"""
    num_days = (end_date - start_date).days

    return {
        "new_contacts": random.randint(50, 150) * (num_days // 7 + 1),
        "new_companies": random.randint(20, 60) * (num_days // 7 + 1),
        "new_deals": random.randint(15, 40) * (num_days // 7 + 1),
        "deal_value": random.randint(100000, 500000),
        "pipeline_stages": [
            {"stage": "Lead", "count": random.randint(100, 300)},
            {"stage": "Qualified", "count": random.randint(50, 150)},
            {"stage": "Proposal", "count": random.randint(20, 60)},
            {"stage": "Negotiation", "count": random.randint(10, 30)},
            {"stage": "Closed Won", "count": random.randint(15, 50)},
            {"stage": "Closed Lost", "count": random.randint(10, 40)},
        ]
    }


def generate_hubspot_data(
    start_date: date,
    end_date: date
) -> dict:
    """Generate sample HubSpot marketing data"""
    num_days = (end_date - start_date).days

    return {
        "emails_sent": random.randint(5000, 20000) * (num_days // 7 + 1),
        "emails_opened": random.randint(1500, 6000) * (num_days // 7 + 1),
        "email_clicks": random.randint(300, 1200) * (num_days // 7 + 1),
        "form_submissions": random.randint(100, 400) * (num_days // 7 + 1),
        "new_contacts": random.randint(200, 600) * (num_days // 7 + 1),
        "landing_page_views": random.randint(10000, 40000) * (num_days // 7 + 1),
        "blog_views": random.randint(20000, 80000) * (num_days // 7 + 1),
        "lifecycle_stages": [
            {"stage": "Subscriber", "count": random.randint(5000, 15000)},
            {"stage": "Lead", "count": random.randint(2000, 8000)},
            {"stage": "Marketing Qualified Lead", "count": random.randint(500, 2000)},
            {"stage": "Sales Qualified Lead", "count": random.randint(200, 800)},
            {"stage": "Opportunity", "count": random.randint(50, 200)},
            {"stage": "Customer", "count": random.randint(100, 500)},
        ]
    }


def generate_llm_tracking_data() -> dict:
    """Generate sample LLM search tracking data"""
    keywords = [
        "freelance management system",
        "best FMS software 2025",
        "freelancer payment solution",
        "contingent workforce management",
        "how to manage freelancers",
        "worksuite vs deel",
        "contractor management platform",
        "global freelancer payments",
    ]

    results = []
    for keyword in keywords:
        brand_mentioned = random.random() > 0.35

        results.append({
            "query": keyword,
            "platform": random.choice(["Perplexity", "ChatGPT", "Claude"]),
            "brand_mentioned": brand_mentioned,
            "brand_position": random.randint(1, 5) if brand_mentioned else None,
            "competitors_mentioned": random.sample(
                ["Deel", "Remote.com", "Fiverr Enterprise", "Upwork Enterprise", "Papaya Global"],
                k=random.randint(1, 3)
            ),
            "sentiment": random.choice(["positive", "neutral", "neutral", "negative"]) if brand_mentioned else "neutral",
        })

    mentioned_count = len([r for r in results if r["brand_mentioned"]])
    positive_count = len([r for r in results if r.get("sentiment") == "positive"])

    return {
        "total_queries_tracked": len(results),
        "mention_rate": round(mentioned_count / len(results) * 100, 1),
        "positive_sentiment_rate": round(positive_count / mentioned_count * 100, 1) if mentioned_count > 0 else 0,
        "avg_position": round(sum(r["brand_position"] for r in results if r["brand_position"]) /
                             len([r for r in results if r["brand_position"]]), 1) if mentioned_count > 0 else None,
        "top_competitors": [
            {"name": "Deel", "mentions": random.randint(5, 12)},
            {"name": "Remote.com", "mentions": random.randint(3, 8)},
            {"name": "Papaya Global", "mentions": random.randint(2, 6)},
            {"name": "Upwork Enterprise", "mentions": random.randint(2, 5)},
        ],
        "results": results,
        "insights": [
            {
                "type": "opportunity",
                "message": "Consider creating content comparing Worksuite vs Deel - frequently mentioned together.",
            },
            {
                "type": "strength",
                "message": "Strong visibility for 'global freelancer payments' queries.",
            },
            {
                "type": "threat",
                "message": "Low visibility for 'best FMS software 2025' - SEO opportunity.",
            },
        ]
    }


def generate_all_demo_data(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> dict:
    """Generate all demo data for the dashboard"""
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=180)

    users_data, revenue_data = generate_daily_metrics(start_date, end_date)

    # Calculate totals
    total_users = int(sum(m.value for m in users_data))
    total_revenue = sum(m.value for m in revenue_data)

    google_campaigns = generate_google_ads_campaigns(start_date, end_date)
    linkedin_campaigns = generate_linkedin_ads_campaigns(start_date, end_date)

    return {
        "date_range": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
        },
        "summary": {
            "total_users": total_users,
            "total_revenue": round(total_revenue, 2),
            "total_ad_spend": round(
                sum(c.spend for c in google_campaigns) +
                sum(c.spend for c in linkedin_campaigns), 2
            ),
        },
        "daily_metrics": {
            "users": [{"date": m.date.isoformat(), "value": m.value} for m in users_data],
            "revenue": [{"date": m.date.isoformat(), "value": m.value} for m in revenue_data],
        },
        "traffic_sources": generate_traffic_sources(),
        "google_ads": {
            "campaigns": [
                {
                    "id": c.campaign_id,
                    "name": c.campaign_name,
                    "status": c.status,
                    "impressions": c.impressions,
                    "clicks": c.clicks,
                    "spend": c.spend,
                    "conversions": c.conversions,
                    "ctr": c.ctr,
                    "cost_per_conversion": c.cost_per_conversion,
                }
                for c in google_campaigns
            ],
            "summary": {
                "total_spend": round(sum(c.spend for c in google_campaigns), 2),
                "total_clicks": sum(c.clicks for c in google_campaigns),
                "total_conversions": sum(c.conversions for c in google_campaigns),
                "avg_ctr": round(sum(c.ctr for c in google_campaigns) / len(google_campaigns), 2),
            }
        },
        "linkedin_ads": {
            "campaigns": [
                {
                    "id": c.campaign_id,
                    "name": c.campaign_name,
                    "status": c.status,
                    "impressions": c.impressions,
                    "clicks": c.clicks,
                    "spend": c.spend,
                    "conversions": c.conversions,
                    "ctr": c.ctr,
                    "cost_per_conversion": c.cost_per_conversion,
                    "leads": c.additional_metrics.get("leads", 0) if c.additional_metrics else 0,
                }
                for c in linkedin_campaigns
            ],
            "summary": {
                "total_spend": round(sum(c.spend for c in linkedin_campaigns), 2),
                "total_clicks": sum(c.clicks for c in linkedin_campaigns),
                "total_conversions": sum(c.conversions for c in linkedin_campaigns),
                "total_leads": sum(c.additional_metrics.get("leads", 0) for c in linkedin_campaigns if c.additional_metrics),
            }
        },
        "attio_crm": generate_attio_crm_data(start_date, end_date),
        "hubspot": generate_hubspot_data(start_date, end_date),
        "llm_tracking": generate_llm_tracking_data(),
    }
