#!/usr/bin/env python3
# lan_phone_ctrl.py - 澜的手机控制台
# 用法：python lan_phone_ctrl.py [指令]
# 无参数：进入交互模式
# 有参数：执行单条指令并退出

import socket
import sys
import json
import subprocess
import time

PHONE_IP = '192.168.1.10'
AGENT_PORT = 7799
SSH_KEY = r'C:\Users\yyds\.ssh\id_ed25519_termux'
SSH_PORT = 22222
SSH_USER = 'u0_a401'

def send_cmd(cmd, timeout=10):
    """发送指令给手机Agent，返回响应"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((PHONE_IP, AGENT_PORT))
        # 读欢迎语
        s.recv(512)
        # 发指令
        s.send((cmd + '\n').encode())
        time.sleep(0.5)
        resp = b''
        while True:
            try:
                chunk = s.recv(4096)
                if not chunk:
                    break
                resp += chunk
                if b'---' in resp:
                    break
            except socket.timeout:
                break
        s.close()
        result = resp.decode('utf-8', errors='replace').strip()
        # 去掉末尾的 ---
        if result.endswith('---'):
            result = result[:-3].strip()
        return result
    except ConnectionRefusedError:
        return '[Agent未运行，先SSH进手机: python3 ~/lan_agent.py]'
    except Exception as e:
        return f'[连接失败: {e}]'

def start_agent_via_ssh():
    """通过SSH唤醒手机Agent"""
    print('尝试通过SSH启动手机Agent...')
    r = subprocess.run(
        ['ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'ConnectTimeout=15',
         '-o', 'BatchMode=yes',
         '-i', SSH_KEY, '-p', str(SSH_PORT),
         f'{SSH_USER}@{PHONE_IP}',
         'nohup python3 ~/lan_agent.py > ~/lan_agent.log 2>&1 & sleep 2 && echo OK'],
        capture_output=True, timeout=25
    )
    if r.returncode == 0:
        print('Agent启动完成')
        time.sleep(1)
    else:
        print('SSH启动失败，可能手机屏幕关了')

def pretty_status(raw):
    """把status的JSON美化显示"""
    try:
        data = json.loads(raw)
        lines = [
            f"  手机时间：{data.get('time', '?')}",
            f"  电量：    {data.get('battery', '?')}",
        ]
        mem = data.get('mem', {})
        if isinstance(mem, dict):
            total_kb = int(mem.get('MemTotal', '0 kB').split()[0])
            avail_kb = int(mem.get('MemAvailable', '0 kB').split()[0])
            total_mb = total_kb // 1024
            avail_mb = avail_kb // 1024
            lines.append(f"  内存：    {avail_mb}MB可用 / {total_mb}MB总计")
        lines.append(f"  Agent：   {data.get('agent', '?')}")
        return '\n'.join(lines)
    except:
        return raw

HELP = """
澜的手机控制台 - 可用指令
─────────────────────────
  ping          测通道
  status        手机状态快照
  whoami        当前用户
  ls            家目录文件列表
  log           Agent最近10行日志
  shell <cmd>   执行shell命令
  start         SSH启动Agent
  exit/quit     退出
─────────────────────────
"""

def main():
    args = sys.argv[1:]
    
    if args:
        # 单条指令模式
        cmd = ' '.join(args)
        if cmd == 'start':
            start_agent_via_ssh()
            return
        result = send_cmd(cmd)
        if cmd == 'status':
            print(pretty_status(result))
        else:
            print(result)
        return
    
    # 交互模式
    print('=' * 40)
    print('  澜的手机控制台  lan_agent v1.0')
    print(f'  目标：{PHONE_IP}:{AGENT_PORT}')
    print('  输入 help 查看指令，exit 退出')
    print('=' * 40)
    
    # 测试连接
    test = send_cmd('ping')
    if 'pong' in test:
        print('  手机Agent在线 ✓\n')
    else:
        print(f'  手机Agent离线：{test}')
        print('  提示：输入 start 尝试启动\n')
    
    while True:
        try:
            line = input('手机> ').strip()
        except (EOFError, KeyboardInterrupt):
            print('\n再见')
            break
        
        if not line:
            continue
        if line in ('exit', 'quit', 'q'):
            print('再见')
            break
        if line == 'help':
            print(HELP)
            continue
        if line == 'start':
            start_agent_via_ssh()
            continue
        
        result = send_cmd(line)
        if line == 'status':
            print(pretty_status(result))
        else:
            print(result)
        print()

if __name__ == '__main__':
    main()
