"""
智能分析模块单元测试
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from open_webui.routers.analysis_migrated import router

# 创建测试应用
app = FastAPI()
app.include_router(router, prefix="/api/v1")
client = TestClient(app)

class TestAnalysisRouter:
    """智能分析路由测试类"""
    
    @pytest.fixture
    def mock_user(self):
        """模拟用户"""
        user = Mock()
        user.id = "test_user_id"
        user.email = "test@example.com"
        user.role = "user"
        return user
    
    @pytest.fixture
    def sample_log_parsing_request(self):
        """示例日志解析请求"""
        return {
            "logContent": "2024-01-01 10:00:00 ERROR: Interface GigabitEthernet0/0/1 is down",
            "logType": "华为交换机",
            "vendor": "华为",
            "deviceModel": "S5700",
            "attachments": []
        }
    
    @pytest.fixture
    def sample_parsing_result(self):
        """示例解析结果"""
        return {
            "anomalies": [
                {
                    "type": "interface_down",
                    "severity": "high",
                    "description": "接口GigabitEthernet0/0/1已断开",
                    "location": "GigabitEthernet0/0/1",
                    "timestamp": "2024-01-01T10:00:00Z"
                }
            ],
            "summary": "检测到接口故障",
            "recommendations": [
                "检查接口物理连接",
                "查看接口配置"
            ]
        }
    
    @pytest.fixture
    def sample_knowledge_results(self):
        """示例知识检索结果"""
        return [
            {
                "content": "接口故障排查步骤：1. 检查物理连接 2. 查看接口状态",
                "metadata": {
                    "source": "华为交换机故障手册.pdf",
                    "page": 15
                },
                "score": 0.95
            },
            {
                "content": "GigabitEthernet接口常见故障及解决方案",
                "metadata": {
                    "source": "网络故障案例集.pdf", 
                    "page": 23
                },
                "score": 0.88
            }
        ]
    
    @patch('open_webui.routers.analysis_migrated.get_verified_user')
    @patch('open_webui.routers.analysis_migrated.log_parsing_service')
    @patch('open_webui.routers.analysis_migrated.get_retrieval_vector_db')
    def test_parse_log_success(self, mock_get_vector_db, mock_log_service, mock_get_user, 
                             mock_user, sample_log_parsing_request, sample_parsing_result, 
                             sample_knowledge_results):
        """测试日志解析成功"""
        # 设置模拟
        mock_get_user.return_value = mock_user
        mock_log_service.parse_log.return_value = sample_parsing_result
        mock_vector_db = Mock()
        mock_get_vector_db.return_value = mock_vector_db
        mock_vector_db.search.return_value = sample_knowledge_results
        
        # 发送请求
        response = client.post("/api/v1/analysis/log-parsing", json=sample_log_parsing_request)
        
        # 验证结果
        assert response.status_code == 200
        data = response.json()
        assert "anomalies" in data
        assert "summary" in data
        assert "recommendations" in data
        assert "relatedKnowledge" in data
        assert "severity" in data
        
        assert len(data["anomalies"]) == 1
        assert data["anomalies"][0]["type"] == "interface_down"
        assert data["severity"] == "high"
        assert len(data["relatedKnowledge"]) == 2
        
        # 验证调用
        mock_log_service.parse_log.assert_called_once()
        mock_vector_db.search.assert_called_once()
    
    @patch('open_webui.routers.analysis_migrated.get_verified_user')
    def test_parse_log_empty_log_type(self, mock_get_user, mock_user):
        """测试空日志类型"""
        # 设置模拟
        mock_get_user.return_value = mock_user
        
        # 发送请求
        request_data = {
            "logContent": "Some log content",
            "logType": "",  # 空日志类型
            "vendor": "华为"
        }
        response = client.post("/api/v1/analysis/log-parsing", json=request_data)
        
        # 验证结果
        assert response.status_code == 400
        assert "日志类型不能为空" in response.json()["detail"]
    
    @patch('open_webui.routers.analysis_migrated.get_verified_user')
    def test_parse_log_empty_content(self, mock_get_user, mock_user):
        """测试空日志内容"""
        # 设置模拟
        mock_get_user.return_value = mock_user
        
        # 发送请求
        request_data = {
            "logContent": "",  # 空日志内容
            "logType": "华为交换机",
            "vendor": "华为"
        }
        response = client.post("/api/v1/analysis/log-parsing", json=request_data)
        
        # 验证结果
        assert response.status_code == 400
        assert "日志内容不能为空" in response.json()["detail"]
    
    @patch('open_webui.routers.analysis_migrated.get_verified_user')
    @patch('open_webui.routers.analysis_migrated.log_parsing_service')
    def test_parse_log_service_error(self, mock_log_service, mock_get_user, mock_user, 
                                   sample_log_parsing_request):
        """测试日志解析服务错误"""
        # 设置模拟
        mock_get_user.return_value = mock_user
        mock_log_service.parse_log.side_effect = Exception("解析服务错误")
        
        # 发送请求
        response = client.post("/api/v1/analysis/log-parsing", json=sample_log_parsing_request)
        
        # 验证结果
        assert response.status_code == 500
        assert "日志解析失败" in response.json()["detail"]
    
    @patch('open_webui.routers.analysis_migrated.get_verified_user')
    @patch('open_webui.routers.analysis_migrated.log_parsing_service')
    @patch('open_webui.routers.analysis_migrated.get_retrieval_vector_db')
    def test_parse_log_vector_db_unavailable(self, mock_get_vector_db, mock_log_service, 
                                           mock_get_user, mock_user, sample_log_parsing_request, 
                                           sample_parsing_result):
        """测试向量数据库不可用时的处理"""
        # 设置模拟
        mock_get_user.return_value = mock_user
        mock_log_service.parse_log.return_value = sample_parsing_result
        mock_get_vector_db.return_value = None  # 向量数据库不可用
        
        # 发送请求
        response = client.post("/api/v1/analysis/log-parsing", json=sample_log_parsing_request)
        
        # 验证结果
        assert response.status_code == 200
        data = response.json()
        assert "anomalies" in data
        assert "relatedKnowledge" in data
        assert len(data["relatedKnowledge"]) == 0  # 没有相关知识
    
    @patch('open_webui.routers.analysis_migrated.get_verified_user')
    @patch('open_webui.routers.analysis_migrated.log_parsing_service')
    @patch('open_webui.routers.analysis_migrated.get_retrieval_vector_db')
    def test_parse_log_severity_aggregation(self, mock_get_vector_db, mock_log_service, 
                                          mock_get_user, mock_user, sample_log_parsing_request):
        """测试严重程度聚合"""
        # 设置模拟
        mock_get_user.return_value = mock_user
        
        # 多个异常，包含不同严重程度
        parsing_result = {
            "anomalies": [
                {"type": "interface_down", "severity": "high", "description": "接口故障"},
                {"type": "cpu_high", "severity": "medium", "description": "CPU使用率高"},
                {"type": "memory_warning", "severity": "low", "description": "内存警告"}
            ],
            "summary": "检测到多个问题",
            "recommendations": ["检查系统状态"]
        }
        mock_log_service.parse_log.return_value = parsing_result
        mock_get_vector_db.return_value = None
        
        # 发送请求
        response = client.post("/api/v1/analysis/log-parsing", json=sample_log_parsing_request)
        
        # 验证结果
        assert response.status_code == 200
        data = response.json()
        assert data["severity"] == "high"  # 应该取最高严重程度
    
    @patch('open_webui.routers.analysis_migrated.get_verified_user')
    @patch('open_webui.routers.analysis_migrated.log_parsing_service')
    @patch('open_webui.routers.analysis_migrated.get_retrieval_vector_db')
    def test_parse_log_with_attachments(self, mock_get_vector_db, mock_log_service, 
                                      mock_get_user, mock_user, sample_parsing_result):
        """测试带附件的日志解析"""
        # 设置模拟
        mock_get_user.return_value = mock_user
        mock_log_service.parse_log.return_value = sample_parsing_result
        mock_get_vector_db.return_value = None
        
        # 带附件的请求
        request_data = {
            "logContent": "Error log content",
            "logType": "华为交换机",
            "vendor": "华为",
            "attachments": [
                {"fileId": "file1", "fileName": "config.txt"},
                {"fileId": "file2", "fileName": "log.txt"}
            ]
        }
        
        # 发送请求
        response = client.post("/api/v1/analysis/log-parsing", json=request_data)
        
        # 验证结果
        assert response.status_code == 200
        data = response.json()
        assert "anomalies" in data
        
        # 验证解析服务被调用时包含附件信息
        call_args = mock_log_service.parse_log.call_args[0]
        assert len(call_args[4]) == 2  # attachments参数
    
    @patch('open_webui.routers.analysis_migrated.get_verified_user')
    @patch('open_webui.routers.analysis_migrated.log_parsing_service')
    @patch('open_webui.routers.analysis_migrated.get_retrieval_vector_db')
    def test_parse_log_knowledge_search_with_filters(self, mock_get_vector_db, mock_log_service, 
                                                    mock_get_user, mock_user, sample_log_parsing_request, 
                                                    sample_parsing_result, sample_knowledge_results):
        """测试知识搜索时的过滤条件"""
        # 设置模拟
        mock_get_user.return_value = mock_user
        mock_log_service.parse_log.return_value = sample_parsing_result
        mock_vector_db = Mock()
        mock_get_vector_db.return_value = mock_vector_db
        mock_vector_db.search.return_value = sample_knowledge_results
        
        # 发送请求
        response = client.post("/api/v1/analysis/log-parsing", json=sample_log_parsing_request)
        
        # 验证结果
        assert response.status_code == 200
        
        # 验证知识搜索调用参数
        search_call = mock_vector_db.search.call_args
        search_query = search_call[0][0]
        search_filters = search_call[1].get("filters", {})
        
        # 应该包含厂商过滤
        assert "vendor" in search_filters
        assert search_filters["vendor"] == "华为"
        
        # 搜索查询应该包含异常信息
        assert "interface_down" in search_query or "接口" in search_query
    
    @patch('open_webui.routers.analysis_migrated.get_verified_user')
    @patch('open_webui.routers.analysis_migrated.log_parsing_service')
    @patch('open_webui.routers.analysis_migrated.get_retrieval_vector_db')
    def test_parse_log_no_anomalies(self, mock_get_vector_db, mock_log_service, 
                                  mock_get_user, mock_user, sample_log_parsing_request):
        """测试没有检测到异常的情况"""
        # 设置模拟
        mock_get_user.return_value = mock_user
        
        # 没有异常的解析结果
        parsing_result = {
            "anomalies": [],
            "summary": "日志正常，未发现异常",
            "recommendations": []
        }
        mock_log_service.parse_log.return_value = parsing_result
        mock_get_vector_db.return_value = None
        
        # 发送请求
        response = client.post("/api/v1/analysis/log-parsing", json=sample_log_parsing_request)
        
        # 验证结果
        assert response.status_code == 200
        data = response.json()
        assert len(data["anomalies"]) == 0
        assert data["severity"] == "low"  # 默认低严重程度
        assert "正常" in data["summary"]

class TestLogParsingValidation:
    """日志解析请求验证测试"""
    
    @pytest.fixture
    def mock_user(self):
        """模拟用户"""
        user = Mock()
        user.id = "test_user_id"
        user.email = "test@example.com"
        user.role = "user"
        return user
    
    @patch('open_webui.routers.analysis_migrated.get_verified_user')
    def test_missing_required_fields(self, mock_get_user, mock_user):
        """测试缺少必需字段"""
        mock_get_user.return_value = mock_user
        
        # 缺少logContent字段
        request_data = {
            "logType": "华为交换机",
            "vendor": "华为"
        }
        response = client.post("/api/v1/analysis/log-parsing", json=request_data)
        assert response.status_code == 422
        
        # 缺少logType字段
        request_data = {
            "logContent": "Some log content",
            "vendor": "华为"
        }
        response = client.post("/api/v1/analysis/log-parsing", json=request_data)
        assert response.status_code == 422
    
    @patch('open_webui.routers.analysis_migrated.get_verified_user')
    def test_invalid_field_types(self, mock_get_user, mock_user):
        """测试无效字段类型"""
        mock_get_user.return_value = mock_user
        
        # attachments应该是数组
        request_data = {
            "logContent": "Some log content",
            "logType": "华为交换机",
            "vendor": "华为",
            "attachments": "invalid_type"  # 应该是数组
        }
        response = client.post("/api/v1/analysis/log-parsing", json=request_data)
        assert response.status_code == 422
    
    @patch('open_webui.routers.analysis_migrated.get_verified_user')
    def test_valid_optional_fields(self, mock_get_user, mock_user):
        """测试有效的可选字段"""
        mock_get_user.return_value = mock_user
        
        # 只包含必需字段
        request_data = {
            "logContent": "Some log content",
            "logType": "华为交换机"
        }
        
        with patch('open_webui.routers.analysis_migrated.log_parsing_service') as mock_service:
            mock_service.parse_log.return_value = {
                "anomalies": [],
                "summary": "正常",
                "recommendations": []
            }
            
            response = client.post("/api/v1/analysis/log-parsing", json=request_data)
            assert response.status_code == 200

if __name__ == "__main__":
    pytest.main([__file__])
