import pandas as pd
import logging
import json
import os
from typing import List, Dict, Any, Set
from paths import get_base_dir

pd.options.mode.copy_on_write = True

WATCHLIST_FILE = os.path.join(get_base_dir(), "watchlist.json")
DEFAULT_WATCHLIST = ["00713", "0050", "0052", "006208", "00891", "00727B", "00918", "00984D"]

class ETFMonitor:
    def __init__(self, initial_list: List[str] = None):
        self.watchlist: Set[str] = self._load_watchlist(initial_list)
        self.df: pd.DataFrame = pd.DataFrame()

    def _load_watchlist(self, default_list: List[str]) -> Set[str]:
        """從檔案載入清單，否則使用預設值。"""
        if os.path.exists(WATCHLIST_FILE):
            try:
                with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        logging.info(f"成功從 {WATCHLIST_FILE} 載入監控清單。")
                        return set(data)
            except Exception as e:
                logging.error(f"讀取 {WATCHLIST_FILE} 失敗，使用預設清單: {e}")
        
        # 檔案不存在或讀取失敗
        final_default = default_list if default_list else DEFAULT_WATCHLIST
        logging.info("使用預設監控清單。")
        self._save_to_file(set(final_default))
        return set(final_default)

    def _save_to_file(self, watchlist: Set[str] = None):
        """將清單儲存至檔案。"""
        target = watchlist if watchlist is not None else self.watchlist
        try:
            with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
                json.dump(sorted(list(target)), f, ensure_ascii=False, indent=4)
            logging.debug(f"已同步監控清單至 {WATCHLIST_FILE}")
        except Exception as e:
            logging.error(f"儲存 {WATCHLIST_FILE} 失敗: {e}")

    def update_data(self, raw_data: List[Dict[str, Any]]):
        """
        處理來自 all_etf.txt 的數據。
        欄位定義：a=代號, b=名稱, e=成交市價, f=預估淨值, g=折溢價(%), c=單位數, d=差異數
        """
        if not raw_data:
            logging.warning("接收到空的原始數據，略過更新。")
            return

        temp_df = pd.DataFrame(raw_data)

        # 根據 2026 最新 API 欄位定義進行映射
        required_cols = {
            'a': '代碼', 
            'b': '名稱', 
            'e': '市價', 
            'f': '淨值',
            'g': '折溢價(%)',
            'c': '已發行單位',
            'd': '單位差異'
        }
        
        # 檢查關鍵欄位 (代碼 a 與 名稱 b 是基礎)
        if 'a' not in temp_df.columns or 'b' not in temp_df.columns:
            logging.error("API 數據結構異常，缺少關鍵代碼或名稱欄位")
            return

        # 選取並重新命名
        available_cols = [c for c in required_cols.keys() if c in temp_df.columns]
        self.df = temp_df[available_cols].rename(columns=required_cols)

        # 清洗數據：處理可能包含逗號的字串 (如富邦系列 ETF: "2,500,000,000")
        target_cols = ['市價', '淨值', '折溢價(%)', '已發行單位', '單位差異']
        for col in target_cols:
            if col in self.df.columns:
                # 確保為字串型態後移除逗號，再轉換為數值
                self.df[col] = self.df[col].astype(str).str.replace(',', '', regex=False)
                self.df[col] = pd.to_numeric(self.df[col], errors='coerce')
        
        # 2026/03/24 校正：API (all_etf.txt) 的 c, d 欄位單位通常為「十股」，需乘以 10 換算為「個」
        # 註：0050 在 API 中為 11 位數 (如 180億)，乘以 10 後為 1800億，使用者確認此比例正確。
        if '已發行單位' in self.df.columns:
            self.df['已發行單位'] = self.df['已發行單位'] * 10
        if '單位差異' in self.df.columns:
            self.df['單位差異'] = self.df['單位差異'] * 10

        # 過濾監控清單
        self.df = self.df[self.df['代碼'].isin(self.watchlist)]

        # 如果 API 沒給折溢價，則自行計算 (防禦性編程)
        if '折溢價(%)' not in self.df.columns or self.df['折溢價(%)'].isnull().any():
            self.df['折溢價(%)'] = ((self.df['市價'] - self.df['淨值']) / self.df['淨值'] * 100).round(2)

        self.df = self.df.sort_values(by='代碼').reset_index(drop=True)

    def add_to_watchlist(self, code: str):
        if code and code not in self.watchlist:
            self.watchlist.add(code)
            self._save_to_file()
            logging.info(f"Watchlist 異動 (新增): {code=}")

    def remove_from_watchlist(self, code: str):
        if code in self.watchlist:
            self.watchlist.discard(code)
            self._save_to_file()
            logging.info(f"Watchlist 異動 (刪除): {code=}")

    def get_display_data(self) -> pd.DataFrame:
        return self.df
