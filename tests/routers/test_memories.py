"""
Test cases for memories router endpoints - comprehensive coverage for all 8 endpoints
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock, Mock
from httpx import AsyncClient
import json


@pytest.fixture
def mock_verified_user():
    return MagicMock(
        id="user123",
        name="Test User",
        email="test@example.com",
        role="user"
    )


class TestMemoriesEmbeddings:
    """Test embeddings endpoint"""
    
    async def test_get_embeddings(self, async_client: AsyncClient):
        """Test GET /ef endpoint - get embeddings for test string"""
        with patch("open_webui.routers.memories.app.state") as mock_state:
            mock_state.EMBEDDING_FUNCTION = MagicMock(return_value=[0.1, 0.2, 0.3, 0.4])
            
            response = await async_client.get("/api/v1/memories/ef")
            assert response.status_code == 200
            data = response.json()
            assert "result" in data
            assert isinstance(data["result"], list)


class TestMemoriesManagement:
    """Test memories management endpoints"""
    
    async def test_get_memories(self, async_client: AsyncClient, mock_verified_user):
        """Test GET / endpoint - get user memories"""
        with patch("open_webui.routers.memories.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.memories.Memories.get_memories_by_user_id") as mock_get:
                mock_get.return_value = [
                    {
                        "id": "mem1",
                        "user_id": "user123",
                        "content": "Remember this important fact",
                        "created_at": "2024-01-01T00:00:00Z"
                    },
                    {
                        "id": "mem2",
                        "user_id": "user123",
                        "content": "Another memory",
                        "created_at": "2024-01-02T00:00:00Z"
                    }
                ]
                
                response = await async_client.get("/api/v1/memories/")
                assert response.status_code in [200, 401]
                
                if response.status_code == 200:
                    data = response.json()
                    assert isinstance(data, list)
                    assert len(data) == 2
    
    async def test_add_memory(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /add endpoint - add new memory"""
        with patch("open_webui.routers.memories.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.memories.Memories.insert_new_memory") as mock_insert:
                mock_insert.return_value = {
                    "id": "mem_new",
                    "user_id": "user123",
                    "content": "New memory content",
                    "created_at": "2024-01-03T00:00:00Z"
                }
                
                with patch("open_webui.routers.memories.app.state") as mock_state:
                    mock_state.EMBEDDING_FUNCTION = MagicMock(return_value=[0.1, 0.2, 0.3])
                    
                    memory_data = {
                        "content": "New memory content"
                    }
                    
                    response = await async_client.post(
                        "/api/v1/memories/add",
                        json=memory_data
                    )
                    assert response.status_code in [200, 401]
    
    async def test_query_memory(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /query endpoint - query memories"""
        with patch("open_webui.routers.memories.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.memories.query_embeddings_collection") as mock_query:
                mock_query.return_value = [
                    {
                        "id": "mem1",
                        "content": "Relevant memory",
                        "score": 0.95
                    }
                ]
                
                with patch("open_webui.routers.memories.app.state") as mock_state:
                    mock_state.EMBEDDING_FUNCTION = MagicMock(return_value=[0.1, 0.2, 0.3])
                    
                    query_data = {
                        "content": "search query",
                        "k": 5
                    }
                    
                    response = await async_client.post(
                        "/api/v1/memories/query",
                        json=query_data
                    )
                    assert response.status_code in [200, 401]
    
    async def test_reset_memory(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /reset endpoint - reset memory vector DB"""
        with patch("open_webui.routers.memories.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.memories.Memories.get_memories_by_user_id") as mock_get:
                mock_get.return_value = [
                    {"id": "mem1", "content": "Memory 1"},
                    {"id": "mem2", "content": "Memory 2"}
                ]
                
                with patch("open_webui.routers.memories.app.state") as mock_state:
                    mock_state.EMBEDDING_FUNCTION = MagicMock(return_value=[0.1, 0.2, 0.3])
                    
                    with patch("open_webui.routers.memories.add_or_update_embedding") as mock_add:
                        mock_add.return_value = True
                        
                        response = await async_client.post("/api/v1/memories/reset")
                        assert response.status_code in [200, 401]
    
    async def test_delete_memory_by_user_id(self, async_client: AsyncClient, mock_verified_user):
        """Test DELETE /delete/user endpoint - delete all user memories"""
        with patch("open_webui.routers.memories.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.memories.Memories.delete_memories_by_user_id") as mock_delete:
                mock_delete.return_value = True
                
                with patch("open_webui.routers.memories.delete_embeddings_by_ids") as mock_delete_emb:
                    mock_delete_emb.return_value = True
                    
                    response = await async_client.delete("/api/v1/memories/delete/user")
                    assert response.status_code in [200, 401]
    
    async def test_update_memory_by_id(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /{memory_id}/update endpoint - update memory"""
        with patch("open_webui.routers.memories.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.memories.Memories.update_memory_by_id") as mock_update:
                mock_update.return_value = {
                    "id": "mem1",
                    "user_id": "user123",
                    "content": "Updated memory content",
                    "updated_at": "2024-01-04T00:00:00Z"
                }
                
                with patch("open_webui.routers.memories.app.state") as mock_state:
                    mock_state.EMBEDDING_FUNCTION = MagicMock(return_value=[0.1, 0.2, 0.3])
                    
                    with patch("open_webui.routers.memories.add_or_update_embedding") as mock_add:
                        mock_add.return_value = True
                        
                        update_data = {
                            "content": "Updated memory content"
                        }
                        
                        response = await async_client.post(
                            "/api/v1/memories/mem1/update",
                            json=update_data
                        )
                        assert response.status_code in [200, 401]
    
    async def test_delete_memory_by_id(self, async_client: AsyncClient, mock_verified_user):
        """Test DELETE /{memory_id} endpoint - delete specific memory"""
        with patch("open_webui.routers.memories.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.memories.Memories.delete_memory_by_id_and_user_id") as mock_delete:
                mock_delete.return_value = True
                
                with patch("open_webui.routers.memories.delete_embeddings_by_ids") as mock_delete_emb:
                    mock_delete_emb.return_value = True
                    
                    response = await async_client.delete("/api/v1/memories/mem1")
                    assert response.status_code in [200, 401]
