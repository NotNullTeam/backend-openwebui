"""
AI日志解析服务

使用AI技术解析网络设备日志，提取关键信息和异常点。
从原backend完整迁移，增强智能分析能力。
"""

import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime

log = logging.getLogger(__name__)


class LogParsingService:
    """AI日志解析服务类"""

    def __init__(self):
        self._load_parsing_rules()

    def _load_parsing_rules(self):
        """加载日志解析规则"""
        self.parsing_rules = {
            'ospf_debug': {
                'patterns': {
                    'mtu_mismatch': r'MTU mismatch|packet too big|DD packet size exceeds|MTU不匹配',
                    'neighbor_stuck': r'ExStart|neighbor stuck|邻居状态|neighbor state',
                    'authentication_fail': r'authentication|认证失败|auth fail',
                    'area_mismatch': r'area mismatch|区域不匹配|different area',
                    'hello_timer': r'hello timer|hello interval|hello间隔'
                },
                'severities': {
                    'mtu_mismatch': 'high',
                    'neighbor_stuck': 'high',
                    'authentication_fail': 'high',
                    'area_mismatch': 'medium',
                    'hello_timer': 'medium'
                }
            },
            'bgp_debug': {
                'patterns': {
                    'session_fail': r'session failed|BGP session|会话失败|connection refused',
                    'as_mismatch': r'AS mismatch|AS number|AS号不匹配',
                    'route_limit': r'maximum routes|路由数量超限|route limit exceeded',
                    'update_error': r'update error|更新错误|malformed update'
                },
                'severities': {
                    'session_fail': 'high',
                    'as_mismatch': 'high',
                    'route_limit': 'medium',
                    'update_error': 'medium'
                }
            },
            'system_log': {
                'patterns': {
                    'interface_down': r'interface.*down|接口.*down|link down',
                    'memory_high': r'memory.*high|内存.*高|out of memory',
                    'cpu_high': r'cpu.*high|CPU.*高|cpu utilization',
                    'temperature': r'temperature|温度.*高|overheating'
                },
                'severities': {
                    'interface_down': 'high',
                    'memory_high': 'high',
                    'cpu_high': 'medium',
                    'temperature': 'high'
                }
            },
            'debug_ip_packet': {
                'patterns': {
                    'packet_drop': r'packet dropped|丢包|drop count',
                    'fragmentation': r'fragmentation|分片|fragment',
                    'checksum_error': r'checksum error|校验和错误|bad checksum',
                    'ttl_exceeded': r'TTL exceeded|TTL超时|time exceeded'
                },
                'severities': {
                    'packet_drop': 'high',
                    'fragmentation': 'medium',
                    'checksum_error': 'medium',
                    'ttl_exceeded': 'low'
                }
            }
        }

        # 增强的解析规则 - 添加更多设备类型和故障模式
        self.parsing_rules.update({
            'stp_debug': {
                'patterns': {
                    'loop_detected': r'loop detected|环路检测|spanning tree loop|STP loop',
                    'root_bridge_change': r'root bridge|根桥变更|topology change|拓扑变更',
                    'port_blocking': r'port.*blocking|端口.*阻塞|discarding state',
                    'bpdu_error': r'BPDU.*error|BPDU错误|invalid BPDU'
                },
                'severities': {
                    'loop_detected': 'high',
                    'root_bridge_change': 'medium',
                    'port_blocking': 'medium',
                    'bpdu_error': 'high'
                }
            },
            'vlan_debug': {
                'patterns': {
                    'vlan_mismatch': r'VLAN.*mismatch|VLAN不匹配|trunk.*error',
                    'native_vlan': r'native VLAN|本征VLAN|VLAN.*native',
                    'vtp_error': r'VTP.*error|VTP错误|VTP.*mismatch'
                },
                'severities': {
                    'vlan_mismatch': 'high',
                    'native_vlan': 'medium',
                    'vtp_error': 'medium'
                }
            },
            'security_log': {
                'patterns': {
                    'unauthorized_access': r'unauthorized|未授权|access denied|登录失败',
                    'ddos_attack': r'DDoS|flood|攻击|异常流量',
                    'intrusion_attempt': r'intrusion|入侵|malicious|恶意',
                    'certificate_error': r'certificate.*error|证书.*错误|SSL.*error'
                },
                'severities': {
                    'unauthorized_access': 'high',
                    'ddos_attack': 'high',
                    'intrusion_attempt': 'high',
                    'certificate_error': 'medium'
                }
            },
            'qos_debug': {
                'patterns': {
                    'bandwidth_exceeded': r'bandwidth.*exceeded|带宽.*超限|rate limit',
                    'queue_full': r'queue.*full|队列.*满|buffer.*full',
                    'traffic_shaping': r'traffic.*shaping|流量.*整形|policing'
                },
                'severities': {
                    'bandwidth_exceeded': 'medium',
                    'queue_full': 'high',
                    'traffic_shaping': 'low'
                }
            },
            'mpls_debug': {
                'patterns': {
                    'label_mismatch': r'label.*mismatch|标签.*不匹配|MPLS.*error',
                    'lsp_down': r'LSP.*down|LSP.*失败|tunnel.*down',
                    'ldp_session': r'LDP.*session|LDP.*会话|label distribution'
                },
                'severities': {
                    'label_mismatch': 'high',
                    'lsp_down': 'high',
                    'ldp_session': 'medium'
                }
            }
        })

        # 解决方案模板
        self.solution_templates = {
            'mtu_mismatch': {
                'action': '检查并统一接口MTU配置',
                'description': '确保OSPF邻居之间的接口MTU值一致',
                'commands': {
                    'Huawei': [
                        'display interface {interface}',
                        'interface {interface}',
                        'mtu {mtu_value}',
                        'commit'
                    ],
                    'Cisco': [
                        'show interface {interface}',
                        'configure terminal',
                        'interface {interface}',
                        'mtu {mtu_value}',
                        'end'
                    ],
                    'Juniper': [
                        'show interfaces {interface}',
                        'configure',
                        'set interfaces {interface} mtu {mtu_value}',
                        'commit'
                    ]
                }
            },
            'neighbor_stuck': {
                'action': '重启OSPF进程并检查配置',
                'description': '清除OSPF邻居状态并重新建立邻接关系',
                'commands': {
                    'Huawei': [
                        'reset ospf process',
                        'display ospf peer'
                    ],
                    'Cisco': [
                        'clear ip ospf process',
                        'show ip ospf neighbor'
                    ],
                    'Juniper': [
                        'restart routing',
                        'show ospf neighbor'
                    ]
                }
            },
            'interface_down': {
                'action': '检查接口物理状态和配置',
                'description': '排查接口物理连接和配置问题',
                'commands': {
                    'Huawei': [
                        'display interface {interface}',
                        'display interface {interface} statistics',
                        'interface {interface}',
                        'undo shutdown'
                    ],
                    'Cisco': [
                        'show interface {interface}',
                        'show interface {interface} statistics',
                        'configure terminal',
                        'interface {interface}',
                        'no shutdown'
                    ],
                    'Juniper': [
                        'show interfaces {interface}',
                        'show interfaces {interface} statistics',
                        'configure',
                        'delete interfaces {interface} disable'
                    ]
                }
            },
            'session_fail': {
                'action': '检查BGP会话配置和连通性',
                'description': '排查BGP邻居会话建立问题',
                'commands': {
                    'Huawei': [
                        'display bgp peer',
                        'ping {peer_ip}',
                        'display bgp routing-table peer {peer_ip} received-routes'
                    ],
                    'Cisco': [
                        'show bgp summary',
                        'ping {peer_ip}',
                        'show bgp neighbors {peer_ip} received-routes'
                    ],
                    'Juniper': [
                        'show bgp summary',
                        'ping {peer_ip}',
                        'show route receive-protocol bgp {peer_ip}'
                    ]
                }
            },
            'loop_detected': {
                'action': '检查并消除网络环路',
                'description': '识别并阻断造成环路的链路',
                'commands': {
                    'Huawei': [
                        'display stp brief',
                        'display stp interface {interface}',
                        'stp enable',
                        'stp mode rstp'
                    ],
                    'Cisco': [
                        'show spanning-tree',
                        'show spanning-tree interface {interface}',
                        'spanning-tree mode rapid-pvst',
                        'spanning-tree portfast'
                    ],
                    'Juniper': [
                        'show spanning-tree bridge',
                        'show spanning-tree interface {interface}',
                        'set protocols rstp'
                    ]
                }
            },
            'vlan_mismatch': {
                'action': '检查并修正VLAN配置',
                'description': '确保trunk链路两端VLAN配置一致',
                'commands': {
                    'Huawei': [
                        'display vlan',
                        'display interface {interface}',
                        'interface {interface}',
                        'port trunk allow-pass vlan {vlan_list}'
                    ],
                    'Cisco': [
                        'show vlan brief',
                        'show interface {interface} switchport',
                        'interface {interface}',
                        'switchport trunk allowed vlan {vlan_list}'
                    ],
                    'Juniper': [
                        'show vlans',
                        'show interfaces {interface}',
                        'set interfaces {interface} unit 0 family ethernet-switching vlan members {vlan_list}'
                    ]
                }
            },
            'unauthorized_access': {
                'action': '加强访问控制和安全策略',
                'description': '检查认证配置并启用安全防护',
                'commands': {
                    'Huawei': [
                        'display users',
                        'display acl all',
                        'aaa authentication-scheme default',
                        'acl number 2000'
                    ],
                    'Cisco': [
                        'show users',
                        'show access-lists',
                        'aaa authentication login default local',
                        'access-list 100 deny ip any any log'
                    ],
                    'Juniper': [
                        'show system users',
                        'show firewall',
                        'set system login user {username} authentication'
                    ]
                }
            },
            'bandwidth_exceeded': {
                'action': '调整QoS策略和带宽限制',
                'description': '优化流量控制和带宽分配',
                'commands': {
                    'Huawei': [
                        'display qos policy interface {interface}',
                        'display traffic-policy statistics interface {interface}',
                        'traffic-policy {policy_name} inbound'
                    ],
                    'Cisco': [
                        'show policy-map interface {interface}',
                        'show class-map',
                        'service-policy input {policy_name}'
                    ],
                    'Juniper': [
                        'show interfaces {interface} extensive',
                        'show firewall policer',
                        'set firewall policer {policer_name} bandwidth-limit {bandwidth}'
                    ]
                }
            },
            'lsp_down': {
                'action': '检查MPLS LSP配置和状态',
                'description': '排查MPLS隧道故障并重建LSP',
                'commands': {
                    'Huawei': [
                        'display mpls lsp',
                        'display mpls te tunnel',
                        'ping mpls te tunnel {tunnel_name}',
                        'refresh mpls te tunnel {tunnel_name}'
                    ],
                    'Cisco': [
                        'show mpls traffic-eng tunnels',
                        'show mpls forwarding-table',
                        'ping mpls traffic-eng tunnel {tunnel_name}',
                        'clear mpls traffic-eng tunnel {tunnel_name}'
                    ],
                    'Juniper': [
                        'show mpls lsp',
                        'show rsvp session',
                        'ping mpls rsvp {lsp_name}',
                        'clear mpls lsp {lsp_name}'
                    ]
                }
            }
        }

    def parse_log(
        self,
        log_type: str,
        vendor: str,
        log_content: str,
        context_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        解析技术日志

        Args:
            log_type: 日志类型
            vendor: 设备厂商
            log_content: 日志内容
            context_info: 上下文信息

        Returns:
            解析结果字典
        """
        try:
            # 检测异常
            anomalies = self._detect_anomalies(log_type, log_content, context_info)

            # 生成摘要
            summary = self._generate_summary(anomalies, log_type)

            # 生成建议操作
            suggested_actions = self._generate_suggested_actions(anomalies, vendor, context_info)

            # 提取关键信息
            key_events = self._extract_key_events(log_content, log_type)

            return {
                'summary': summary,
                'anomalies': anomalies,
                'suggestedActions': suggested_actions,
                'keyEvents': key_events,
                'logMetrics': {
                    'totalLines': len(log_content.split('\n')),
                    'anomalyCount': len(anomalies),
                    'timeRange': self._extract_time_range(log_content),
                    'vendor': vendor,
                    'logType': log_type
                }
            }

        except Exception as e:
            log.error(f"Log parsing error: {str(e)}")
            return {
                'summary': f'日志解析过程中发生错误：{str(e)}',
                'anomalies': [],
                'suggestedActions': [],
                'keyEvents': [],
                'logMetrics': {
                    'totalLines': 0,
                    'anomalyCount': 0,
                    'timeRange': None,
                    'vendor': vendor,
                    'logType': log_type
                }
            }

    def _detect_anomalies(
        self,
        log_type: str,
        log_content: str,
        context_info: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """检测日志中的异常"""
        anomalies = []

        if log_type not in self.parsing_rules:
            return anomalies

        rules = self.parsing_rules[log_type]

        for anomaly_type, pattern in rules['patterns'].items():
            matches = re.finditer(pattern, log_content, re.IGNORECASE | re.MULTILINE)

            for match in matches:
                # 提取上下文
                line_start = max(0, log_content.rfind('\n', 0, match.start()) + 1)
                line_end = log_content.find('\n', match.end())
                if line_end == -1:
                    line_end = len(log_content)

                evidence_line = log_content[line_start:line_end].strip()

                anomaly = {
                    'type': anomaly_type.upper(),
                    'severity': rules['severities'].get(anomaly_type, 'medium'),
                    'location': self._extract_location(evidence_line, context_info),
                    'description': self._get_anomaly_description(anomaly_type),
                    'evidence': [evidence_line],
                    'timestamp': self._extract_timestamp(evidence_line),
                    'lineNumber': log_content[:match.start()].count('\n') + 1
                }

                anomalies.append(anomaly)

        # 去重相似的异常
        return self._deduplicate_anomalies(anomalies)

    def _generate_summary(self, anomalies: List[Dict[str, Any]], log_type: str) -> str:
        """生成日志分析摘要"""
        if not anomalies:
            return f"分析完成，{log_type}日志中未发现明显异常"

        high_severity = [a for a in anomalies if a['severity'] == 'high']
        medium_severity = [a for a in anomalies if a['severity'] == 'medium']

        summary_parts = []

        if high_severity:
            summary_parts.append(f"发现{len(high_severity)}个高严重性问题")

        if medium_severity:
            summary_parts.append(f"发现{len(medium_severity)}个中等严重性问题")

        # 总结主要问题类型
        problem_types = {}
        for anomaly in anomalies:
            problem_type = anomaly['type']
            if problem_type not in problem_types:
                problem_types[problem_type] = 0
            problem_types[problem_type] += 1

        if problem_types:
            main_problems = sorted(problem_types.items(), key=lambda x: x[1], reverse=True)[:2]
            problem_desc = ', '.join([f"{prob[0].lower().replace('_', ' ')}" for prob in main_problems])
            summary_parts.append(f"主要问题涉及：{problem_desc}")

        return "；".join(summary_parts)

    def _generate_suggested_actions(
        self,
        anomalies: List[Dict[str, Any]],
        vendor: str,
        context_info: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """生成建议操作"""
        actions = []
        processed_types = set()

        for anomaly in anomalies:
            anomaly_type = anomaly['type'].lower()

            if anomaly_type in processed_types:
                continue

            processed_types.add(anomaly_type)

            if anomaly_type in self.solution_templates:
                template = self.solution_templates[anomaly_type]

                action = {
                    'action': template['action'],
                    'priority': anomaly['severity'],
                    'description': template['description'],
                    'commands': template['commands'].get(vendor, template['commands'].get('Huawei', [])),
                    'relatedAnomalies': [anomaly['type']]
                }

                # 应用上下文信息
                if context_info:
                    action['commands'] = self._apply_context_to_commands(
                        action['commands'], context_info
                    )

                actions.append(action)

        # 按优先级排序
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        actions.sort(key=lambda x: priority_order.get(x['priority'], 3))

        return actions

    def _extract_key_events(self, log_content: str, log_type: str) -> List[Dict[str, Any]]:
        """提取关键事件"""
        events = []
        lines = log_content.split('\n')

        for i, line in enumerate(lines):
            timestamp = self._extract_timestamp(line)
            if timestamp:
                event = {
                    'timestamp': timestamp,
                    'lineNumber': i + 1,
                    'content': line.strip(),
                    'severity': self._determine_line_severity(line)
                }
                events.append(event)

        # 只返回重要事件
        important_events = [e for e in events if e['severity'] in ['high', 'medium']]
        return important_events[-20:]  # 最近20个重要事件

    def _extract_location(self, evidence_line: str, context_info: Optional[Dict[str, Any]]) -> str:
        """从证据行中提取位置信息"""
        # 尝试提取接口名称
        interface_patterns = [
            r'interface\s+(\S+)',
            r'GigabitEthernet(\d+/\d+/\d+)',
            r'GE(\d+/\d+/\d+)',
            r'Ethernet(\d+/\d+)',
            r'接口\s+(\S+)'
        ]

        for pattern in interface_patterns:
            match = re.search(pattern, evidence_line, re.IGNORECASE)
            if match:
                return match.group(1)

        # 如果没有找到，使用上下文信息
        if context_info and 'deviceModel' in context_info:
            return context_info['deviceModel']

        return 'Unknown'

    def _get_anomaly_description(self, anomaly_type: str) -> str:
        """获取异常描述"""
        descriptions = {
            'mtu_mismatch': 'MTU配置不匹配导致邻居无法正常建立',
            'neighbor_stuck': 'OSPF邻居状态异常，无法正常收敛',
            'authentication_fail': '认证失败，检查认证密钥配置',
            'area_mismatch': 'OSPF区域配置不匹配',
            'hello_timer': 'Hello定时器配置不匹配',
            'session_fail': 'BGP会话建立失败',
            'as_mismatch': 'AS号配置不匹配',
            'interface_down': '接口状态异常，链路可能中断',
            'memory_high': '内存使用率过高，可能影响系统稳定性',
            'cpu_high': 'CPU使用率过高，可能影响性能',
            'packet_drop': '数据包丢弃，检查网络质量',
            'fragmentation': '数据包分片，可能影响传输效率'
        }
        return descriptions.get(anomaly_type, f'检测到{anomaly_type}类型异常')

    def _extract_timestamp(self, line: str) -> Optional[str]:
        """从日志行中提取时间戳"""
        timestamp_patterns = [
            r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}',
            r'\d{2}:\d{2}:\d{2}',
            r'\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}'
        ]

        for pattern in timestamp_patterns:
            match = re.search(pattern, line)
            if match:
                return match.group(0)

        return None

    def _extract_time_range(self, log_content: str) -> Optional[Dict[str, str]]:
        """提取日志时间范围"""
        lines = log_content.split('\n')

        first_timestamp = None
        last_timestamp = None

        for line in lines:
            timestamp = self._extract_timestamp(line)
            if timestamp:
                if not first_timestamp:
                    first_timestamp = timestamp
                last_timestamp = timestamp

        if first_timestamp and last_timestamp:
            return {
                'start': first_timestamp,
                'end': last_timestamp
            }

        return None

    def _determine_line_severity(self, line: str) -> str:
        """判断日志行的严重性"""
        line_lower = line.lower()

        if any(keyword in line_lower for keyword in ['error', 'fail', 'down', 'critical']):
            return 'high'
        elif any(keyword in line_lower for keyword in ['warning', 'warn', 'timeout']):
            return 'medium'
        else:
            return 'low'

    def _deduplicate_anomalies(self, anomalies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """去重相似的异常"""
        unique_anomalies = []
        seen_types = set()

        for anomaly in anomalies:
            key = f"{anomaly['type']}_{anomaly['location']}"
            if key not in seen_types:
                seen_types.add(key)
                unique_anomalies.append(anomaly)

        return unique_anomalies

    def _apply_context_to_commands(
        self,
        commands: List[str],
        context_info: Dict[str, Any]
    ) -> List[str]:
        """应用上下文信息到命令"""
        processed_commands = []

        for command in commands:
            try:
                processed_command = command.format(**context_info)
                processed_commands.append(processed_command)
            except KeyError:
                processed_commands.append(command)

        return processed_commands


# 全局服务实例
log_parsing_service = LogParsingService()
