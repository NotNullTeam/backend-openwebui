"""
Test cases for monitoring router endpoints
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient
from httpx import AsyncClient
import json
from datetime import datetime
import os


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


class TestMonitoringHealth:
    """Test health and status endpoints"""
    
    async def test_get_system_health(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /health endpoint"""
        with patch("open_webui.routers.monitoring.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.monitoring.check_system_health", return_value={
                "status": "healthy",
                "services": {
                    "database": {"status": "healthy"},
                    "vector_db": {"status": "healthy"}
                }
            }):
                response = await async_client.get("/api/v1/monitoring/health")
                assert response.status_code in [200, 401]
    
    async def test_get_system_status(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /status endpoint"""
        with patch("open_webui.routers.monitoring.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.monitoring.psutil.cpu_percent", return_value=25.0):
                with patch("open_webui.routers.monitoring.psutil.virtual_memory", return_value=MagicMock(percent=50.0)):
                    with patch("open_webui.routers.monitoring.psutil.disk_usage", return_value=MagicMock(percent=60.0)):
                        response = await async_client.get("/api/v1/monitoring/status")
                        assert response.status_code in [200, 401]


class TestMonitoringMetrics:
    """Test metrics and performance endpoints"""
    
    async def test_get_performance_metrics(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /metrics endpoint"""
        with patch("open_webui.routers.monitoring.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.monitoring.get_performance_data", return_value={
                "cpu": [],
                "memory": [],
                "disk": [],
                "network": []
            }):
                response = await async_client.get("/api/v1/monitoring/metrics?hours=24")
                assert response.status_code in [200, 401]
    
    async def test_run_diagnostics(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /diagnostics endpoint"""
        with patch("open_webui.routers.monitoring.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.monitoring.psutil.cpu_percent", return_value=25.0):
                with patch("open_webui.routers.monitoring.psutil.virtual_memory", return_value=MagicMock(percent=50.0)):
                    with patch("open_webui.routers.monitoring.psutil.disk_usage", return_value=MagicMock(percent=60.0)):
                        with patch("open_webui.routers.monitoring.check_database_connection", return_value=True):
                            with patch("open_webui.routers.monitoring.check_vector_db_connection", return_value=True):
                                response = await async_client.get("/api/v1/monitoring/diagnostics")
                                assert response.status_code in [200, 401]


class TestMonitoringAlerts:
    """Test alert management endpoints"""
    
    async def test_get_alerts(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /alerts endpoint"""
        with patch("open_webui.routers.monitoring.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.monitoring.get_system_alerts", return_value=[]):
                response = await async_client.get("/api/v1/monitoring/alerts")
                assert response.status_code in [200, 401]
    
    async def test_resolve_alert(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /alerts/{alert_id}/resolve endpoint"""
        with patch("open_webui.routers.monitoring.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.monitoring.resolve_alert_by_id", return_value=True):
                response = await async_client.post("/api/v1/monitoring/alerts/alert123/resolve")
                assert response.status_code in [200, 404, 401]


class TestMonitoringMaintenance:
    """Test maintenance and cleanup endpoints"""
    
    async def test_cleanup_system(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /maintenance/cleanup endpoint"""
        with patch("open_webui.routers.monitoring.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.monitoring.cleanup_old_logs", return_value=100):
                with patch("open_webui.routers.monitoring.cleanup_temp_files", return_value=50):
                    with patch("open_webui.routers.monitoring.cleanup_expired_sessions", return_value=10):
                        response = await async_client.post("/api/v1/monitoring/maintenance/cleanup")
                        assert response.status_code in [200, 401]


class TestMonitoringLogs:
    """Test logging endpoints"""
    
    async def test_get_system_logs(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /logs endpoint"""
        with patch("open_webui.routers.monitoring.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.monitoring.os.path.exists", return_value=True):
                with patch("builtins.open", create=True) as mock_open:
                    mock_file = MagicMock()
                    mock_file.readlines.return_value = [
                        "2024-01-01 00:00:00 INFO Test log entry\n"
                    ]
                    mock_open.return_value.__enter__.return_value = mock_file
                    response = await async_client.get("/api/v1/monitoring/logs?level=INFO&limit=100")
                    assert response.status_code in [200, 401]


class TestMonitoringBackup:
    """Test backup management endpoints"""
    
    async def test_create_backup(self, async_client: AsyncClient, mock_admin_user):
        """Test POST /backup endpoint"""
        with patch("open_webui.routers.monitoring.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.monitoring.os.makedirs"):
                with patch("open_webui.routers.monitoring.create_database_backup", return_value="backup_20240101.sql"):
                    with patch("open_webui.routers.monitoring.backup_vector_db", return_value=True):
                        with patch("open_webui.routers.monitoring.backup_config_files", return_value=True):
                            response = await async_client.post("/api/v1/monitoring/backup")
                            assert response.status_code in [200, 401]
    
    async def test_list_backups(self, async_client: AsyncClient, mock_admin_user):
        """Test GET /backup endpoint"""
        with patch("open_webui.routers.monitoring.get_admin_user", return_value=mock_admin_user):
            with patch("open_webui.routers.monitoring.os.path.exists", return_value=True):
                with patch("open_webui.routers.monitoring.os.listdir", return_value=["backup_20240101.sql"]):
                    with patch("open_webui.routers.monitoring.os.path.getsize", return_value=1024000):
                        with patch("open_webui.routers.monitoring.os.path.getmtime", return_value=1704067200):
                            response = await async_client.get("/api/v1/monitoring/backup")
                            assert response.status_code in [200, 401]
