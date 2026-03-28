@echo off
title Vector AI Server
color 0A
echo.
echo  ========================================
echo     Vector AI Local Server
echo  ========================================
echo.
echo  Starting server on http://localhost:5002
echo  Keep this window open while using Vector.
echo  Close this window to stop the server.
echo.
echo  ========================================
echo.
cd /d "C:\VectorAI\Server"
python server_local.py
echo.
echo  Server stopped. You can close this window.
pause
