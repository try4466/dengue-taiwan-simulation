# bi_plot.py
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

merged = pd.read_csv('data/bi_dengue_merged.csv', encoding='utf-8-sig')
corr   = pd.read_csv('data/bi_county_corr.csv',   encoding='utf-8-sig')

# ── 圖一：各縣市 Pearson r 長條圖 ──────────────────────────
corr_sorted = corr.sort_values('r', ascending=True)
colors = ['#D94F3D' if r >= 0 else '#4F81BD' for r in corr_sorted['r']]

fig1 = go.Figure(go.Bar(
    x=corr_sorted['r'],
    y=corr_sorted['縣市'],
    orientation='h',
    marker_color=colors,
    text=[f"r={r:.3f}{'✓' if s=='✓' else ''}" 
          for r, s in zip(corr_sorted['r'], corr_sorted['顯著'])],
    textposition='outside',
))
fig1.add_vline(x=0, line_width=1.5, line_color='black')
fig1.update_layout(
    title='各縣市布氏指數 × 登革熱病例 Pearson 相關係數',
    xaxis_title='Pearson r',
    xaxis=dict(range=[-0.55, 0.85]),
    height=550,
    template='plotly_white',
    margin=dict(l=80, r=120)
)
fig1.write_html('data/plot_pearson_r.html')
print("✅ 圖一完成：data/plot_pearson_r.html")

# ── 圖二：BI × 病例散佈圖 ──────────────────────────────────
# 排除極端爆發年（2015、2023）以看清一般趨勢
df_main = merged[~((merged['County']=='臺南市') & 
                    (merged['year'].isin([2015,2023])))]

fig2 = px.scatter(
    merged,
    x='BI_mean', y='cases',
    color='County',
    hover_data=['year','month','County','BI_mean','cases'],
    labels={'BI_mean':'布氏指數（月平均）','cases':'月病例數'},
    title='布氏指數 × 登革熱月病例數（2010–2026）',
    template='plotly_white',
    opacity=0.65,
)

# 加整體趨勢線
z = np.polyfit(merged['BI_mean'], merged['cases'], 1)
x_range = np.linspace(0, merged['BI_mean'].max(), 100)
fig2.add_trace(go.Scatter(
    x=x_range, y=np.poly1d(z)(x_range),
    mode='lines', name='趨勢線',
    line=dict(color='black', width=2, dash='dash')
))
fig2.update_layout(height=550)
fig2.write_html('data/plot_bi_scatter.html')
print("✅ 圖二完成：data/plot_bi_scatter.html")

# ── 圖三：臺南市單獨 BI 趨勢 vs 病例 ──────────────────────
tainan = merged[merged['County']=='臺南市'].copy()
tainan['date'] = pd.to_datetime(
    tainan[['year','month']].assign(day=1))
tainan = tainan.sort_values('date')

fig3 = make_subplots(specs=[[{"secondary_y": True}]])
fig3.add_trace(go.Bar(
    x=tainan['date'], y=tainan['cases'],
    name='月病例數', marker_color='rgba(216,90,48,0.5)'
), secondary_y=False)
fig3.add_trace(go.Scatter(
    x=tainan['date'], y=tainan['BI_mean'],
    name='布氏指數', line=dict(color='#1D9E75', width=2)
), secondary_y=True)
fig3.update_layout(
    title='臺南市：布氏指數 vs 月病例數',
    template='plotly_white', height=450,
    legend=dict(orientation='h', y=1.05)
)
fig3.update_yaxes(title_text='月病例數', secondary_y=False)
fig3.update_yaxes(title_text='布氏指數', secondary_y=True)
fig3.write_html('data/plot_tainan.html')
print("✅ 圖三完成：data/plot_tainan.html")

print("\n全部完成！用瀏覽器開啟 data/ 資料夾裡的 .html 檔案查看圖表")
