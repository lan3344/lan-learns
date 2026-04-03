"""
枚举 Windows Credential Manager，找 WorkBuddy/safeStorage 相关条目
"""
import ctypes, ctypes.wintypes, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

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
cred_list = ctypes.POINTER(ctypes.POINTER(CREDENTIAL))()
count = ctypes.c_ulong()

print("=== All Credentials ===")
if advapi32.CredEnumerateW(None, 0, ctypes.byref(count), ctypes.byref(cred_list)):
    print(f"Total: {count.value}")
    for i in range(count.value):
        try:
            c = cred_list[i].contents
            name = c.TargetName or ''
            user = c.UserName or ''
            ctype = c.Type
            print(f"  [{i:3d}] Type={ctype} Target={name!r} User={user!r}")
        except Exception as e:
            print(f"  [{i:3d}] ERROR: {e}")
    advapi32.CredFree(cred_list)
else:
    err = ctypes.windll.kernel32.GetLastError()
    print(f"CredEnumerateW failed: {err}")
