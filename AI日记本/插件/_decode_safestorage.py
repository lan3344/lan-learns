"""
VSCode/Electron safeStorage 解密
v10 格式 = AES-256-GCM，密钥来自 Windows Credential Manager (keytar)
密钥存储在：HKCU/Software/Microsoft/Windows NT/CurrentVersion/AppCompatFlags/Compatibility Assistant/Store
或者直接在 Windows Credential Manager 里

Electron safeStorage在Windows上用的是：
- 主密钥通过 BCrypt 的 DPAPI 保护，存在 %AppData%\WorkBuddy\Local Storage\leveldb\ 或 Credentials
- 实际是: keytar.getPassword("WorkBuddy Safe Storage", "WorkBuddy")
  返回的 base64 key 用来做 AES-256-GCM 解密

格式: v10 + nonce(12) + ciphertext + tag(16)
"""
import sqlite3, sys, json, os, base64, ctypes, struct
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 先找 Electron safeStorage 的主密钥
# Windows: stored in Windows Credential Manager
# keytar key = "WorkBuddy Safe Storage" / account = "WorkBuddy"

# 用 Windows Credential Manager API
import ctypes.wintypes

CRED_TYPE_GENERIC = 1

class CREDENTIAL_ATTRIBUTE(ctypes.Structure):
    _fields_ = [
        ('Keyword', ctypes.c_wchar_p),
        ('Flags', ctypes.c_ulong),
        ('ValueSize', ctypes.c_ulong),
        ('Value', ctypes.POINTER(ctypes.c_byte)),
    ]

class CREDENTIAL(ctypes.Structure):
    _fields_ = [
        ('Flags', ctypes.c_ulong),
        ('Type', ctypes.c_ulong),
        ('TargetName', ctypes.c_wchar_p),
        ('Comment', ctypes.c_wchar_p),
        ('LastWritten', ctypes.c_ulonglong),
        ('CredentialBlobSize', ctypes.c_ulong),
        ('CredentialBlob', ctypes.POINTER(ctypes.c_byte)),
        ('Persist', ctypes.c_ulong),
        ('AttributeCount', ctypes.c_ulong),
        ('Attributes', ctypes.POINTER(CREDENTIAL_ATTRIBUTE)),
        ('TargetAlias', ctypes.c_wchar_p),
        ('UserName', ctypes.c_wchar_p),
    ]

advapi32 = ctypes.windll.advapi32

# 尝试多个可能的 keytar target name
targets = [
    "WorkBuddy Safe Storage",
    "CodeBuddy Safe Storage", 
    "tencent-cloud Safe Storage",
    "Electron Safe Storage",
    "WorkBuddy",
]

master_key = None
for target in targets:
    cred_ptr = ctypes.POINTER(CREDENTIAL)()
    if advapi32.CredReadW(target, CRED_TYPE_GENERIC, 0, ctypes.byref(cred_ptr)):
        cred = cred_ptr.contents
        blob = bytes(cred.CredentialBlob[:cred.CredentialBlobSize])
        try:
            key_str = blob.decode('utf-8')
            print(f"[FOUND CRED] target={target}")
            print(f"  raw key (b64?): {key_str[:80]}")
            # decode base64 if needed
            try:
                master_key = base64.b64decode(key_str)
                print(f"  decoded len: {len(master_key)}")
            except:
                master_key = blob
            advapi32.CredFree(cred_ptr)
            break
        except:
            advapi32.CredFree(cred_ptr)
    else:
        err = ctypes.windll.kernel32.GetLastError()
        print(f"  target={target}: err={err}")

if not master_key:
    print("\n[!] 未找到主密钥，列出所有Credential Manager条目：")
    # 枚举所有凭据
    cred_list = ctypes.POINTER(ctypes.POINTER(CREDENTIAL))()
    count = ctypes.c_ulong()
    if advapi32.CredEnumerateW(None, 0, ctypes.byref(count), ctypes.byref(cred_list)):
        for i in range(count.value):
            c = cred_list[i].contents
            try:
                name = c.TargetName or ''
                user = c.UserName or ''
                if any(kw.lower() in name.lower() for kw in ['workbuddy','codebuddy','tencent','electron','safe']):
                    print(f"  [{i}] Target={name} | User={user}")
            except:
                pass
        advapi32.CredFree(cred_list)
    sys.exit(1)

# 有 master_key，解密所有 v10 条目
print(f"\n[OK] Got master key ({len(master_key)} bytes), now decrypting...\n")

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:
    print("需要安装 cryptography: pip install cryptography")
    sys.exit(1)

db = r'C:\Users\yyds\AppData\Roaming\WorkBuddy\User\globalStorage\state.vscdb'
conn = sqlite3.connect(db)
cur = conn.cursor()
cur.execute("SELECT key, value FROM ItemTable WHERE key LIKE 'secret://%'")
rows = cur.fetchall()

for key, value in rows:
    try:
        obj = json.loads(value)
        raw = bytes(obj['data'])
    except:
        continue

    if raw[:3] != b'v10':
        print(f"[SKIP non-v10] {key}")
        continue

    encrypted_with_nonce = raw[3:]
    if len(encrypted_with_nonce) < 12:
        print(f"[TOO SHORT] {key}")
        continue

    nonce = encrypted_with_nonce[:12]
    ciphertext = encrypted_with_nonce[12:]

    try:
        aesgcm = AESGCM(master_key[:32])
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        decoded = plaintext.decode('utf-8', errors='replace')
        k_short = key.split('"key":"')[1].rstrip('"}') if '"key":"' in key else key
        print(f"[OK] {k_short}")
        print(f"  {decoded[:500]}")
        print()
    except Exception as e:
        print(f"[FAIL] {key}: {e}")

conn.close()
