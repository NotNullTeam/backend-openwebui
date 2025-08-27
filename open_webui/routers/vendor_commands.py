"""
厂商命令生成路由
支持多厂商网络设备命令生成
"""

import json
import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from open_webui.utils.auth import get_verified_user
from open_webui.internal.db import get_db
from open_webui.models.cases import Case, CaseNode


log = logging.getLogger(__name__)
router = APIRouter()


class VendorCommand(BaseModel):
    vendor: str
    command: str
    description: str
    syntax: str
    example: str
    category: str  # diagnostic | remediation | info


class CommandResponse(BaseModel):
    node_id: str
    vendor: str
    problem_type: str
    commands: List[VendorCommand]
    explanation: str


# 厂商命令模板库
VENDOR_COMMANDS: Dict[str, Dict[str, List[Dict[str, str]]]] = {
    "cisco": {
        "ip_conflict": [
            {
                "command": "show ip arp",
                "description": "查看 ARP 表，确认 IP 与 MAC 对应关系",
                "syntax": "show ip arp [ip-address]",
                "example": "show ip arp 192.168.1.100",
                "category": "diagnostic",
            },
            {
                "command": "clear arp-cache",
                "description": "清除 ARP 缓存",
                "syntax": "clear arp-cache [interface]",
                "example": "clear arp-cache",
                "category": "remediation",
            },
            {
                "command": "show mac address-table",
                "description": "查看 MAC 地址表",
                "syntax": "show mac address-table [address mac-address]",
                "example": "show mac address-table address 0001.2233.4455",
                "category": "diagnostic",
            },
        ],
        "routing_issue": [
            {
                "command": "show ip route",
                "description": "查看路由表，确认目的网段路由",
                "syntax": "show ip route [destination]",
                "example": "show ip route 10.0.0.0",
                "category": "diagnostic",
            },
            {
                "command": "show ip protocols",
                "description": "查看路由协议配置",
                "syntax": "show ip protocols",
                "example": "show ip protocols",
                "category": "diagnostic",
            },
            {
                "command": "show ip ospf neighbor",
                "description": "查看 OSPF 邻居状态",
                "syntax": "show ip ospf neighbor [detail]",
                "example": "show ip ospf neighbor detail",
                "category": "diagnostic",
            },
        ],
        "vpn_issue": [
            {
                "command": "show crypto isakmp sa",
                "description": "查看 IKE SA 状态",
                "syntax": "show crypto isakmp sa [detail]",
                "example": "show crypto isakmp sa detail",
                "category": "diagnostic",
            },
            {
                "command": "show crypto ipsec sa",
                "description": "查看 IPSec SA 状态",
                "syntax": "show crypto ipsec sa [peer ip-address]",
                "example": "show crypto ipsec sa peer 203.0.113.1",
                "category": "diagnostic",
            },
            {
                "command": "clear crypto session",
                "description": "清除加密会话",
                "syntax": "clear crypto session [remote ip-address]",
                "example": "clear crypto session remote 203.0.113.1",
                "category": "remediation",
            },
        ],
    },
    "huawei": {
        "ip_conflict": [
            {
                "command": "display arp",
                "description": "查看 ARP 表信息",
                "syntax": "display arp [ip-address]",
                "example": "display arp 192.168.1.100",
                "category": "diagnostic",
            },
            {
                "command": "reset arp",
                "description": "清除 ARP 表项",
                "syntax": "reset arp [interface interface-type interface-number]",
                "example": "reset arp interface GigabitEthernet 0/0/1",
                "category": "remediation",
            },
            {
                "command": "display mac-address",
                "description": "查看 MAC 地址表",
                "syntax": "display mac-address [mac-address]",
                "example": "display mac-address 0001-2233-4455",
                "category": "diagnostic",
            },
        ],
        "routing_issue": [
            {
                "command": "display ip routing-table",
                "description": "查看路由表",
                "syntax": "display ip routing-table [ip-address]",
                "example": "display ip routing-table 10.0.0.0",
                "category": "diagnostic",
            },
            {
                "command": "display ospf peer",
                "description": "查看OSPF邻居",
                "syntax": "display ospf peer [brief|detail]",
                "example": "display ospf peer detail",
                "category": "diagnostic",
            },
            {
                "command": "display bgp peer",
                "description": "查看BGP邻居",
                "syntax": "display bgp peer [ip-address]",
                "example": "display bgp peer 10.1.1.1",
                "category": "diagnostic",
            },
        ],
        "vpn_issue": [
            {
                "command": "display ike sa",
                "description": "查看IKE SA信息",
                "syntax": "display ike sa [remote ip-address]",
                "example": "display ike sa remote 203.0.113.1",
                "category": "diagnostic",
            },
            {
                "command": "display ipsec sa",
                "description": "查看IPSec SA信息",
                "syntax": "display ipsec sa [brief|detail]",
                "example": "display ipsec sa detail",
                "category": "diagnostic",
            },
            {
                "command": "reset ike sa",
                "description": "重置IKE SA",
                "syntax": "reset ike sa [remote ip-address]",
                "example": "reset ike sa remote 203.0.113.1",
                "category": "remediation",
            },
        ],
    },
    "juniper": {
        "ip_conflict": [
            {
                "command": "show arp",
                "description": "显示ARP缓存",
                "syntax": "show arp [hostname host | interface interface-name]",
                "example": "show arp interface ge-0/0/0",
                "category": "diagnostic",
            },
            {
                "command": "clear arp",
                "description": "清除ARP缓存",
                "syntax": "clear arp [hostname host | interface interface-name]",
                "example": "clear arp interface ge-0/0/0",
                "category": "remediation",
            },
        ],
        "routing_issue": [
            {
                "command": "show route",
                "description": "显示路由表",
                "syntax": "show route [destination-prefix]",
                "example": "show route 10.0.0.0/8",
                "category": "diagnostic",
            },
            {
                "command": "show ospf neighbor",
                "description": "显示OSPF邻居",
                "syntax": "show ospf neighbor [detail]",
                "example": "show ospf neighbor detail",
                "category": "diagnostic",
            },
        ],
    }
}


def get_problem_type_from_text(text: str) -> str:
    t = (text or "").lower()
    if any(k in t for k in ["ip conflict", "ip冲突", "地址冲突", "arp"]):
        return "ip_conflict"
    if any(k in t for k in ["route", "routing", "路由", "ospf", "bgp"]):
        return "routing_issue"
    if any(k in t for k in ["vpn", "ipsec", "ike", "tunnel", "隧道"]):
        return "vpn_issue"
    return "ip_conflict"


@router.get("/cases/{case_id}/nodes/{node_id}/commands")
async def get_node_vendor_commands(
    case_id: str,
    node_id: str,
    user=Depends(get_verified_user),
) -> CommandResponse:
    """根据节点内容与厂商信息生成命令建议。"""
    try:
        # 校验案例归属
        with get_db() as db:
            c = db.query(Case).filter(Case.id == case_id).first()
            if not c or c.user_id != user.id:
                raise HTTPException(status_code=404, detail="案例不存在")

            n = db.query(CaseNode).filter(CaseNode.id == node_id, CaseNode.case_id == case_id).first()
            if not n:
                raise HTTPException(status_code=404, detail="节点不存在")

            # 解析节点文本
            text = ""
            try:
                obj = json.loads(n.content or "")
                if isinstance(obj, dict):
                    text = str(obj.get("text") or obj.get("analysis") or obj.get("answer") or "")
                else:
                    text = str(obj)
            except Exception:
                text = n.content or ""

            # 厂商与问题类型
            meta = n.metadata_ or {}
            vendor = str(meta.get("vendor") or c.vendor or "cisco").lower()
            problem_type = str(meta.get("problem_type") or get_problem_type_from_text(text))

            # 获取命令模板
            vendor_cmds = VENDOR_COMMANDS.get(vendor, VENDOR_COMMANDS["cisco"])
            command_set = vendor_cmds.get(problem_type, vendor_cmds.get("ip_conflict", []))
            commands = [
                VendorCommand(
                    vendor=vendor,
                    command=item["command"],
                    description=item["description"],
                    syntax=item["syntax"],
                    example=item["example"],
                    category=item.get("category", "diagnostic"),
                )
                for item in command_set
            ]

            explanation = f"基于 {vendor.upper()} 设备的 {problem_type.replace('_',' ')} 问题，建议执行以下命令进行诊断/修复。"

            return CommandResponse(
                node_id=node_id,
                vendor=vendor,
                problem_type=problem_type,
                commands=commands,
                explanation=explanation,
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
    user=Depends(get_verified_user),
) -> Dict:
    """根据厂商和问题描述生成命令建议"""
    try:
        vendor = (vendor or "cisco").lower()
        desc_lower = (problem_description or "").lower()
        if any(k in desc_lower for k in ["ip", "conflict", "arp", "冲突"]):
            problem_type = "ip_conflict"
        elif any(k in desc_lower for k in ["route", "routing", "路由", "ospf", "bgp"]):
            problem_type = "routing_issue"
        elif any(k in desc_lower for k in ["vpn", "ipsec", "tunnel", "隧道"]):
            problem_type = "vpn_issue"
        else:
            problem_type = "ip_conflict"

        # 获取命令
        vendor_cmds = VENDOR_COMMANDS.get(vendor, VENDOR_COMMANDS["cisco"])
        commands = vendor_cmds.get(problem_type, [])

        return {
            "vendor": vendor,
            "problem_type": problem_type,
            "commands": commands,
            "supported_vendors": list(VENDOR_COMMANDS.keys()),
        }

    except Exception as e:
        log.error(f"生成厂商命令失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"生成厂商命令失败: {str(e)}")
