"""
批量操作集成测试

测试批量操作的端到端流程：
1. 批量文件上传和处理
2. 批量案例创建和管理
3. 批量操作的错误处理
4. 批量操作的性能测试
"""

import pytest
import json
import tempfile
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from open_webui.routers.cases_migrated import router as cases_router
from open_webui.routers.files import router as files_router

# 创建测试应用
app = FastAPI()
app.include_router(cases_router, prefix="/api/v1")
app.include_router(files_router, prefix="/api/v1")

client = TestClient(app)

class TestBatchOperationsIntegration:
    """批量操作集成测试"""
    
    @pytest.fixture
    def mock_user(self):
        """模拟用户"""
        user = Mock()
        user.id = "batch_user_id"
        user.email = "batch@example.com"
        user.name = "Batch Test User"
        user.role = "user"
        return user
    
    @pytest.fixture
    def mock_admin_user(self):
        """模拟管理员用户"""
        user = Mock()
        user.id = "batch_admin_id"
        user.email = "admin@example.com"
        user.name = "Batch Admin User"
        user.role = "admin"
        return user
    
    def test_batch_file_upload_and_processing(self, mock_user):
        """测试批量文件上传和处理"""
        
        with patch('open_webui.routers.files.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.files.Files') as mock_files:
                with patch('open_webui.routers.files.allowed_file', return_value=True):
                    with patch('open_webui.routers.files.idp_service') as mock_idp:
                        
                        # 模拟文件上传成功
                        mock_files_list = []
                        for i in range(3):
                            mock_file = Mock()
                            mock_file.id = f"file_{i}"
                            mock_file.filename = f"document_{i}.pdf"
                            mock_file.user_id = mock_user.id
                            mock_files_list.append(mock_file)
                        
                        mock_files.insert_new_file.side_effect = mock_files_list
                        mock_files.get_file_by_id.side_effect = lambda file_id: next(
                            (f for f in mock_files_list if f.id == file_id), None
                        )
                        
                        # 模拟IDP处理
                        mock_idp.process_document_async.return_value = {
                            "task_id": "idp_task_123",
                            "status": "PROCESSING"
                        }
                        
                        # 批量上传文件
                        files_data = []
                        for i in range(3):
                            files_data.append(
                                ("files", (f"document_{i}.pdf", f"content_{i}".encode(), "application/pdf"))
                            )
                        
                        metadata = {
                            "vendor": "华为",
                            "tags": "批量测试,文档",
                            "category": "技术文档"
                        }
                        
                        response = client.post(
                            "/api/v1/files/batch",
                            files=files_data,
                            data=metadata
                        )
                        
                        assert response.status_code == 200
                        data = response.json()
                        assert data["status"] == "success"
                        assert len(data["results"]) == 3
                        assert data["summary"]["successful"] == 3
                        assert data["summary"]["failed"] == 0
                        
                        # 验证每个文件的结果
                        for i, result in enumerate(data["results"]):
                            assert result["status"] == "success"
                            assert result["fileId"] == f"file_{i}"
                            assert result["filename"] == f"document_{i}.pdf"
    
    def test_batch_file_processing_with_idp(self, mock_user):
        """测试批量文件IDP处理"""
        
        with patch('open_webui.routers.files.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.files.Files') as mock_files:
                with patch('open_webui.routers.files.idp_service') as mock_idp:
                    with patch('open_webui.routers.files.vector_db_service') as mock_vector:
                        
                        # 准备测试文件
                        mock_files_list = []
                        for i in range(2):
                            mock_file = Mock()
                            mock_file.id = f"process_file_{i}"
                            mock_file.filename = f"process_doc_{i}.pdf"
                            mock_file.user_id = mock_user.id
                            mock_file.meta = {"vendor": "华为"}
                            mock_files_list.append(mock_file)
                        
                        mock_files.get_file_by_id.side_effect = lambda file_id: next(
                            (f for f in mock_files_list if f.id == file_id), None
                        )
                        
                        # 模拟IDP处理结果
                        mock_idp.process_document_async.return_value = {
                            "task_id": "batch_idp_task",
                            "status": "COMPLETED",
                            "result": {
                                "text": "处理后的文档内容",
                                "metadata": {"pages": 10}
                            }
                        }
                        
                        # 模拟向量化处理
                        mock_vector.add_documents.return_value = {"success": True}
                        
                        # 批量处理请求
                        process_data = {
                            "fileIds": ["process_file_0", "process_file_1"],
                            "options": {
                                "enableIDP": True,
                                "enableVectorization": True,
                                "vendor": "华为"
                            }
                        }
                        
                        response = client.post("/api/v1/files/batch/process", json=process_data)
                        
                        assert response.status_code == 200
                        data = response.json()
                        assert data["status"] == "success"
                        assert len(data["results"]) == 2
                        assert data["summary"]["successful"] == 2
                        
                        # 验证处理结果
                        for result in data["results"]:
                            assert result["status"] == "success"
                            assert "idp_task_id" in result
                            assert result["processing_status"] == "COMPLETED"
    
    def test_batch_case_operations(self, mock_user):
        """测试批量案例操作"""
        
        with patch('open_webui.routers.cases_migrated.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.cases_migrated.cases_table') as mock_cases_table:
                
                # 批量创建案例
                mock_cases_list = []
                for i in range(3):
                    mock_case = Mock()
                    mock_case.id = f"batch_case_{i}"
                    mock_case.title = f"批量案例_{i}"
                    mock_case.user_id = mock_user.id
                    mock_cases_list.append(mock_case)
                
                mock_cases_table.insert_new_case.side_effect = mock_cases_list
                
                batch_create_data = {
                    "cases": [
                        {
                            "query": f"批量查询_{i}",
                            "title": f"批量案例_{i}",
                            "vendor": "华为",
                            "category": "批量测试",
                            "attachments": []
                        }
                        for i in range(3)
                    ]
                }
                
                create_response = client.post("/api/v1/cases/batch", json=batch_create_data)
                
                assert create_response.status_code == 200
                create_data = create_response.json()
                assert create_data["status"] == "success"
                assert len(create_data["results"]) == 3
                assert create_data["summary"]["successful"] == 3
                
                # 验证创建结果
                created_case_ids = []
                for i, result in enumerate(create_data["results"]):
                    assert result["status"] == "success"
                    assert result["caseId"] == f"batch_case_{i}"
                    created_case_ids.append(result["caseId"])
                
                # 批量更新案例
                mock_cases_table.get_case_by_id.side_effect = lambda case_id: next(
                    (c for c in mock_cases_list if c.id == case_id), None
                )
                mock_cases_table.update_case.return_value = True
                
                batch_update_data = {
                    "updates": [
                        {
                            "caseId": case_id,
                            "title": f"更新后的案例_{i}",
                            "status": "COMPLETED"
                        }
                        for i, case_id in enumerate(created_case_ids)
                    ]
                }
                
                update_response = client.put("/api/v1/cases/batch", json=batch_update_data)
                
                assert update_response.status_code == 200
                update_data = update_response.json()
                assert update_data["status"] == "success"
                assert update_data["summary"]["successful"] == 3
                
                # 批量删除案例
                mock_cases_table.delete_case.return_value = True
                
                batch_delete_data = {
                    "caseIds": created_case_ids
                }
                
                delete_response = client.delete("/api/v1/cases/batch", json=batch_delete_data)
                
                assert delete_response.status_code == 200
                delete_data = delete_response.json()
                assert delete_data["status"] == "success"
                assert delete_data["summary"]["successful"] == 3
    
    def test_batch_operations_error_handling(self, mock_user):
        """测试批量操作错误处理"""
        
        # 测试批量文件上传部分失败
        with patch('open_webui.routers.files.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.files.Files') as mock_files:
                with patch('open_webui.routers.files.allowed_file') as mock_allowed:
                    
                    # 模拟部分文件类型不支持
                    mock_allowed.side_effect = [True, False, True]  # 第二个文件不支持
                    
                    mock_file1 = Mock()
                    mock_file1.id = "success_file_1"
                    mock_file1.filename = "success_1.pdf"
                    
                    mock_file3 = Mock()
                    mock_file3.id = "success_file_3"
                    mock_file3.filename = "success_3.pdf"
                    
                    mock_files.insert_new_file.side_effect = [mock_file1, None, mock_file3]
                    
                    files_data = [
                        ("files", ("success_1.pdf", b"content1", "application/pdf")),
                        ("files", ("invalid.exe", b"content2", "application/octet-stream")),
                        ("files", ("success_3.pdf", b"content3", "application/pdf"))
                    ]
                    
                    response = client.post("/api/v1/files/batch", files=files_data)
                    
                    assert response.status_code == 207  # Multi-Status
                    data = response.json()
                    assert data["status"] == "partial_success"
                    assert data["summary"]["successful"] == 2
                    assert data["summary"]["failed"] == 1
                    
                    # 验证结果详情
                    results = data["results"]
                    assert results[0]["status"] == "success"
                    assert results[1]["status"] == "error"
                    assert "不支持的文件类型" in results[1]["error"]
                    assert results[2]["status"] == "success"
        
        # 测试批量案例创建部分失败
        with patch('open_webui.routers.cases_migrated.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.cases_migrated.cases_table') as mock_cases_table:
                
                # 模拟部分案例创建失败
                def mock_insert_case(case_data):
                    if "失败" in case_data.get("title", ""):
                        raise Exception("案例创建失败")
                    mock_case = Mock()
                    mock_case.id = f"case_{case_data['title']}"
                    return mock_case
                
                mock_cases_table.insert_new_case.side_effect = mock_insert_case
                
                batch_data = {
                    "cases": [
                        {"query": "成功查询1", "title": "成功案例1", "vendor": "华为", "category": "测试"},
                        {"query": "失败查询", "title": "失败案例", "vendor": "华为", "category": "测试"},
                        {"query": "成功查询2", "title": "成功案例2", "vendor": "华为", "category": "测试"}
                    ]
                }
                
                response = client.post("/api/v1/cases/batch", json=batch_data)
                
                assert response.status_code == 207  # Multi-Status
                data = response.json()
                assert data["status"] == "partial_success"
                assert data["summary"]["successful"] == 2
                assert data["summary"]["failed"] == 1
    
    def test_batch_operations_performance(self, mock_user):
        """测试批量操作性能"""
        
        with patch('open_webui.routers.cases_migrated.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.cases_migrated.cases_table') as mock_cases_table:
                
                # 模拟大量案例创建
                def mock_insert_case(case_data):
                    mock_case = Mock()
                    mock_case.id = f"perf_case_{case_data['title']}"
                    return mock_case
                
                mock_cases_table.insert_new_case.side_effect = mock_insert_case
                
                # 创建50个案例的批量请求
                large_batch_data = {
                    "cases": [
                        {
                            "query": f"性能测试查询_{i}",
                            "title": f"性能测试案例_{i}",
                            "vendor": "华为",
                            "category": "性能测试",
                            "attachments": []
                        }
                        for i in range(50)
                    ]
                }
                
                import time
                start_time = time.time()
                
                response = client.post("/api/v1/cases/batch", json=large_batch_data)
                
                end_time = time.time()
                processing_time = end_time - start_time
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
                assert len(data["results"]) == 50
                assert data["summary"]["successful"] == 50
                
                # 验证处理时间合理（应该在合理范围内）
                assert processing_time < 10.0  # 50个案例应该在10秒内完成
                
                # 验证批量操作的效率
                avg_time_per_case = processing_time / 50
                assert avg_time_per_case < 0.2  # 每个案例平均处理时间应小于200ms

class TestBatchOperationsPermissions:
    """批量操作权限测试"""
    
    @pytest.fixture
    def mock_user(self):
        """模拟普通用户"""
        user = Mock()
        user.id = "normal_user_id"
        user.email = "normal@example.com"
        user.role = "user"
        return user
    
    @pytest.fixture
    def mock_admin(self):
        """模拟管理员用户"""
        user = Mock()
        user.id = "admin_user_id"
        user.email = "admin@example.com"
        user.role = "admin"
        return user
    
    def test_batch_delete_permissions(self, mock_user, mock_admin):
        """测试批量删除权限控制"""
        
        # 普通用户只能删除自己的案例
        with patch('open_webui.routers.cases_migrated.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.cases_migrated.cases_table') as mock_cases_table:
                
                # 模拟案例，其中一个不属于当前用户
                mock_case1 = Mock()
                mock_case1.id = "user_case_1"
                mock_case1.user_id = mock_user.id
                
                mock_case2 = Mock()
                mock_case2.id = "other_user_case"
                mock_case2.user_id = "other_user_id"
                
                mock_cases_table.get_case_by_id.side_effect = lambda case_id: {
                    "user_case_1": mock_case1,
                    "other_user_case": mock_case2
                }.get(case_id)
                
                batch_delete_data = {
                    "caseIds": ["user_case_1", "other_user_case"]
                }
                
                response = client.delete("/api/v1/cases/batch", json=batch_delete_data)
                
                assert response.status_code == 207  # Multi-Status
                data = response.json()
                assert data["status"] == "partial_success"
                assert data["summary"]["successful"] == 1  # 只能删除自己的案例
                assert data["summary"]["failed"] == 1
                
                # 验证权限错误
                failed_result = next(r for r in data["results"] if r["status"] == "error")
                assert "权限不足" in failed_result["error"]
        
        # 管理员可以删除所有案例
        with patch('open_webui.routers.cases_migrated.get_verified_user', return_value=mock_admin):
            with patch('open_webui.routers.cases_migrated.cases_table') as mock_cases_table:
                
                mock_cases_table.get_case_by_id.side_effect = lambda case_id: Mock(id=case_id, user_id="any_user")
                mock_cases_table.delete_case.return_value = True
                
                batch_delete_data = {
                    "caseIds": ["case_1", "case_2", "case_3"]
                }
                
                response = client.delete("/api/v1/cases/batch", json=batch_delete_data)
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
                assert data["summary"]["successful"] == 3
                assert data["summary"]["failed"] == 0

if __name__ == "__main__":
    pytest.main([__file__])
