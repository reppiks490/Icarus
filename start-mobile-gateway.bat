@echo off
setlocal
cd /d "%~dp0"

if not defined ICARUS_HOME set "ICARUS_HOME=%CD%"
if not defined ICARUS_ADMIN_TOKEN (
  echo ICARUS_ADMIN_TOKEN is not set.
  echo Set it in this terminal before starting the mobile gateway.
  exit /b 2
)
if not defined ICARUS_MOBILE_PAIRING_SECRET (
  echo ICARUS_MOBILE_PAIRING_SECRET is not set.
  echo Set a long random pairing secret in this terminal before starting the mobile gateway.
  exit /b 2
)

echo Checking ICARUS engine and mobile gateway configuration...
python -m icarus_mobile_gateway --root "%ICARUS_HOME%" doctor --engine http://127.0.0.1:8791
if errorlevel 1 exit /b %errorlevel%

echo.
echo Starting ICARUS Mobile Gateway on 127.0.0.1:8792...
python -m icarus_mobile_gateway --root "%ICARUS_HOME%" serve --host 127.0.0.1 --port 8792 --engine http://127.0.0.1:8791
