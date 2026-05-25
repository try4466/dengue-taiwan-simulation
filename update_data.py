# ============================================================
#  CDC 登革熱資料自動下載腳本
#  由 GitHub Actions 每週一 08:00（台灣時間）自動執行
# ============================================================
import requests
import os
from datetime import datetime

# ── 設定 ──────────────────────────────────────────────────
CDC_URL    = 'https://od.cdc.gov.tw/eic/Dengue_Daily.csv'
DENGUE_PATH = os.path.join('data', 'Dengue_Daily.csv')

MOS_URL    = 'https://od.cdc.gov.tw/eic/MosIndex_All.csv'
MOS_PATH   = os.path.join('data', 'MosIndex_All.csv')

# ── 函式一：登革熱病例 ────────────────────────────────────
def download():
    print(f'[{datetime.now()}] 開始下載 CDC 登革熱資料...')
    os.makedirs('data', exist_ok=True)
    resp = requests.get(CDC_URL, timeout=60, verify=False)
    resp.raise_for_status()
    with open(DENGUE_PATH, 'wb') as f:
        f.write(resp.content)
    size_kb = len(resp.content) / 1024
    print(f'✅ 登革熱下載完成！{DENGUE_PATH}（{size_kb:.0f} KB）')

# ── 函式二：布氏指數 ──────────────────────────────────────
def download_mosindex():
    print(f'[{datetime.now()}] 開始下載 MosIndex_All.csv ...')
    os.makedirs('data', exist_ok=True)
    resp = requests.get(MOS_URL, timeout=120, verify=False)
    resp.raise_for_status()
    with open(MOS_PATH, 'wb') as f:
        f.write(resp.content)
    size_mb = len(resp.content) / 1024 / 1024
    print(f'✅ MosIndex 下載完成！{MOS_PATH}（{size_mb:.1f} MB）')

# ── 執行兩個 ──────────────────────────────────────────────
if __name__ == '__main__':
    download()
    download_mosindex()
