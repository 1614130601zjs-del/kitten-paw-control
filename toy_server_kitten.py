
    
    """
小猫爪 MCP 控制服务器 - Render 部署专用 (Streamable HTTP 端点: /mcp)
"""
import json
import os
import httpx
from mcp.server.fastmcp import FastMCP  # 使用官方 mcp 包

ACCOUNT_ID = os.environ.get("CACHITO_ACCOUNT_ID", "你的账号ID")
DEVICE_ID = 13

mcp = FastMCP("Kitten Paw Control", version="1.0.0")
code = None

def calc_hex(intensity: int) -> str:
    val = round(intensity * 0.75 + 25)
    return format(min(max(val, 0), 255), '02x')

@mcp.tool()
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

@mcp.tool()
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

@mcp.tool()
async def toy_state() -> str:
    return f"邀请码: {code or '未设置'}"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8001))
    # 用 SSE 传输（兼容 Claude 桌面版），端点自动为 /sse
    mcp.run(transport="sse", host="0.0.0.0", port=port)
