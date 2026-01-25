"""
LLM Search Results Tracker
==========================

Tracks brand visibility and mentions in AI-generated search results.
Supports Perplexity AI and can be extended for other AI search platforms.
"""

import asyncio
from datetime import datetime, date
from dataclasses import dataclass, field
from typing import Optional
import aiohttp
import json
import structlog

from ..config import LLMTrackingConfig

logger = structlog.get_logger(__name__)


@dataclass
class LLMSearchResult:
    """Result from an LLM search query"""
    query: str
    platform: str
    response_text: str
    brand_mentioned: bool
    brand_position: Optional[int]  # Position in list if mentioned (1 = first)
    competitors_mentioned: list[str]
    sentiment: str  # positive, neutral, negative
    citations: list[str]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    raw_response: dict = field(default_factory=dict)


class LLMSearchTracker:
    """
    Track brand visibility across AI search platforms.

    Monitors how your brand appears when users search for relevant
    keywords using AI-powered search tools like Perplexity.
    """

    def __init__(self, config: LLMTrackingConfig):
        self.config = config
        self.logger = logger.bind(component="LLMSearchTracker")
        self.brand_name = "Worksuite"
        self.brand_variations = [
            "worksuite",
            "work suite",
            "worksuite.com",
        ]

    async def track_query_perplexity(self, query: str) -> Optional[LLMSearchResult]:
        """
        Track a search query using Perplexity AI.

        Perplexity provides real-time web search with citations,
        making it ideal for tracking brand mentions.
        """
        if not self.config.perplexity_api_key:
            self.logger.warning("Perplexity API key not configured")
            return None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.perplexity.ai/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.config.perplexity_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "llama-3.1-sonar-small-128k-online",
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a helpful assistant that provides detailed, factual answers about software and business tools. Include specific product recommendations when relevant."
                            },
                            {
                                "role": "user",
                                "content": query
                            }
                        ],
                        "return_citations": True,
                    }
                ) as response:
                    if response.status != 200:
                        error = await response.text()
                        self.logger.error("Perplexity API error", status=response.status, error=error)
                        return None

                    data = await response.json()

                    response_text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    citations = data.get("citations", [])

                    result = self._analyze_response(
                        query=query,
                        platform="Perplexity",
                        response_text=response_text,
                        citations=citations,
                        raw_response=data,
                    )

                    return result

        except Exception as e:
            self.logger.error("Failed to track Perplexity query", error=str(e))
            return None

    async def track_query_openai(self, query: str) -> Optional[LLMSearchResult]:
        """
        Track a search query using OpenAI (simulated - no web search).

        Note: Standard OpenAI API doesn't have web search.
        This tracks how the model responds based on training data.
        """
        if not self.config.openai_api_key:
            self.logger.warning("OpenAI API key not configured")
            return None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.config.openai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a helpful assistant that provides detailed answers about software and business tools. When discussing options, list specific products and their key features."
                            },
                            {
                                "role": "user",
                                "content": query
                            }
                        ],
                        "max_tokens": 1000,
                    }
                ) as response:
                    if response.status != 200:
                        return None

                    data = await response.json()
                    response_text = data.get("choices", [{}])[0].get("message", {}).get("content", "")

                    result = self._analyze_response(
                        query=query,
                        platform="OpenAI",
                        response_text=response_text,
                        citations=[],
                        raw_response=data,
                    )

                    return result

        except Exception as e:
            self.logger.error("Failed to track OpenAI query", error=str(e))
            return None

    async def track_query_anthropic(self, query: str) -> Optional[LLMSearchResult]:
        """
        Track a search query using Anthropic Claude.

        Note: Standard Anthropic API doesn't have web search.
        This tracks how Claude responds based on training data.
        """
        if not self.config.anthropic_api_key:
            self.logger.warning("Anthropic API key not configured")
            return None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.config.anthropic_api_key,
                        "Content-Type": "application/json",
                        "anthropic-version": "2023-06-01",
                    },
                    json={
                        "model": "claude-3-haiku-20240307",
                        "max_tokens": 1000,
                        "messages": [
                            {
                                "role": "user",
                                "content": query
                            }
                        ],
                    }
                ) as response:
                    if response.status != 200:
                        return None

                    data = await response.json()
                    response_text = data.get("content", [{}])[0].get("text", "")

                    result = self._analyze_response(
                        query=query,
                        platform="Anthropic",
                        response_text=response_text,
                        citations=[],
                        raw_response=data,
                    )

                    return result

        except Exception as e:
            self.logger.error("Failed to track Anthropic query", error=str(e))
            return None

    def _analyze_response(
        self,
        query: str,
        platform: str,
        response_text: str,
        citations: list,
        raw_response: dict,
    ) -> LLMSearchResult:
        """Analyze an LLM response for brand mentions and sentiment"""
        response_lower = response_text.lower()

        # Check for brand mention
        brand_mentioned = any(
            variation in response_lower
            for variation in self.brand_variations
        )

        # Find position if mentioned
        brand_position = None
        if brand_mentioned:
            brand_position = self._find_brand_position(response_text)

        # Check for competitor mentions
        competitors_mentioned = [
            comp for comp in self.config.competitors
            if comp.lower() in response_lower
        ]

        # Basic sentiment analysis
        sentiment = self._analyze_sentiment(response_text, brand_mentioned)

        return LLMSearchResult(
            query=query,
            platform=platform,
            response_text=response_text,
            brand_mentioned=brand_mentioned,
            brand_position=brand_position,
            competitors_mentioned=competitors_mentioned,
            sentiment=sentiment,
            citations=citations,
            raw_response=raw_response,
        )

    def _find_brand_position(self, response_text: str) -> Optional[int]:
        """Find the position of brand in a numbered or bulleted list"""
        lines = response_text.split("\n")
        position = 0

        for line in lines:
            line_stripped = line.strip()
            # Check if line starts with number or bullet
            if (line_stripped and
                (line_stripped[0].isdigit() or
                 line_stripped.startswith(("-", "*", "•")))):
                position += 1
                if any(v in line_stripped.lower() for v in self.brand_variations):
                    return position

        # Not in a list, but mentioned
        return None

    def _analyze_sentiment(self, response_text: str, brand_mentioned: bool) -> str:
        """Basic sentiment analysis for brand mentions"""
        if not brand_mentioned:
            return "neutral"

        response_lower = response_text.lower()

        positive_indicators = [
            "leading", "top", "best", "excellent", "recommended",
            "popular", "trusted", "reliable", "comprehensive",
            "innovative", "powerful", "efficient", "scalable",
        ]

        negative_indicators = [
            "expensive", "complex", "difficult", "limited",
            "lacks", "missing", "outdated", "slow", "issues",
        ]

        positive_count = sum(1 for word in positive_indicators if word in response_lower)
        negative_count = sum(1 for word in negative_indicators if word in response_lower)

        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        return "neutral"

    async def run_tracking_batch(
        self,
        queries: Optional[list[str]] = None,
        platforms: Optional[list[str]] = None
    ) -> list[LLMSearchResult]:
        """
        Run tracking for multiple queries across platforms.

        Args:
            queries: List of queries to track (defaults to config keywords)
            platforms: List of platforms to query (defaults to all configured)

        Returns:
            List of LLMSearchResult objects
        """
        if queries is None:
            queries = self.config.tracked_keywords

        if platforms is None:
            platforms = []
            if self.config.perplexity_api_key:
                platforms.append("perplexity")
            if self.config.openai_api_key:
                platforms.append("openai")
            if self.config.anthropic_api_key:
                platforms.append("anthropic")

        results = []

        for query in queries:
            for platform in platforms:
                self.logger.info("Tracking query", query=query, platform=platform)

                if platform == "perplexity":
                    result = await self.track_query_perplexity(query)
                elif platform == "openai":
                    result = await self.track_query_openai(query)
                elif platform == "anthropic":
                    result = await self.track_query_anthropic(query)
                else:
                    continue

                if result:
                    results.append(result)

                # Rate limiting
                await asyncio.sleep(1)

        return results

    def get_visibility_summary(self, results: list[LLMSearchResult]) -> dict:
        """
        Generate a visibility summary from tracking results.

        Returns metrics like:
        - Mention rate (% of queries where brand was mentioned)
        - Average position when mentioned
        - Competitor mention frequency
        - Sentiment breakdown
        """
        if not results:
            return {
                "total_queries": 0,
                "mention_rate": 0,
                "avg_position": None,
                "sentiment_breakdown": {},
                "top_competitors": [],
                "platforms": {},
            }

        total = len(results)
        mentioned = [r for r in results if r.brand_mentioned]
        mention_count = len(mentioned)

        # Average position
        positions = [r.brand_position for r in mentioned if r.brand_position]
        avg_position = sum(positions) / len(positions) if positions else None

        # Sentiment breakdown
        sentiment_breakdown = {
            "positive": len([r for r in mentioned if r.sentiment == "positive"]),
            "neutral": len([r for r in mentioned if r.sentiment == "neutral"]),
            "negative": len([r for r in mentioned if r.sentiment == "negative"]),
        }

        # Competitor frequency
        competitor_counts = {}
        for result in results:
            for comp in result.competitors_mentioned:
                competitor_counts[comp] = competitor_counts.get(comp, 0) + 1

        top_competitors = sorted(
            competitor_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]

        # Platform breakdown
        platforms = {}
        for result in results:
            if result.platform not in platforms:
                platforms[result.platform] = {"total": 0, "mentioned": 0}
            platforms[result.platform]["total"] += 1
            if result.brand_mentioned:
                platforms[result.platform]["mentioned"] += 1

        return {
            "total_queries": total,
            "mention_count": mention_count,
            "mention_rate": (mention_count / total * 100) if total > 0 else 0,
            "avg_position": avg_position,
            "sentiment_breakdown": sentiment_breakdown,
            "top_competitors": top_competitors,
            "platforms": platforms,
        }
