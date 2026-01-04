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

# Test Hunter

@pytest.mark.asyncio
async def test_hunter_fetch_user_stars(mock_httpx_client):
    hunter = Hunter()
    # Mocking environment variable
    with patch.dict("os.environ", {"GITHUB_TOKEN": "fake_token"}):
        # Mocking the response
        mock_response = MagicMock()
        mock_response.status_code = 200
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

def test_local_brain_calculate_user_vector():
    brain = LocalBrain()
    # Mock vectorize to return predictable vectors
    brain.vectorize = MagicMock(side_effect=[
        np.array([1.0, 2.0]),
        np.array([3.0, 4.0])
    ])

    descriptions = ["d1", "d2"]
    user_vector = brain.calculate_user_vector(descriptions)

    # Mean of [1, 2] and [3, 4] is [2, 3]
    expected = np.array([2.0, 3.0])
    np.testing.assert_array_equal(user_vector, expected)

def test_local_brain_calculate_user_vector_empty():
    brain = LocalBrain()
    user_vector = brain.calculate_user_vector([])
    assert user_vector.shape == (384,)
    assert np.all(user_vector == 0)

# Test Storage

def test_storage_get_finding():
    # Use in-memory DB for testing
    storage = TunerStorage(":memory:")

    # Insert a finding manually
    f_id = storage.save_finding("Test Title", "http://test.url", "Test Desc", 100, "Python")
    assert f_id != -1

    finding = storage.get_finding(f_id)
    assert finding is not None
    assert finding["title"] == "Test Title"
    assert finding["url"] == "http://test.url"

    finding = storage.get_finding(999)
    assert finding is None
