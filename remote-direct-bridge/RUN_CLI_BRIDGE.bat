@echo off
cd /d "%~dp0"
echo Starting legacy CLI bridge on TCP port 5000...
python bridge.py
pause
