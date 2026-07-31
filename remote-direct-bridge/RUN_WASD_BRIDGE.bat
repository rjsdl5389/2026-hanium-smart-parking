@echo off
cd /d "%~dp0"
echo Starting REMOTE_DIRECT v5 GUI bridge on TCP port 5000...
python bridge_gui.py
pause
