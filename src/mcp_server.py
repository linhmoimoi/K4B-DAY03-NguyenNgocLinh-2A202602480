"""Small MCP/JSON-RPC boundary used by the ReAct agent."""

import json
import sys
from typing import Any, Dict, List

from tools import TOOLS_SCHEMA, dispatch_tool_call


if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


class MCPAcademicServer:
    """MCP-compatible server exposing both baseline and VinBus tools."""

    def __init__(self, server_name: str = "vinbus-customer-service-mcp-server"):
        self.server_name = server_name
        self.version = "2026.1.0"

    def list_tools(self) -> List[Dict[str, Any]]:
        """Return every published tool schema."""
        return TOOLS_SCHEMA

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch a tool and wrap its JSON result in a stable JSON-RPC object."""
        if not isinstance(arguments, dict):
            result = {"status": "INVALID_ARGUMENT", "error": "arguments phải là object JSON."}
        else:
            raw_result = dispatch_tool_call(tool_name, arguments)
            try:
                result = json.loads(raw_result)
                if not isinstance(result, dict):
                    result = {
                        "status": "EXECUTION_ERROR",
                        "error": "Tool trả về JSON không phải object.",
                    }
            except (TypeError, json.JSONDecodeError) as exc:
                result = {"status": "EXECUTION_ERROR", "error": f"JSON tool không hợp lệ: {exc}"}

        return {
            "jsonrpc": "2.0",
            "server": self.server_name,
            "tool": tool_name,
            "result": result,
        }


if __name__ == "__main__":
    server = MCPAcademicServer()
    print("==========================================================")
    print(f"🔌 MCP SERVER: {server.server_name} (Version: {server.version})")
    print("==========================================================")
    print(f"📦 Số lượng Tools công bố: {len(server.list_tools())}")
    smoke = server.call_tool(
        "bus_route_query",
        {"origin": "KĐT Ocean Park", "destination": "Bến xe Mỹ Đình"},
    )
    print(json.dumps(smoke, ensure_ascii=False, indent=2))
