import os
import sys


def get_base_dir() -> str:
    """回傳應用程式資料檔（watchlist.json / execution.log）應該落地的資料夾。

    - 若以 PyInstaller 打包成單一 .exe 執行（sys.frozen 為 True），回傳該 .exe
      所在的資料夾，而不是 PyInstaller onefile 解壓縮用的暫存目錄
      (sys._MEIPASS)，確保資料檔案不會隨程式結束被清除。
    - 一般以 `python main.py` 或原始碼方式執行時，回傳本檔案所在資料夾
      （即專案根目錄），不依賴呼叫時的當前工作目錄 (cwd)。
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))
