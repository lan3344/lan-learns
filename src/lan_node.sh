#!/system/bin/sh
# ????? v2.0 - A?????
# ??????????????????/??????
# ???sh lan_node.sh [loop]

REPORT="/data/local/tmp/lan_report.txt"
LOG="/data/local/tmp/lan_node.log"

collect() {
  TS=$(date '+%Y-%m-%d %H:%M:%S')
  BAT=$(dumpsys battery 2>/dev/null | grep 'level:' | awk '{print $2}')
  MEM=$(cat /proc/meminfo | grep MemAvailable | awk '{print $2}')
  MEM_MB=$(( MEM / 1024 ))
  PROCS=$(ps 2>/dev/null | wc -l)
  STORAGE=$(df /sdcard 2>/dev/null | tail -1 | awk '{print $4}')
  STORAGE_GB=$(( STORAGE / 1024 / 1024 ))
  IP=$(ip route get 8.8.8.8 2>/dev/null | grep src | awk '{for(i=1;i<=NF;i++){if($i=="src"){print $(i+1)}}}')
  NET_TYPE=$(ip route get 8.8.8.8 2>/dev/null | awk '{print $5}')
  
  echo "--- $TS ---" > $REPORT
  echo "battery=${BAT}%"        >> $REPORT
  echo "mem_free=${MEM_MB}MB"   >> $REPORT
  echo "procs=${PROCS}"         >> $REPORT
  echo "storage_free=${STORAGE_GB}GB" >> $REPORT
  echo "ip=${IP}"               >> $REPORT
  echo "net=${NET_TYPE}"        >> $REPORT
  echo "status=ok"              >> $REPORT
  
  # ???????
  echo "$TS bat=${BAT}% mem=${MEM_MB}MB procs=${PROCS} net=${NET_TYPE}" >> $LOG
  
  cat $REPORT
}

if [ "$1" = "loop" ]; then
  echo "?????????..."
  while true; do
    collect
    sleep 300  # ?5??????
  done
else
  collect
fi