"""Tests for the discover module"""
import pytest
from scraper.discover import GitHubDiscovery


def test_generate_patch_url():
    """Test .patch URL generation."""
    discovery = GitHubDiscovery()
    
    url = discovery.generate_patch_url(
        "owner",
        "repo",
        "abc123def456"
    )
    
    assert url == "https://github.com/owner/repo/commit/abc123def456.patch"


def test_github_discovery_init():
    """Test GitHubDiscovery initialization."""
    # Without token
    discovery = GitHubDiscovery()
    assert discovery.token is None
    assert discovery.headers == {}
    
    # With token
    discovery_with_token = GitHubDiscovery(token="ghp_test123")
    assert discovery_with_token.token == "ghp_test123"
    assert "Authorization" in discovery_with_token.headers
    assert discovery_with_token.headers["Authorization"] == "token ghp_test123"


def test_languages_and_topics_defined():
    """Test that language and topic lists are defined."""
    assert len(GitHubDiscovery.LANGUAGES) > 0
    assert len(GitHubDiscovery.TOPICS) > 0
    
    # Check some common ones
    assert "python" in GitHubDiscovery.LANGUAGES
    assert "javascript" in GitHubDiscovery.LANGUAGES
    assert "web" in GitHubDiscovery.TOPICS


# Note: Integration tests that call GitHub API are skipped
# Run them manually with: pytest -k "integration" -v
@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_repos_integration():
    """Integration test for searching repos (requires internet)."""
    discovery = GitHubDiscovery()
    repos = await discovery.search_repos(language="python", min_stars=100, max_results=5)
    
    # Should get some results
    assert len(repos) > 0
    assert "owner" in repos[0]
    assert "name" in repos[0]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_discover_random_patches_integration():
    """Integration test for discovering patches (requires internet)."""
    discovery = GitHubDiscovery()
    
    patches = []
    async for patch_url in discovery.discover_random_patches(count=2, language="python"):
        patches.append(patch_url)
    
    assert len(patches) <= 2
    for patch in patches:
        assert patch.startswith("https://github.com/")
        assert patch.endswith(".patch")
