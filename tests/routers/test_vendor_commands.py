"""
Test cases for vendor_commands router endpoints - comprehensive coverage for all 2 endpoints
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from httpx import AsyncClient
import json


@pytest.fixture
def mock_verified_user():
    return MagicMock(
        id="user123",
        name="Test User",
        email="user@example.com",
        role="user"
    )


@pytest.fixture
def mock_case():
    return {
        "id": "case123",
        "title": "Network Issue",
        "user_id": "user123",
        "nodes": [
            {
                "id": "node123",
                "type": "diagnosis",
                "content": "Router configuration issue"
            }
        ]
    }


@pytest.fixture
def mock_vendor_commands():
    return {
        "vendor": "cisco",
        "commands": [
            {
                "command": "show ip interface brief",
                "description": "Display interface status and IP addresses",
                "category": "diagnostic"
            },
            {
                "command": "show running-config",
                "description": "Display current configuration",
                "category": "diagnostic"
            },
            {
                "command": "configure terminal",
                "description": "Enter configuration mode",
                "category": "configuration"
            }
        ],
        "explanation": "These commands will help diagnose the router configuration issue",
        "warnings": ["Ensure you have proper backup before making configuration changes"]
    }


class TestGetNodeVendorCommands:
    """Test get node vendor commands endpoint"""
    
    async def test_get_node_vendor_commands_cisco(self, async_client: AsyncClient, mock_verified_user, mock_case, mock_vendor_commands):
        """Test GET /cases/{case_id}/nodes/{node_id}/commands for Cisco"""
        with patch("open_webui.routers.vendor_commands.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.vendor_commands.Cases.get_case_by_id", return_value=mock_case):
                with patch("open_webui.routers.vendor_commands.detect_vendor", return_value="cisco"):
                    with patch("open_webui.routers.vendor_commands.get_cisco_commands") as mock_cisco:
                        mock_cisco.return_value = mock_vendor_commands["commands"]
                        response = await async_client.get(
                            "/api/v1/vendor_commands/cases/case123/nodes/node123/commands",
                            params={"vendor": "cisco"}
                        )
                        assert response.status_code == 200
                        data = response.json()
                        assert data["vendor"] == "cisco"
                        assert len(data["commands"]) == 3
                        assert data["commands"][0]["command"] == "show ip interface brief"
    
    async def test_get_node_vendor_commands_huawei(self, async_client: AsyncClient, mock_verified_user, mock_case):
        """Test GET /cases/{case_id}/nodes/{node_id}/commands for Huawei"""
        with patch("open_webui.routers.vendor_commands.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.vendor_commands.Cases.get_case_by_id", return_value=mock_case):
                with patch("open_webui.routers.vendor_commands.detect_vendor", return_value="huawei"):
                    with patch("open_webui.routers.vendor_commands.get_huawei_commands") as mock_huawei:
                        mock_huawei.return_value = [
                            {
                                "command": "display ip interface brief",
                                "description": "Display interface status",
                                "category": "diagnostic"
                            }
                        ]
                        response = await async_client.get(
                            "/api/v1/vendor_commands/cases/case123/nodes/node123/commands",
                            params={"vendor": "huawei"}
                        )
                        assert response.status_code == 200
                        data = response.json()
                        assert data["vendor"] == "huawei"
                        assert len(data["commands"]) == 1
    
    async def test_get_node_vendor_commands_auto_detect(self, async_client: AsyncClient, mock_verified_user, mock_case):
        """Test GET /cases/{case_id}/nodes/{node_id}/commands with auto-detection"""
        with patch("open_webui.routers.vendor_commands.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.vendor_commands.Cases.get_case_by_id", return_value=mock_case):
                with patch("open_webui.routers.vendor_commands.detect_vendor", return_value="cisco"):
                    with patch("open_webui.routers.vendor_commands.get_cisco_commands") as mock_cisco:
                        mock_cisco.return_value = []
                        response = await async_client.get(
                            "/api/v1/vendor_commands/cases/case123/nodes/node123/commands"
                        )
                        assert response.status_code == 200
                        data = response.json()
                        assert "vendor" in data
    
    async def test_get_node_vendor_commands_case_not_found(self, async_client: AsyncClient, mock_verified_user):
        """Test GET /cases/{case_id}/nodes/{node_id}/commands with non-existent case"""
        with patch("open_webui.routers.vendor_commands.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.vendor_commands.Cases.get_case_by_id", return_value=None):
                response = await async_client.get(
                    "/api/v1/vendor_commands/cases/invalid/nodes/node123/commands"
                )
                assert response.status_code == 404
                assert "案例不存在" in response.json()["detail"]
    
    async def test_get_node_vendor_commands_node_not_found(self, async_client: AsyncClient, mock_verified_user, mock_case):
        """Test GET /cases/{case_id}/nodes/{node_id}/commands with non-existent node"""
        with patch("open_webui.routers.vendor_commands.get_verified_user", return_value=mock_verified_user):
            mock_case_no_node = {**mock_case, "nodes": []}
            with patch("open_webui.routers.vendor_commands.Cases.get_case_by_id", return_value=mock_case_no_node):
                response = await async_client.get(
                    "/api/v1/vendor_commands/cases/case123/nodes/invalid/commands"
                )
                assert response.status_code == 404
                assert "节点不存在" in response.json()["detail"]
    
    async def test_get_node_vendor_commands_unauthorized(self, async_client: AsyncClient, mock_verified_user, mock_case):
        """Test GET /cases/{case_id}/nodes/{node_id}/commands with unauthorized user"""
        with patch("open_webui.routers.vendor_commands.get_verified_user", return_value=mock_verified_user):
            unauthorized_case = {**mock_case, "user_id": "other_user"}
            with patch("open_webui.routers.vendor_commands.Cases.get_case_by_id", return_value=unauthorized_case):
                response = await async_client.get(
                    "/api/v1/vendor_commands/cases/case123/nodes/node123/commands"
                )
                assert response.status_code == 403
                assert "无权访问" in response.json()["detail"]


class TestGenerateVendorCommands:
    """Test generate vendor commands endpoint"""
    
    async def test_generate_vendor_commands_cisco(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /commands/generate for Cisco"""
        with patch("open_webui.routers.vendor_commands.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.vendor_commands.generate_cisco_solution") as mock_generate:
                mock_generate.return_value = {
                    "commands": [
                        "interface GigabitEthernet0/1",
                        "ip address 192.168.1.1 255.255.255.0",
                        "no shutdown"
                    ],
                    "explanation": "Configure IP address on interface"
                }
                response = await async_client.post(
                    "/api/v1/vendor_commands/commands/generate",
                    params={
                        "vendor": "cisco",
                        "problem_description": "Configure IP address on GigabitEthernet0/1"
                    }
                )
                assert response.status_code == 200
                data = response.json()
                assert data["vendor"] == "cisco"
                assert "commands" in data
                assert len(data["commands"]) == 3
    
    async def test_generate_vendor_commands_huawei(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /commands/generate for Huawei"""
        with patch("open_webui.routers.vendor_commands.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.vendor_commands.generate_huawei_solution") as mock_generate:
                mock_generate.return_value = {
                    "commands": [
                        "interface GigabitEthernet0/0/1",
                        "ip address 192.168.1.1 255.255.255.0",
                        "undo shutdown"
                    ],
                    "explanation": "Configure IP address on interface"
                }
                response = await async_client.post(
                    "/api/v1/vendor_commands/commands/generate",
                    params={
                        "vendor": "huawei",
                        "problem_description": "Configure IP address"
                    }
                )
                assert response.status_code == 200
                data = response.json()
                assert data["vendor"] == "huawei"
                assert "commands" in data
    
    async def test_generate_vendor_commands_general(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /commands/generate for general vendor"""
        with patch("open_webui.routers.vendor_commands.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.vendor_commands.generate_general_solution") as mock_generate:
                mock_generate.return_value = {
                    "commands": ["Check interface status", "Verify IP configuration"],
                    "explanation": "General troubleshooting steps"
                }
                response = await async_client.post(
                    "/api/v1/vendor_commands/commands/generate",
                    params={
                        "vendor": "general",
                        "problem_description": "Network connectivity issue"
                    }
                )
                assert response.status_code == 200
                data = response.json()
                assert data["vendor"] == "general"
    
    async def test_generate_vendor_commands_unsupported_vendor(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /commands/generate with unsupported vendor"""
        with patch("open_webui.routers.vendor_commands.get_verified_user", return_value=mock_verified_user):
            response = await async_client.post(
                "/api/v1/vendor_commands/commands/generate",
                params={
                    "vendor": "unknown_vendor",
                    "problem_description": "Test problem"
                }
            )
            assert response.status_code == 400
            assert "不支持的厂商" in response.json()["detail"]
    
    async def test_generate_vendor_commands_empty_description(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /commands/generate with empty problem description"""
        with patch("open_webui.routers.vendor_commands.get_verified_user", return_value=mock_verified_user):
            response = await async_client.post(
                "/api/v1/vendor_commands/commands/generate",
                params={
                    "vendor": "cisco",
                    "problem_description": ""
                }
            )
            assert response.status_code in [400, 422]
    
    async def test_generate_vendor_commands_llm_error(self, async_client: AsyncClient, mock_verified_user):
        """Test POST /commands/generate with LLM error"""
        with patch("open_webui.routers.vendor_commands.get_verified_user", return_value=mock_verified_user):
            with patch("open_webui.routers.vendor_commands.generate_cisco_solution", side_effect=Exception("LLM error")):
                response = await async_client.post(
                    "/api/v1/vendor_commands/commands/generate",
                    params={
                        "vendor": "cisco",
                        "problem_description": "Test problem"
                    }
                )
                assert response.status_code == 500
                assert "生成厂商命令失败" in response.json()["detail"]
