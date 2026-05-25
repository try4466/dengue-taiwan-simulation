import requests
import os
from datetime import datetime

CDC_URL     = 'https://od.cdc.gov.tw/eic/Dengue_Daily.csv'
DENGUE_PATH = os.path.join('data', 'Dengue_Daily.csv')

MOS_URL     = 'https://od.cdc.gov.tw/eic/MosIndex_All.csv'
MOS_PATH    = os.path.join('data', 'MosIndex_All.csv')

def download():
    print(f'[{datetime.now()}] 開始下載 CDC 登革熱資料...')
    os.makedirs('data', exist_ok=True)
    resp = requests.get(CDC_URL, timeout=60, verify=False)
    resp.raise_for_status()
    with open(DENGUE_PATH, 'wb') as f:
        f.write(resp.content)
    size_kb = len(resp.content) / 1024
    print(f'✅ 下載完成！{DENGUE_PATH}（{size_kb:.0f} KB）')

def download_mosindex():
    """MosIndex 只在本地執行，不放 GitHub Actions（檔案太大）"""
    print(f'[{datetime.now()}] 開始下載 MosIndex_All.csv ...')
    os.makedirs('data', exist_ok=True)
    resp = requests.get(MOS_URL, timeout=300, verify=False)
    resp.raise_for_status()
    with open(MOS_PATH, 'wb') as f:
        f.write(resp.content)
    size_mb = len(resp.content) / 1024 / 1024
    print(f'✅ MosIndex 下載完成！{MOS_PATH}（{size_mb:.1f} MB）')

if __name__ == '__main__':
    import sys
    if '--mos' in sys.argv:
        download_mosindex()   # 只有加 --mos 才下載（本地手動用）
    else:
        download()            # GitHub Actions 只跑這個
