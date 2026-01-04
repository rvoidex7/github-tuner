import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import numpy as np
from tuner.hunter import Hunter
from tuner.brain import LocalBrain
from tuner.storage import TunerStorage

# Mocks for external dependencies

@pytest.fixture
def mock_httpx_client():
    with patch("httpx.AsyncClient") as mock:
        yield mock

@pytest.fixture
def mock_sentence_transformer():
    with patch("sentence_transformers.SentenceTransformer") as mock:
        yield mock

@pytest.fixture
def mock_aiosqlite():
    with patch("aiosqlite.connect") as mock:
        mock_conn = AsyncMock()
        mock.return_value = mock_conn
        mock_conn.__aenter__.return_value = mock_conn
        yield mock

# Test Hunter

@pytest.mark.asyncio
async def test_hunter_fetch_user_stars(mock_httpx_client):
    hunter = Hunter()
    # Mocking environment variable
    with patch.dict("os.environ", {"GITHUB_TOKEN": "fake_token"}):
        # Mocking the response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {} # No rate limit headers
        mock_response.json.return_value = [
            {"full_name": "owner/repo1", "description": "desc1"},
            {"full_name": "owner/repo2", "description": "desc2"},
        ]
        hunter.client.get = AsyncMock(return_value=mock_response)

        descriptions = await hunter.fetch_user_starred_repos()

        assert len(descriptions) == 2
        assert descriptions[0] == "owner/repo1 desc1"
        assert descriptions[1] == "owner/repo2 desc2"

@pytest.mark.asyncio
async def test_hunter_star_repo(mock_httpx_client):
    hunter = Hunter()
    with patch.dict("os.environ", {"GITHUB_TOKEN": "fake_token"}):
        mock_response = MagicMock()
        mock_response.status_code = 204
        hunter.client.put = AsyncMock(return_value=mock_response)

        success = await hunter.star_repo("owner", "repo")
        assert success is True

        hunter.client.put.assert_called_with(
            "https://api.github.com/user/starred/owner/repo",
            headers={
                "Authorization": "token fake_token",
                "Accept": "application/vnd.github.v3+json",
                "Content-Length": "0"
            }
        )

# Test LocalBrain

def test_local_brain_clustering():
    brain = LocalBrain()
    # Mock vectorize to return predictable vectors
    # Create two groups of vectors
    v1 = np.array([1.0, 0.0])
    v2 = np.array([0.9, 0.1])
    v3 = np.array([0.0, 1.0])
    v4 = np.array([0.1, 0.9])

    brain.vectorize = MagicMock(side_effect=[v1, v2, v3, v4])

    descriptions = ["d1", "d2", "d3", "d4"]
    # With k=2, we expect roughly two centers around [1,0] and [0,1]
    clusters = brain.generate_interest_clusters(descriptions, k=2)

    assert len(clusters) == 2
    # Verify we got something vector-like
    assert clusters[0].shape == (2,)

def test_local_brain_clustering_fallback():
    # If sklearn fails or few items
    brain = LocalBrain()
    brain.vectorize = MagicMock(return_value=np.zeros(384))

    descriptions = ["d1"]
    clusters = brain.generate_interest_clusters(descriptions, k=5)

    # Should return all points if less than k
    assert len(clusters) == 1

# Test Storage (Async)

@pytest.mark.asyncio
async def test_storage_get_finding():
    # Use in-memory DB for testing with real aiosqlite if installed,
    # but since we might not want to depend on real DB in unit tests, we can use it if available or mock.
    # The current TunerStorage handles :memory: correctly.

    storage = TunerStorage(":memory:")
    await storage.initialize()

    try:
        f_id = await storage.save_finding("Test Title", "http://test.url", "Test Desc", 100, "Python")
        assert f_id != -1

        finding = await storage.get_finding(f_id)
        assert finding is not None
        assert finding["title"] == "Test Title"
        assert finding["url"] == "http://test.url"

        finding = await storage.get_finding(999)
        assert finding is None
    finally:
        await storage.close()
