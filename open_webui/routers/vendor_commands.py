"""
厂商命令生成路由
支持多厂商网络设备命令生成
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, List, Optional
from pydantic import BaseModel
import logging

from open_webui.utils.auth import get_verified_user
from open_webui.models.cases import Case as Cases

log = logging.getLogger(__name__)
router = APIRouter()


class VendorCommand(BaseModel):
    """厂商命令模型"""
    vendor: str
    command: str
    description: str
    syntax: str
    example: str
    category: str


class CommandResponse(BaseModel):
    """命令响应模型"""
    node_id: str
    vendor: str
    problem_type: str
    commands: List[VendorCommand]
    explanation: str


# 厂商命令模板库
VENDOR_COMMANDS = {
    "cisco": {
        "ip_conflict": [
            {
                "command": "show ip arp",
                "description": "查看ARP表，确认IP地址对应的MAC地址",
                "syntax": "show ip arp [ip-address]",
                "example": "show ip arp 192.168.1.100",
                "category": "diagnostic"
            },
            {
                "command": "clear arp-cache",
                "description": "清除ARP缓存",
                "syntax": "clear arp-cache [interface]",
                "example": "clear arp-cache",
                "category": "remediation"
            },
            {
                "command": "show mac address-table",
                "description": "查看MAC地址表",
                "syntax": "show mac address-table [address mac-address]",
                "example": "show mac address-table address 00:1a:2b:3c:4d:5e",
                "category": "diagnostic"
            }
        ],
        "routing_issue": [
            {
                "command": "show ip route",
                "description": "查看路由表",
                "syntax": "show ip route [destination]",
                "example": "show ip route 10.0.0.0",
                "category": "diagnostic"
            },
            {
                "command": "show ip protocols",
                "description": "查看路由协议配置",
                "syntax": "show ip protocols",
                "example": "show ip protocols",
                "category": "diagnostic"
            },
            {
                "command": "show ip ospf neighbor",
                "description": "查看OSPF邻居状态",
                "syntax": "show ip ospf neighbor [detail]",
                "example": "show ip ospf neighbor detail",
                "category": "diagnostic"
            }
        ],
        "vpn_issue": [
            {
                "command": "show crypto isakmp sa",
                "description": "查看IKE SA状态",
                "syntax": "show crypto isakmp sa [detail]",
                "example": "show crypto isakmp sa detail",
                "category": "diagnostic"
            },
            {
                "command": "show crypto ipsec sa",
                "description": "查看IPSec SA状态",
                "syntax": "show crypto ipsec sa [peer ip-address]",
                "example": "show crypto ipsec sa peer 203.0.113.1",
                "category": "diagnostic"
            },
            {
                "command": "clear crypto session",
                "description": "清除加密会话",
                "syntax": "clear crypto session [remote ip-address]",
                "example": "clear crypto session remote 203.0.113.1",
                "category": "remediation"
            }
        ]
    },
    "huawei": {
        "ip_conflict": [
            {
                "command": "display arp",
                "description": "查看ARP表信息",
                "syntax": "display arp [ip-address]",
                "example": "display arp 192.168.1.100",
                "category": "diagnostic"
            },
            {
                "command": "reset arp",
                "description": "清除ARP表项",
                "syntax": "reset arp [interface interface-type interface-number]",
                "example": "reset arp interface GigabitEthernet 0/0/1",
                "category": "remediation"
            },
            {
                "command": "display mac-address",
                "description": "查看MAC地址表",
                "syntax": "display mac-address [mac-address]",
                "example": "display mac-address 00-1a-2b-3c-4d-5e",
                "category": "diagnostic"
            }
        ],
        "routing_issue": [
            {
                "command": "display ip routing-table",
                "description": "查看路由表",
                "syntax": "display ip routing-table [ip-address]",
                "example": "display ip routing-table 10.0.0.0",
                "category": "diagnostic"
            },
            {
                "command": "display ospf peer",
                "description": "查看OSPF邻居",
                "syntax": "display ospf peer [brief|detail]",
                "example": "display ospf peer detail",
                "category": "diagnostic"
            },
            {
                "command": "display bgp peer",
                "description": "查看BGP邻居",
                "syntax": "display bgp peer [ip-address]",
                "example": "display bgp peer 10.1.1.1",
                "category": "diagnostic"
            }
        ],
        "vpn_issue": [
            {
                "command": "display ike sa",
                "description": "查看IKE SA信息",
                "syntax": "display ike sa [remote ip-address]",
                "example": "display ike sa remote 203.0.113.1",
                "category": "diagnostic"
            },
            {
                "command": "display ipsec sa",
                "description": "查看IPSec SA信息",
                "syntax": "display ipsec sa [brief|detail]",
                "example": "display ipsec sa detail",
                "category": "diagnostic"
            },
            {
                "command": "reset ike sa",
                "description": "重置IKE SA",
                "syntax": "reset ike sa [remote ip-address]",
                "example": "reset ike sa remote 203.0.113.1",
                "category": "remediation"
            }
        ]
    },
    "juniper": {
        "ip_conflict": [
            {
                "command": "show arp",
                "description": "显示ARP缓存",
                "syntax": "show arp [hostname host | interface interface-name]",
                "example": "show arp interface ge-0/0/0",
                "category": "diagnostic"
            },
            {
                "command": "clear arp",
                "description": "清除ARP缓存",
                "syntax": "clear arp [hostname host | interface interface-name]",
                "example": "clear arp interface ge-0/0/0",
                "category": "remediation"
            }
        ],
        "routing_issue": [
            {
                "command": "show route",
                "description": "显示路由表",
                "syntax": "show route [destination-prefix]",
                "example": "show route 10.0.0.0/8",
                "category": "diagnostic"
            },
            {
                "command": "show ospf neighbor",
                "description": "显示OSPF邻居",
                "syntax": "show ospf neighbor [detail]",
                "example": "show ospf neighbor detail",
                "category": "diagnostic"
            }
        ]
    }
}


def get_problem_type_from_node(node_data: dict) -> str:
    """从节点数据推断问题类型"""
    content = node_data.get("content", "").lower()
    metadata = node_data.get("metadata", {})

    # 基于内容关键词判断
    if any(keyword in content for keyword in ["ip conflict", "ip冲突", "地址冲突", "arp"]):
        return "ip_conflict"
    elif any(keyword in content for keyword in ["route", "routing", "路由", "ospf", "bgp"]):
        return "routing_issue"
    elif any(keyword in content for keyword in ["vpn", "ipsec", "ike", "tunnel", "隧道"]):
        return "vpn_issue"

    # 基于元数据判断
    problem_type = metadata.get("problem_type", "")
    if problem_type:
        return problem_type

    return "general"


@router.get("/cases/{case_id}/nodes/{node_id}/commands")
async def get_node_vendor_commands(
    case_id: str,
    node_id: str,
    user=Depends(get_verified_user)
) -> CommandResponse:
    """
    获取节点的厂商特定命令

    根据节点内容和厂商信息，生成相应的诊断和修复命令
    """
    try:
        # 获取案例
        case = Cases.get_case_by_id_and_user_id(case_id, user.id)
        if not case:
            raise HTTPException(status_code=404, detail="案例不存在")

        # 获取节点信息
        nodes = case.get("nodes", [])
        node = None
        for n in nodes:
            if n.get("id") == node_id:
                node = n
                break

        if not node:
            raise HTTPException(status_code=404, detail="节点不存在")

        # 获取厂商信息
        metadata = node.get("metadata", {})
        vendor = metadata.get("vendor", "cisco").lower()

        # 推断问题类型
        problem_type = get_problem_type_from_node(node)

        # 获取对应的命令集
        vendor_cmds = VENDOR_COMMANDS.get(vendor, VENDOR_COMMANDS["cisco"])
        command_set = vendor_cmds.get(problem_type, vendor_cmds.get("ip_conflict", []))

        # 构建命令列表
        commands = []
        for cmd in command_set:
            commands.append(VendorCommand(
                vendor=vendor,
                command=cmd["command"],
                description=cmd["description"],
                syntax=cmd["syntax"],
                example=cmd["example"],
                category=cmd["category"]
            ))

        # 生成说明
        explanation = f"基于{vendor.upper()}设备的{problem_type.replace('_', ' ')}问题，建议执行以下命令进行诊断和修复。"

        return CommandResponse(
            node_id=node_id,
            vendor=vendor,
            problem_type=problem_type,
            commands=commands,
            explanation=explanation
        )

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"获取厂商命令失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取厂商命令失败: {str(e)}")


@router.post("/commands/generate")
async def generate_vendor_commands(
    vendor: str,
    problem_description: str,
    user=Depends(get_verified_user)
) -> Dict:
    """
    根据厂商和问题描述生成命令

    动态生成厂商特定的诊断和修复命令
    """
    try:
        vendor = vendor.lower()

        # 分析问题类型
        problem_type = "general"
        desc_lower = problem_description.lower()

        if any(keyword in desc_lower for keyword in ["ip", "conflict", "arp", "冲突"]):
            problem_type = "ip_conflict"
        elif any(keyword in desc_lower for keyword in ["route", "routing", "路由"]):
            problem_type = "routing_issue"
        elif any(keyword in desc_lower for keyword in ["vpn", "ipsec", "tunnel"]):
            problem_type = "vpn_issue"

        # 获取命令
        vendor_cmds = VENDOR_COMMANDS.get(vendor, VENDOR_COMMANDS["cisco"])
        commands = vendor_cmds.get(problem_type, [])

        return {
            "vendor": vendor,
            "problem_type": problem_type,
            "commands": commands,
            "supported_vendors": list(VENDOR_COMMANDS.keys())
        }

    except Exception as e:
        log.error(f"生成厂商命令失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"生成厂商命令失败: {str(e)}")
