"""
完整工作流集成测试

测试从用户登录到案例分析的完整流程
"""

import pytest
import asyncio
from httpx import AsyncClient
from unittest.mock import patch, MagicMock

class TestCompleteWorkflow:
    """完整工作流测试"""
    
    @pytest.mark.asyncio
    async def test_complete_case_analysis_workflow(self, async_client: AsyncClient):
        """测试完整的案例分析工作流"""
        
        # 1. 用户登录
        login_data = {
            "email": "test@example.com",
            "password": "testpass123"
        }
        
        with patch('open_webui.models.users.Users.get_user_by_email') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = "user123"
            mock_user.email = "test@example.com"
            mock_user.role = "user"
            mock_get_user.return_value = mock_user
            
            login_response = await async_client.post("/api/v1/auths/signin", json=login_data)
            assert login_response.status_code == 200
            token = login_response.json()["token"]
            headers = {"Authorization": f"Bearer {token}"}
        
        # 2. 上传知识文档
        with patch('open_webui.storage.provider.Storage.upload_file') as mock_upload:
            mock_upload.return_value = ("file content", "path/to/file")
            
            files = {"file": ("test.pdf", b"PDF content", "application/pdf")}
            upload_response = await async_client.post(
                "/api/v1/files/", 
                files=files,
                headers=headers
            )
            assert upload_response.status_code == 200
            file_id = upload_response.json()["id"]
        
        # 3. 文档安全扫描
        scan_response = await async_client.post(
            f"/api/v1/files/{file_id}/scan",
            headers=headers
        )
        assert scan_response.status_code == 200
        assert scan_response.json()["is_safe"] == True
        
        # 4. 创建案例
        case_data = {
            "title": "网络连接问题",
            "description": "用户无法访问内网服务器",
            "problem_type": "network",
            "vendor": "cisco"
        }
        
        with patch('open_webui.models.cases.Cases.insert_new_case') as mock_insert:
            mock_insert.return_value = MagicMock(id="case123")
            
            case_response = await async_client.post(
                "/api/v1/cases/",
                json=case_data,
                headers=headers
            )
            assert case_response.status_code == 200
            case_id = case_response.json()["id"]
        
        # 5. 智能分析
        analysis_data = {
            "log_content": "ERROR: Connection timeout to 192.168.1.100",
            "analysis_type": "network"
        }
        
        analysis_response = await async_client.post(
            "/api/v1/analysis/log-parsing",
            json=analysis_data,
            headers=headers
        )
        assert analysis_response.status_code == 200
        
        # 6. 节点重生
        regenerate_data = {
            "prompt": "请提供更详细的解决方案",
            "regeneration_strategy": "detailed"
        }
        
        with patch('open_webui.models.cases.CaseNode.query') as mock_query:
            mock_node = MagicMock()
            mock_node.id = "node123"
            mock_node.content = '{"analysis": "网络连接问题分析"}'
            mock_query.return_value.filter_by.return_value.first.return_value = mock_node
            
            regenerate_response = await async_client.post(
                f"/api/v1/cases/{case_id}/nodes/node123/regenerate",
                json=regenerate_data,
                headers=headers
            )
            assert regenerate_response.status_code == 200
        
        # 7. 获取统计数据
        stats_response = await async_client.get(
            "/api/v1/statistics/overview",
            headers=headers
        )
        assert stats_response.status_code == 200
        
    @pytest.mark.asyncio
    async def test_batch_operations_workflow(self, async_client: AsyncClient):
        """测试批量操作工作流"""
        
        headers = {"Authorization": "Bearer test_token"}
        
        # 1. 批量创建案例
        batch_cases = {
            "cases": [
                {
                    "title": f"案例{i}",
                    "description": f"描述{i}",
                    "problem_type": "network",
                    "vendor": "cisco"
                }
                for i in range(1, 6)
            ]
        }
        
        with patch('open_webui.services.batch_processor.process_items_batch') as mock_batch:
            mock_result = MagicMock()
            mock_result.success_count = 5
            mock_result.failed_count = 0
            mock_result.total_count = 5
            mock_result.success_items = [["case1", "case2", "case3", "case4", "case5"]]
            mock_result.failed_items = []
            mock_batch.return_value = mock_result
            
            batch_response = await async_client.post(
                "/api/v1/cases/batch/create",
                json=batch_cases,
                headers=headers
            )
            assert batch_response.status_code == 200
            assert batch_response.json()["success_count"] == 5
        
        # 2. 批量文件扫描
        scan_request = {
            "file_ids": ["file1", "file2", "file3"]
        }
        
        batch_scan_response = await async_client.post(
            "/api/v1/files/batch/scan",
            json=scan_request,
            headers=headers
        )
        assert batch_scan_response.status_code == 200
        
    @pytest.mark.asyncio
    async def test_error_handling_workflow(self, async_client: AsyncClient):
        """测试错误处理工作流"""
        
        headers = {"Authorization": "Bearer invalid_token"}
        
        # 1. 无效认证
        response = await async_client.get("/api/v1/cases/", headers=headers)
        assert response.status_code == 401
        
        # 2. 资源不存在
        valid_headers = {"Authorization": "Bearer valid_token"}
        response = await async_client.get(
            "/api/v1/cases/nonexistent",
            headers=valid_headers
        )
        assert response.status_code == 404
        
        # 3. 参数验证错误
        invalid_case_data = {
            "title": "",  # 空标题
            "description": "测试描述"
        }
        
        response = await async_client.post(
            "/api/v1/cases/",
            json=invalid_case_data,
            headers=valid_headers
        )
        assert response.status_code == 422
        
    @pytest.mark.asyncio
    async def test_performance_workflow(self, async_client: AsyncClient):
        """测试性能相关工作流"""
        
        headers = {"Authorization": "Bearer test_token"}
        
        # 1. 向量索引重建
        with patch('open_webui.services.vector_rebuild_service.start_vector_rebuild') as mock_rebuild:
            mock_progress = MagicMock()
            mock_progress.status.value = "pending"
            mock_progress.total_count = 100
            mock_rebuild.return_value = mock_progress
            
            rebuild_response = await async_client.post(
                "/api/v1/dev/vector/rebuild",
                headers=headers
            )
            assert rebuild_response.status_code == 200
            task_id = rebuild_response.json()["data"]["task_id"]
        
        # 2. 查询重建状态
        with patch('open_webui.services.vector_rebuild_service.get_rebuild_progress') as mock_get_progress:
            mock_progress.status.value = "running"
            mock_progress.progress = 50.0
            mock_get_progress.return_value = mock_progress
            
            status_response = await async_client.get(
                f"/api/v1/dev/vector/rebuild/status?task_id={task_id}",
                headers=headers
            )
            assert status_response.status_code == 200
        
        # 3. 性能监控
        perf_response = await async_client.get(
            "/api/v1/system/metrics",
            headers=headers
        )
        assert perf_response.status_code == 200
