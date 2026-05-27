# bi_merge.py
import pandas as pd
from scipy import stats

print("讀取資料...")
bi = pd.read_csv('data/bi_monthly.csv', encoding='utf-8-sig')

dengue = pd.read_csv('data/Dengue_Daily.csv', encoding='utf-8-sig', low_memory=False)

# 登革熱：只保留本土、月度彙整
dengue['發病日'] = pd.to_datetime(dengue['發病日'], errors='coerce')
dengue = dengue[dengue['是否境外移入'] == '否']
dengue['year']  = dengue['發病日'].dt.year
dengue['month'] = dengue['發病日'].dt.month

dengue_monthly = (
    dengue.groupby(['year', 'month', '居住縣市'])['確定病例數']
    .sum()
    .reset_index()
    .rename(columns={'居住縣市': 'County', '確定病例數': 'cases'})
)
dengue_monthly['County'] = dengue_monthly['County'].str.replace('台', '臺', regex=False)
# 合併
merged = pd.merge(bi, dengue_monthly, on=['year', 'month', 'County'], how='inner')
merged = merged[merged['year'].between(2010, 2026)]

print(f"合併後：{len(merged):,} 筆")
print(f"縣市數：{merged['County'].nunique()}")
print(f"年份：{merged['year'].min()} ~ {merged['year'].max()}")

# Pearson 相關性
r, p = stats.pearsonr(merged['BI_mean'], merged['cases'])
print(f"\n整體 Pearson r = {r:.3f}，p = {p:.4f}")

# 各縣市
print("\n各縣市相關性（r 由高到低）：")
rows = []
for county, grp in merged.groupby('County'):
    if len(grp) >= 6:
        r_c, p_c = stats.pearsonr(grp['BI_mean'], grp['cases'])
        rows.append({'縣市': county, 'r': round(r_c, 3), 
                     'p': round(p_c, 4), 'n': len(grp),
                     '顯著': '✓' if p_c < 0.05 else ''})

corr_df = pd.DataFrame(rows).sort_values('r', ascending=False)
print(corr_df.to_string(index=False))

# 存檔
merged.to_csv('data/bi_dengue_merged.csv', index=False, encoding='utf-8-sig')
corr_df.to_csv('data/bi_county_corr.csv', index=False, encoding='utf-8-sig')
print("\n✅ 儲存完成！")