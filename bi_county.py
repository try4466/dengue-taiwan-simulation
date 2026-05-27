# bi_county.py
import pandas as pd

print("讀取 MosIndex_All.csv（約需30秒）...")
df = pd.read_csv('data/MosIndex_All.csv', 
                 encoding='utf-8-sig',
                 usecols=['Date', 'County', 'BI', 'HIAeg'],
                 low_memory=False)

print(f"原始資料：{len(df):,} 筆")

# 日期處理
df['Date'] = pd.to_datetime(df['Date'])
df['year']  = df['Date'].dt.year
df['month'] = df['Date'].dt.month

# 縣市名稱統一（台→臺）
df['County'] = df['County'].str.replace('台', '臺', regex=False)

# BI 清洗
df['BI'] = pd.to_numeric(df['BI'], errors='coerce')
df = df[df['BI'] >= 0]

# 縣市月度彙整
monthly = (
    df.groupby(['year', 'month', 'County'])
    .agg(BI_mean=('BI', 'mean'),
         BI_max =('BI', 'max'),
         surveys =('BI', 'count'))
    .reset_index()
)

print(f"月度彙整後：{len(monthly):,} 筆")
print(f"涵蓋縣市：{monthly['County'].unique().tolist()}")
print(f"年份範圍：{monthly['year'].min()} ~ {monthly['year'].max()}")
print("\n前5筆：")
print(monthly.head())

# 存檔
monthly.to_csv('data/bi_monthly.csv', index=False, encoding='utf-8-sig')
print("\n✅ 儲存完成！data/bi_monthly.csv")