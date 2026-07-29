import httpx
import asyncio
import logging
import time
from typing import List, Dict, Any

# 證交所 2026 最新整合型 API (包含上市與上櫃)
ALL_ETF_URL = "https://mis.twse.com.tw/stock/data/all_etf.txt"
REFERER_URL = "https://mis.twse.com.tw/stock/various-areas/etf-price/indicator-disclosure-etf?lang=zhHant"

# 關閉模擬數據模式，對接真實資料
DEBUG_MODE = False

async def fetch_real_etf_data(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """
    從證交所 all_etf.txt 抓取即時數據。
    必須帶上正確的 Referer 標頭。
    """
    params = {"_": int(time.time() * 1000)}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": REFERER_URL,
        "Accept": "application/json, text/javascript, */*; q=0.01"
    }
    
    try:
        response = await client.get(ALL_ETF_URL, params=params, headers=headers, timeout=10.0)
        
        match response.status_code:
            case 200:
                data = response.json()
                logging.debug(f"JSON 根鍵值: {list(data.keys())}")
                # 數據通常位於 a1 陣列中的各個區段，需攤平
                all_msgs = []
                if "a1" in data:
                    for section in data["a1"]:
                        if isinstance(section, dict) and "msgArray" in section:
                            all_msgs.extend(section["msgArray"])
                logging.info(f"成功收集到 {len(all_msgs)} 筆原始 ETF 數據")
                return all_msgs
            case _:
                logging.error(f"API 請求失敗 ({response.status_code}): {ALL_ETF_URL=}")
                return []
    except httpx.ConnectError as ce:
        # 特別處理 SSL/連線問題並記錄關鍵資訊
        logging.error(f"連線/SSL 驗證失敗 (請確保 verify=False 正常運作): {str(ce)=}")
        return []
    except Exception as e:
        logging.error(f"API 抓取異常: {type(e).__name__=}, {str(e)=}")
        return []

async def get_combined_etf_data() -> List[Dict[str, Any]]:
    """
    獲取整合後的 ETF 數據。
    """
    async with httpx.AsyncClient(verify=False) as client:
        data = await fetch_real_etf_data(client)
        
        if not data and DEBUG_MODE:
            # 只有在 DEBUG_MODE 下才回傳模擬數據
            from api_client_mock import get_mock_data # 假設我們移除了 mock
            return [] 
            
        return data

# 如果需要保留 mock 邏輯供未來測試
def get_mock_data() -> List[Dict[str, Any]]:
    import random
    codes = ["00713", "0050", "0052", "006208", "00891", "00727B", "00918", "00984D"]
    mock_list = []
    for code in codes:
        nav = round(random.uniform(20.0, 150.0), 2)
        price = round(nav * random.uniform(0.99, 1.01), 2)
        mock_list.append({
            'a': code,
            'b': f"ETF {code} (模擬)",
            'e': str(price),
            'f': str(nav),
            'g': f"{(price-nav)/nav*100:.2f}"
        })
    return mock_list
