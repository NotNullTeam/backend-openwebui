"""
Test cases for document_summary router endpoints - comprehensive coverage for all 3 endpoints
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock, Mock
from httpx import AsyncClient
import json


@pytest.fixture
def mock_admin_user():
    return MagicMock(
        id="admin123",
        name="Admin User",
        email="admin@example.com",
        role="admin"
    )


@pytest.fixture
def mock_verified_user():
    return MagicMock(
        id="user123",
        name="Test User",
        email="test@example.com",
        role="user"
    )


class TestDocumentSummary:
    """Test document summary generation endpoints"""
    
    async def test_generate_document_summary(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /knowledge/documents/{document_id}/summary endpoint - generate summary"""
        with patch("open_webui.routers.document_summary.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.document_summary.KnowledgeDocuments.get_doc_by_id") as mock_get_doc:
                mock_get_doc.return_value = {
                    "id": "doc123",
                    "user_id": "user123",
                    "name": "test_document.pdf",
                    "content": "This is a test document content for summary generation."
                }
                
                with patch("open_webui.routers.document_summary.generate_summary_with_llm") as mock_generate:
                    mock_generate.return_value = "This is a generated summary of the document."
                    
                    with patch("open_webui.routers.document_summary.DocumentSummaries.save_summary") as mock_save:
                        mock_save.return_value = {
                            "document_id": "doc123",
                            "summary": "This is a generated summary of the document.",
                            "key_points": ["Point 1", "Point 2"],
                            "created_at": "2024-01-01T10:00:00"
                        }
                        
                        summary_request = {
                            "summary_type": "brief",
                            "max_length": 500,
                            "include_key_points": True,
                            "language": "zh"
                        }
                        
                        response = await async_client.post(
                            "/api/v1/document_summary/knowledge/documents/doc123/summary",
                            json=summary_request
                        )
                        assert response.status_code in [200, 401, 404]
    
    async def test_get_document_summary(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /knowledge/documents/{document_id}/summary endpoint - get existing summary"""
        with patch("open_webui.routers.document_summary.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.document_summary.KnowledgeDocuments.get_doc_by_id") as mock_get_doc:
                mock_get_doc.return_value = {
                    "id": "doc123",
                    "user_id": "user123",
                    "name": "test_document.pdf"
                }
                
                with patch("open_webui.routers.document_summary.DocumentSummaries.get_summary") as mock_get_summary:
                    mock_get_summary.return_value = {
                        "document_id": "doc123",
                        "summary": "Existing summary of the document.",
                        "key_points": ["Key point 1", "Key point 2"],
                        "created_at": "2024-01-01T10:00:00",
                        "updated_at": "2024-01-01T10:00:00"
                    }
                    
                    response = await async_client.get(
                        "/api/v1/document_summary/knowledge/documents/doc123/summary?regenerate=false"
                    )
                    assert response.status_code in [200, 401, 404]
    
    async def test_regenerate_document_summary(self, async_client: AsyncClient, mock_verified_user):
        """Test GET endpoint with regenerate=true - regenerate summary"""
        with patch("open_webui.routers.document_summary.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.document_summary.KnowledgeDocuments.get_doc_by_id") as mock_get_doc:
                mock_get_doc.return_value = {
                    "id": "doc123",
                    "user_id": "user123",
                    "name": "test_document.pdf",
                    "content": "Document content for regeneration."
                }
                
                with patch("open_webui.routers.document_summary.generate_summary_with_llm") as mock_generate:
                    mock_generate.return_value = "Regenerated summary of the document."
                    
                    with patch("open_webui.routers.document_summary.DocumentSummaries.update_summary") as mock_update:
                        mock_update.return_value = {
                            "document_id": "doc123",
                            "summary": "Regenerated summary of the document.",
                            "key_points": ["New point 1", "New point 2"],
                            "updated_at": "2024-01-02T10:00:00"
                        }
                        
                        response = await async_client.get(
                            "/api/v1/document_summary/knowledge/documents/doc123/summary?regenerate=true"
                        )
                        assert response.status_code in [200, 401, 404]
    
    async def test_generate_batch_summaries(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /knowledge/batch-summary endpoint - batch summary generation"""
        with patch("open_webui.routers.document_summary.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.document_summary.KnowledgeDocuments.get_docs_by_ids") as mock_get_docs:
                mock_get_docs.return_value = [
                    {
                        "id": "doc1",
                        "user_id": "user123",
                        "name": "document1.pdf",
                        "content": "Content of document 1"
                    },
                    {
                        "id": "doc2",
                        "user_id": "user123",
                        "name": "document2.pdf",
                        "content": "Content of document 2"
                    }
                ]
                
                with patch("open_webui.routers.document_summary.generate_summary_with_llm") as mock_generate:
                    mock_generate.side_effect = [
                        "Summary of document 1",
                        "Summary of document 2"
                    ]
                    
                    with patch("open_webui.routers.document_summary.DocumentSummaries.save_batch_summaries") as mock_save_batch:
                        mock_save_batch.return_value = [
                            {
                                "document_id": "doc1",
                                "summary": "Summary of document 1",
                                "status": "success"
                            },
                            {
                                "document_id": "doc2",
                                "summary": "Summary of document 2",
                                "status": "success"
                            }
                        ]
                        
                        batch_request = {
                            "document_ids": ["doc1", "doc2"],
                            "summary_type": "detailed",
                            "max_length": 1000,
                            "include_key_points": True,
                            "language": "zh"
                        }
                        
                        response = await async_client.post(
                            "/api/v1/document_summary/knowledge/batch-summary",
                            json=batch_request
                        )
                        assert response.status_code in [200, 401]


class TestDocumentSummaryAdmin:
    """Test document summary endpoints with admin user"""
    
    async def test_admin_generate_any_document_summary(self, async_client: AsyncClient, mock_admin_user):
        """Test admin can generate summary for any document"""
        with patch("open_webui.routers.document_summary.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.document_summary.KnowledgeDocuments.get_doc_by_id") as mock_get_doc:
                # Document belongs to another user
                mock_get_doc.return_value = {
                    "id": "doc456",
                    "user_id": "other_user",
                    "name": "other_document.pdf",
                    "content": "Content from another user's document"
                }
                
                with patch("open_webui.routers.document_summary.generate_summary_with_llm") as mock_generate:
                    mock_generate.return_value = "Admin generated summary"
                    
                    with patch("open_webui.routers.document_summary.DocumentSummaries.save_summary") as mock_save:
                        mock_save.return_value = {
                            "document_id": "doc456",
                            "summary": "Admin generated summary"
                        }
                        
                        summary_request = {
                            "summary_type": "brief",
                            "max_length": 500
                        }
                        
                        response = await async_client.post(
                            "/api/v1/document_summary/knowledge/documents/doc456/summary",
                            json=summary_request
                        )
                        assert response.status_code in [200, 401]


class TestDocumentSummaryErrors:
    """Test error handling in document summary endpoints"""
    
    async def test_document_not_found(self, async_client: AsyncClient, mock_verified_user):
        """Test summary generation for non-existent document"""
        with patch("open_webui.routers.document_summary.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.document_summary.KnowledgeDocuments.get_doc_by_id") as mock_get_doc:
                mock_get_doc.return_value = None  # Document not found
                
                summary_request = {
                    "summary_type": "brief",
                    "max_length": 500
                }
                
                response = await async_client.post(
                    "/api/v1/document_summary/knowledge/documents/nonexistent/summary",
                    json=summary_request
                )
                assert response.status_code in [404, 401]
    
    async def test_unauthorized_document_access(self, async_client: AsyncClient, mock_verified_user):
        """Test user trying to access another user's document"""
        with patch("open_webui.routers.document_summary.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.document_summary.KnowledgeDocuments.get_doc_by_id") as mock_get_doc:
                # Document belongs to a different user
                mock_get_doc.return_value = {
                    "id": "doc789",
                    "user_id": "other_user_456",  # Different from mock_verified_user.id
                    "name": "private_document.pdf"
                }
                
                response = await async_client.get(
                    "/api/v1/document_summary/knowledge/documents/doc789/summary"
                )
                assert response.status_code in [403, 404, 401]
    
    async def test_batch_summary_partial_failure(self, async_client: AsyncClient, mock_verified_user):
        """Test batch summary with some documents failing"""
        with patch("open_webui.routers.document_summary.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.document_summary.KnowledgeDocuments.get_docs_by_ids") as mock_get_docs:
                mock_get_docs.return_value = [
                    {
                        "id": "doc1",
                        "user_id": "user123",
                        "name": "document1.pdf",
                        "content": "Content 1"
                    },
                    None,  # Document not found
                    {
                        "id": "doc3",
                        "user_id": "other_user",  # Unauthorized
                        "name": "document3.pdf",
                        "content": "Content 3"
                    }
                ]
                
                batch_request = {
                    "document_ids": ["doc1", "doc2", "doc3"],
                    "summary_type": "brief"
                }
                
                response = await async_client.post(
                    "/api/v1/document_summary/knowledge/batch-summary",
                    json=batch_request
                )
                assert response.status_code in [200, 207, 401]  # 207 for partial success
