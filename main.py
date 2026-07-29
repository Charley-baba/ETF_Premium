import asyncio
import logging
import platform
import pandas as pd
from typing import List
from rich.live import Live
from rich.table import Table
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text

# Windows 專用按鍵處理
if platform.system() == "Windows":
    import msvcrt
else:
    # 非 Windows 環境（如 Linux/Docker）降級處理，雖然專案目前是 Windows Terminal
    msvcrt = None

from api_client import get_combined_etf_data
from monitor import ETFMonitor
from logging_config import setup_logging

# Solarized Light 顏色定義
SOLARIZED_BLUE = "#268BD2"
SOLARIZED_RED = "#DC322F"
SOLARIZED_GREEN = "#859900"
SOLARIZED_BASE01 = "#586E75" 

class ETFApp:
    def __init__(self):
        self.console = Console()
        self.monitor = ETFMonitor()
        self.status_msg = "系統啟動中..."
        self.input_buffer = "" # 目前鍵入的內容
        self.last_op_msg = ""   # 上次操作結果
        self.page = 0
        self.max_page = 0

    def generate_table(self) -> Table:
        table = Table(title="極速 ETF 即時監控系統 (SRS v3.1)", 
                      header_style=f"bold {SOLARIZED_BLUE}",
                      title_style=f"bold {SOLARIZED_BLUE}",
                      expand=False,
                      show_lines=True)
        
        table.add_column("項次", justify="right", style="dim")
        table.add_column("代碼", style="bold", justify="center")
        table.add_column("名稱", justify="left")
        table.add_column("折溢價 (%)", justify="right")
        table.add_column("市價", justify="right")
        table.add_column("預估淨值", justify="right")
        table.add_column("已發行單位", justify="right")
        table.add_column("單位差異", justify="right")
        table.add_column("項次", justify="right", style="dim")

        df = self.monitor.get_display_data()
        if df.empty:
            table.add_row("", "", "數據加載中...", "", "", "", "", "", "")
            return table

        # Pagination logic
        available_lines = self.console.height - 14
        page_size = max(1, available_lines // 2)
        self.max_page = max(0, (len(df) - 1) // page_size)
        self.page = min(self.page, self.max_page)
        
        start_idx = self.page * page_size
        end_idx = start_idx + page_size
        page_df = df.iloc[start_idx:end_idx]

        for i, (_, row) in enumerate(page_df.iterrows()):
            actual_idx = start_idx + i + 1
            premium = row['折溢價(%)']
            units = row.get('已發行單位', 0)
            diff = row.get('單位差異', 0)
            
            color = SOLARIZED_BASE01
            style = ""
            if premium > 0.5:
                color = SOLARIZED_RED
                style = "bold "
            elif premium < -0.5:
                color = SOLARIZED_GREEN
                style = "bold "

            # 差異數顏色
            diff_color = SOLARIZED_BASE01
            if diff > 0:
                diff_color = SOLARIZED_RED
            elif diff < 0:
                diff_color = SOLARIZED_GREEN

            table.add_row(
                str(actual_idx),
                Text(str(row['代碼']), style=SOLARIZED_BLUE),
                str(row['名稱']),
                Text(f"{premium:+.2f}%", style=f"{style}{color}"),
                f"{row['市價']:.2f}",
                f"{row['淨值']:.2f}",
                f"{int(units):,}" if not pd.isna(units) else "N/A",
                Text(f"{int(diff):+,}" if not pd.isna(diff) else "N/A", style=diff_color),
                str(actual_idx)
            )
        return table

    def make_layout(self) -> Layout:
        layout = Layout()
        layout.split(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=4)
        )

        # 狀態與輸入合併在 footer
        footer_text = Text()
        footer_text.append("狀態: ", style=f"bold {SOLARIZED_BLUE}")
        footer_text.append(f"{self.status_msg} ", style=SOLARIZED_BASE01)
        if self.last_op_msg:
            footer_text.append(f"| {self.last_op_msg} ", style=SOLARIZED_GREEN)

        # 輸入區塊預覽
        input_panel_content = Text()
        input_panel_content.append("指令鍵入: ", style=f"bold {SOLARIZED_RED}")
        input_panel_content.append(f"{self.input_buffer}█", style="bold") # 加入游標模擬
        input_panel_content.append("  ※ 指令請使用英數輸入法輸入", style=f"bold {SOLARIZED_RED}")
        input_panel_content.append("\n")
        input_panel_content.append("增加 ETF，輸入：", style="dim")
        input_panel_content.append("+ETF代碼 ↵", style=f"bold {SOLARIZED_GREEN}")
        input_panel_content.append("　／　移除 ETF，輸入：", style="dim")
        input_panel_content.append("-ETF代碼 ↵", style=f"bold {SOLARIZED_RED}")
        input_panel_content.append("　／　使用 ↑ ↓ 方向鍵翻頁", style="dim")

        layout["header"].update(Panel(Text(f"即時行情監控 - 每 15 秒更新一次 (頁碼 {self.page+1}/{self.max_page+1})", justify="center", style=f"bold {SOLARIZED_BLUE}")))
        layout["main"].update(self.generate_table())
        layout["footer"].update(Panel(input_panel_content, title=footer_text, title_align="left"))
        return layout

    async def update_loop(self):
        while True:
            try:
                raw_data = await get_combined_etf_data()
                self.monitor.update_data(raw_data)
                self.status_msg = "數據更新成功 (15s 週期)"
            except Exception as e:
                self.status_msg = f"更新失敗: {type(e).__name__}"
                logging.error(f"更新錯誤: {str(e)}", exc_info=True)
            await asyncio.sleep(15)

    async def input_loop(self):
        if msvcrt is None:
            logging.warning("非 Windows 環境，輸入功能受限。")
            return

        byte_buffer = b""

        def _utf8_byte_count(first_byte: int) -> int:
            if first_byte < 0x80:
                return 1
            elif first_byte < 0xE0:
                return 2
            elif first_byte < 0xF0:
                return 3
            else:
                return 4

        while True:
            if msvcrt.kbhit():
                byte_key = msvcrt.getch()
                
                if byte_key in (b'\xe0', b'\x00'):
                    next_byte = msvcrt.getch()
                    if next_byte == b'H': # Up arrow
                        self.page = max(0, self.page - 1)
                    elif next_byte == b'P': # Down arrow
                        self.page += 1
                    elif next_byte == b'I': # PageUp
                        self.page = max(0, self.page - 1)
                    elif next_byte == b'Q': # PageDown
                        self.page += 1
                    continue
                
                first_byte = byte_key[0]

                # 處理 Enter (回車)
                if byte_key in (b'\r', b'\n'):
                    byte_buffer = b""
                    cmd = self.input_buffer.strip()
                    if cmd:
                        self.process_command(cmd)
                        self.input_buffer = ""
                # 處理 Backspace (倒退鍵)
                elif byte_key == b'\x08':
                    byte_buffer = b""
                    self.input_buffer = self.input_buffer[:-1]
                # Escape 鍵 — 清空輸入
                elif byte_key == b'\x1b':
                    byte_buffer = b""
                    self.input_buffer = ""
                # 控制字元 / 方向鍵序列 (跳過)
                elif first_byte < 0x20 and byte_key not in (b'\t',):
                    byte_buffer = b""
                    continue
                # 其他位元組 — 組裝 UTF-8 序列
                else:
                    byte_buffer += byte_key
                    needed = _utf8_byte_count(byte_buffer[0])
                    if len(byte_buffer) == needed:
                        try:
                            char = byte_buffer.decode('utf-8')
                            if char.isprintable() or char in (" ", "\t"):
                                self.input_buffer += char
                        except UnicodeDecodeError:
                            pass
                        byte_buffer = b""

            await asyncio.sleep(0.01)

    def process_command(self, cmd: str):
        cmd = cmd.strip()
        if cmd.startswith("+"):
            code = cmd[1:].strip()
            self.monitor.add_to_watchlist(code)
            self.last_op_msg = f"已新增 {code}"
        elif cmd.startswith("-"):
            code = cmd[1:].strip()
            self.monitor.remove_from_watchlist(code)
            self.last_op_msg = f"已移除 {code}"
        else:
            self.monitor.add_to_watchlist(cmd)
            self.last_op_msg = f"已新增 {cmd}"

    async def run(self):
        setup_logging()
        with Live(self.make_layout(), refresh_per_second=10, screen=True) as live:
            update_task = asyncio.create_task(self.update_loop())
            input_task = asyncio.create_task(self.input_loop())
            
            while True:
                live.update(self.make_layout())
                await asyncio.sleep(0.1)

if __name__ == "__main__":
    app = ETFApp()
    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        print("\n系統正常結束。")