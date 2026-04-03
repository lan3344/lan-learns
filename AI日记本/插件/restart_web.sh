#!/data/data/com.termux/files/usr/bin/bash
# 重启蓝的Web服务
pkill -f lan_web.py 2>/dev/null
sleep 1
cd ~
nohup python lan_web.py > lan_web.log 2>&1 &
sleep 2
echo "PID=$!"
curl -s http://127.0.0.1:8080/manifest.json | head -4
