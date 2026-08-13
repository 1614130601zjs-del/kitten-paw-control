async def handle_rpc(request: Request):
    # ===== 打印原始请求 =====
    raw_body = await request.body()
    print(f"[DEBUG] Received: {raw_body.decode()}")
    # =======================
    try:
        body = await request.json()
    except:
        return JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}, status_code=400)

    # ... 后面代码不变 ...
"""
小猫爪 MCP 控制服务器 - 自定义 HTTP 端点 (/mcp)
支持 initialize 握手
"""
import json
import os
import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
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
    try:
        body = await request.json()
    except:
        return JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}, status_code=400)

    method = body.get("method")
    params = body.get("params", {})
    req_id = body.get("id")   # 可能为 None（通知）

    # ---------- 处理 initialize（必须） ----------
    if method == "initialize":
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "0.1.0",
                "serverInfo": {
                    "name": "Kitten Paw Control",
                    "version": "1.0.0"
                },
                "capabilities": {
                    "tools": {}
                }
            }
        })

    # ---------- 处理 notifications/initialized（无需响应） ----------
    if method == "notifications/initialized":
        # 通知不需要id，返回空响应
        return JSONResponse({}, status_code=200)

    # ---------- 处理 tools/list ----------
    if method == "tools/list":
        tools = [
            {
                "name": "toy_join",
                "description": "加入远程控制。参数: invite_code (字符串)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "invite_code": {"type": "string", "description": "6位邀请码"}
                    },
                    "required": ["invite_code"]
                }
            },
            {
                "name": "toy_control",
                "description": "控制小猫爪。action: 'vibrate' 或 'stop'，intensity 0-100，duration 毫秒",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["vibrate", "stop"]},
                        "intensity": {"type": "integer", "default": 30},
                        "duration": {"type": "integer", "default": 3000}
                    },
                    "required": ["action"]
                }
            },
            {
                "name": "toy_state",
                "description": "查看当前连接状态",
                "inputSchema": {"type": "object", "properties": {}}
            }
        ]
        return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools}})

    # ---------- 处理 tools/call ----------
    if method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        if tool_name == "toy_join":
            invite_code = arguments.get("invite_code")
            if not invite_code:
                return JSONResponse({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32602, "message": "Missing invite_code"}})
            result = await toy_join(invite_code)
            return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": result}]}})
        elif tool_name == "toy_control":
            action = arguments.get("action")
            intensity = arguments.get("intensity", 30)
            duration = arguments.get("duration", 3000)
            if action not in ["vibrate", "stop"]:
                return JSONResponse({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32602, "message": "Invalid action"}})
            result = await toy_control(action, intensity, duration)
            return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": result}]}})
        elif tool_name == "toy_state":
            result = await toy_state()
            return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": result}]}})
        else:
            return JSONResponse({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Tool not found"}})

    # ---------- 其他方法一律返回 Method not found ----------
    return JSONResponse({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Method not found"}})

app = Starlette(routes=[
    Route("/mcp", handle_rpc, methods=["POST"]),
    Route("/", lambda r: JSONResponse({"status": "ok"}), methods=["GET"])
])

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
