@echo off
setlocal EnableDelayedExpansion

echo ========================================
echo  IP期限管理システム - Windows ビルド
echo ========================================
echo.

REM ── Python 確認 ─────────────────────────────────────────────────────────
python --version > /dev/null 2>&1
if errorlevel 1 (
    echo [ERROR] Python が見つかりません。Python 3.11 以上をインストールしてください。
    pause & exit /b 1
)

REM ── 依存パッケージ確認・インストール ────────────────────────────────────
echo [1/4] 依存パッケージを確認中...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [ERROR] requirements.txt のインストールに失敗しました。
    pause & exit /b 1
)

echo [2/4] PyInstaller をインストール中...
pip install "pyinstaller>=6.0" --quiet
if errorlevel 1 (
    echo [ERROR] PyInstaller のインストールに失敗しました。
    pause & exit /b 1
)

REM ── ビルド前クリーン ─────────────────────────────────────────────────────
echo [3/4] ビルド中（初回は 5～10 分かかります）...
if exist build   rmdir /s /q build
if exist dist    rmdir /s /q dist
if exist IPDeadlineManager.spec del /q IPDeadlineManager.spec

REM ── PyInstaller 実行 ─────────────────────────────────────────────────────
pyinstaller ^
    --name "IPDeadlineManager" ^
    --onedir ^
    --noconsole ^
    --collect-all streamlit ^
    --collect-all altair ^
    --collect-all pandas ^
    --collect-all pydeck ^
    --collect-all pyarrow ^
    --collect-all narwhals ^
    --hidden-import "streamlit.runtime.scriptrunner.magic_funcs" ^
    --hidden-import "streamlit.components.v1" ^
    --hidden-import "streamlit.elements.lib.column_types" ^
    --hidden-import "dateutil.relativedelta" ^
    --add-data "app.py;." ^
    --add-data "db.py;." ^
    --add-data "logic.py;." ^
    launcher.py

if errorlevel 1 (
    echo.
    echo [ERROR] ビルドに失敗しました。上記のエラーメッセージを確認してください。
    pause & exit /b 1
)

REM ── 完了メッセージ ────────────────────────────────────────────────────────
echo.
echo [4/4] ビルド完了！
echo.
echo 成果物フォルダ: dist\IPDeadlineManager\
echo 実行ファイル  : dist\IPDeadlineManager\IPDeadlineManager.exe
echo.
echo 配布方法:
echo   dist\IPDeadlineManager\ フォルダをまるごとコピーして渡してください。
echo   IPDeadlineManager.exe をダブルクリックするとブラウザが自動で開きます。
echo   deadline.db は .exe と同じフォルダに自動生成されます。
echo.
pause
