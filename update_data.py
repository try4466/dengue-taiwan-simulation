# ============================================================
#  CDC 登革熱資料自動下載腳本
#  由 GitHub Actions 每週一 08:00（台灣時間）自動執行
# ============================================================

import requests
import os
from datetime import datetime

CDC_URL = 'https://od.cdc.gov.tw/eic/Dengue_Daily.csv'
SAVE_PATH = os.path.join('data', 'Dengue_Daily.csv')

def download():
    print(f'[{datetime.now()}] 開始下載 CDC 登革熱資料...')
    os.makedirs('data', exist_ok=True)

    resp = requests.get(CDC_URL, timeout=60)
    resp.raise_for_status()

    with open(SAVE_PATH, 'wb') as f:
        f.write(resp.content)

    size_kb = len(resp.content) / 1024
    print(f'✅ 下載完成！儲存至 {SAVE_PATH}（{size_kb:.0f} KB）')

if __name__ == '__main__':
    download()