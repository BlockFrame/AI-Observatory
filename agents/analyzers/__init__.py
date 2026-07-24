"""
Analyzer Agents

Each analyzer is responsible for analyzing collected items from a specific category
and producing a CategoryReport.
"""

from .news_analyzer import NewsAnalyzer
from .research_analyzer import ResearchAnalyzer
from .social_analyzer import SocialAnalyzer
from .github_trending_analyzer import GitHubTrendingAnalyzer

__all__ = [
    'NewsAnalyzer',
    'ResearchAnalyzer',
    'SocialAnalyzer',
    'GitHubTrendingAnalyzer',
]
