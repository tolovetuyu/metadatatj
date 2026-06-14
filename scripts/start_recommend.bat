@echo off
cd /d %~dp0..
if not exist logs mkdir logs
start /B python src\tornado_server_recommend.py > logs\recommend.log 2>&1
echo 推荐服务已后台启动，端口见 .env 中 RECOMMEND_PORT
