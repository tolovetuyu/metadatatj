@echo off
cd /d %~dp0..
if not exist logs mkdir logs
start /B python src\tornado_server_admin.py > logs\admin.log 2>&1
echo 管理后台已启动: http://127.0.0.1:6070/admin
