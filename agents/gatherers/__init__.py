"""
Gatherer Agents

Each gatherer is responsible for collecting items from a specific source category.
"""

from .news_gatherer import NewsGatherer
from .research_gatherer import ResearchGatherer
from .social_gatherer import SocialGatherer
from .link_follower import LinkFollower
from .hackernews import HackerNewsGatherer
from .github_trending import GitHubTrendingGatherer

__all__ = [
    'NewsGatherer',
    'ResearchGatherer',
    'SocialGatherer',
    'LinkFollower',
    'HackerNewsGatherer',
    'GitHubTrendingGatherer',
]
