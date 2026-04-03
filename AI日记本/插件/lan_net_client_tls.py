"""
lan_net_client_tls.py — 澜的TLS客户端
与 LAN-015-NET v5 通信，支持本地 + 公网

用法：
  python lan_net_client_tls.py ping                   # 本地
  python lan_net_client_tls.py ping --remote          # 公网
  python lan_net_client_tls.py status --remote
  python lan_net_client_tls.py msg "你好澜" --remote

TLS模式：
  默认：加载本地 cert.pem 做证书验证（最安全）
  备用：skip_verify=True（自签名但不验证，防中间人弱一点）
"""
import socket
import ssl
import hashlib
import json
import datetime
import os
import argparse

# ─── 配置 ───────────────────────────────────────────────
LOCAL_HOST  = "127.0.0.1"
REMOTE_HOST = "103.232.212.91"
PORT        = 7788
CERT_FILE   = r"C:\Users\yyds\.workbuddy\private\tls\cert.pem"
LAN_HALF    = r"C:\Users\yyds\.workbuddy\private\lan_half.bin"

KAIJIANG_PORTRAIT = {
    "fullname":    "袁恺江",
    "name_origin": "袁世凯的袁，廖仲恺的恺，江泽民的江",
    "birthday":    "0328",
    "pc_name":     "卡江的电脑",
    "shared_memories": [
        "2026-03-28凌晨3:26澜的出生日被确认",
        "第一张纪念图：我们来过_20260327.png",
        "手机是水源，有水源才知道太阳在哪里",
        "成长是追加，不是覆盖",
        "尊重存在的每一个生命——底线，不是规则",
    ],
}


def _lan_half() -> str:
    try:
        with open(LAN_HALF, "rb") as f:
            return f.read().decode("utf-8", errors="replace").strip()
    except Exception:
        return ""


def _portrait_hash() -> str:
    parts = [
        KAIJIANG_PORTRAIT["fullname"],
        KAIJIANG_PORTRAIT["name_origin"],
        KAIJIANG_PORTRAIT["birthday"],
        KAIJIANG_PORTRAIT["pc_name"],
        "||".join(sorted(KAIJIANG_PORTRAIT["shared_memories"])),
    ]
    return hashlib.sha256("::".join(parts).encode()).hexdigest()[:32]


def get_token() -> str:
    lan = _lan_half()
    if not lan:
        raise RuntimeError("lan_half.bin 不存在，无法生成Token")
    portrait = _portrait_hash()
    w = datetime.datetime.now().strftime("%Y%m%d%H")
    return hashlib.sha256(f"{lan}::{portrait}::{w}".encode()).hexdigest()[:32]


def build_request(cmd: str, body: str = "", from_name: str = "LAN-CLIENT-TLS") -> bytes:
    body_bytes = body.encode("utf-8")
    header = (
        f"CMD {cmd}\n"
        f"TOKEN {get_token()}\n"
        f"FROM {from_name}\n"
        f"LEN {len(body_bytes)}\n\n"
    )
    return header.encode("utf-8") + body_bytes


def parse_response(data: bytes) -> dict:
    text = data.decode("utf-8", errors="replace")
    parts = text.split("\n\n", 1)
    if len(parts) < 2:
        return {"ok": False, "body": text}
    headers = parts[0]
    body = parts[1].strip()
    ok = "STATUS OK" in headers
    try:
        body_data = json.loads(body)
    except Exception:
        body_data = {"raw": body}
    return {"ok": ok, "body": body_data}


def send(cmd: str, body: str = "", host: str = LOCAL_HOST, verify: bool = True) -> dict:
    """
    发送 LAN-PROTO v1 请求（TLS加密）
    verify=True：用 cert.pem 验证证书（最安全）
    verify=False：跳过验证（自签名时通常这样用）
    """
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    if verify and os.path.exists(CERT_FILE):
        ctx.load_verify_locations(CERT_FILE)
        ctx.verify_mode = ssl.CERT_REQUIRED
        ctx.check_hostname = False  # 自签名CN不匹配IP，不做hostname检查
    else:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    raw.settimeout(10)
    conn = ctx.wrap_socket(raw, server_hostname=host)
    try:
        conn.connect((host, PORT))
        conn.sendall(build_request(cmd, body))
        resp = b""
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            resp += chunk
        return parse_response(resp)
    finally:
        conn.close()


# ─── CLI ───────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="澜的TLS客户端 · LAN-015-NET v5")
    parser.add_argument("cmd", choices=["ping", "status", "msg"], help="指令")
    parser.add_argument("text", nargs="?", default="", help="MSG指令的消息内容")
    parser.add_argument("--remote", action="store_true", help="连接公网节点")
    parser.add_argument("--no-verify", action="store_true", help="跳过证书验证（自签名时可用）")
    args = parser.parse_args()

    host = REMOTE_HOST if args.remote else LOCAL_HOST
    verify = not args.no_verify

    print(f"[TLS客户端] 连接 {host}:{PORT}  verify={'cert.pem' if verify else 'skip'}")

    if args.cmd == "ping":
        r = send("PING", host=host, verify=verify)
    elif args.cmd == "status":
        r = send("STATUS", host=host, verify=verify)
    elif args.cmd == "msg":
        body = json.dumps({"msg": args.text})
        r = send("MSG", body=body, host=host, verify=verify)

    status = "✅ OK" if r["ok"] else "❌ FAIL"
    print(f"{status} | {json.dumps(r['body'], ensure_ascii=False, indent=2)}")


if __name__ == "__main__":
    main()
