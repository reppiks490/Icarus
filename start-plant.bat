@echo off
REM Grok (xAI) — 2026-09-20. Whole file. Double-click this. It opens PowerShell on start-plant.ps1.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-plant.ps1"
if errorlevel 1 pause
