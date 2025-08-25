"""
API契约测试

验证API接口的请求/响应格式符合OpenAPI规范
"""

import pytest
import json
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from open_webui.routers.cases_migrated import router as cases_router
from open_webui.routers.knowledge_unified import router_v1 as knowledge_router
from open_webui.routers.analysis_migrated import router as analysis_router

# 创建测试应用
app = FastAPI()
app.include_router(cases_router, prefix="/api/v1")
app.include_router(knowledge_router, prefix="/api/v1")
app.include_router(analysis_router, prefix="/api/v1")

client = TestClient(app)

class TestAPIContracts:
    """API契约测试类"""
    
    @pytest.fixture
    def mock_user(self):
        """模拟用户"""
        user = Mock()
        user.id = "contract_user_id"
        user.email = "contract@example.com"
        user.role = "user"
        return user
    
    def test_cases_api_contracts(self, mock_user):
        """测试案例API契约"""
        
        # 测试GET /cases响应格式
        with patch('open_webui.routers.cases_migrated.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.cases_migrated.cases_table') as mock_cases_table:
                mock_cases_table.get_cases_by_user_id.return_value = []
                
                response = client.get("/api/v1/cases")
                assert response.status_code == 200
                
                data = response.json()
                # 验证响应结构
                assert "cases" in data
                assert "pagination" in data
                assert isinstance(data["cases"], list)
                assert isinstance(data["pagination"], dict)
                
                # 验证分页结构
                pagination = data["pagination"]
                required_pagination_fields = ["total", "page", "per_page", "pages"]
                for field in required_pagination_fields:
                    assert field in pagination
                    assert isinstance(pagination[field], int)
        
        # 测试POST /cases请求/响应格式
        with patch('open_webui.routers.cases_migrated.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.cases_migrated.cases_table') as mock_cases_table:
                mock_case = Mock()
                mock_case.id = "test_case_id"
                mock_cases_table.insert_new_case.return_value = mock_case
                
                # 有效请求
                valid_request = {
                    "query": "测试查询",
                    "title": "测试案例",
                    "vendor": "华为",
                    "category": "测试",
                    "attachments": []
                }
                
                response = client.post("/api/v1/cases", json=valid_request)
                assert response.status_code == 200
                
                data = response.json()
                # 验证响应结构
                required_fields = ["caseId", "message"]
                for field in required_fields:
                    assert field in data
                
                assert isinstance(data["caseId"], str)
                assert isinstance(data["message"], str)
        
        # 测试无效请求格式
        with patch('open_webui.routers.cases_migrated.get_verified_user', return_value=mock_user):
            # 缺少必需字段
            invalid_request = {"title": "测试案例"}
            response = client.post("/api/v1/cases", json=invalid_request)
            assert response.status_code == 422
            
            # 验证错误响应格式
            error_data = response.json()
            assert "detail" in error_data
    
    def test_knowledge_api_contracts(self, mock_user):
        """测试知识管理API契约"""
        
        # 测试GET /documents响应格式
        with patch('open_webui.routers.knowledge_migrated.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.knowledge_migrated.Files') as mock_files:
                mock_files.get_files_by_user_id.return_value = []
                
                response = client.get("/api/v1/documents")
                assert response.status_code == 200
                
                data = response.json()
                # 验证响应结构
                assert "documents" in data
                assert "pagination" in data
                assert isinstance(data["documents"], list)
                assert isinstance(data["pagination"], dict)
        
        # 测试POST /knowledge/search请求/响应格式
        with patch('open_webui.routers.knowledge_migrated.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.knowledge_migrated.get_retrieval_vector_db') as mock_get_db:
                with patch('open_webui.routers.knowledge_migrated.similarity_normalizer') as mock_normalizer:
                    
                    mock_vector_db = Mock()
                    mock_get_db.return_value = mock_vector_db
                    mock_vector_db.search.return_value = []
                    mock_normalizer.normalize_scores.return_value = []
                    
                    # 有效搜索请求
                    valid_search = {
                        "query": "测试查询",
                        "topK": 5,
                        "vendor": "华为"
                    }
                    
                    response = client.post("/api/v1/knowledge/search", json=valid_search)
                    assert response.status_code == 200
                    
                    data = response.json()
                    # 验证响应结构
                    assert "results" in data
                    assert "query" in data
                    assert "totalResults" in data
                    assert isinstance(data["results"], list)
                    assert isinstance(data["totalResults"], int)
        
        # 测试搜索建议API
        with patch('open_webui.routers.knowledge_migrated.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.knowledge_migrated.get_retrieval_vector_db') as mock_get_db:
                mock_vector_db = Mock()
                mock_get_db.return_value = mock_vector_db
                mock_vector_db.get_suggestions.return_value = ["建议1", "建议2"]
                
                response = client.get("/api/v1/knowledge/search-suggestions?query=测试")
                assert response.status_code == 200
                
                data = response.json()
                assert "suggestions" in data
                assert isinstance(data["suggestions"], list)
    
    def test_analysis_api_contracts(self, mock_user):
        """测试分析API契约"""
        
        # 测试POST /analysis/log-parsing请求/响应格式
        with patch('open_webui.routers.analysis_migrated.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.analysis_migrated.log_parsing_service') as mock_service:
                with patch('open_webui.routers.analysis_migrated.get_retrieval_vector_db') as mock_get_db:
                    
                    # 模拟解析结果
                    mock_service.parse_log.return_value = {
                        "anomalies": [
                            {
                                "type": "interface_down",
                                "severity": "high",
                                "description": "接口故障",
                                "location": "GigabitEthernet0/0/1",
                                "timestamp": "2024-01-01T10:00:00Z"
                            }
                        ],
                        "summary": "检测到接口故障",
                        "recommendations": ["检查物理连接"]
                    }
                    
                    mock_vector_db = Mock()
                    mock_get_db.return_value = mock_vector_db
                    mock_vector_db.search.return_value = []
                    
                    # 有效日志解析请求
                    valid_request = {
                        "logContent": "2024-01-01 10:00:00 ERROR: Interface down",
                        "logType": "华为交换机",
                        "vendor": "华为",
                        "deviceModel": "S5700",
                        "attachments": []
                    }
                    
                    response = client.post("/api/v1/analysis/log-parsing", json=valid_request)
                    assert response.status_code == 200
                    
                    data = response.json()
                    # 验证响应结构
                    required_fields = ["anomalies", "summary", "recommendations", "relatedKnowledge", "severity"]
                    for field in required_fields:
                        assert field in data
                    
                    # 验证异常结构
                    assert isinstance(data["anomalies"], list)
                    if data["anomalies"]:
                        anomaly = data["anomalies"][0]
                        anomaly_fields = ["type", "severity", "description", "location", "timestamp"]
                        for field in anomaly_fields:
                            assert field in anomaly
                    
                    # 验证其他字段类型
                    assert isinstance(data["summary"], str)
                    assert isinstance(data["recommendations"], list)
                    assert isinstance(data["relatedKnowledge"], list)
                    assert data["severity"] in ["low", "medium", "high"]
    
    def test_error_response_contracts(self, mock_user):
        """测试错误响应契约"""
        
        # 测试404错误格式
        with patch('open_webui.routers.cases_migrated.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.cases_migrated.cases_table') as mock_cases_table:
                mock_cases_table.get_case_by_id.return_value = None
                
                response = client.get("/api/v1/cases/nonexistent")
                assert response.status_code == 404
                
                error_data = response.json()
                assert "detail" in error_data
                assert isinstance(error_data["detail"], str)
        
        # 测试403权限错误格式
        with patch('open_webui.routers.cases_migrated.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.cases_migrated.cases_table') as mock_cases_table:
                mock_case = Mock()
                mock_case.user_id = "other_user_id"  # 不同用户
                mock_cases_table.get_case_by_id.return_value = mock_case
                
                response = client.get("/api/v1/cases/forbidden_case")
                assert response.status_code == 403
                
                error_data = response.json()
                assert "detail" in error_data
                assert isinstance(error_data["detail"], str)
        
        # 测试422验证错误格式
        with patch('open_webui.routers.cases_migrated.get_verified_user', return_value=mock_user):
            invalid_data = {"invalid_field": "value"}
            response = client.post("/api/v1/cases", json=invalid_data)
            assert response.status_code == 422
            
            error_data = response.json()
            assert "detail" in error_data
            # 422错误的detail应该是数组格式
            assert isinstance(error_data["detail"], list)
        
        # 测试500服务器错误格式
        with patch('open_webui.routers.analysis_migrated.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.analysis_migrated.log_parsing_service') as mock_service:
                mock_service.parse_log.side_effect = Exception("Internal error")
                
                request_data = {
                    "logContent": "test log",
                    "logType": "华为交换机",
                    "vendor": "华为"
                }
                
                response = client.post("/api/v1/analysis/log-parsing", json=request_data)
                assert response.status_code == 500
                
                error_data = response.json()
                assert "detail" in error_data
                assert isinstance(error_data["detail"], str)

class TestResponseHeaders:
    """响应头测试"""
    
    @pytest.fixture
    def mock_user(self):
        """模拟用户"""
        user = Mock()
        user.id = "header_user_id"
        user.email = "header@example.com"
        user.role = "user"
        return user
    
    def test_content_type_headers(self, mock_user):
        """测试Content-Type响应头"""
        
        with patch('open_webui.routers.cases_migrated.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.cases_migrated.cases_table') as mock_cases_table:
                mock_cases_table.get_cases_by_user_id.return_value = []
                
                response = client.get("/api/v1/cases")
                assert response.status_code == 200
                assert response.headers["content-type"] == "application/json"
    
    def test_cors_headers(self, mock_user):
        """测试CORS响应头（如果配置了的话）"""
        
        with patch('open_webui.routers.knowledge_migrated.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.knowledge_migrated.Files') as mock_files:
                mock_files.get_files_by_user_id.return_value = []
                
                response = client.get("/api/v1/documents")
                assert response.status_code == 200
                
                # 检查是否有CORS头（可选）
                # 这取决于实际的CORS配置
                # assert "access-control-allow-origin" in response.headers

class TestPaginationContracts:
    """分页契约测试"""
    
    @pytest.fixture
    def mock_user(self):
        """模拟用户"""
        user = Mock()
        user.id = "pagination_user_id"
        user.email = "pagination@example.com"
        user.role = "user"
        return user
    
    def test_pagination_parameters(self, mock_user):
        """测试分页参数"""
        
        with patch('open_webui.routers.cases_migrated.get_verified_user', return_value=mock_user):
            with patch('open_webui.routers.cases_migrated.cases_table') as mock_cases_table:
                mock_cases_table.get_cases_by_user_id.return_value = []
                
                # 测试默认分页
                response = client.get("/api/v1/cases")
                assert response.status_code == 200
                data = response.json()
                assert data["pagination"]["page"] == 1
                assert data["pagination"]["per_page"] == 20
                
                # 测试自定义分页
                response = client.get("/api/v1/cases?page=2&pageSize=10")
                assert response.status_code == 200
                data = response.json()
                assert data["pagination"]["page"] == 2
                assert data["pagination"]["per_page"] == 10
                
                # 测试无效分页参数
                response = client.get("/api/v1/cases?page=0&pageSize=-1")
                assert response.status_code == 200  # 应该使用默认值
                data = response.json()
                assert data["pagination"]["page"] >= 1
                assert data["pagination"]["per_page"] >= 1

if __name__ == "__main__":
    pytest.main([__file__])
