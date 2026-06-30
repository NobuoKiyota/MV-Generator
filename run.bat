@echo off
cd /d z:\mv-generator
echo ===================================================
echo   自走型MVジェネレーター Streamlit アプリケーションを起動します
echo ===================================================
echo.
echo 1. ブラウザで http://localhost:8501 を開いています...
start "" "http://localhost:8501"
echo.
echo 2. Streamlit サーバーを起動中... (このウィンドウは閉じないでください)
"F:\mv-generator-venv\Scripts\streamlit.exe" run app.py
pause
