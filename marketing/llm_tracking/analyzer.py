"""
LLM Response Analyzer
=====================

Advanced analysis of LLM search responses including:
- Deep sentiment analysis
- Feature extraction
- Competitive positioning analysis
- Trend detection over time
"""

import re
from datetime import datetime, date, timedelta
from dataclasses import dataclass
from typing import Optional
from collections import defaultdict
import structlog

from .tracker import LLMSearchResult

logger = structlog.get_logger(__name__)


@dataclass
class BrandInsight:
    """Insight extracted from LLM responses"""
    insight_type: str  # "strength", "weakness", "opportunity", "threat"
    description: str
    source_query: str
    source_platform: str
    confidence: float  # 0.0 to 1.0
    timestamp: datetime


@dataclass
class CompetitorComparison:
    """Comparison between brand and competitor"""
    competitor: str
    times_mentioned_together: int
    our_position_vs_theirs: list[int]  # Positive = we're ranked higher
    common_contexts: list[str]


class LLMResponseAnalyzer:
    """
    Analyze LLM search results for deeper brand insights.

    Provides:
    - Feature extraction (what features are mentioned)
    - Competitive analysis (how we compare to competitors)
    - Trend analysis (changes over time)
    - Actionable insights
    """

    def __init__(self, brand_name: str = "Worksuite"):
        self.brand_name = brand_name
        self.brand_variations = [brand_name.lower(), brand_name.lower().replace(" ", "")]
        self.logger = logger.bind(component="LLMResponseAnalyzer")

        # Feature categories to detect
        self.feature_keywords = {
            "payment": ["payment", "pay", "invoice", "billing", "payout"],
            "onboarding": ["onboard", "onboarding", "setup", "getting started"],
            "compliance": ["compliance", "compliant", "tax", "legal", "contract"],
            "global": ["global", "international", "worldwide", "countries"],
            "integration": ["integration", "integrate", "connect", "api"],
            "automation": ["automation", "automated", "automatic", "workflow"],
            "reporting": ["report", "analytics", "dashboard", "insights"],
            "collaboration": ["collaborate", "collaboration", "team", "communication"],
            "security": ["secure", "security", "privacy", "encrypted"],
            "scalability": ["scale", "scalable", "enterprise", "growth"],
        }

    def extract_features_mentioned(
        self,
        results: list[LLMSearchResult]
    ) -> dict[str, int]:
        """
        Extract which product features are mentioned in LLM responses.

        Returns a count of mentions for each feature category.
        """
        feature_counts = defaultdict(int)

        for result in results:
            if not result.brand_mentioned:
                continue

            response_lower = result.response_text.lower()

            for feature, keywords in self.feature_keywords.items():
                if any(kw in response_lower for kw in keywords):
                    feature_counts[feature] += 1

        return dict(feature_counts)

    def analyze_competitive_positioning(
        self,
        results: list[LLMSearchResult],
        competitors: list[str]
    ) -> list[CompetitorComparison]:
        """
        Analyze how the brand is positioned against competitors.

        Returns comparison data for each competitor found in results.
        """
        comparisons = {}

        for competitor in competitors:
            comparisons[competitor] = {
                "times_mentioned_together": 0,
                "our_position_vs_theirs": [],
                "common_contexts": [],
            }

        for result in results:
            response_lower = result.response_text.lower()

            for competitor in competitors:
                comp_lower = competitor.lower()

                if comp_lower not in response_lower:
                    continue

                # Check if both brands mentioned
                brand_mentioned = any(v in response_lower for v in self.brand_variations)

                if brand_mentioned:
                    comparisons[competitor]["times_mentioned_together"] += 1

                    # Try to determine relative position
                    brand_pos = self._find_position_in_text(response_lower, self.brand_variations)
                    comp_pos = self._find_position_in_text(response_lower, [comp_lower])

                    if brand_pos and comp_pos:
                        # Positive = we appear first
                        comparisons[competitor]["our_position_vs_theirs"].append(
                            comp_pos - brand_pos
                        )

                    # Extract context (sentence where both appear)
                    context = self._extract_shared_context(
                        result.response_text,
                        self.brand_variations,
                        [competitor]
                    )
                    if context:
                        comparisons[competitor]["common_contexts"].append(context[:200])

        return [
            CompetitorComparison(
                competitor=comp,
                times_mentioned_together=data["times_mentioned_together"],
                our_position_vs_theirs=data["our_position_vs_theirs"],
                common_contexts=data["common_contexts"][:3],  # Limit to 3 examples
            )
            for comp, data in comparisons.items()
            if data["times_mentioned_together"] > 0
        ]

    def _find_position_in_text(
        self,
        text: str,
        terms: list[str]
    ) -> Optional[int]:
        """Find the character position of first occurrence of any term"""
        positions = []
        for term in terms:
            pos = text.find(term)
            if pos >= 0:
                positions.append(pos)

        return min(positions) if positions else None

    def _extract_shared_context(
        self,
        text: str,
        brand_terms: list[str],
        competitor_terms: list[str]
    ) -> Optional[str]:
        """Extract the sentence where both brand and competitor are mentioned"""
        sentences = re.split(r'[.!?]', text)

        for sentence in sentences:
            sent_lower = sentence.lower()
            has_brand = any(term in sent_lower for term in brand_terms)
            has_competitor = any(term.lower() in sent_lower for term in competitor_terms)

            if has_brand and has_competitor:
                return sentence.strip()

        return None

    def generate_insights(
        self,
        results: list[LLMSearchResult]
    ) -> list[BrandInsight]:
        """
        Generate actionable insights from LLM search results.

        Identifies strengths, weaknesses, opportunities, and threats.
        """
        insights = []

        # Analyze mention patterns
        total = len(results)
        mentioned_results = [r for r in results if r.brand_mentioned]
        mention_rate = len(mentioned_results) / total if total > 0 else 0

        # Insight: Low visibility
        if mention_rate < 0.3:
            insights.append(BrandInsight(
                insight_type="threat",
                description=f"Brand visibility is low ({mention_rate:.0%} mention rate). Consider increasing content marketing and SEO efforts for targeted keywords.",
                source_query="aggregate",
                source_platform="all",
                confidence=0.9,
                timestamp=datetime.utcnow(),
            ))

        # Insight: High visibility
        elif mention_rate > 0.7:
            insights.append(BrandInsight(
                insight_type="strength",
                description=f"Strong brand visibility ({mention_rate:.0%} mention rate) in AI search results.",
                source_query="aggregate",
                source_platform="all",
                confidence=0.9,
                timestamp=datetime.utcnow(),
            ))

        # Analyze sentiment
        positive_count = len([r for r in mentioned_results if r.sentiment == "positive"])
        negative_count = len([r for r in mentioned_results if r.sentiment == "negative"])

        if negative_count > positive_count:
            insights.append(BrandInsight(
                insight_type="threat",
                description="More negative than positive sentiment detected in AI responses. Review negative contexts for improvement areas.",
                source_query="aggregate",
                source_platform="all",
                confidence=0.7,
                timestamp=datetime.utcnow(),
            ))

        # Analyze competitor presence
        all_competitors = []
        for r in results:
            all_competitors.extend(r.competitors_mentioned)

        if all_competitors:
            top_competitor = max(set(all_competitors), key=all_competitors.count)
            top_count = all_competitors.count(top_competitor)

            insights.append(BrandInsight(
                insight_type="opportunity",
                description=f"{top_competitor} is mentioned {top_count} times. Consider creating comparison content to differentiate.",
                source_query="aggregate",
                source_platform="all",
                confidence=0.8,
                timestamp=datetime.utcnow(),
            ))

        # Analyze features mentioned
        features = self.extract_features_mentioned(results)
        if features:
            top_feature = max(features, key=features.get)
            insights.append(BrandInsight(
                insight_type="strength",
                description=f"'{top_feature.title()}' is the most mentioned feature category. Highlight this in marketing.",
                source_query="aggregate",
                source_platform="all",
                confidence=0.75,
                timestamp=datetime.utcnow(),
            ))

            # Find potentially missing features
            for feature in self.feature_keywords:
                if feature not in features or features[feature] == 0:
                    insights.append(BrandInsight(
                        insight_type="opportunity",
                        description=f"'{feature.title()}' feature is not being highlighted in AI responses. Consider creating content around this.",
                        source_query="aggregate",
                        source_platform="all",
                        confidence=0.6,
                        timestamp=datetime.utcnow(),
                    ))

        return insights

    def analyze_trends(
        self,
        results: list[LLMSearchResult],
        previous_results: Optional[list[LLMSearchResult]] = None
    ) -> dict:
        """
        Analyze trends by comparing current results with previous results.

        Returns trend indicators for key metrics.
        """
        current_metrics = self._calculate_metrics(results)

        if not previous_results:
            return {
                "current": current_metrics,
                "previous": None,
                "trends": {},
            }

        previous_metrics = self._calculate_metrics(previous_results)

        trends = {}

        # Calculate changes
        for metric in ["mention_rate", "positive_rate", "avg_position"]:
            current_val = current_metrics.get(metric, 0)
            previous_val = previous_metrics.get(metric, 0)

            if previous_val > 0:
                change = ((current_val - previous_val) / previous_val) * 100
            else:
                change = 100 if current_val > 0 else 0

            trends[metric] = {
                "current": current_val,
                "previous": previous_val,
                "change_percent": change,
                "direction": "up" if change > 0 else "down" if change < 0 else "stable",
            }

        return {
            "current": current_metrics,
            "previous": previous_metrics,
            "trends": trends,
        }

    def _calculate_metrics(self, results: list[LLMSearchResult]) -> dict:
        """Calculate key metrics from results"""
        if not results:
            return {
                "mention_rate": 0,
                "positive_rate": 0,
                "avg_position": None,
                "total_queries": 0,
            }

        total = len(results)
        mentioned = [r for r in results if r.brand_mentioned]
        mention_count = len(mentioned)

        positive_count = len([r for r in mentioned if r.sentiment == "positive"])

        positions = [r.brand_position for r in mentioned if r.brand_position]
        avg_position = sum(positions) / len(positions) if positions else None

        return {
            "mention_rate": (mention_count / total) * 100,
            "positive_rate": (positive_count / mention_count * 100) if mention_count > 0 else 0,
            "avg_position": avg_position,
            "total_queries": total,
        }

    def get_query_recommendations(
        self,
        results: list[LLMSearchResult]
    ) -> list[str]:
        """
        Recommend new queries to track based on patterns in results.

        Identifies gaps in coverage and suggests relevant keywords.
        """
        recommendations = []

        # Analyze which query types perform well
        high_visibility_queries = [
            r.query for r in results
            if r.brand_mentioned and r.brand_position and r.brand_position <= 3
        ]

        low_visibility_queries = [
            r.query for r in results
            if not r.brand_mentioned
        ]

        # Extract common words from high-visibility queries
        high_vis_words = set()
        for query in high_visibility_queries:
            words = query.lower().split()
            high_vis_words.update(words)

        # Suggest variations of low-visibility queries with high-vis words
        common_modifiers = ["best", "top", "enterprise", "comparison", "vs", "review", "2024"]

        for query in low_visibility_queries[:5]:
            for modifier in common_modifiers:
                if modifier not in query.lower():
                    recommendations.append(f"{modifier} {query}")
                    break

        # Add competitor comparison queries
        for result in results:
            for comp in result.competitors_mentioned:
                comp_query = f"Worksuite vs {comp}"
                if comp_query not in recommendations:
                    recommendations.append(comp_query)

        return recommendations[:10]  # Limit recommendations
