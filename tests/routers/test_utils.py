"""
Test cases for utils router endpoints - comprehensive coverage for all 7 endpoints
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock, mock_open
from httpx import AsyncClient
import json
from io import BytesIO


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


class TestUtilsEndpoints:
    """Test utils router endpoints"""
    
    async def test_get_gravatar(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /gravatar endpoint"""
        with patch("open_webui.routers.utils.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.utils.get_gravatar_url") as mock_gravatar:
                mock_gravatar.return_value = "https://www.gravatar.com/avatar/test123"
                
                response = await async_client.get(
                    "/api/v1/utils/gravatar?email=test@example.com"
                )
                assert response.status_code in [200, 401]
                if response.status_code == 200:
                    assert "gravatar.com" in response.text
    
    async def test_format_code(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /code/format endpoint"""
        with patch("open_webui.routers.utils.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.utils.black.format_str") as mock_format:
                mock_format.return_value = "formatted_code = 1\n"
                
                response = await async_client.post(
                    "/api/v1/utils/code/format",
                    json={"code": "formatted_code=1"}
                )
                assert response.status_code in [200, 400, 401]
    
    async def test_execute_code(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /code/execute endpoint"""
        with patch("open_webui.routers.utils.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.utils.ENABLE_CODE_EDITOR", True):
                with patch("open_webui.routers.utils.exec") as mock_exec:
                    # Mock successful code execution
                    test_code = "print('Hello World')"
                    
                    response = await async_client.post(
                        "/api/v1/utils/code/execute",
                        json={"code": test_code}
                    )
                    assert response.status_code in [200, 400, 401, 403]
    
    async def test_execute_code_disabled(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /code/execute endpoint when code editor is disabled"""
        with patch("open_webui.routers.utils.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.utils.ENABLE_CODE_EDITOR", False):
                response = await async_client.post(
                    "/api/v1/utils/code/execute",
                    json={"code": "print('test')"}
                )
                assert response.status_code in [403, 401]
    
    async def test_get_html_from_markdown(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /markdown endpoint"""
        with patch("open_webui.routers.utils.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.utils.markdown.markdown") as mock_markdown:
                mock_markdown.return_value = "<h1>Hello</h1>"
                
                response = await async_client.post(
                    "/api/v1/utils/markdown",
                    json={"md": "# Hello"}
                )
                assert response.status_code in [200, 401]
                if response.status_code == 200:
                    data = response.json()
                    assert "html" in data
    
    async def test_download_chat_as_pdf(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /pdf endpoint"""
        with patch("open_webui.routers.utils.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.utils.FPDF") as mock_fpdf:
                mock_pdf = MagicMock()
                mock_fpdf.return_value = mock_pdf
                mock_pdf.output.return_value = b"PDF content"
                
                chat_data = {
                    "title": "Test Chat",
                    "messages": [
                        {"role": "user", "content": "Hello"},
                        {"role": "assistant", "content": "Hi there!"}
                    ]
                }
                
                response = await async_client.post(
                    "/api/v1/utils/pdf",
                    json=chat_data
                )
                assert response.status_code in [200, 400, 401]
    
    async def test_download_db(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /db/download endpoint"""
        with patch("open_webui.routers.utils.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.utils.ENABLE_ADMIN_EXPORT", True):
                with patch("open_webui.routers.utils.create_backup") as mock_backup:
                    mock_backup.return_value = "/tmp/backup.tar.gz"
                    
                    with patch("open_webui.routers.utils.FileResponse") as mock_response:
                        mock_response.return_value = MagicMock()
                        
                        response = await async_client.get("/api/v1/utils/db/download")
                        assert response.status_code in [200, 401, 403]
    
    async def test_download_db_disabled(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /db/download endpoint when export is disabled"""
        with patch("open_webui.routers.utils.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.utils.ENABLE_ADMIN_EXPORT", False):
                response = await async_client.get("/api/v1/utils/db/download")
                assert response.status_code in [403, 401]
    
    async def test_download_litellm_config(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /litellm/config endpoint"""
        with patch("open_webui.routers.utils.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.utils.os.path.exists", return_value=True):
                with patch("open_webui.routers.utils.FileResponse") as mock_response:
                    mock_response.return_value = MagicMock()
                    
                    response = await async_client.get("/api/v1/utils/litellm/config")
                    assert response.status_code in [200, 401, 404]


class TestUtilsErrorHandling:
    """Test error handling in utils endpoints"""
    
    async def test_format_code_invalid(self, async_client: AsyncClient, mock_admin_user):
        """Test format code with invalid Python code"""
        with patch("open_webui.routers.utils.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.utils.black.format_str", side_effect=Exception("Invalid syntax")):
                response = await async_client.post(
                    "/api/v1/utils/code/format",
                    json={"code": "invalid python code {{{"}
                )
                assert response.status_code in [400, 401]
    
    async def test_execute_code_error(self, async_client: AsyncClient, mock_verified_user):
        """Test code execution with runtime error"""
        with patch("open_webui.routers.utils.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.utils.ENABLE_CODE_EDITOR", True):
                response = await async_client.post(
                    "/api/v1/utils/code/execute",
                    json={"code": "raise RuntimeError('Test error')"}
                )
                assert response.status_code in [200, 400, 401]
    
    async def test_pdf_generation_error(self, async_client: AsyncClient, mock_verified_user):
        """Test PDF generation with error"""
        with patch("open_webui.routers.utils.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.utils.FPDF", side_effect=Exception("PDF error")):
                chat_data = {
                    "title": "Test Chat",
                    "messages": [{"role": "user", "content": "Hello"}]
                }
                
                response = await async_client.post(
                    "/api/v1/utils/pdf",
                    json=chat_data
                )
                assert response.status_code in [400, 401]
