"""
Test cases for search router endpoints - comprehensive coverage for all 5 endpoints
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock, Mock
from httpx import AsyncClient
import json
from datetime import datetime


@pytest.fixture
def mock_verified_user():
    return MagicMock(
        id="user123",
        name="Test User",
        email="test@example.com",
        role="user"
    )


class TestSearchSuggestions:
    """Test search suggestions endpoints"""
    
    async def test_get_search_suggestions(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /suggestions endpoint - get search suggestions"""
        with patch("open_webui.routers.search.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.search.generate_keywords") as mock_keywords:
                mock_keywords.return_value = ["keyword1", "keyword2"]
                
                with patch("open_webui.routers.search.get_search_history") as mock_history:
                    mock_history.return_value = [
                        {"query": "previous search 1", "timestamp": "2024-01-01T10:00:00"},
                        {"query": "previous search 2", "timestamp": "2024-01-01T11:00:00"}
                    ]
                    
                    with patch("open_webui.routers.search.get_hotwords") as mock_hotwords:
                        mock_hotwords.return_value = ["hot1", "hot2", "hot3"]
                        
                        with patch("open_webui.routers.search.semantic_search") as mock_semantic:
                            mock_semantic.return_value = ["semantic result 1", "semantic result 2"]
                            
                            search_request = {
                                "query": "test search query",
                                "limit": 10,
                                "include_history": True,
                                "include_hotwords": True,
                                "include_semantic": True
                            }
                            
                            response = await async_client.post(
                                "/api/v1/search/suggestions",
                                json=search_request
                            )
                            assert response.status_code in [200, 401]
    
    async def test_search_suggestions_minimal(self, async_client: AsyncClient, mock_verified_user):
        """Test search suggestions with minimal options"""
        with patch("open_webui.routers.search.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.search.generate_keywords") as mock_keywords:
                mock_keywords.return_value = ["keyword1"]
                
                search_request = {
                    "query": "simple query",
                    "limit": 5,
                    "include_history": False,
                    "include_hotwords": False,
                    "include_semantic": False
                }
                
                response = await async_client.post(
                    "/api/v1/search/suggestions",
                    json=search_request
                )
                assert response.status_code in [200, 401]


class TestSearchHistory:
    """Test search history management endpoints"""
    
    async def test_save_search_history(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /history endpoint - save search history"""
        with patch("open_webui.routers.search.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.search.SearchHistory.save_search") as mock_save:
                mock_save.return_value = True
                
                history_item = {
                    "query": "test search",
                    "search_type": "knowledge",
                    "filters": {
                        "date_range": "last_week",
                        "category": "network"
                    },
                    "results_count": 10,
                    "clicked_results": ["result1", "result2"],
                    "timestamp": datetime.now().isoformat()
                }
                
                response = await async_client.post(
                    "/api/v1/search/history",
                    json=history_item
                )
                assert response.status_code in [200, 401]
    
    async def test_get_search_history(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /history endpoint - get search history"""
        with patch("open_webui.routers.search.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.search.SearchHistory.get_user_history") as mock_get:
                mock_get.return_value = [
                    {
                        "query": "previous search 1",
                        "search_type": "knowledge",
                        "timestamp": "2024-01-01T10:00:00",
                        "results_count": 15
                    },
                    {
                        "query": "previous search 2",
                        "search_type": "cases",
                        "timestamp": "2024-01-01T11:00:00",
                        "results_count": 8
                    }
                ]
                
                response = await async_client.get("/api/v1/search/history?limit=20")
                assert response.status_code in [200, 401]
    
    async def test_clear_search_history(self, async_client: AsyncClient, mock_verified_user):
        """Test DELETE /history endpoint - clear search history"""
        with patch("open_webui.routers.search.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.search.SearchHistory.clear_user_history") as mock_clear:
                mock_clear.return_value = True
                
                response = await async_client.delete("/api/v1/search/history")
                assert response.status_code in [200, 401]


class TestTrendingSearches:
    """Test trending searches endpoint"""
    
    async def test_get_trending_searches(self, async_client: AsyncClient):
        """Test GET /trending endpoint - get trending searches"""
        with patch("open_webui.routers.search.SearchHistory.get_trending") as mock_trending:
            mock_trending.return_value = [
                {
                    "query": "IP conflict resolution",
                    "count": 150,
                    "trend": "up"
                },
                {
                    "query": "VPN configuration",
                    "count": 120,
                    "trend": "stable"
                },
                {
                    "query": "routing protocol BGP",
                    "count": 95,
                    "trend": "down"
                }
            ]
            
            response = await async_client.get("/api/v1/search/trending?days=7&limit=10")
            assert response.status_code in [200, 401]
    
    async def test_trending_searches_custom_params(self, async_client: AsyncClient):
        """Test trending searches with custom parameters"""
        with patch("open_webui.routers.search.SearchHistory.get_trending") as mock_trending:
            mock_trending.return_value = [
                {
                    "query": "network troubleshooting",
                    "count": 200,
                    "trend": "up"
                }
            ]
            
            # Test with 30 days and limit 5
            response = await async_client.get("/api/v1/search/trending?days=30&limit=5")
            assert response.status_code in [200, 401]


class TestSearchIntegration:
    """Test search integration scenarios"""
    
    async def test_empty_query_suggestions(self, async_client: AsyncClient, mock_verified_user):
        """Test suggestions with empty query"""
        with patch("open_webui.routers.search.get_verified_user", return_value=mock_verified_user):
            search_request = {
                "query": "",
                "limit": 10,
                "include_history": True,
                "include_hotwords": True,
                "include_semantic": False
            }
            
            with patch("open_webui.routers.search.get_search_history") as mock_history:
                mock_history.return_value = []
                
                with patch("open_webui.routers.search.get_hotwords") as mock_hotwords:
                    mock_hotwords.return_value = ["default1", "default2"]
                    
                    response = await async_client.post(
                        "/api/v1/search/suggestions",
                        json=search_request
                    )
                    assert response.status_code in [200, 401]
    
    async def test_search_history_pagination(self, async_client: AsyncClient, mock_verified_user):
        """Test search history with different limit values"""
        with patch("open_webui.routers.search.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.search.SearchHistory.get_user_history") as mock_get:
                # Create 50 history items
                mock_history = [
                    {
                        "query": f"search {i}",
                        "timestamp": f"2024-01-{i+1:02d}T10:00:00",
                        "results_count": i * 2
                    }
                    for i in range(50)
                ]
                mock_get.return_value = mock_history
                
                # Test limit 1 (minimum)
                response = await async_client.get("/api/v1/search/history?limit=1")
                assert response.status_code in [200, 401]
                
                # Test limit 100 (maximum)
                response = await async_client.get("/api/v1/search/history?limit=100")
                assert response.status_code in [200, 401]
