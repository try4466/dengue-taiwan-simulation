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
    try:
        resp = requests.get(CDC_URL, timeout=60, verify=False)
        # 疾管署對境外 IP 回傳 "Host not in allowlist"
        if 'not in allowlist' in resp.text[:100]:
            print('⚠️  od.cdc.gov.tw 封鎖境外 IP（Host not in allowlist）')
            print('ℹ️  保留既有資料，workflow 正常結束（exit 0）')
            return
        resp.raise_for_status()
        with open(DENGUE_PATH, 'wb') as f:
            f.write(resp.content)
        size_kb = len(resp.content) / 1024
        print(f'✅ 下載完成！{DENGUE_PATH}（{size_kb:.0f} KB）')
    except requests.exceptions.ConnectTimeout:
        print('⚠️  連線逾時（境外 IP 封鎖），保留既有資料，workflow 正常結束')
    except Exception as e:
        print(f'⚠️  下載失敗：{e}，保留既有資料，workflow 正常結束')

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
        download_mosindex()
    else:
        download()