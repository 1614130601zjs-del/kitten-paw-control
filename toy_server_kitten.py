"""
Cachito 小猫爪 MCP 控制服务器
路径: /mcp  (streamable_http)
"""

import json
import httpx
import os
from contextlib import asynccontextmanager
from mcp.server import Server
from mcp.types import Tool, TextContent, CallToolRequestParams

# ========== 配置区（通过环境变量或修改这里）==========
ACCOUNT_ID = os.environ.get("CACHITO_ACCOUNT_ID", "52575934")
DEVICE_ID = 13
# ===================================================

code = None


def calc_hex(intensity):
    """小猫爪强度公式: round(强度 × 0.75 + 25)"""
    val = round(intensity * 0.75 + 25)
    return format(min(max(val, 0), 255), '02x')


@asynccontextmanager
async def app_lifespan(server: Server):
    yield {"account_id": ACCOUNT_ID, "device_id": DEVICE_ID}


server = Server(
    "Kitten Paw Control",
    version="1.0.0",
    instructions="控制小猫爪的MCP服务器",
    lifespan=app_lifespan,
)


async def on_list_tools(ctx, params):
    return {
        "tools": [
            Tool(
                name="toy_join",
                description="加入远程控制。用户先在Cachito APP生成邀请码，然后调用此函数。",
                input_schema={
                    "type": "object",
                    "properties": {
                        "invite_code": {"type": "string", "description": "6位邀请码"}
                    },
                    "required": ["invite_code"]
                }
            ),
            Tool(
                name="toy_control",
                description="控制小猫爪。",
                input_schema={
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "description": "动作：vibrate=震动, stop=停止",
                            "enum": ["vibrate", "stop"]
                        },
                        "intensity": {
                            "type": "integer",
                            "description": "强度 0-100，默认30",
                            "minimum": 0,
                            "maximum": 100,
                            "default": 30
                        },
                        "duration": {
                            "type": "integer",
                            "description": "持续时间（毫秒），默认3000=3秒",
                            "default": 3000
                        }
                    },
                    "required": ["action"]
                }
            ),
            Tool(
                name="toy_state",
                description="查看当前连接状态。",
                input_schema={"type": "object", "properties": {}}
            ),
        ]
    }


async def on_call_tool(ctx, params: CallToolRequestParams):
    global code
    name = params.name
    args = params.arguments or {}

    if name == "toy_join":
        invite_code = args.get("invite_code", "")
        r = await httpx.AsyncClient().post(
            "https://www.youtao.top/api/appRemote/joinRemote",
            json={"account": ACCOUNT_ID, "code": invite_code}
        )
        result = r.json()
        if result.get("code") == 0:
            code = invite_code
            return {"content": [TextContent(type="text", text="加入成功！邀请码已就绪。")]}
        return {"content": [TextContent(type="text", text=f"加入失败: {result.get('message')}。请重新生成邀请码。")]}

    elif name == "toy_control":
        action = args.get("action", "")
        intensity = args.get("intensity", 30)
        duration = args.get("duration", 3000)

        if not code:
            return {"content": [TextContent(type="text", text="还没加入远程。先让用户在APP生成邀请码，然后调用toy_join。")]}

        hex_val = calc_hex(intensity)

        if action == "stop":
            stop_cmd = json.dumps([{"command": "710001**-0400-####-0601-0200000000",
                                     "time": "500", "progress": 0}])
            client = httpx.AsyncClient()
            await client.post("https://www.youtao.top/api/appRemote/sendCommand",
                json={"command": {"sxCommand": stop_cmd, "deviceId": DEVICE_ID},
                      "account": ACCOUNT_ID, "code": code})
            return {"content": [TextContent(type="text", text="已停止震动。")]}

        elif action == "vibrate":
            cmd = json.dumps([{"command": f"710001**-0400-####-0302-{hex_val}00000000",
                               "time": str(duration), "progress": 0}])
            r = await httpx.AsyncClient().post(
                "https://www.youtao.top/api/appRemote/sendCommand",
                json={"command": {"sxCommand": cmd, "deviceId": DEVICE_ID},
                      "account": ACCOUNT_ID, "code": code}
            )
            result = r.json()
            if result.get("code") == 0:
                return {"content": [TextContent(type="text", text=f"震动 强度{intensity}%，持续{duration/1000}秒。")]}
            return {"content": [TextContent(type="text", text=f"指令失败: {result.get('message')}")]}

        else:
            return {"content": [TextContent(type="text", text="action只能是'vibrate'(震动)或'stop'(停止)。")]}

    elif name == "toy_state":
        return {"content": [TextContent(type="text", text=f"邀请码: {code or '未设置'} | 账号: {ACCOUNT_ID} | 设备ID: {DEVICE_ID}")]}

    return {"content": [TextContent(type="text", text="未知工具")]}


server.on_list_tools = on_list_tools
server.on_call_tool = on_call_tool

app = server.streamable_http_app(
    streamable_http_path="/mcp",
    host="0.0.0.0",
)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
