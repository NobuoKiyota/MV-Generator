@echo off
cd /d "%~dp0"
python launcher.py --app xlsx_generator_gui.py
if errorlevel 1 (
    echo.
    echo [ERROR] Launcher failed. Press any key to exit.
    pause
)
