"""
解密 WorkBuddy state.vscdb 里的 secret:// 条目
Chromium Electron 用 Windows DPAPI 加密，前3字节是版本标记（v10），
第4~16字节是 AES-GCM nonce（如果是 Chromium 新版），或者直接DPAPI。
对于 VSCode/Electron，secret是通过 safeStorage (keytar) -> Windows Credential Manager 存的。
先试直接DPAPI解密。
"""
import sqlite3, sys, json, ctypes, struct
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

db = r'C:\Users\yyds\AppData\Roaming\WorkBuddy\User\globalStorage\state.vscdb'
conn = sqlite3.connect(db)
cur = conn.cursor()

# 拉所有 secret:// 条目
cur.execute("SELECT key, value FROM ItemTable WHERE key LIKE 'secret://%'")
rows = cur.fetchall()
print(f'Found {len(rows)} secret entries\n')

for key, value in rows:
    # 解析 JSON -> Buffer bytes
    try:
        obj = json.loads(value)
        raw = bytes(obj['data'])
    except:
        print(f'[SKIP] {key}: not JSON buffer')
        continue

    # v10 开头是 Electron safeStorage (DPAPI)
    # 实际加密数据从第3字节开始（跳过 "v10" 魔数）
    magic = raw[:3]
    encrypted = raw[3:]

    print(f'KEY: {key}')
    print(f'  magic: {magic}')
    print(f'  encrypted len: {len(encrypted)}')

    # 尝试 DPAPI 解密
    try:
        import win32crypt
        decrypted = win32crypt.CryptUnprotectData(encrypted, None, None, None, 0)
        plaintext = decrypted[1].decode('utf-8', errors='replace')
        print(f'  [DECRYPTED] {plaintext[:300]}')
    except ImportError:
        # 没有win32crypt，试ctypes直接调用
        try:
            class DATA_BLOB(ctypes.Structure):
                _fields_ = [("cbData", ctypes.c_ulong),
                             ("pbData", ctypes.POINTER(ctypes.c_char))]

            p = ctypes.create_string_buffer(encrypted, len(encrypted))
            blobin = DATA_BLOB(ctypes.sizeof(p), p)
            blobout = DATA_BLOB()
            retval = ctypes.windll.crypt32.CryptUnprotectData(
                ctypes.byref(blobin), None, None, None, None, 0,
                ctypes.byref(blobout))
            if retval:
                cbData = blobout.cbData
                pbData = blobout.pbData
                buffer = ctypes.string_at(pbData, cbData)
                plaintext = buffer.decode('utf-8', errors='replace')
                print(f'  [DECRYPTED-ctypes] {plaintext[:300]}')
                ctypes.windll.kernel32.LocalFree(blobout.pbData)
            else:
                err = ctypes.windll.kernel32.GetLastError()
                print(f'  [DPAPI-FAIL] error={err}')
        except Exception as e:
            print(f'  [ERROR] {e}')
    except Exception as e:
        print(f'  [win32crypt error] {e}')

    print()

conn.close()
