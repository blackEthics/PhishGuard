@echo off
title PhishGuard
cd /d "%~dp0webapp"

echo.
echo  ============================================
echo   PhishGuard - Phishing URL Detection System
echo  ============================================
echo.
echo  Starting server... (takes ~10 seconds)
echo  Open browser to: http://127.0.0.1:5000
echo.
echo  Press Ctrl+C to stop the server.
echo  ============================================
echo.

python app.py

echo.
echo  Server stopped. Press any key to close.
pause >nul
