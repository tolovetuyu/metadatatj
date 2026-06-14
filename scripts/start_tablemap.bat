@echo off
cd /d %~dp0..
if not exist logs mkdir logs
start /B python src\tornado_server_tablemap.py > logs\tablemap.log 2>&1
echo 表映射服务已后台启动，端口见 .env 中 TABLEMAP_PORT
