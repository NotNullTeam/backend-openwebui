"""
系统监控服务

提供系统性能监控、健康检查、指标收集和告警功能
"""

import asyncio
import psutil
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

from open_webui.internal.db import get_db
from open_webui.models.cases import Case, CaseNode, CaseEdge
from open_webui.models.files import Files
from open_webui.models.knowledge import Knowledges
from open_webui.retrieval.vector.main import get_retrieval_vector_db

logger = logging.getLogger(__name__)

class AlertLevel(str, Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class SystemMetrics:
    """系统指标"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_gb: float
    memory_total_gb: float
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float
    network_sent_mb: float
    network_recv_mb: float
    active_connections: int

@dataclass
class DatabaseMetrics:
    """数据库指标"""
    timestamp: datetime
    total_cases: int
    total_nodes: int
    total_edges: int
    total_files: int
    total_knowledge: int
    avg_case_processing_time: float
    db_size_mb: float

@dataclass
class VectorDBMetrics:
    """向量数据库指标"""
    timestamp: datetime
    total_documents: int
    total_vectors: int
    index_size_mb: float
    avg_search_time_ms: float
    search_requests_per_minute: int

@dataclass
class Alert:
    """告警信息"""
    id: str
    level: AlertLevel
    title: str
    message: str
    timestamp: datetime
    resolved: bool = False
    metadata: Dict[str, Any] = None

class MonitoringService:
    """监控服务"""
    
    def __init__(self):
        self.alerts: List[Alert] = []
        self.metrics_history: List[SystemMetrics] = []
        self.db_metrics_history: List[DatabaseMetrics] = []
        self.vector_metrics_history: List[VectorDBMetrics] = []
        self.last_network_stats = None
        self.search_request_count = 0
        self.search_time_samples = []
        
        # 告警阈值
        self.thresholds = {
            'cpu_warning': 70.0,
            'cpu_critical': 90.0,
            'memory_warning': 80.0,
            'memory_critical': 95.0,
            'disk_warning': 85.0,
            'disk_critical': 95.0,
            'response_time_warning': 5000,  # ms
            'response_time_critical': 10000,  # ms
        }
    
    async def start_monitoring(self):
        """启动监控服务"""
        logger.info("启动系统监控服务")
        
        # 启动监控任务
        asyncio.create_task(self._system_metrics_collector())
        asyncio.create_task(self._database_metrics_collector())
        asyncio.create_task(self._vector_db_metrics_collector())
        asyncio.create_task(self._alert_processor())
        asyncio.create_task(self._cleanup_old_data())
    
    async def _system_metrics_collector(self):
        """系统指标收集器"""
        while True:
            try:
                metrics = await self._collect_system_metrics()
                self.metrics_history.append(metrics)
                
                # 检查告警条件
                await self._check_system_alerts(metrics)
                
                # 保持最近24小时的数据
                cutoff_time = datetime.now() - timedelta(hours=24)
                self.metrics_history = [m for m in self.metrics_history if m.timestamp > cutoff_time]
                
            except Exception as e:
                logger.error(f"系统指标收集错误: {e}")
            
            await asyncio.sleep(60)  # 每分钟收集一次
    
    async def _database_metrics_collector(self):
        """数据库指标收集器"""
        while True:
            try:
                metrics = await self._collect_database_metrics()
                self.db_metrics_history.append(metrics)
                
                # 保持最近24小时的数据
                cutoff_time = datetime.now() - timedelta(hours=24)
                self.db_metrics_history = [m for m in self.db_metrics_history if m.timestamp > cutoff_time]
                
            except Exception as e:
                logger.error(f"数据库指标收集错误: {e}")
            
            await asyncio.sleep(300)  # 每5分钟收集一次
    
    async def _vector_db_metrics_collector(self):
        """向量数据库指标收集器"""
        while True:
            try:
                metrics = await self._collect_vector_db_metrics()
                if metrics:
                    self.vector_metrics_history.append(metrics)
                
                # 保持最近24小时的数据
                cutoff_time = datetime.now() - timedelta(hours=24)
                self.vector_metrics_history = [m for m in self.vector_metrics_history if m.timestamp > cutoff_time]
                
            except Exception as e:
                logger.error(f"向量数据库指标收集错误: {e}")
            
            await asyncio.sleep(300)  # 每5分钟收集一次
    
    async def _collect_system_metrics(self) -> SystemMetrics:
        """收集系统指标"""
        # CPU使用率
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # 内存使用情况
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_used_gb = memory.used / (1024**3)
        memory_total_gb = memory.total / (1024**3)
        
        # 磁盘使用情况
        disk = psutil.disk_usage('/')
        disk_percent = (disk.used / disk.total) * 100
        disk_used_gb = disk.used / (1024**3)
        disk_total_gb = disk.total / (1024**3)
        
        # 网络统计
        network = psutil.net_io_counters()
        network_sent_mb = network.bytes_sent / (1024**2)
        network_recv_mb = network.bytes_recv / (1024**2)
        
        # 活跃连接数
        active_connections = len(psutil.net_connections())
        
        return SystemMetrics(
            timestamp=datetime.now(),
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_used_gb=memory_used_gb,
            memory_total_gb=memory_total_gb,
            disk_percent=disk_percent,
            disk_used_gb=disk_used_gb,
            disk_total_gb=disk_total_gb,
            network_sent_mb=network_sent_mb,
            network_recv_mb=network_recv_mb,
            active_connections=active_connections
        )
    
    async def _collect_database_metrics(self) -> DatabaseMetrics:
        """收集数据库指标"""
        try:
            with get_db() as db:
                # 统计各类数据数量
                total_cases = db.query(Case).count()
                total_nodes = db.query(CaseNode).count()
                total_edges = db.query(CaseEdge).count()
                
                # 文件和知识统计
                total_files = len(Files.get_files())
                total_knowledge = len(Knowledges.get_knowledge())
                
                # 平均处理时间（模拟）
                avg_case_processing_time = 2.5  # 秒
                
                # 数据库大小（估算）
                db_size_mb = (total_cases * 0.1 + total_nodes * 0.05 + total_edges * 0.02) * 1024
                
                return DatabaseMetrics(
                    timestamp=datetime.now(),
                    total_cases=total_cases,
                    total_nodes=total_nodes,
                    total_edges=total_edges,
                    total_files=total_files,
                    total_knowledge=total_knowledge,
                    avg_case_processing_time=avg_case_processing_time,
                    db_size_mb=db_size_mb
                )
        except Exception as e:
            logger.error(f"数据库指标收集失败: {e}")
            return DatabaseMetrics(
                timestamp=datetime.now(),
                total_cases=0,
                total_nodes=0,
                total_edges=0,
                total_files=0,
                total_knowledge=0,
                avg_case_processing_time=0,
                db_size_mb=0
            )
    
    async def _collect_vector_db_metrics(self) -> Optional[VectorDBMetrics]:
        """收集向量数据库指标"""
        try:
            vector_db = get_retrieval_vector_db()
            if not vector_db:
                return None
            
            # 获取向量数据库统计信息
            stats = getattr(vector_db, 'get_stats', lambda: {})()
            
            # 计算平均搜索时间
            avg_search_time = sum(self.search_time_samples) / len(self.search_time_samples) if self.search_time_samples else 0
            
            return VectorDBMetrics(
                timestamp=datetime.now(),
                total_documents=stats.get('total_documents', 0),
                total_vectors=stats.get('total_vectors', 0),
                index_size_mb=stats.get('index_size_mb', 0),
                avg_search_time_ms=avg_search_time,
                search_requests_per_minute=self.search_request_count
            )
        except Exception as e:
            logger.error(f"向量数据库指标收集失败: {e}")
            return None
    
    async def _check_system_alerts(self, metrics: SystemMetrics):
        """检查系统告警条件"""
        alerts_to_add = []
        
        # CPU告警
        if metrics.cpu_percent >= self.thresholds['cpu_critical']:
            alerts_to_add.append(Alert(
                id=f"cpu_critical_{int(time.time())}",
                level=AlertLevel.CRITICAL,
                title="CPU使用率严重过高",
                message=f"CPU使用率达到 {metrics.cpu_percent:.1f}%，超过临界阈值",
                timestamp=metrics.timestamp,
                metadata={"cpu_percent": metrics.cpu_percent}
            ))
        elif metrics.cpu_percent >= self.thresholds['cpu_warning']:
            alerts_to_add.append(Alert(
                id=f"cpu_warning_{int(time.time())}",
                level=AlertLevel.WARNING,
                title="CPU使用率过高",
                message=f"CPU使用率达到 {metrics.cpu_percent:.1f}%，超过警告阈值",
                timestamp=metrics.timestamp,
                metadata={"cpu_percent": metrics.cpu_percent}
            ))
        
        # 内存告警
        if metrics.memory_percent >= self.thresholds['memory_critical']:
            alerts_to_add.append(Alert(
                id=f"memory_critical_{int(time.time())}",
                level=AlertLevel.CRITICAL,
                title="内存使用率严重过高",
                message=f"内存使用率达到 {metrics.memory_percent:.1f}%，超过临界阈值",
                timestamp=metrics.timestamp,
                metadata={"memory_percent": metrics.memory_percent}
            ))
        elif metrics.memory_percent >= self.thresholds['memory_warning']:
            alerts_to_add.append(Alert(
                id=f"memory_warning_{int(time.time())}",
                level=AlertLevel.WARNING,
                title="内存使用率过高",
                message=f"内存使用率达到 {metrics.memory_percent:.1f}%，超过警告阈值",
                timestamp=metrics.timestamp,
                metadata={"memory_percent": metrics.memory_percent}
            ))
        
        # 磁盘告警
        if metrics.disk_percent >= self.thresholds['disk_critical']:
            alerts_to_add.append(Alert(
                id=f"disk_critical_{int(time.time())}",
                level=AlertLevel.CRITICAL,
                title="磁盘空间严重不足",
                message=f"磁盘使用率达到 {metrics.disk_percent:.1f}%，超过临界阈值",
                timestamp=metrics.timestamp,
                metadata={"disk_percent": metrics.disk_percent}
            ))
        elif metrics.disk_percent >= self.thresholds['disk_warning']:
            alerts_to_add.append(Alert(
                id=f"disk_warning_{int(time.time())}",
                level=AlertLevel.WARNING,
                title="磁盘空间不足",
                message=f"磁盘使用率达到 {metrics.disk_percent:.1f}%，超过警告阈值",
                timestamp=metrics.timestamp,
                metadata={"disk_percent": metrics.disk_percent}
            ))
        
        # 添加告警
        for alert in alerts_to_add:
            await self._add_alert(alert)
    
    async def _add_alert(self, alert: Alert):
        """添加告警"""
        # 检查是否已存在相同类型的未解决告警
        existing_alert = None
        for existing in self.alerts:
            if not existing.resolved and existing.title == alert.title:
                existing_alert = existing
                break
        
        if existing_alert:
            # 更新现有告警
            existing_alert.message = alert.message
            existing_alert.timestamp = alert.timestamp
            existing_alert.metadata = alert.metadata
        else:
            # 添加新告警
            self.alerts.append(alert)
            logger.warning(f"新告警: {alert.title} - {alert.message}")
    
    async def _alert_processor(self):
        """告警处理器"""
        while True:
            try:
                # 处理告警逻辑（发送通知、记录日志等）
                unresolved_alerts = [a for a in self.alerts if not a.resolved]
                
                if unresolved_alerts:
                    critical_count = len([a for a in unresolved_alerts if a.level == AlertLevel.CRITICAL])
                    warning_count = len([a for a in unresolved_alerts if a.level == AlertLevel.WARNING])
                    
                    if critical_count > 0:
                        logger.critical(f"系统存在 {critical_count} 个严重告警")
                    if warning_count > 0:
                        logger.warning(f"系统存在 {warning_count} 个警告告警")
                
            except Exception as e:
                logger.error(f"告警处理错误: {e}")
            
            await asyncio.sleep(60)  # 每分钟处理一次
    
    async def _cleanup_old_data(self):
        """清理旧数据"""
        while True:
            try:
                # 清理旧告警（保留7天）
                cutoff_time = datetime.now() - timedelta(days=7)
                self.alerts = [a for a in self.alerts if a.timestamp > cutoff_time]
                
                # 清理搜索时间样本
                self.search_time_samples = self.search_time_samples[-100:]  # 保留最近100个样本
                self.search_request_count = 0  # 重置计数
                
            except Exception as e:
                logger.error(f"数据清理错误: {e}")
            
            await asyncio.sleep(3600)  # 每小时清理一次
    
    def get_system_health(self) -> Dict[str, Any]:
        """获取系统健康状态"""
        if not self.metrics_history:
            return {"status": "unknown", "message": "暂无监控数据"}
        
        latest_metrics = self.metrics_history[-1]
        unresolved_alerts = [a for a in self.alerts if not a.resolved]
        
        # 判断健康状态
        critical_alerts = [a for a in unresolved_alerts if a.level == AlertLevel.CRITICAL]
        warning_alerts = [a for a in unresolved_alerts if a.level == AlertLevel.WARNING]
        
        if critical_alerts:
            status = "critical"
            message = f"系统存在 {len(critical_alerts)} 个严重问题"
        elif warning_alerts:
            status = "warning"
            message = f"系统存在 {len(warning_alerts)} 个警告"
        elif (latest_metrics.cpu_percent > 50 or 
              latest_metrics.memory_percent > 60 or 
              latest_metrics.disk_percent > 70):
            status = "degraded"
            message = "系统性能轻微下降"
        else:
            status = "healthy"
            message = "系统运行正常"
        
        return {
            "status": status,
            "message": message,
            "timestamp": latest_metrics.timestamp.isoformat(),
            "metrics": {
                "cpu_percent": latest_metrics.cpu_percent,
                "memory_percent": latest_metrics.memory_percent,
                "disk_percent": latest_metrics.disk_percent,
                "active_connections": latest_metrics.active_connections
            },
            "alerts": {
                "critical": len(critical_alerts),
                "warning": len(warning_alerts),
                "total_unresolved": len(unresolved_alerts)
            }
        }
    
    def get_performance_metrics(self, hours: int = 24) -> Dict[str, Any]:
        """获取性能指标"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        # 过滤指定时间范围内的数据
        recent_metrics = [m for m in self.metrics_history if m.timestamp > cutoff_time]
        recent_db_metrics = [m for m in self.db_metrics_history if m.timestamp > cutoff_time]
        recent_vector_metrics = [m for m in self.vector_metrics_history if m.timestamp > cutoff_time]
        
        if not recent_metrics:
            return {"error": "暂无性能数据"}
        
        # 计算统计信息
        cpu_values = [m.cpu_percent for m in recent_metrics]
        memory_values = [m.memory_percent for m in recent_metrics]
        disk_values = [m.disk_percent for m in recent_metrics]
        
        return {
            "time_range": f"最近{hours}小时",
            "system_metrics": {
                "cpu": {
                    "current": recent_metrics[-1].cpu_percent,
                    "average": sum(cpu_values) / len(cpu_values),
                    "max": max(cpu_values),
                    "min": min(cpu_values)
                },
                "memory": {
                    "current": recent_metrics[-1].memory_percent,
                    "average": sum(memory_values) / len(memory_values),
                    "max": max(memory_values),
                    "min": min(memory_values),
                    "used_gb": recent_metrics[-1].memory_used_gb,
                    "total_gb": recent_metrics[-1].memory_total_gb
                },
                "disk": {
                    "current": recent_metrics[-1].disk_percent,
                    "average": sum(disk_values) / len(disk_values),
                    "max": max(disk_values),
                    "min": min(disk_values),
                    "used_gb": recent_metrics[-1].disk_used_gb,
                    "total_gb": recent_metrics[-1].disk_total_gb
                }
            },
            "database_metrics": {
                "total_cases": recent_db_metrics[-1].total_cases if recent_db_metrics else 0,
                "total_nodes": recent_db_metrics[-1].total_nodes if recent_db_metrics else 0,
                "total_edges": recent_db_metrics[-1].total_edges if recent_db_metrics else 0,
                "total_files": recent_db_metrics[-1].total_files if recent_db_metrics else 0,
                "db_size_mb": recent_db_metrics[-1].db_size_mb if recent_db_metrics else 0
            },
            "vector_db_metrics": {
                "total_documents": recent_vector_metrics[-1].total_documents if recent_vector_metrics else 0,
                "total_vectors": recent_vector_metrics[-1].total_vectors if recent_vector_metrics else 0,
                "avg_search_time_ms": recent_vector_metrics[-1].avg_search_time_ms if recent_vector_metrics else 0
            }
        }
    
    def record_search_time(self, search_time_ms: float):
        """记录搜索时间"""
        self.search_time_samples.append(search_time_ms)
        self.search_request_count += 1
    
    def resolve_alert(self, alert_id: str) -> bool:
        """解决告警"""
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.resolved = True
                logger.info(f"告警已解决: {alert.title}")
                return True
        return False
    
    def get_alerts(self, resolved: Optional[bool] = None) -> List[Dict[str, Any]]:
        """获取告警列表"""
        alerts = self.alerts
        
        if resolved is not None:
            alerts = [a for a in alerts if a.resolved == resolved]
        
        return [
            {
                "id": alert.id,
                "level": alert.level.value,
                "title": alert.title,
                "message": alert.message,
                "timestamp": alert.timestamp.isoformat(),
                "resolved": alert.resolved,
                "metadata": alert.metadata or {}
            }
            for alert in sorted(alerts, key=lambda x: x.timestamp, reverse=True)
        ]

# 全局监控服务实例
monitoring_service = MonitoringService()

async def start_monitoring():
    """启动监控服务"""
    await monitoring_service.start_monitoring()
