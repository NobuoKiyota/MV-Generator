@echo off
:: バッチファイルがあるディレクトリに移動
cd /d "%~dp0"

echo ===================================================
echo   自走型MVジェネレーター Streamlit アプリケーションを起動します
echo ===================================================
echo.

set VENV_DIR=%~dp0venv

:: 仮想環境の存在チェックと自動作成
if not exist "%VENV_DIR%" (
    echo [INFO] 仮想環境 "%VENV_DIR%" が見つかりません。新規作成します...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] 仮想環境の作成に失敗しました。Pythonがインストールされているか確認してください。
        pause
        exit /b 1
    )
    
    echo [INFO] PyTorch CUDA 12.1対応版 をインストールしています [約2.5GB、数分かかります]...
    "%VENV_DIR%\Scripts\python.exe" -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
    if errorlevel 1 (
        echo [WARNING] CUDA版PyTorchのインストールに失敗しました。標準のPyTorchを試みます...
        "%VENV_DIR%\Scripts\python.exe" -m pip install torch torchvision
    )
    
    echo [INFO] 依存パッケージをインストールしています...
    "%VENV_DIR%\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] パッケージのインストールに失敗しました。
        pause
        exit /b 1
    )
    echo [INFO] 仮想環境の作成とすべてのインストールが完了しました。
)

:: モデルのダウンロード・ウォームアップ
echo [INFO] 画像生成モデル [DreamShaper-8] の確認とダウンロードを行います...
"%VENV_DIR%\Scripts\python" download_model.py
if errorlevel 1 (
    echo [ERROR] モデルのダウンロードまたは初期化に失敗しました。
    pause
    exit /b 1
)

echo 1. ブラウザで http://localhost:8501 を開いています...
start "" "http://localhost:8501"
echo.
echo 2. Streamlit サーバーを起動中... [このウィンドウは閉じないでください]
"%VENV_DIR%\Scripts\streamlit.exe" run app.py
pause
