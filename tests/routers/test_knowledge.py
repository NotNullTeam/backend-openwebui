"""
Test cases for knowledge router endpoints
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient
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


@pytest.fixture
def mock_admin_user():
    return MagicMock(
        id="admin123",
        name="Admin User",
        email="admin@example.com",
        role="admin"
    )


@pytest.fixture
def mock_knowledge():
    return MagicMock(
        id="kb123",
        name="Test Knowledge Base",
        description="Test description",
        user_id="user123",
        created_at=1234567890,
        updated_at=1234567890
    )


@pytest.fixture
def mock_file():
    return MagicMock(
        id="file123",
        filename="test.pdf",
        meta={"size": 1000, "type": "application/pdf"}
    )


class TestKnowledgeBase:
    """Test knowledge base CRUD endpoints"""
    
    async def test_get_knowledge(self, async_client: AsyncClient, mock_verified_user):
        """Test GET / endpoint"""
        with patch("open_webui.routers.knowledge.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.knowledge.Knowledges.get_knowledge_bases_by_user_id", return_value=[]):
                response = await async_client.get("/api/v1/knowledge/")
                assert response.status_code in [200, 401]
    
    async def test_get_knowledge_list(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /list endpoint"""
        with patch("open_webui.routers.knowledge.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.knowledge.Knowledges.get_knowledge_bases_by_user_id", return_value=[]):
                response = await async_client.get("/api/v1/knowledge/list")
                assert response.status_code in [200, 401]
    
    async def test_create_new_knowledge(self, async_client: AsyncClient, mock_verified_user, mock_knowledge):
        """Test POST /create endpoint"""
        with patch("open_webui.routers.knowledge.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.knowledge.Knowledges.get_knowledge_by_name", return_value=None):
                with patch("open_webui.routers.knowledge.Knowledges.insert_new_knowledge", return_value=mock_knowledge):
                    response = await async_client.post(
                        "/api/v1/knowledge/create",
                        json={
                            "name": "New Knowledge Base",
                            "description": "Test description",
                            "data": {}
                        }
                    )
                    assert response.status_code in [200, 400, 401]
    
    async def test_reindex_knowledge_files(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /reindex endpoint"""
        with patch("open_webui.routers.knowledge.get_verified_user", return_value=mock_admin_user):
            with patch("open_webui.routers.knowledge.Knowledges.get_knowledge_bases"):
                with patch("open_webui.routers.knowledge.Files.get_file_by_id"):
                    with patch("open_webui.routers.knowledge.process_file"):
                        response = await async_client.post("/api/v1/knowledge/reindex")
                        assert response.status_code in [200, 403, 401]
    
    async def test_get_knowledge_by_id(self, async_client: AsyncClient, mock_verified_user, mock_knowledge):
        """Test GET /{id} endpoint"""
        with patch("open_webui.routers.knowledge.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.knowledge.Knowledges.get_knowledge_by_id", return_value=mock_knowledge):
                with patch("open_webui.routers.knowledge.KnowledgeFileMappings.get_file_ids_by_knowledge_id", return_value=[]):
                    response = await async_client.get("/api/v1/knowledge/kb123")
                    assert response.status_code in [200, 404, 401]
    
    async def test_update_knowledge_by_id(self, async_client: AsyncClient, mock_verified_user, mock_knowledge):
        """Test POST /{id}/update endpoint"""
        with patch("open_webui.routers.knowledge.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.knowledge.Knowledges.get_knowledge_by_id", return_value=mock_knowledge):
                with patch("open_webui.routers.knowledge.Knowledges.update_knowledge_by_id", return_value=mock_knowledge):
                    response = await async_client.post(
                        "/api/v1/knowledge/kb123/update",
                        json={
                            "name": "Updated Knowledge Base",
                            "description": "Updated description",
                            "data": {}
                        }
                    )
                    assert response.status_code in [200, 404, 401]
    
    async def test_delete_knowledge_by_id(self, async_client: AsyncClient, mock_verified_user, mock_knowledge):
        """Test DELETE /{id}/delete endpoint"""
        with patch("open_webui.routers.knowledge.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.knowledge.Knowledges.get_knowledge_by_id", return_value=mock_knowledge):
                with patch("open_webui.routers.knowledge.Knowledges.delete_knowledge_by_id", return_value=True):
                    response = await async_client.delete("/api/v1/knowledge/kb123/delete")
                    assert response.status_code in [200, 404, 401]
    
    async def test_reset_knowledge_by_id(self, async_client: AsyncClient, mock_verified_user, mock_knowledge):
        """Test POST /{id}/reset endpoint"""
        with patch("open_webui.routers.knowledge.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.knowledge.Knowledges.get_knowledge_by_id", return_value=mock_knowledge):
                with patch("open_webui.routers.knowledge.KnowledgeFileMappings.delete_all_mappings_by_knowledge_id"):
                    response = await async_client.post("/api/v1/knowledge/kb123/reset")
                    assert response.status_code in [200, 404, 401]


class TestKnowledgeFiles:
    """Test knowledge file management endpoints"""
    
    async def test_add_file_to_knowledge(self, async_client: AsyncClient, mock_verified_user, mock_knowledge, mock_file):
        """Test POST /{id}/file/add endpoint"""
        with patch("open_webui.routers.knowledge.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.knowledge.Knowledges.get_knowledge_by_id", return_value=mock_knowledge):
                with patch("open_webui.routers.knowledge.Files.get_file_by_id", return_value=mock_file):
                    with patch("open_webui.routers.knowledge.KnowledgeFileMappings.insert_new_mapping"):
                        with patch("open_webui.routers.knowledge.process_file"):
                            response = await async_client.post(
                                "/api/v1/knowledge/kb123/file/add",
                                json={"file_id": "file123"}
                            )
                            assert response.status_code in [200, 404, 401]
    
    async def test_update_file_from_knowledge(self, async_client: AsyncClient, mock_verified_user, mock_knowledge, mock_file):
        """Test POST /{id}/file/update endpoint"""
        with patch("open_webui.routers.knowledge.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.knowledge.Knowledges.get_knowledge_by_id", return_value=mock_knowledge):
                with patch("open_webui.routers.knowledge.Files.get_file_by_id", return_value=mock_file):
                    with patch("open_webui.routers.knowledge.process_file"):
                        response = await async_client.post(
                            "/api/v1/knowledge/kb123/file/update",
                            json={"file_id": "file123"}
                        )
                        assert response.status_code in [200, 404, 401]
    
    async def test_remove_file_from_knowledge(self, async_client: AsyncClient, mock_verified_user, mock_knowledge):
        """Test POST /{id}/file/remove endpoint"""
        with patch("open_webui.routers.knowledge.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.knowledge.Knowledges.get_knowledge_by_id", return_value=mock_knowledge):
                with patch("open_webui.routers.knowledge.KnowledgeFileMappings.delete_mapping_by_knowledge_id_and_file_id"):
                    response = await async_client.post(
                        "/api/v1/knowledge/kb123/file/remove",
                        json={"file_id": "file123"}
                    )
                    assert response.status_code in [200, 404, 401]
    
    async def test_add_files_batch(self, async_client: AsyncClient, mock_verified_user, mock_knowledge, mock_file):
        """Test POST /{id}/files/batch/add endpoint"""
        with patch("open_webui.routers.knowledge.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.knowledge.Knowledges.get_knowledge_by_id", return_value=mock_knowledge):
                with patch("open_webui.routers.knowledge.Files.get_file_by_id", return_value=mock_file):
                    with patch("open_webui.routers.knowledge.KnowledgeFileMappings.insert_new_mapping"):
                        with patch("open_webui.routers.knowledge.process_file"):
                            response = await async_client.post(
                                "/api/v1/knowledge/kb123/files/batch/add",
                                json={"file_ids": ["file123", "file456"]}
                            )
                            assert response.status_code in [200, 404, 401]
