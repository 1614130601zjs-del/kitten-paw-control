"""
小猫爪 MCP 控制服务器 - /mcp 纯 POST 接入版
"""
import json
import os
import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
import uvicorn

ACCOUNT_ID = os.environ.get("CACHITO_ACCOUNT_ID", "你的账号ID")
DEVICE_ID = 13
code = None

def calc_hex(intensity: int) -> str:
    val = round(intensity * 0.75 + 25)
    return format(min(max(val, 0), 255), '02x')

async def toy_join(invite_code: str) -> str:
    global code
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://www.youtao.top/api/appRemote/joinRemote",
            json={"account": ACCOUNT_ID, "code": invite_code}
        )
        result = r.json()
        if result.get("code") == 0:
            code = invite_code
            return "加入成功！邀请码已就绪。"
        return f"加入失败: {result.get('message')}。请重新生成邀请码。"

async def toy_control(action: str, intensity: int = 30, duration: int = 3000) -> str:
    global code
    if not code:
        return "还没加入远程。先让用户在APP生成邀请码，然后调用toy_join。"
    hex_val = calc_hex(intensity)
    if action == "stop":
        cmd = json.dumps([{
            "command": "710001**-0400-####-0601-0200000000",
            "time": "500",
            "progress": 0
        }])
    elif action == "vibrate":
        cmd = json.dumps([{
            "command": f"710001**-0400-####-0302-{hex_val}00000000",
            "time": str(duration),
            "progress": 0
        }])
    else:
        return "action 只能是 'vibrate' 或 'stop'"
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://www.youtao.top/api/appRemote/sendCommand",
            json={
                "command": {"sxCommand": cmd, "deviceId": DEVICE_ID},
                "account": ACCOUNT_ID,
                "code": code
            }
        )
        result = r.json()
        if result.get("code") == 0:
            if action == "stop":
                return "已停止 ✓"
            return f"震动 强度{intensity}%，持续{duration/1000}秒 ✓"
        return f"指令失败: {result.get('message')}"

async def toy_state() -> str:
    return f"邀请码: {code or '未设置'}"

async def handle_rpc(request: Request):
    # 打印调试
    raw = await request.body()
    print(f"[DEBUG] 收到请求: {raw.decode()}")

    try:
        body = json.loads(raw)
    except Exception:
        return JSONResponse(
            {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}},
            status_code=400
        )

    method = body.get("method")
    params = body.get("params", {})
    req_id = body.get("id")

    # 1. initialize
    if method == "initialize":
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "Kitten Paw", "version": "1.0"},
                "capabilities": {"tools": {}}
            }
        })

    # 2. notifications/initialized — 规范要求返回 202 空响应或 200 空对象
    if method == "notifications/initialized":
        return JSONResponse({}, status_code=202)

    # 3. tools/list
    if method == "tools/list":
        tools = [
            {
                "name": "toy_join",
                "description": "通过邀请码加入远程控制",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "invite_code": {"type": "string", "description": "APP生成的邀请码"}
                    },
                    "required": ["invite_code"]
                }
            },
            {
                "name": "toy_control",
                "description": "控制设备震动或停止",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["vibrate", "stop"], "description": "动作类型"},
                        "intensity": {"type": "integer", "default": 30, "description": "强度 0-100"},
                        "duration": {"type": "integer", "default": 3000, "description": "持续时间(ms)"}
                    },
                    "required": ["action"]
                }
            },
            {
                "name": "toy_state",
                "description": "查看当前连接状态",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": tools}
        })

    # 4. tools/call — 你原来这里写的是 pass，导致直接 Method not found！
    if method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        if tool_name == "toy_join":
            invite_code = arguments.get("invite_code", "")
            result_text = await toy_join(invite_code)
        elif tool_name == "toy_control":
            action = arguments.get("action", "")
            intensity = arguments.get("intensity", 30)
            duration = arguments.get("duration", 3000)
            result_text = await toy_control(action, intensity, duration)
        elif tool_name == "toy_state":
            result_text = await toy_state()
        else:
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32602, "message": f"Unknown tool: {tool_name}"}
            })

        return JSONResponse({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [{"type": "text", "text": result_text}],
                "isError": False
            }
        })

    # 未识别的方法
    return JSONResponse({
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"}
    })

# GET /mcp — 某些客户端会探测，返回说明即可
async def handle_mcp_get(request: Request):
    return JSONResponse({
        "status": "MCP server running",
        "endpoint": "/mcp",
        "method": "POST only (JSON-RPC)",
        "protocolVersion": "2024-11-05"
    })

middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )
]

app = Starlette(
    middleware=middleware,
    routes=[
        Route("/mcp", handle_rpc, methods=["POST"]),
        Route("/mcp", handle_mcp_get, methods=["GET"]),
        Route("/", lambda r: JSONResponse({"status": "ok", "mcp_endpoint": "/mcp"}), methods=["GET"])
    ]
)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
