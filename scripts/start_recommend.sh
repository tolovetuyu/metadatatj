#!/bin/bash
cd "$(dirname "$0")/.."
nohup python src/tornado_server_recommend.py > logs/recommend.log 2>&1 &
echo "推荐服务 PID: $!"
