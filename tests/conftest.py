"""
测试配置文件

提供测试用的fixtures和配置
"""

import pytest
import asyncio
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

# 测试数据库配置
@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环用于异步测试"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def mock_db_session():
    """模拟数据库会话"""
    session = Mock()
    session.query.return_value = session
    session.filter.return_value = session
    session.filter_by.return_value = session
    session.first.return_value = None
    session.all.return_value = []
    session.add.return_value = None
    session.commit.return_value = None
    session.rollback.return_value = None
    return session

@pytest.fixture
def mock_vector_db():
    """模拟向量数据库"""
    vector_db = Mock()
    vector_db.search.return_value = []
    vector_db.add_texts.return_value = None
    vector_db.delete.return_value = None
    vector_db.get_suggestions.return_value = []
    vector_db.get_tags.return_value = []
    return vector_db

@pytest.fixture
def mock_authenticated_user():
    """模拟已认证用户"""
    user = Mock()
    user.id = "test_user_id"
    user.email = "test@example.com"
    user.name = "Test User"
    user.role = "user"
    user.profile_image_url = None
    return user

@pytest.fixture
def mock_admin_user():
    """模拟管理员用户"""
    user = Mock()
    user.id = "admin_user_id"
    user.email = "admin@example.com"
    user.name = "Admin User"
    user.role = "admin"
    user.profile_image_url = None
    return user

@pytest.fixture
def test_app():
    """创建测试应用"""
    app = FastAPI()
    return app

@pytest.fixture
def test_client(test_app):
    """创建测试客户端"""
    return TestClient(test_app)

# 通用模拟数据
@pytest.fixture
def sample_case_data():
    """示例案例数据"""
    return {
        "id": "test_case_id",
        "title": "测试案例",
        "query": "网络连接问题",
        "status": "ACTIVE",
        "vendor": "华为",
        "category": "网络故障",
        "user_id": "test_user_id",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        "metadata": {}
    }

@pytest.fixture
def sample_file_data():
    """示例文件数据"""
    return {
        "id": "test_file_id",
        "filename": "test_document.pdf",
        "user_id": "test_user_id",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        "meta": {
            "size": 1024,
            "content_type": "application/pdf",
            "vendor": "华为",
            "tags": ["网络", "故障"]
        }
    }

@pytest.fixture
def sample_knowledge_data():
    """示例知识数据"""
    return {
        "id": "test_knowledge_id",
        "name": "测试知识",
        "description": "测试知识描述",
        "user_id": "test_user_id",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        "data": {
            "file_id": "test_file_id",
            "chunks_count": 5
        }
    }

# 测试环境配置
@pytest.fixture(autouse=True)
def mock_config():
    """模拟配置"""
    with patch.dict('os.environ', {
        'DATA_DIR': '/test/data',
        'WEAVIATE_URL': 'http://localhost:8080',
        'CONTENT_EXTRACTION_ENGINE': 'alibaba_idp'
    }):
        yield

@pytest.fixture(autouse=True)
def mock_logging():
    """模拟日志记录"""
    with patch('logging.getLogger') as mock_logger:
        logger = Mock()
        mock_logger.return_value = logger
        yield logger
