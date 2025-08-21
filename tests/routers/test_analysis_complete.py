"""
智能分析模块完整测试套件
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, Mock, AsyncMock
from datetime import datetime
import json

from open_webui.main import app


client = TestClient(app)


class TestAnalysisEndpoints:
    """智能分析所有端点的完整测试"""
    
    # ===== POST /analysis/logs 日志分析 =====
    @patch('open_webui.routers.analysis_migrated.get_verified_user')
    @patch('open_webui.routers.analysis_migrated.analyze_logs')
    def test_analyze_logs(self, mock_analyze, mock_user):
        """测试日志分析"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_analyze.return_value = {
            "summary": "发现3个潜在问题",
            "issues": [
                {
                    "type": "error",
                    "severity": "high",
                    "message": "频繁的连接超时",
                    "count": 15,
                    "pattern": "timeout after 30s",
                    "recommendation": "检查网络连接或增加超时时间"
                },
                {
                    "type": "warning",
                    "severity": "medium",
                    "message": "内存使用率偏高",
                    "count": 8,
                    "recommendation": "考虑优化内存使用或扩容"
                }
            ],
            "statistics": {
                "total_lines": 1000,
                "error_count": 23,
                "warning_count": 45
            }
        }
        
        response = client.post(
            "/api/v1/analysis/logs",
            json={
                "logs": "2024-01-20 ERROR: Connection timeout...",
                "time_range": "1h"
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["issues"]) == 2
        assert data["issues"][0]["severity"] == "high"
    
    # ===== POST /analysis/network 网络分析 =====
    @patch('open_webui.routers.analysis_migrated.get_verified_user')
    @patch('open_webui.routers.analysis_migrated.analyze_network_issue')
    def test_analyze_network_issue(self, mock_analyze, mock_user):
        """测试网络问题分析"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_analyze.return_value = {
            "diagnosis": {
                "problem": "路由环路",
                "confidence": 0.85,
                "affected_devices": ["Router-A", "Router-B"],
                "root_cause": "OSPF配置错误导致的路由环路"
            },
            "solution": {
                "steps": [
                    "检查Router-A的OSPF配置",
                    "验证Router-B的路由表",
                    "修正OSPF区域配置"
                ],
                "commands": [
                    "show ip ospf neighbor",
                    "show ip route ospf",
                    "clear ip ospf process"
                ]
            },
            "related_knowledge": [
                {"title": "OSPF故障排查指南", "relevance": 0.92},
                {"title": "路由环路检测方法", "relevance": 0.88}
            ]
        }
        
        response = client.post(
            "/api/v1/analysis/network",
            json={
                "description": "网络出现环路，数据包TTL耗尽",
                "topology": {"devices": ["Router-A", "Router-B"]},
                "symptoms": ["packet loss", "high latency"]
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["diagnosis"]["problem"] == "路由环路"
        assert len(data["solution"]["steps"]) == 3
    
    # ===== POST /analysis/performance 性能分析 =====
    @patch('open_webui.routers.analysis_migrated.get_verified_user')
    @patch('open_webui.routers.analysis_migrated.analyze_performance')
    def test_analyze_performance(self, mock_analyze, mock_user):
        """测试性能分析"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_analyze.return_value = {
            "metrics": {
                "cpu_usage": {"avg": 75, "peak": 95, "trend": "increasing"},
                "memory_usage": {"avg": 60, "peak": 80, "trend": "stable"},
                "disk_io": {"read": 100, "write": 50, "unit": "MB/s"},
                "network_throughput": {"in": 800, "out": 600, "unit": "Mbps"}
            },
            "bottlenecks": [
                {
                    "resource": "CPU",
                    "severity": "high",
                    "impact": "响应时间增加30%",
                    "recommendation": "优化CPU密集型任务或增加CPU资源"
                }
            ],
            "forecast": {
                "cpu_exhaustion": "2天内可能达到100%",
                "memory_exhaustion": "稳定，无风险",
                "disk_space": "剩余空间充足"
            }
        }
        
        response = client.post(
            "/api/v1/analysis/performance",
            json={
                "metrics": {"cpu": [75, 80, 85, 90, 95]},
                "timeframe": "1h",
                "threshold_alerts": True
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["metrics"]["cpu_usage"]["peak"] == 95
        assert len(data["bottlenecks"]) > 0
    
    # ===== POST /analysis/security 安全分析 =====
    @patch('open_webui.routers.analysis_migrated.get_verified_user')
    @patch('open_webui.routers.analysis_migrated.analyze_security_events')
    def test_analyze_security_events(self, mock_analyze, mock_user):
        """测试安全事件分析"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_analyze.return_value = {
            "threat_level": "medium",
            "events": [
                {
                    "type": "brute_force",
                    "severity": "high",
                    "source_ip": "192.168.1.100",
                    "target": "SSH服务",
                    "attempts": 150,
                    "status": "blocked"
                },
                {
                    "type": "port_scan",
                    "severity": "low",
                    "source_ip": "10.0.0.50",
                    "ports_scanned": [22, 80, 443, 3306]
                }
            ],
            "recommendations": [
                "启用fail2ban防护",
                "限制SSH访问IP白名单",
                "部署入侵检测系统"
            ]
        }
        
        response = client.post(
            "/api/v1/analysis/security",
            json={
                "log_type": "firewall",
                "events": ["failed login attempts", "port scanning"],
                "time_window": "24h"
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["threat_level"] == "medium"
        assert len(data["events"]) == 2
    
    # ===== POST /analysis/config 配置分析 =====
    @patch('open_webui.routers.analysis_migrated.get_verified_user')
    @patch('open_webui.routers.analysis_migrated.analyze_configuration')
    def test_analyze_configuration(self, mock_analyze, mock_user):
        """测试配置分析"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_analyze.return_value = {
            "compliance": {
                "score": 85,
                "passed": 17,
                "failed": 3,
                "warnings": 5
            },
            "issues": [
                {
                    "rule": "密码复杂度",
                    "status": "failed",
                    "message": "密码最小长度应为12位",
                    "fix": "set password-policy min-length 12"
                },
                {
                    "rule": "日志审计",
                    "status": "warning",
                    "message": "未启用详细日志记录"
                }
            ],
            "best_practices": [
                "启用双因素认证",
                "定期备份配置",
                "使用配置版本控制"
            ]
        }
        
        response = client.post(
            "/api/v1/analysis/config",
            json={
                "config_text": "enable password cisco123...",
                "device_type": "cisco_ios",
                "check_compliance": True
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["compliance"]["score"] == 85
        assert len(data["issues"]) > 0
    
    # ===== GET /analysis/recommendations 获取推荐 =====
    @patch('open_webui.routers.analysis_migrated.get_verified_user')
    @patch('open_webui.routers.analysis_migrated.get_recommendations')
    def test_get_recommendations(self, mock_get_rec, mock_user):
        """测试获取智能推荐"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_get_rec.return_value = {
            "case_based": [
                {
                    "title": "类似问题解决方案",
                    "relevance": 0.95,
                    "case_id": "case-456",
                    "summary": "OSPF邻居关系建立失败的解决方法"
                }
            ],
            "knowledge_based": [
                {
                    "title": "OSPF配置最佳实践",
                    "doc_id": "doc-789",
                    "relevance": 0.88
                }
            ],
            "action_items": [
                "检查MTU设置是否一致",
                "验证区域ID配置",
                "确认认证参数匹配"
            ]
        }
        
        response = client.get(
            "/api/v1/analysis/recommendations?case_id=case-123",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["case_based"]) > 0
        assert len(data["action_items"]) == 3
    
    # ===== POST /analysis/predict 预测分析 =====
    @patch('open_webui.routers.analysis_migrated.get_verified_user')
    @patch('open_webui.routers.analysis_migrated.predict_issues')
    def test_predict_issues(self, mock_predict, mock_user):
        """测试问题预测"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_predict.return_value = {
            "predictions": [
                {
                    "issue": "磁盘空间不足",
                    "probability": 0.78,
                    "time_to_event": "48小时",
                    "impact": "服务中断",
                    "prevention": "清理日志文件或扩容磁盘"
                },
                {
                    "issue": "证书即将过期",
                    "probability": 1.0,
                    "time_to_event": "7天",
                    "impact": "HTTPS服务不可用",
                    "prevention": "更新SSL证书"
                }
            ],
            "risk_score": 75,
            "recommended_actions": [
                {"priority": "high", "action": "更新SSL证书"},
                {"priority": "medium", "action": "磁盘空间清理"}
            ]
        }
        
        response = client.post(
            "/api/v1/analysis/predict",
            json={
                "metrics": {"disk_usage": 85, "cert_expiry_days": 7},
                "lookback_days": 30
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["predictions"]) == 2
        assert data["risk_score"] == 75
    
    # ===== POST /analysis/compare 对比分析 =====
    @patch('open_webui.routers.analysis_migrated.get_verified_user')
    @patch('open_webui.routers.analysis_migrated.compare_configurations')
    def test_compare_configurations(self, mock_compare, mock_user):
        """测试配置对比分析"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_compare.return_value = {
            "differences": [
                {
                    "section": "interface",
                    "device_a": "ip address 192.168.1.1 255.255.255.0",
                    "device_b": "ip address 192.168.1.2 255.255.255.0",
                    "impact": "IP地址冲突风险"
                },
                {
                    "section": "routing",
                    "device_a": "ospf cost 10",
                    "device_b": "ospf cost 20",
                    "impact": "路由路径不对称"
                }
            ],
            "similarity_score": 0.85,
            "recommendations": [
                "统一OSPF cost值以确保路由对称",
                "检查IP地址分配避免冲突"
            ]
        }
        
        response = client.post(
            "/api/v1/analysis/compare",
            json={
                "config_a": "interface config...",
                "config_b": "interface config...",
                "focus_areas": ["routing", "security"]
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["differences"]) == 2
        assert data["similarity_score"] == 0.85
    
    # ===== POST /analysis/root-cause 根因分析 =====
    @patch('open_webui.routers.analysis_migrated.get_verified_user')
    @patch('open_webui.routers.analysis_migrated.analyze_root_cause')
    def test_root_cause_analysis(self, mock_analyze, mock_user):
        """测试根因分析"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_analyze.return_value = {
            "root_cause": {
                "description": "交换机端口双工模式不匹配",
                "confidence": 0.92,
                "evidence": [
                    "大量的Late Collision错误",
                    "CRC错误持续增加",
                    "重传率异常高"
                ]
            },
            "impact_chain": [
                "端口双工不匹配",
                "数据包冲突增加",
                "重传率上升",
                "网络性能下降"
            ],
            "resolution": {
                "immediate": "手动设置双工模式为全双工",
                "long_term": "启用自动协商并监控",
                "commands": ["interface gi0/1", "duplex full", "speed 1000"]
            }
        }
        
        response = client.post(
            "/api/v1/analysis/root-cause",
            json={
                "symptoms": ["packet loss", "high retransmission"],
                "affected_devices": ["Switch-A"],
                "timeline": "started 2 hours ago"
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["root_cause"]["confidence"] == 0.92
        assert len(data["impact_chain"]) == 4
    
    # ===== 边界条件和异常测试 =====
    @patch('open_webui.routers.analysis_migrated.get_verified_user')
    def test_empty_log_analysis(self, mock_user):
        """测试空日志分析"""
        mock_user.return_value = MagicMock(id="user-123")
        
        response = client.post(
            "/api/v1/analysis/logs",
            json={"logs": ""},
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 400
        assert "日志内容不能为空" in response.json()["detail"]
    
    @patch('open_webui.routers.analysis_migrated.get_verified_user')
    @patch('open_webui.routers.analysis_migrated.analyze_network_issue')
    def test_analysis_timeout(self, mock_analyze, mock_user):
        """测试分析超时"""
        mock_user.return_value = MagicMock(id="user-123")
        mock_analyze.side_effect = TimeoutError("Analysis timeout")
        
        response = client.post(
            "/api/v1/analysis/network",
            json={"description": "complex issue"},
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 504
        assert "分析超时" in response.json()["detail"]
    
    @patch('open_webui.routers.analysis_migrated.get_verified_user')
    def test_invalid_config_format(self, mock_user):
        """测试无效配置格式"""
        mock_user.return_value = MagicMock(id="user-123")
        
        response = client.post(
            "/api/v1/analysis/config",
            json={
                "config_text": "invalid@#$config",
                "device_type": "unknown_device"
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 422
        assert "不支持的设备类型" in response.json()["detail"]
