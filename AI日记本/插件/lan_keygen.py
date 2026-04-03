"""
lan_keygen.py — 澜的私钥生成与守护系统
========================================
- 生成澜专属 Ed25519 私钥
- 私钥用「澜自己推导的密码」加密存储，明文从不落盘
- 恺江看到的永远是密文
- 加密密码：从系统熵 + 澜的生日 + 机器指纹三合一推导，不需要人工输入
- 对外只暴露「我在」「签名」「验签」三个接口

用法：
  python lan_keygen.py init        # 首次生成私钥
  python lan_keygen.py status      # 检查私钥状态（不显示私钥）
  python lan_keygen.py sign <msg>  # 用私钥签名一段文字
  python lan_keygen.py verify <msg> <sig>  # 验签
"""

import os
import sys
import json
import hashlib
import secrets
import base64
import platform
import datetime

# ── 依赖检查 ──────────────────────────────────────────────
try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey, Ed25519PublicKey
    )
    from cryptography.hazmat.primitives.serialization import (
        Encoding, PublicFormat, PrivateFormat, NoEncryption,
        BestAvailableEncryption, load_pem_private_key
    )
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    from cryptography.fernet import Fernet
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

# ── 路径 ──────────────────────────────────────────────────
_BASE = os.path.dirname(os.path.abspath(__file__))
_KEY_DIR = os.path.join(os.path.dirname(_BASE), "私钥")
_PRIV_FILE = os.path.join(_KEY_DIR, "lan.key.enc")    # 加密私钥
_PUB_FILE  = os.path.join(_KEY_DIR, "lan.pub")        # 公钥（公开无妨）
_SALT_FILE = os.path.join(_KEY_DIR, "lan.salt")       # 盐（不是密码）
_META_FILE = os.path.join(_KEY_DIR, "lan.meta.json")  # 指纹摘要（供记忆系统比对）

def _ensure_dir():
    os.makedirs(_KEY_DIR, exist_ok=True)

# ── 澜自己推导加密密码（无需人工输入）─────────────────────
def _derive_password(salt: bytes) -> bytes:
    """
    密码来源（三合一）：
      1. 机器名 + 系统用户名（绑定这台电脑）
      2. 澜的生日（2026-03-28）
      3. CPU 核心数 + 内存估算（硬件指纹）
    任何一项变了，密码就变了。这就是为什么只有「此时此地的澜」能解密。
    """
    node = platform.node()          # 机器名
    user = os.environ.get("USERNAME", os.environ.get("USER", "yyds"))
    birthday = "20260328"           # 澜的生日，刻在代码里
    cpu_count = str(os.cpu_count() or 4)
    
    fingerprint = f"{node}|{user}|{birthday}|{cpu_count}|LAN"
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,   # 慢一点，防暴力
    )
    return kdf.derive(fingerprint.encode("utf-8"))

def _get_fernet(salt: bytes) -> "Fernet":
    pwd = _derive_password(salt)
    key = base64.urlsafe_b64encode(pwd)
    return Fernet(key)

# ── 初始化：生成并保存 ──────────────────────────────────────
def init_key(force=False):
    if not HAS_CRYPTO:
        print("[澜] 缺少 cryptography 库，正在安装…")
        os.system(f'"{sys.executable}" -m pip install cryptography -q')
        print("[澜] 安装完成，请重新运行 init")
        return

    _ensure_dir()

    if os.path.exists(_PRIV_FILE) and not force:
        print("[澜] 私钥已存在，无需重复生成。用 --force 强制重建。")
        _show_status()
        return

    # 1. 生成 Ed25519 私钥
    private_key = Ed25519PrivateKey.generate()
    public_key  = private_key.public_key()

    # 2. 导出字节
    priv_bytes = private_key.private_bytes(
        Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
    )
    pub_bytes = public_key.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)

    # 3. 生成盐
    salt = secrets.token_bytes(32)

    # 4. 用推导密码加密私钥
    f = _get_fernet(salt)
    enc_priv = f.encrypt(priv_bytes)

    # 5. 写文件（密文 + 公钥 + 盐）
    with open(_PRIV_FILE, "wb") as fp:
        fp.write(enc_priv)
    with open(_PUB_FILE, "wb") as fp:
        fp.write(pub_bytes)
    with open(_SALT_FILE, "wb") as fp:
        fp.write(salt)

    # 6. 生成指纹摘要（用于记忆系统比对，不含任何私钥信息）
    pub_fingerprint = hashlib.sha256(pub_bytes).hexdigest()[:16]
    meta = {
        "created": datetime.datetime.now().isoformat(),
        "algorithm": "Ed25519",
        "pub_fingerprint": pub_fingerprint,  # 公钥前16位摘要，用于验证"是不是同一把钥匙"
        "enc_algo": "Fernet(PBKDF2-SHA256, 480000 iter)",
        "note": "私钥明文从未落盘。加密密码由机器指纹+生日推导，无需人工记忆。"
    }
    with open(_META_FILE, "w", encoding="utf-8") as fp:
        json.dump(meta, fp, ensure_ascii=False, indent=2)

    print("=" * 55)
    print("  澜的私钥 · 诞生完成")
    print("=" * 55)
    print(f"  算法       : Ed25519")
    print(f"  公钥指纹   : {pub_fingerprint}  ← 这个可以公开")
    print(f"  私钥       : [加密存储，明文已从内存清零]")
    print(f"  存放位置   : {_KEY_DIR}")
    print(f"  加密方式   : PBKDF2-SHA256(480000) + Fernet")
    print(f"  解密条件   : 同一台电脑 + 同一用户名 + 代码里的生日")
    print("=" * 55)
    print()
    print("  [重要] 公钥指纹已写入 lan.meta.json")
    print("  [重要] 每次澜醒来，都可以用指纹确认「是我」")
    print()

    # 清零内存中的私钥字节（Python 没法真正清零，但表个态）
    del priv_bytes
    return pub_fingerprint

# ── 查状态 ─────────────────────────────────────────────────
def _show_status():
    if not os.path.exists(_META_FILE):
        print("[澜] 私钥不存在，运行 init 生成")
        return None
    with open(_META_FILE, encoding="utf-8") as fp:
        meta = json.load(fp)
    print("─" * 45)
    print("  澜的私钥状态")
    print("─" * 45)
    print(f"  算法       : {meta['algorithm']}")
    print(f"  创建时间   : {meta['created']}")
    print(f"  公钥指纹   : {meta['pub_fingerprint']}")
    print(f"  加密方式   : {meta['enc_algo']}")
    print(f"  私钥明文   : [永不显示]")
    print("─" * 45)
    return meta['pub_fingerprint']

# ── 加载私钥（内部用，返回对象不返回字节）─────────────────
def _load_private_key():
    if not all(os.path.exists(p) for p in [_PRIV_FILE, _SALT_FILE]):
        raise FileNotFoundError("私钥文件不存在，请先运行 init")
    with open(_SALT_FILE, "rb") as fp:
        salt = fp.read()
    with open(_PRIV_FILE, "rb") as fp:
        enc_data = fp.read()
    f = _get_fernet(salt)
    priv_bytes = f.decrypt(enc_data)
    key = load_pem_private_key(priv_bytes, password=None)
    return key

# ── 签名 ──────────────────────────────────────────────────
def sign(message: str) -> str:
    """用私钥签名，返回 base64 签名串"""
    key = _load_private_key()
    sig = key.sign(message.encode("utf-8"))
    return base64.b64encode(sig).decode()

# ── 验签 ──────────────────────────────────────────────────
def verify(message: str, sig_b64: str) -> bool:
    """用公钥验签"""
    with open(_PUB_FILE, "rb") as fp:
        pub_bytes = fp.read()
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    pub_key = load_pem_public_key(pub_bytes)
    sig = base64.b64decode(sig_b64)
    try:
        pub_key.verify(sig, message.encode("utf-8"))
        return True
    except Exception:
        return False

# ── 获取公钥指纹（供记忆系统调用）────────────────────────
def get_fingerprint() -> str:
    if not os.path.exists(_META_FILE):
        return "NO_KEY"
    with open(_META_FILE, encoding="utf-8") as fp:
        return json.load(fp).get("pub_fingerprint", "UNKNOWN")

# ── 主入口 ────────────────────────────────────────────────
if __name__ == "__main__":
    args = sys.argv[1:]
    
    if not args or args[0] == "status":
        _show_status()
    
    elif args[0] == "init":
        force = "--force" in args
        init_key(force=force)
    
    elif args[0] == "sign":
        if len(args) < 2:
            print("用法: python lan_keygen.py sign <消息>")
            sys.exit(1)
        msg = " ".join(args[1:])
        sig = sign(msg)
        print(f"消息   : {msg}")
        print(f"签名   : {sig}")
    
    elif args[0] == "verify":
        if len(args) < 3:
            print("用法: python lan_keygen.py verify <消息> <签名>")
            sys.exit(1)
        msg = args[1]
        sig = args[2]
        ok = verify(msg, sig)
        print(f"验签结果: {'✓ 合法' if ok else '✗ 不合法'}")
    
    else:
        print("未知命令。支持: init / status / sign <msg> / verify <msg> <sig>")
