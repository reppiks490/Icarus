@echo off
REM Grok (xAI) — 2026-09-20. Whole file. Yahoo path. Double-click this.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-yahoo.ps1"
if errorlevel 1 pause
