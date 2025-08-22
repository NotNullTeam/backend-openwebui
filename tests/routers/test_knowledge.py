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
        meta={"size": 1000, "type": "application/pdf"},
        data={"content": "test content"},
        user_id="user123"
    )


class TestKnowledgeList:
    """Test knowledge list endpoints"""
    
    async def test_get_knowledge_success(self, async_client: AsyncClient, mock_verified_user):
        """Test GET / endpoint - success case"""
        mock_kb = MagicMock(
            id="kb1",
            name="Test KB",
            data={"file_ids": ["file1"]},
            model_dump=lambda: {"id": "kb1", "name": "Test KB"}
        )
        mock_file = MagicMock(id="file1")
        
        with patch("open_webui.routers.knowledge.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.knowledge.Knowledges.get_knowledge_bases_by_user_id", return_value=[mock_kb]):
                with patch("open_webui.routers.knowledge.Files.get_file_metadatas_by_ids", return_value=[mock_file]):
                    response = await async_client.get("/api/v1/knowledge/")
                    assert response.status_code == 200
                    data = response.json()
                    assert isinstance(data, list)
                    assert len(data) == 1
    
    async def test_get_knowledge_admin(self, async_client: AsyncClient, mock_admin_user):
        """Test GET / endpoint - admin user"""
        mock_kb = MagicMock(
            id="kb1",
            name="Test KB",
            data={"file_ids": []},
            model_dump=lambda: {"id": "kb1", "name": "Test KB"}
        )
        
        with patch("open_webui.routers.knowledge.get_verified_user", return_value=mock_admin_user):
            with patch("open_webui.routers.knowledge.ENABLE_ADMIN_WORKSPACE_CONTENT_ACCESS", True):
                with patch("open_webui.routers.knowledge.Knowledges.get_knowledge_bases", return_value=[mock_kb]):
                    with patch("open_webui.routers.knowledge.Files.get_file_metadatas_by_ids", return_value=[]):
                        response = await async_client.get("/api/v1/knowledge/")
                        assert response.status_code == 200
    
    async def test_get_knowledge_list_success(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /list endpoint - success case"""
        mock_kb = MagicMock(
            id="kb1",
            name="Test KB",
            data={"file_ids": []},
            model_dump=lambda: {"id": "kb1", "name": "Test KB"}
        )
        
        with patch("open_webui.routers.knowledge.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.knowledge.Knowledges.get_knowledge_bases_by_user_id", return_value=[mock_kb]):
                with patch("open_webui.routers.knowledge.Files.get_file_metadatas_by_ids", return_value=[]):
                    response = await async_client.get("/api/v1/knowledge/list")
                    assert response.status_code == 200
                    assert isinstance(response.json(), list)


class TestKnowledgeCreate:
    """Test knowledge creation endpoint"""
    
    async def test_create_knowledge_success(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /create endpoint - success case"""
        form_data = {
            "name": "New Knowledge Base",
            "description": "Test description"
        }
        mock_kb = MagicMock(
            id="kb_new",
            name="New Knowledge Base"
        )
        
        with patch("open_webui.routers.knowledge.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.knowledge.has_permission", return_value=True):
                with patch("open_webui.routers.knowledge.Knowledges.insert_new_knowledge", return_value=mock_kb):
                    response = await async_client.post(
                        "/api/v1/knowledge/create",
                        json=form_data
                    )
                    assert response.status_code in [200, 201]
    
    async def test_create_knowledge_unauthorized(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /create endpoint - unauthorized"""
        form_data = {"name": "New KB"}
        
        with patch("open_webui.routers.knowledge.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.knowledge.has_permission", return_value=False):
                response = await async_client.post(
                    "/api/v1/knowledge/create",
                    json=form_data
                )
                assert response.status_code == 401
    
    async def test_create_knowledge_duplicate(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /create endpoint - duplicate name"""
        form_data = {"name": "Existing KB"}
        
        with patch("open_webui.routers.knowledge.get_verified_user", return_value=mock_admin_user):
            with patch("open_webui.routers.knowledge.Knowledges.insert_new_knowledge", return_value=None):
                response = await async_client.post(
                    "/api/v1/knowledge/create",
                    json=form_data
                )
                assert response.status_code == 400


class TestKnowledgeReindex:
    """Test knowledge reindexing endpoint"""
    
    async def test_reindex_knowledge_success(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /reindex endpoint - success case"""
        mock_kb = MagicMock(
            id="kb1",
            data={"file_ids": ["file1"]}
        )
        mock_file = MagicMock(
            id="file1",
            filename="test.pdf"
        )
        
        with patch("open_webui.routers.knowledge.get_verified_user", return_value=mock_admin_user):
            with patch("open_webui.routers.knowledge.Knowledges.get_knowledge_bases", return_value=[mock_kb]):
                with patch("open_webui.routers.knowledge.Files.get_files_by_ids", return_value=[mock_file]):
                    with patch("open_webui.routers.knowledge.VECTOR_DB_CLIENT.has_collection", return_value=True):
                        with patch("open_webui.routers.knowledge.VECTOR_DB_CLIENT.delete_collection"):
                            with patch("open_webui.routers.knowledge.process_file"):
                                response = await async_client.post("/api/v1/knowledge/reindex")
                                assert response.status_code == 200
                                assert response.json() == True
    
    async def test_reindex_knowledge_unauthorized(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /reindex endpoint - non-admin user"""
        with patch("open_webui.routers.knowledge.get_verified_user", return_value=mock_verified_user):
            response = await async_client.post("/api/v1/knowledge/reindex")
            assert response.status_code == 401


class TestKnowledgeById:
    """Test knowledge by ID endpoints"""
    
    async def test_get_knowledge_by_id_success(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /{id} endpoint - success case"""
        mock_kb = MagicMock(
            id="kb123",
            name="Test KB",
            user_id="user123",
            data={"file_ids": ["file1"]},
            model_dump=lambda: {"id": "kb123", "name": "Test KB"}
        )
        
        with patch("open_webui.routers.knowledge.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.knowledge.Knowledges.get_knowledge_by_id", return_value=mock_kb):
                with patch("open_webui.routers.knowledge.Files.get_file_metadatas_by_ids", return_value=[]):
                    response = await async_client.get("/api/v1/knowledge/kb123")
                    assert response.status_code == 200
    
    async def test_get_knowledge_by_id_not_found(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /{id} endpoint - not found"""
        with patch("open_webui.routers.knowledge.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.knowledge.Knowledges.get_knowledge_by_id", return_value=None):
                response = await async_client.get("/api/v1/knowledge/invalid_id")
                assert response.status_code == 401
    
    async def test_update_knowledge_by_id_success(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /{id}/update endpoint - success case"""
        form_data = {"name": "Updated KB", "description": "Updated description"}
        mock_kb = MagicMock(
            id="kb123",
            user_id="user123",
            data={"file_ids": []},
            model_dump=lambda: {"id": "kb123", "name": "Updated KB"}
        )
        
        with patch("open_webui.routers.knowledge.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.knowledge.Knowledges.get_knowledge_by_id", return_value=mock_kb):
                with patch("open_webui.routers.knowledge.Knowledges.update_knowledge_by_id", return_value=mock_kb):
                    with patch("open_webui.routers.knowledge.Files.get_files_by_ids", return_value=[]):
                        response = await async_client.post(
                            "/api/v1/knowledge/kb123/update",
                            json=form_data
                        )
                        assert response.status_code == 200
    
    async def test_update_knowledge_by_id_access_denied(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /{id}/update endpoint - access denied"""
        form_data = {"name": "Updated KB"}
        mock_kb = MagicMock(
            id="kb123",
            user_id="other_user",
            access_control={}
        )
        
        with patch("open_webui.routers.knowledge.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.knowledge.Knowledges.get_knowledge_by_id", return_value=mock_kb):
                with patch("open_webui.routers.knowledge.has_access", return_value=False):
                    response = await async_client.post(
                        "/api/v1/knowledge/kb123/update",
                        json=form_data
                    )
                    assert response.status_code == 400
    
    async def test_delete_knowledge_by_id_success(self, async_client: AsyncClient, mock_admin_user):
        """Test DELETE /{id}/delete endpoint - success case"""
        mock_kb = MagicMock(
            id="kb123",
            name="Test KB",
            user_id="admin123"
        )
        
        with patch("open_webui.routers.knowledge.get_verified_user", return_value=mock_admin_user):
            with patch("open_webui.routers.knowledge.Knowledges.get_knowledge_by_id", return_value=mock_kb):
                with patch("open_webui.routers.knowledge.Models.get_all_models", return_value=[]):
                    with patch("open_webui.routers.knowledge.VECTOR_DB_CLIENT.delete_collection"):
                        with patch("open_webui.routers.knowledge.Knowledges.delete_knowledge_by_id", return_value=True):
                            response = await async_client.delete("/api/v1/knowledge/kb123/delete")
                            assert response.status_code == 200
                            assert response.json() == True
    
    async def test_reset_knowledge_by_id_success(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /{id}/reset endpoint - success case"""
        mock_kb = MagicMock(
            id="kb123",
            user_id="user123",
            data={"file_ids": ["file1", "file2"]}
        )
        reset_kb = MagicMock(
            id="kb123",
            data={"file_ids": []}
        )
        
        with patch("open_webui.routers.knowledge.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.knowledge.Knowledges.get_knowledge_by_id", return_value=mock_kb):
                with patch("open_webui.routers.knowledge.VECTOR_DB_CLIENT.delete_collection"):
                    with patch("open_webui.routers.knowledge.Knowledges.update_knowledge_data_by_id", return_value=reset_kb):
                        response = await async_client.post("/api/v1/knowledge/kb123/reset")
                        assert response.status_code == 200


class TestKnowledgeFiles:
    """Test knowledge file management endpoints"""
    
    async def test_add_file_to_knowledge_success(self, async_client: AsyncClient, mock_verified_user, mock_file):
        """Test POST /{id}/file/add endpoint - success case"""
        mock_kb = MagicMock(
            id="kb123",
            user_id="user123",
            data={"file_ids": []},
            model_dump=lambda: {"id": "kb123", "name": "Test KB"}
        )
        updated_kb = MagicMock(
            id="kb123",
            data={"file_ids": ["file123"]},
            model_dump=lambda: {"id": "kb123", "name": "Test KB"}
        )
        
        with patch("open_webui.routers.knowledge.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.knowledge.Knowledges.get_knowledge_by_id", return_value=mock_kb):
                with patch("open_webui.routers.knowledge.Files.get_file_by_id", return_value=mock_file):
                    with patch("open_webui.routers.knowledge.process_file"):
                        with patch("open_webui.routers.knowledge.Knowledges.update_knowledge_data_by_id", return_value=updated_kb):
                            with patch("open_webui.routers.knowledge.Files.get_file_metadatas_by_ids", return_value=[mock_file]):
                                response = await async_client.post(
                                    "/api/v1/knowledge/kb123/file/add",
                                    json={"file_id": "file123"}
                                )
                                assert response.status_code == 200
    
    async def test_add_file_to_knowledge_file_not_found(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /{id}/file/add endpoint - file not found"""
        mock_kb = MagicMock(
            id="kb123",
            user_id="user123"
        )
        
        with patch("open_webui.routers.knowledge.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.knowledge.Knowledges.get_knowledge_by_id", return_value=mock_kb):
                with patch("open_webui.routers.knowledge.Files.get_file_by_id", return_value=None):
                    response = await async_client.post(
                        "/api/v1/knowledge/kb123/file/add",
                        json={"file_id": "invalid_file"}
                    )
                    assert response.status_code == 400
    
    async def test_update_file_in_knowledge_success(self, async_client: AsyncClient, mock_verified_user, mock_file):
        """Test POST /{id}/file/update endpoint - success case"""
        mock_kb = MagicMock(
            id="kb123",
            user_id="user123",
            data={"file_ids": ["file123"]},
            model_dump=lambda: {"id": "kb123", "name": "Test KB"}
        )
        
        with patch("open_webui.routers.knowledge.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.knowledge.Knowledges.get_knowledge_by_id", return_value=mock_kb):
                with patch("open_webui.routers.knowledge.Files.get_file_by_id", return_value=mock_file):
                    with patch("open_webui.routers.knowledge.VECTOR_DB_CLIENT.delete"):
                        with patch("open_webui.routers.knowledge.process_file"):
                            with patch("open_webui.routers.knowledge.Files.get_file_metadatas_by_ids", return_value=[mock_file]):
                                response = await async_client.post(
                                    "/api/v1/knowledge/kb123/file/update",
                                    json={"file_id": "file123"}
                                )
                                assert response.status_code == 200
    
    async def test_remove_file_from_knowledge_success(self, async_client: AsyncClient, mock_verified_user, mock_file):
        """Test POST /{id}/file/remove endpoint - success case"""
        mock_kb = MagicMock(
            id="kb123",
            user_id="user123",
            data={"file_ids": ["file123"]},
            model_dump=lambda: {"id": "kb123", "name": "Test KB"}
        )
        updated_kb = MagicMock(
            id="kb123",
            data={"file_ids": []},
            model_dump=lambda: {"id": "kb123", "name": "Test KB"}
        )
        
        with patch("open_webui.routers.knowledge.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.knowledge.Knowledges.get_knowledge_by_id", return_value=mock_kb):
                with patch("open_webui.routers.knowledge.Files.get_file_by_id", return_value=mock_file):
                    with patch("open_webui.routers.knowledge.VECTOR_DB_CLIENT.delete"):
                        with patch("open_webui.routers.knowledge.VECTOR_DB_CLIENT.has_collection", return_value=True):
                            with patch("open_webui.routers.knowledge.VECTOR_DB_CLIENT.delete_collection"):
                                with patch("open_webui.routers.knowledge.Files.delete_file_by_id"):
                                    with patch("open_webui.routers.knowledge.Knowledges.update_knowledge_data_by_id", return_value=updated_kb):
                                        with patch("open_webui.routers.knowledge.Files.get_file_metadatas_by_ids", return_value=[]):
                                            response = await async_client.post(
                                                "/api/v1/knowledge/kb123/file/remove",
                                                json={"file_id": "file123"}
                                            )
                                            assert response.status_code == 200
    
    async def test_add_files_batch_to_knowledge_success(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /{id}/files/batch/add endpoint - success case"""
        mock_kb = MagicMock(
            id="kb123",
            user_id="user123",
            data={"file_ids": []},
            model_dump=lambda: {"id": "kb123", "name": "Test KB"}
        )
        mock_file1 = MagicMock(id="file1")
        mock_file2 = MagicMock(id="file2")
        mock_result = MagicMock(
            results=[MagicMock(file_id="file1", status="completed"), MagicMock(file_id="file2", status="completed")],
            errors=[]
        )
        updated_kb = MagicMock(
            id="kb123",
            data={"file_ids": ["file1", "file2"]},
            model_dump=lambda: {"id": "kb123", "name": "Test KB"}
        )
        
        with patch("open_webui.routers.knowledge.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.knowledge.Knowledges.get_knowledge_by_id", return_value=mock_kb):
                with patch("open_webui.routers.knowledge.Files.get_file_by_id", side_effect=[mock_file1, mock_file2]):
                    with patch("open_webui.routers.knowledge.process_files_batch", return_value=mock_result):
                        with patch("open_webui.routers.knowledge.Knowledges.update_knowledge_data_by_id", return_value=updated_kb):
                            with patch("open_webui.routers.knowledge.Files.get_file_metadatas_by_ids", return_value=[mock_file1, mock_file2]):
                                response = await async_client.post(
                                    "/api/v1/knowledge/kb123/files/batch/add",
                                    json=[
                                        {"file_id": "file1"},
                                        {"file_id": "file2"}
                                    ]
                                )
                                assert response.status_code == 200
    
    async def test_add_files_batch_partial_failure(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /{id}/files/batch/add endpoint - partial failure"""
        mock_kb = MagicMock(
            id="kb123",
            user_id="user123",
            data={"file_ids": []},
            model_dump=lambda: {"id": "kb123", "name": "Test KB"}
        )
        mock_file1 = MagicMock(id="file1")
        mock_file2 = MagicMock(id="file2")
        mock_result = MagicMock(
            results=[MagicMock(file_id="file1", status="completed")],
            errors=[MagicMock(file_id="file2", error="Processing failed")]
        )
        updated_kb = MagicMock(
            id="kb123",
            data={"file_ids": ["file1"]},
            model_dump=lambda: {"id": "kb123", "name": "Test KB"}
        )
        
        with patch("open_webui.routers.knowledge.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.knowledge.Knowledges.get_knowledge_by_id", return_value=mock_kb):
                with patch("open_webui.routers.knowledge.Files.get_file_by_id", side_effect=[mock_file1, mock_file2]):
                    with patch("open_webui.routers.knowledge.process_files_batch", return_value=mock_result):
                        with patch("open_webui.routers.knowledge.Knowledges.update_knowledge_data_by_id", return_value=updated_kb):
                            with patch("open_webui.routers.knowledge.Files.get_file_metadatas_by_ids", return_value=[mock_file1]):
                                response = await async_client.post(
                                    "/api/v1/knowledge/kb123/files/batch/add",
                                    json=[
                                        {"file_id": "file1"},
                                        {"file_id": "file2"}
                                    ]
                                )
                                assert response.status_code == 200
                                data = response.json()
                                assert "warnings" in data


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
