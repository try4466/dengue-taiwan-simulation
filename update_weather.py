"""
update_weather.py
自動從 CWA C-B0024-001 抓最新30天逐日資料，
聚合成月後補進 weather_monthly_codis.csv

執行方式：
    python update_weather.py
    （由 GitHub Actions 每週一 08:00 自動執行）
"""

import requests
import pandas as pd
import os
import warnings
from datetime import datetime
warnings.filterwarnings('ignore')

# ── 設定 ──────────────────────────────────────────────────────
WEATHER_CSV = 'data/weather_monthly_codis.csv'

CITY_STATION = {
    '台南市': '467410',
    '高雄市': '467441',  # C-B0024-001 用 467441
    '嘉義市': '467480',
    '屏東縣': '467590',
}

# API Key：本機從 secrets.toml 讀，GitHub Actions 從環境變數讀
def get_api_key():
    # GitHub Actions 環境變數
    key = os.environ.get('CWA_API_KEY', '')
    if key:
        print(f'✅ 使用環境變數 API Key：{key[:10]}...')
        return key
    # 本機 secrets.toml
    toml_path = '.streamlit/secrets.toml'
    if os.path.exists(toml_path):
        with open(toml_path) as f:
            for line in f:
                if 'api_key' in line and '=' in line:
                    key = line.split('=', 1)[1].strip().strip('"').strip("'")
                    print(f'✅ 使用 secrets.toml API Key：{key[:10]}...')
                    return key
    raise ValueError('❌ 找不到 CWA API Key！請設定環境變數 CWA_API_KEY 或 .streamlit/secrets.toml')

# ── 抓取最新30天逐日資料 ──────────────────────────────────────
def fetch_daily_recent(station_id: str, api_key: str) -> pd.DataFrame:
    """
    C-B0024-001：最近30天逐日地面觀測資料
    回傳 columns = [date, temp_mean, rain_sum]
    """
    url = 'https://opendata.cwa.gov.tw/api/v1/rest/datastore/C-B0024-001'
    params = {
        'Authorization': api_key,
        'stationId':     station_id,
        'format':        'JSON',
    }
    try:
        resp = requests.get(url, params=params, timeout=30, verify=False)
        resp.raise_for_status()
        data = resp.json()

        locations = data['records']['location']
        target = None
        for loc in locations:
            if loc['station']['StationID'] == station_id:
                target = loc
                break

        if target is None:
            print(f'  ⚠️ 找不到測站 {station_id}')
            return pd.DataFrame()

        rows = []
        for obs in target['stationObsTimes']['stationObsTime']:
            date_str = obs['DateTime'][:10]  # 取 YYYY-MM-DD
            elements = obs['weatherElements']

            try:
                # 氣溫：取 Mean 欄位
                temp = elements.get('AirTemperature', None)
                if temp is None or str(temp).strip() in ['', 'None', '-']:
                    continue
                temp = float(temp)

                # 降雨
                rain = elements.get('Precipitation', '0')
                if str(rain).strip() in ['', 'None', '-', 'T']:
                    rain = 0.0
                rain = float(rain)
                if rain < 0:
                    rain = 0.0

                rows.append({
                    'date':  pd.to_datetime(date_str),
                    'temp':  temp,
                    'rain':  rain,
                })
            except (ValueError, TypeError):
                continue

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        df = df.sort_values('date').reset_index(drop=True)
        print(f'  → 抓到 {len(df)} 筆逐日資料（{df["date"].min().date()} ~ {df["date"].max().date()}）')
        return df

    except Exception as e:
        print(f'  ❌ API 錯誤（station={station_id}）：{e}')
        return pd.DataFrame()

# ── 逐日 → 月聚合 ──────────────────────────────────────────────
def aggregate_to_monthly(daily_df: pd.DataFrame, city: str) -> pd.DataFrame:
    """把逐日資料聚合成月均溫 + 月降雨"""
    if daily_df.empty:
        return pd.DataFrame()

    daily_df = daily_df.copy()
    daily_df['year']  = daily_df['date'].dt.year
    daily_df['month'] = daily_df['date'].dt.month

    # 只保留當月資料完整的月份（至少 20 天）
    monthly = (daily_df.groupby(['year', 'month'])
               .agg(
                   temp_mean=('temp', 'mean'),
                   rain_sum=('rain', 'sum'),
                   day_count=('temp', 'count'),
               )
               .reset_index())

    monthly = monthly[monthly['day_count'] >= 20].copy()
    monthly['temp_mean'] = monthly['temp_mean'].round(1)
    monthly['rain_sum']  = monthly['rain_sum'].round(1)
    monthly['County'] = city
    return monthly[['County', 'year', 'month', 'temp_mean', 'rain_sum']]

# ── 主程式 ────────────────────────────────────────────────────
def main():
    print(f'\n{"="*50}')
    print(f'氣象資料自動更新 {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    print(f'{"="*50}')

    api_key = get_api_key()

    # 讀取現有 CSV
    if os.path.exists(WEATHER_CSV):
        existing = pd.read_csv(WEATHER_CSV, encoding='utf-8-sig')
        print(f'\n📂 現有資料：{len(existing)} 筆，最新至 {existing["year"].max()}-{existing["month"].max():02d}')
    else:
        existing = pd.DataFrame(columns=['County', 'year', 'month', 'temp_mean', 'rain_sum'])
        print(f'\n📂 未找到現有資料，將建立新檔案')

    # 抓取各縣市最新資料
    new_rows = []
    for city, station_id in CITY_STATION.items():
        print(f'\n🏙️ {city}（{station_id}）...')
        daily = fetch_daily_recent(station_id, api_key)
        if daily.empty:
            continue
        monthly = aggregate_to_monthly(daily, city)
        if monthly.empty:
            print(f'  ⚠️ 無完整月份資料（需至少20天）')
            continue
        print(f'  → 聚合出 {len(monthly)} 個月份')
        new_rows.append(monthly)

    if not new_rows:
        print('\n⚠️ 無新資料可更新')
        return

    new_df = pd.concat(new_rows, ignore_index=True)

    # 合併：以 County+year+month 為 key，新資料覆蓋舊資料
    combined = pd.concat([existing, new_df], ignore_index=True)
    combined = (combined
                .drop_duplicates(subset=['County', 'year', 'month'], keep='last')
                .sort_values(['County', 'year', 'month'])
                .reset_index(drop=True))

    # 統計更新了多少
    old_count = len(existing)
    new_count = len(combined)
    print(f'\n📊 更新結果：{old_count} 筆 → {new_count} 筆（新增/更新 {new_count - old_count} 筆）')
    print(f'   最新資料至：{combined["year"].max()}-{combined["month"].max():02d}')

    # 存檔
    os.makedirs('data', exist_ok=True)
    combined.to_csv(WEATHER_CSV, index=False, encoding='utf-8-sig')
    print(f'\n✅ 已儲存至 {WEATHER_CSV}')
    print(f'{"="*50}\n')

if __name__ == '__main__':
    main()
