"""
生产环境配置优化

包含生产环境的优化配置：
1. 数据库连接池优化
2. 缓存配置优化
3. 日志配置优化
4. 安全配置强化
5. 性能监控配置
"""

import os
from typing import Dict, Any, Optional
from pathlib import Path

class ProductionConfig:
    """生产环境配置类"""

    # 基础配置
    ENV = "production"
    DEBUG = False
    TESTING = False

    # 数据库配置优化
    DATABASE_CONFIG = {
        "pool_size": 20,  # 连接池大小
        "max_overflow": 30,  # 最大溢出连接数
        "pool_timeout": 30,  # 连接超时时间
        "pool_recycle": 3600,  # 连接回收时间（1小时）
        "pool_pre_ping": True,  # 连接前ping检查
        "echo": False,  # 生产环境不输出SQL
        "connect_args": {
            "connect_timeout": 10,
            "read_timeout": 30,
            "write_timeout": 30,
            "charset": "utf8mb4",
            "autocommit": False
        }
    }

    # Redis缓存配置优化
    REDIS_CONFIG = {
        "host": os.getenv("REDIS_HOST", "localhost"),
        "port": int(os.getenv("REDIS_PORT", 6379)),
        "db": int(os.getenv("REDIS_DB", 0)),
        "password": os.getenv("REDIS_PASSWORD"),
        "socket_timeout": 5,
        "socket_connect_timeout": 5,
        "socket_keepalive": True,
        "socket_keepalive_options": {},
        "connection_pool_kwargs": {
            "max_connections": 50,
            "retry_on_timeout": True
        },
        "decode_responses": True,
        "health_check_interval": 30
    }

    # 向量数据库配置
    WEAVIATE_CONFIG = {
        "host": os.getenv("WEAVIATE_HOST", "localhost"),
        "port": int(os.getenv("WEAVIATE_PORT", 8080)),
        "grpc_port": int(os.getenv("WEAVIATE_GRPC_PORT", 50051)),
        "timeout_config": (5, 60),  # (connect_timeout, read_timeout)
        "connection_params": {
            "session_pool_connections": 20,
            "session_pool_maxsize": 20,
            "session_pool_block": False
        },
        "additional_headers": {
            "X-OpenAI-Api-Key": os.getenv("OPENAI_API_KEY", ""),
        }
    }

    # 阿里云IDP配置
    ALIYUN_IDP_CONFIG = {
        "access_key_id": os.getenv("ALIYUN_ACCESS_KEY_ID"),
        "access_key_secret": os.getenv("ALIYUN_ACCESS_KEY_SECRET"),
        "region": os.getenv("ALIYUN_REGION", "cn-shanghai"),
        "endpoint": os.getenv("ALIYUN_IDP_ENDPOINT"),
        "timeout": 300,  # 5分钟超时
        "max_retries": 3,
        "retry_delay": 2,
        "concurrent_limit": 10  # 并发限制
    }

    # 文件上传配置
    FILE_UPLOAD_CONFIG = {
        "max_file_size": 100 * 1024 * 1024,  # 100MB
        "allowed_extensions": {
            '.pdf', '.doc', '.docx', '.txt', '.md', '.rtf',
            '.xls', '.xlsx', '.csv', '.ppt', '.pptx',
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'
        },
        "upload_folder": os.getenv("UPLOAD_FOLDER", "/app/uploads"),
        "temp_folder": os.getenv("TEMP_FOLDER", "/app/temp"),
        "enable_security_scan": True,
        "quarantine_folder": "/app/quarantine"
    }

    # 日志配置
    LOGGING_CONFIG = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "detailed": {
                "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s [%(filename)s:%(lineno)d]",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "simple": {
                "format": "%(asctime)s [%(levelname)s] %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "json": {
                "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                "format": "%(asctime)s %(name)s %(levelname)s %(message)s %(filename)s %(lineno)d"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "INFO",
                "formatter": "simple",
                "stream": "ext://sys.stdout"
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "detailed",
                "filename": "/app/logs/app.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 10
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "ERROR",
                "formatter": "detailed",
                "filename": "/app/logs/error.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5
            },
            "json_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "json",
                "filename": "/app/logs/app.json",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 10
            }
        },
        "loggers": {
            "": {  # root logger
                "level": "INFO",
                "handlers": ["console", "file", "error_file"]
            },
            "uvicorn": {
                "level": "INFO",
                "handlers": ["file"],
                "propagate": False
            },
            "sqlalchemy": {
                "level": "WARNING",
                "handlers": ["file"],
                "propagate": False
            },
            "open_webui": {
                "level": "INFO",
                "handlers": ["console", "file", "json_file"],
                "propagate": False
            }
        }
    }

    # 安全配置
    SECURITY_CONFIG = {
        "secret_key": os.getenv("SECRET_KEY"),
        "jwt_secret_key": os.getenv("JWT_SECRET_KEY"),
        "jwt_algorithm": "HS256",
        "jwt_expiration_hours": 24,
        "password_hash_rounds": 12,
        "max_login_attempts": 5,
        "lockout_duration": 900,  # 15分钟
        "session_timeout": 3600,  # 1小时
        "csrf_protection": True,
        "secure_headers": {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'"
        }
    }

    # 性能监控配置
    MONITORING_CONFIG = {
        "enable_metrics": True,
        "metrics_endpoint": "/metrics",
        "health_check_endpoint": "/health",
        "enable_profiling": False,  # 生产环境关闭
        "request_timeout": 30,
        "slow_query_threshold": 1.0,  # 1秒
        "memory_threshold": 0.8,  # 80%
        "cpu_threshold": 0.8,  # 80%
        "disk_threshold": 0.9  # 90%
    }

    # 缓存策略配置
    CACHE_CONFIG = {
        "default_timeout": 3600,  # 1小时
        "search_cache_timeout": 1800,  # 30分钟
        "user_cache_timeout": 900,  # 15分钟
        "file_cache_timeout": 7200,  # 2小时
        "max_cache_size": 1000,  # 最大缓存条目数
        "cache_key_prefix": "openwebui:",
        "enable_compression": True
    }

    # 异步任务配置
    CELERY_CONFIG = {
        "broker_url": os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1"),
        "result_backend": os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
        "task_serializer": "json",
        "accept_content": ["json"],
        "result_serializer": "json",
        "timezone": "Asia/Shanghai",
        "enable_utc": True,
        "worker_prefetch_multiplier": 1,
        "task_acks_late": True,
        "worker_max_tasks_per_child": 1000,
        "task_time_limit": 300,  # 5分钟
        "task_soft_time_limit": 240,  # 4分钟
        "worker_concurrency": 4
    }

def get_production_config() -> Dict[str, Any]:
    """获取生产环境配置"""
    config = ProductionConfig()

    # 验证必需的环境变量
    required_env_vars = [
        "SECRET_KEY",
        "JWT_SECRET_KEY",
        "DATABASE_URL",
        "ALIYUN_ACCESS_KEY_ID",
        "ALIYUN_ACCESS_KEY_SECRET"
    ]

    missing_vars = []
    for var in required_env_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        raise ValueError(f"缺少必需的环境变量: {', '.join(missing_vars)}")

    return {
        "database": config.DATABASE_CONFIG,
        "redis": config.REDIS_CONFIG,
        "weaviate": config.WEAVIATE_CONFIG,
        "aliyun_idp": config.ALIYUN_IDP_CONFIG,
        "file_upload": config.FILE_UPLOAD_CONFIG,
        "logging": config.LOGGING_CONFIG,
        "security": config.SECURITY_CONFIG,
        "monitoring": config.MONITORING_CONFIG,
        "cache": config.CACHE_CONFIG,
        "celery": config.CELERY_CONFIG
    }

def optimize_database_connection(database_url: str) -> str:
    """优化数据库连接字符串"""
    if "mysql" in database_url:
        # MySQL优化参数
        optimizations = [
            "charset=utf8mb4",
            "autocommit=false",
            "pool_recycle=3600",
            "pool_size=20",
            "max_overflow=30"
        ]

        separator = "&" if "?" in database_url else "?"
        return f"{database_url}{separator}{'&'.join(optimizations)}"

    return database_url

def setup_production_directories():
    """设置生产环境目录"""
    directories = [
        "/app/logs",
        "/app/uploads",
        "/app/temp",
        "/app/quarantine",
        "/app/backups"
    ]

    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)

        # 设置适当的权限
        os.chmod(directory, 0o755)

def validate_production_environment() -> Dict[str, bool]:
    """验证生产环境配置"""
    checks = {}

    # 检查必需的环境变量
    required_vars = [
        "SECRET_KEY", "JWT_SECRET_KEY", "DATABASE_URL",
        "REDIS_HOST", "WEAVIATE_HOST",
        "ALIYUN_ACCESS_KEY_ID", "ALIYUN_ACCESS_KEY_SECRET"
    ]

    for var in required_vars:
        checks[f"env_var_{var}"] = bool(os.getenv(var))

    # 检查目录权限
    directories = ["/app/logs", "/app/uploads", "/app/temp"]
    for directory in directories:
        checks[f"directory_{directory}"] = os.path.exists(directory) and os.access(directory, os.W_OK)

    # 检查端口可用性
    import socket

    def check_port(host: str, port: int) -> bool:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except:
            return False

    checks["redis_connection"] = check_port(
        os.getenv("REDIS_HOST", "localhost"),
        int(os.getenv("REDIS_PORT", 6379))
    )

    checks["weaviate_connection"] = check_port(
        os.getenv("WEAVIATE_HOST", "localhost"),
        int(os.getenv("WEAVIATE_PORT", 8080))
    )

    return checks

# 导出配置
production_config = get_production_config()
