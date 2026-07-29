import logging
import os

from paths import get_base_dir

def setup_logging(log_file=None):
    """
    配置專案日誌系統。
    遵循 Python 開發規範：使用 UTF-8 編碼以支援繁體中文。
    log_file 預設落在應用程式所在資料夾（見 paths.get_base_dir），
    不論以原始碼或打包後的 .exe 執行都會落在同一個位置。
    """
    if log_file is None:
        log_file = os.path.join(get_base_dir(), "execution.log")

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # 建立 Formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # File Handler (強制使用 utf-8)
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logging.info("日誌系統已初始化 (編碼: UTF-8)")

if __name__ == "__main__":
    setup_logging()
    logging.info("測試繁體中文日誌輸出：成功")
