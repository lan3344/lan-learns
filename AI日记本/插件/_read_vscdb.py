import sqlite3, sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

db = r'C:\Users\yyds\AppData\Roaming\WorkBuddy\User\globalStorage\state.vscdb'
conn = sqlite3.connect(db)
cur = conn.cursor()

# 查所有表
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cur.fetchall()
print('Tables:', [t[0] for t in tables])
print()

# 找 tencent/plan/tier/subscription/quota/account/copilot 相关key
keywords = ['plan', 'tier', 'subscription', 'quota', 'copilot', 'tencent', 'account', 'token', 'auth', 'user', 'premium', 'vip', 'free', 'paid']
for kw in keywords:
    cur.execute(f"SELECT key, value FROM ItemTable WHERE key LIKE '%{kw}%'")
    rows = cur.fetchall()
    if rows:
        print(f'=== keyword: {kw} ({len(rows)} rows) ===')
        for k, v in rows[:5]:
            val_str = v[:300] if isinstance(v, str) else str(v)[:300]
            print(f'  KEY: {k}')
            print(f'  VAL: {val_str}')
            print()

conn.close()
