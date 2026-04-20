"""
launcher.py - Windows デスクトップ起動エントリポイント

PyInstaller でビルドした場合の動作:
  - sys.frozen == True
  - sys._MEIPASS : 展開された一時フォルダ（app.py/db.py/logic.py 等が入る）
  - sys.executable: .exe のフルパス → deadline.db はここと同じフォルダに置く

開発時 (python launcher.py) でも同じように動作する。
"""

import os
import sys
import socket
import threading
import time
import webbrowser
import urllib.request


def _get_dirs():
    """(meipass_dir, exe_dir) を返す。"""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS, os.path.dirname(sys.executable)
    d = os.path.dirname(os.path.abspath(__file__))
    return d, d


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        return s.getsockname()[1]


def _wait_and_open(port: int, timeout: int = 120):
    """サーバーが応答するまで待ってからブラウザを開く。"""
    url = f"http://localhost:{port}/_stcore/health"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            webbrowser.open(f"http://localhost:{port}")
            return
        except Exception:
            time.sleep(0.5)


def main():
    meipass_dir, exe_dir = _get_dirs()

    # db.py がこの環境変数を参照して deadline.db の保存先を決める
    os.environ["DEADLINE_DB_DIR"] = exe_dir

    app_path = os.path.join(meipass_dir, "app.py")
    port = _free_port()

    threading.Thread(target=_wait_and_open, args=(port,), daemon=True).start()

    sys.argv = [
        "streamlit",
        "run",
        app_path,
        "--server.port",
        str(port),
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
        "--global.developmentMode",
        "false",
    ]

    from streamlit.web import cli as stcli

    try:
        stcli.main()
    except SystemExit:
        pass


if __name__ == "__main__":
    main()
