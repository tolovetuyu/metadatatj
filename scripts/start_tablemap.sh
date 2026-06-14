#!/bin/bash
cd "$(dirname "$0")/.."
nohup python src/tornado_server_tablemap.py > logs/tablemap.log 2>&1 &
echo "表映射服务 PID: $!"
