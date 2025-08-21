"""
系统监控模块完整测试套件
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime, timedelta
import psutil

from open_webui.main import app


client = TestClient(app)


class TestSystemEndpoints:
    """系统监控所有端点的完整测试"""
    
    # ===== GET /system/health 健康检查 =====
    @patch('open_webui.routers.system_migrated.get_database_status')
    @patch('open_webui.routers.system_migrated.get_weaviate_status')
    @patch('open_webui.routers.system_migrated.get_llm_status')
    def test_health_check_all_healthy(self, mock_llm, mock_weaviate, mock_db):
        """测试所有服务健康"""
        mock_db.return_value = {"status": "healthy", "latency": 5}
        mock_weaviate.return_value = {"status": "healthy", "latency": 10}
        mock_llm.return_value = {"status": "healthy", "models": ["gpt-4", "gpt-3.5"]}
        
        response = client.get("/api/v1/system/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"]["status"] == "healthy"
        assert data["weaviate"]["status"] == "healthy"
        assert data["llm"]["status"] == "healthy"
    
    @patch('open_webui.routers.system_migrated.get_database_status')
    @patch('open_webui.routers.system_migrated.get_weaviate_status')
    def test_health_check_partial_failure(self, mock_weaviate, mock_db):
        """测试部分服务不健康"""
        mock_db.return_value = {"status": "healthy", "latency": 5}
        mock_weaviate.return_value = {"status": "unhealthy", "error": "Connection failed"}
        
        response = client.get("/api/v1/system/health")
        
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["weaviate"]["status"] == "unhealthy"
    
    # ===== GET /system/health/detailed 详细健康检查 =====
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    @patch('open_webui.routers.system_migrated.get_database_connection_pool')
    def test_detailed_health_check(self, mock_pool, mock_disk, mock_memory, mock_cpu):
        """测试详细健康检查"""
        mock_cpu.return_value = 45.5
        mock_memory.return_value = MagicMock(percent=60.2, total=16000000000, available=6400000000)
        mock_disk.return_value = MagicMock(percent=70.0, total=500000000000, free=150000000000)
        mock_pool.return_value = {
            "size": 10,
            "checked_in": 8,
            "checked_out": 2,
            "overflow": 0
        }
        
        response = client.get("/api/v1/system/health/detailed")
        
        assert response.status_code == 200
        data = response.json()
        assert data["cpu"]["percent"] == 45.5
        assert data["memory"]["percent"] == 60.2
        assert data["disk"]["percent"] == 70.0
        assert data["database"]["connection_pool"]["size"] == 10
    
    # ===== GET /system/metrics 系统指标 =====
    @patch('open_webui.routers.system_migrated.get_verified_user')
    @patch('open_webui.routers.system_migrated.get_admin_user')
    @patch('open_webui.routers.system_migrated.get_system_metrics')
    def test_get_metrics_admin(self, mock_metrics, mock_admin, mock_user):
        """测试管理员获取系统指标"""
        mock_user.return_value = MagicMock(role="admin")
        mock_admin.return_value = MagicMock(role="admin")
        mock_metrics.return_value = {
            "total_users": 100,
            "active_users": 25,
            "total_cases": 500,
            "total_documents": 1000,
            "storage_used": 5000000000,
            "api_calls_today": 10000,
            "avg_response_time": 250
        }
        
        response = client.get(
            "/api/v1/system/metrics",
            headers={"Authorization": "Bearer admin-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_users"] == 100
        assert data["active_users"] == 25
        assert data["api_calls_today"] == 10000
    
    @patch('open_webui.routers.system_migrated.get_verified_user')
    @patch('open_webui.routers.system_migrated.get_admin_user')
    def test_get_metrics_non_admin(self, mock_admin, mock_user):
        """测试非管理员无法获取系统指标"""
        mock_user.return_value = MagicMock(role="user")
        mock_admin.return_value = None
        
        response = client.get(
            "/api/v1/system/metrics",
            headers={"Authorization": "Bearer user-token"}
        )
        
        assert response.status_code == 403
    
    # ===== GET /system/logs 系统日志 =====
    @patch('open_webui.routers.system_migrated.get_admin_user')
    @patch('open_webui.routers.system_migrated.get_system_logs')
    def test_get_system_logs_admin(self, mock_logs, mock_admin):
        """测试管理员获取系统日志"""
        mock_admin.return_value = MagicMock(role="admin")
        mock_logs.return_value = [
            {
                "timestamp": datetime.utcnow().isoformat(),
                "level": "ERROR",
                "message": "Database connection failed",
                "module": "database"
            },
            {
                "timestamp": datetime.utcnow().isoformat(),
                "level": "INFO",
                "message": "User login successful",
                "module": "auth"
            }
        ]
        
        response = client.get(
            "/api/v1/system/logs?level=ERROR&limit=100",
            headers={"Authorization": "Bearer admin-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        assert data[0]["level"] == "ERROR"
    
    # ===== GET /system/activity 系统活动 =====
    @patch('open_webui.routers.system_migrated.get_verified_user')
    @patch('open_webui.routers.system_migrated.get_system_activity')
    def test_get_system_activity(self, mock_activity, mock_user):
        """测试获取系统活动"""
        mock_user.return_value = MagicMock(id="user-123", role="admin")
        mock_activity.return_value = {
            "online_users": ["user-1", "user-2", "user-3"],
            "recent_activities": [
                {
                    "user_id": "user-1",
                    "action": "create_case",
                    "timestamp": datetime.utcnow().isoformat()
                },
                {
                    "user_id": "user-2",
                    "action": "upload_document",
                    "timestamp": datetime.utcnow().isoformat()
                }
            ],
            "active_sessions": 15
        }
        
        response = client.get(
            "/api/v1/system/activity",
            headers={"Authorization": "Bearer admin-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["online_users"]) == 3
        assert data["active_sessions"] == 15
    
    # ===== POST /system/maintenance 维护模式 =====
    @patch('open_webui.routers.system_migrated.get_admin_user')
    @patch('open_webui.routers.system_migrated.set_maintenance_mode')
    def test_set_maintenance_mode(self, mock_set_mode, mock_admin):
        """测试设置维护模式"""
        mock_admin.return_value = MagicMock(role="admin")
        mock_set_mode.return_value = True
        
        response = client.post(
            "/api/v1/system/maintenance",
            json={
                "enabled": True,
                "message": "系统维护中，预计2小时完成",
                "estimated_end": (datetime.utcnow() + timedelta(hours=2)).isoformat()
            },
            headers={"Authorization": "Bearer admin-token"}
        )
        
        assert response.status_code == 200
        assert response.json()["status"] == "maintenance_mode_enabled"
    
    # ===== POST /system/backup 系统备份 =====
    @patch('open_webui.routers.system_migrated.get_admin_user')
    @patch('open_webui.routers.system_migrated.create_backup')
    def test_create_system_backup(self, mock_backup, mock_admin):
        """测试创建系统备份"""
        mock_admin.return_value = MagicMock(role="admin")
        mock_backup.return_value = {
            "backup_id": "backup-20250121-123456",
            "size": 1000000000,
            "path": "/backups/backup-20250121-123456.tar.gz",
            "created_at": datetime.utcnow().isoformat()
        }
        
        response = client.post(
            "/api/v1/system/backup",
            json={"include_uploads": True, "compress": True},
            headers={"Authorization": "Bearer admin-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "backup_id" in data
        assert data["size"] > 0
    
    # ===== POST /system/cache/clear 清除缓存 =====
    @patch('open_webui.routers.system_migrated.get_admin_user')
    @patch('open_webui.routers.system_migrated.clear_cache')
    def test_clear_system_cache(self, mock_clear, mock_admin):
        """测试清除系统缓存"""
        mock_admin.return_value = MagicMock(role="admin")
        mock_clear.return_value = {
            "cleared": True,
            "freed_space": 500000000,
            "cache_types": ["redis", "file_cache", "query_cache"]
        }
        
        response = client.post(
            "/api/v1/system/cache/clear",
            json={"cache_types": ["all"]},
            headers={"Authorization": "Bearer admin-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["cleared"] is True
        assert data["freed_space"] > 0
    
    # ===== 边界条件和异常测试 =====
    @patch('psutil.cpu_percent')
    def test_health_check_high_cpu(self, mock_cpu):
        """测试CPU使用率过高"""
        mock_cpu.return_value = 95.0
        
        response = client.get("/api/v1/system/health/detailed")
        
        assert response.status_code == 200
        data = response.json()
        assert data["cpu"]["percent"] == 95.0
        assert "warning" in data["cpu"].get("status", "").lower()
    
    @patch('psutil.virtual_memory')
    def test_health_check_low_memory(self, mock_memory):
        """测试内存不足"""
        mock_memory.return_value = MagicMock(
            percent=95.0,
            available=500000000  # 只有500MB可用
        )
        
        response = client.get("/api/v1/system/health/detailed")
        
        assert response.status_code == 200
        data = response.json()
        assert data["memory"]["percent"] == 95.0
    
    @patch('open_webui.routers.system_migrated.get_database_status')
    def test_health_check_database_timeout(self, mock_db):
        """测试数据库超时"""
        mock_db.side_effect = TimeoutError("Database connection timeout")
        
        response = client.get("/api/v1/system/health")
        
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
    
    @patch('open_webui.routers.system_migrated.get_admin_user')
    @patch('open_webui.routers.system_migrated.get_system_logs')
    def test_logs_with_invalid_filter(self, mock_logs, mock_admin):
        """测试无效的日志过滤参数"""
        mock_admin.return_value = MagicMock(role="admin")
        mock_logs.return_value = []
        
        response = client.get(
            "/api/v1/system/logs?level=INVALID_LEVEL",
            headers={"Authorization": "Bearer admin-token"}
        )
        
        assert response.status_code in [200, 400]
    
    @patch('open_webui.routers.system_migrated.get_admin_user')
    def test_backup_insufficient_space(self, mock_admin):
        """测试备份时空间不足"""
        mock_admin.return_value = MagicMock(role="admin")
        
        with patch('open_webui.routers.system_migrated.create_backup') as mock_backup:
            mock_backup.side_effect = IOError("Insufficient disk space")
            
            response = client.post(
                "/api/v1/system/backup",
                json={"include_uploads": True},
                headers={"Authorization": "Bearer admin-token"}
            )
            
            assert response.status_code == 507  # Insufficient Storage
