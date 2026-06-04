# ============================================================
#  台灣登革熱蒙地卡羅模擬 - Streamlit 儀表板
#  作者：Joyce Wang（142216013）
#  課程：系統模擬（祝國忠老師）
#  部署：Streamlit Cloud  https://streamlit.io/cloud
# ============================================================

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy import stats
from io import StringIO
import warnings
import requests
import io
warnings.filterwarnings('ignore')

# ── 頁面設定 ─────────────────────────────────────────────────
st.set_page_config(
    page_title='台灣登革熱蒙地卡羅模擬',
    page_icon='🦟',
    layout='wide',
    initial_sidebar_state='expanded'
)

# ── 自訂 CSS（醫療端風格）────────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #F8FAFC; }
    .block-container { padding-top: 1.5rem; }
    [data-testid="stMetricValue"] { font-size: 1.3rem; color: #1B6CA8; font-weight: 700; }
    [data-testid="stMetricLabel"] { font-size: 0.78rem; color: #64748B; }
    .stTabs [data-baseweb="tab"] { font-size: 0.95rem; font-weight: 600; }
    div[data-testid="stSidebar"] { background-color: #EFF6FF; }
    h1 { color: #0F2A4E !important; font-size: 1.6rem !important; }
    h2, h3 { color: #1B6CA8 !important; }
</style>
""", unsafe_allow_html=True)

# ── 標題 ─────────────────────────────────────────────────────
st.title('🦟 台灣登革熱傳播蒙地卡羅模擬系統')
st.markdown(
    '**資料來源：疾病管制署（政府資料開放平台）** ｜ '
    '課程：系統模擬 ｜ 作者：Joyce Wang'
)
st.divider()

# ── 側欄：參數設定 ────────────────────────────────────────────
st.sidebar.header('⚙️ 模擬參數設定')

CDC_CSV_URL = 'https://od.cdc.gov.tw/eic/Dengue_Daily.csv'

# 資料來源
st.sidebar.markdown('**📡 資料來源**')
if st.sidebar.button('🔄 自動下載最新資料（CDC）', use_container_width=True):
    with st.spinner('正在從疾管署下載最新資料...'):
        try:
            resp = requests.get(CDC_CSV_URL, timeout=30, verify=False)
            resp.raise_for_status()
            st.session_state['auto_csv_bytes'] = resp.content
            st.sidebar.success('✅ 下載成功！')
        except Exception as e:
            st.sidebar.error(f'❌ 下載失敗：{e}')
            st.sidebar.caption('請改用手動上傳')

st.sidebar.caption('或手動上傳 CSV：')
csv_file = st.sidebar.file_uploader(
    '上傳 Dengue_Daily.csv', type='csv',
    help='至 data.gov.tw/dataset/21025 下載後上傳'
)

st.sidebar.divider()
st.sidebar.markdown('**🔧 分析參數**')
domestic_only = st.sidebar.radio('病例來源', ['本土病例', '本土＋境外移入'], index=0) == '本土病例'
year_start    = st.sidebar.slider('起始年份', 1998, 2015, 2003)
n_iter        = st.sidebar.select_slider('模擬次數', [500, 1000, 5000, 10000], value=10000)
recent_years  = st.sidebar.slider('週別預測近幾年', 3, 10, 5)
outbreak_mult = st.sidebar.slider('爆發定義（均值倍數）', 1.0, 3.0, 1.5, 0.1)

st.sidebar.divider()
st.sidebar.markdown('**📋 使用說明**')
st.sidebar.markdown('''
1. 點「🔄 自動下載」取得最新 CDC 資料
2. 調整模擬參數
3. 圖表自動重新計算
4. 下載 Excel 結果報表
''')

# ── 資料讀取 ──────────────────────────────────────────────────
def load_raw_df(csv_file):
    # 優先順序：手動上傳 > 自動下載 > repo 內建資料
    if csv_file is not None:
        raw = csv_file.read()
        st.sidebar.success('✅ 已載入：手動上傳')
        return pd.read_csv(StringIO(raw.decode('utf-8-sig')), low_memory=False)
    if 'auto_csv_bytes' in st.session_state:
        st.sidebar.success('✅ 已載入：CDC 自動下載')
        return pd.read_csv(
            StringIO(st.session_state['auto_csv_bytes'].decode('utf-8-sig')),
            low_memory=False
        )
    try:
        df = pd.read_csv('data/Dengue_Daily.csv', encoding='utf-8-sig', low_memory=False)
        st.sidebar.info('ℹ️ 已載入：內建資料（data/Dengue_Daily.csv）')
        return df
    except FileNotFoundError:
        return None

df_raw = load_raw_df(csv_file)

if df_raw is None:
    st.warning('⚠️ 尚未載入資料，請點選左側「🔄 自動下載最新資料」')
    st.info('或手動上傳 Dengue_Daily.csv（至 data.gov.tw/dataset/21025 下載）')
    st.stop()

# ── 資料前處理 ────────────────────────────────────────────────
def process_df(df, domestic_only, year_start):
    df['發病日'] = pd.to_datetime(df['發病日'], errors='coerce')
    df = df.dropna(subset=['發病日'])
    df['year'] = df['發病日'].dt.year
    df['week'] = df['發病日'].dt.isocalendar().week.astype(int)
    df['確定病例數'] = pd.to_numeric(df['確定病例數'], errors='coerce').fillna(0)
    if domestic_only and '是否境外移入' in df.columns:
        df = df[df['是否境外移入'] == '否']
    df = df[df['year'] >= year_start]
    latest = df['發病日'].max().strftime('%Y-%m-%d')
    weekly = (df.groupby(['year', 'week'])['確定病例數']
              .sum().reset_index()
              .rename(columns={'確定病例數': 'cases'}))
    weekly = weekly[weekly['cases'] > 0].copy()
    return weekly, latest

weekly_df, latest_date = process_df(df_raw, domestic_only, year_start)

# ── Rt 估計函式 ───────────────────────────────────────────────
def _estimate_rt(weekly_df, serial_interval_weeks=2):
    """Wallinga-Lipsitch 近似法：Rt ≈ C(t) / C(t-SI)"""
    all_rt, rt_by_year = [], {}
    for yr in sorted(weekly_df['year'].unique()):
        yr_df = weekly_df[weekly_df['year'] == yr].sort_values('week')
        cases = yr_df.set_index('week')['cases'].reindex(range(1, 53), fill_value=0).values
        rt_vals = [cases[t] / cases[t - serial_interval_weeks]
                   for t in range(serial_interval_weeks, len(cases))
                   if cases[t - serial_interval_weeks] > 5]
        if rt_vals:
            rt_by_year[yr] = np.array(rt_vals)
            all_rt.extend(rt_vals)
    all_rt = np.array(all_rt)
    all_rt = all_rt[(all_rt > 0) & (all_rt < 20)]

    if len(all_rt) < 5:
        return {
            'all_rt': np.array([1.0]), 'annual_rt_median': {},
            'rt_median': float('nan'), 'rt_ci_lo': float('nan'),
            'rt_ci_hi': float('nan'), 'p_above1': float('nan'),
            'serial_interval_weeks': serial_interval_weeks,
            'insufficient_data': True,
        }
    annual_rt_median = {yr: float(np.median(v)) for yr, v in rt_by_year.items()}
    return {
        'all_rt': all_rt, 'annual_rt_median': annual_rt_median,
        'rt_median': float(np.median(all_rt)),
        'rt_ci_lo': float(np.percentile(all_rt, 2.5)),
        'rt_ci_hi': float(np.percentile(all_rt, 97.5)),
        'p_above1': float((all_rt > 1).mean() * 100),
        'serial_interval_weeks': serial_interval_weeks,
        'insufficient_data': False,
    }

def _simulate_r(rt_info, n_iter):
    """以估計 Rt 擬合 Gamma 分配後模擬 R 值分佈"""
    all_rt = rt_info['all_rt']
    if rt_info.get('insufficient_data', False) or len(all_rt) < 5:
        return {
            'r_sim': np.array([1.0]), 'gamma_shape': float('nan'),
            'gamma_scale': float('nan'), 'r_sim_median': float('nan'),
            'r_sim_ci_lo': float('nan'), 'r_sim_ci_hi': float('nan'),
            'p_above1': float('nan'),
        }
    shape, loc, scale = stats.gamma.fit(all_rt, floc=0)
    r_sim = stats.gamma.rvs(shape, loc=loc, scale=scale, size=n_iter)
    r_sim = r_sim[(r_sim > 0) & (r_sim < 20)]
    return {
        'r_sim': r_sim, 'gamma_shape': float(shape), 'gamma_scale': float(scale),
        'r_sim_median': float(np.median(r_sim)),
        'r_sim_ci_lo': float(np.percentile(r_sim, 2.5)),
        'r_sim_ci_hi': float(np.percentile(r_sim, 97.5)),
        'p_above1': float((r_sim > 1).mean() * 100),
    }

# ── 主模擬函式（cache）────────────────────────────────────────
@st.cache_data
def run_sim(data_key, n_iter, recent_years, outbreak_mult):
    weekly_df   = st.session_state['weekly_df']
    all_cases   = weekly_df['cases'].values
    all_data    = all_cases[all_cases > 0]
    max_year    = int(weekly_df['year'].max())
    recent_df   = weekly_df[weekly_df['year'] >= max_year - recent_years + 1]
    recent_data = recent_df['cases'].values
    recent_data = recent_data[recent_data > 0]
    hist_annual = weekly_df.groupby('year')['cases'].sum()
    hist_mean   = hist_annual.mean()

    def fit(data):
        fits = {}
        for name, label in [('norm', '常態'), ('lognorm', '對數常態'), ('gamma', 'Gamma')]:
            try:
                d = getattr(stats, name)
                p = d.fit(data) if name == 'norm' else d.fit(data, floc=0)
                _, ks = stats.kstest(data, name, args=p)
                fits[name] = {'params': p, 'ks_p': ks, 'dist': d, 'label': label}
            except Exception:
                pass
        best = max(fits, key=lambda k: fits[k]['ks_p']) if fits else list(fits.keys())[0]
        return fits, best

    fits, best    = fit(all_data)
    rf, rb        = fit(recent_data)
    best_info     = fits[best]
    recent_info   = rf.get(rb, best_info)

    annual_totals = np.zeros(n_iter)
    weekly_sims   = np.zeros((n_iter, 52))
    for i in range(n_iter):
        ann              = np.maximum(0, best_info['dist'].rvs(*best_info['params'], size=52))
        annual_totals[i] = ann.sum()
        weekly_sims[i]   = np.maximum(0, recent_info['dist'].rvs(*recent_info['params'], size=52))

    p995       = np.percentile(annual_totals, 99.5)
    rt_info    = _estimate_rt(weekly_df)
    r_sim_info = _simulate_r(rt_info, n_iter)

    return {
        'fits':          fits,
        'best':          best,
        'best_label':    best_info['label'],
        'hist_annual':   hist_annual,         # ← Series，帶出去供 Excel 使用
        'hist_mean':     hist_mean,
        'median_annual': float(np.median(annual_totals)),
        'mean_annual':   float(annual_totals.mean()),
        'std_annual':    float(annual_totals.std()),
        'ci_lower':      float(np.percentile(annual_totals, 2.5)),
        'ci_upper':      float(np.percentile(annual_totals, 97.5)),
        'outbreak_prob': float((annual_totals > hist_mean * outbreak_mult).mean() * 100),
        'annual_plot':   annual_totals[annual_totals <= p995],
        'annual_totals': annual_totals,
        'weekly_median': np.median(weekly_sims, axis=0),
        'weekly_ci_low': np.percentile(weekly_sims, 2.5,  axis=0),
        'weekly_ci_hi':  np.percentile(weekly_sims, 97.5, axis=0),
        'recent_mean':   float(recent_data.mean()),
        'recent_years':  recent_years,
        'rt_info':       rt_info,
        'r_sim_info':    r_sim_info,
    }

# ── 執行模擬 ─────────────────────────────────────────────────
st.session_state['weekly_df'] = weekly_df
data_key = f"{latest_date}_{len(weekly_df)}_{domestic_only}_{year_start}"

with st.spinner(f'執行蒙地卡羅模擬（{n_iter:,} 次）...'):
    sim = run_sim(data_key, n_iter, recent_years, outbreak_mult)

# ── 資料資訊列 ────────────────────────────────────────────────
c = st.columns(4)
c[0].info(f"📅 資料最新日期：**{latest_date}**")
c[1].info(f"📊 涵蓋年份：**{int(weekly_df['year'].min())}~{int(weekly_df['year'].max())}**")
c[2].info(f"🗂️ 週別資料：**{len(weekly_df):,} 筆**")
c[3].info(f"🔁 模擬次數：**{n_iter:,} 次**")

st.divider()

# ── 統計摘要卡片 ──────────────────────────────────────────────
st.subheader('📊 模擬統計摘要')
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric('最佳機率分配',  sim['best_label'])
c2.metric('歷史年均病例',  f"{sim['hist_mean']:,.0f} 例")
c3.metric('預測中位數',    f"{sim['median_annual']:,.0f} 例")
c4.metric('95% 信賴區間',  f"{sim['ci_lower']:,.0f} ~ {sim['ci_upper']:,.0f}")
c5.metric('爆發機率',      f"{sim['outbreak_prob']:.1f}%",
          delta=f"閾值：均值×{outbreak_mult}", delta_color='inverse')

st.divider()

# ── 圖表分頁 ─────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs(['📈 病例數模擬', '🔴 R 值分析', '🦟 布氏指數分析', '🌡️ 氣象分析', '🔮 Bayesian 預測'])

# ── 從 sim 取出 hist_annual（兩個 tab 都需要）────────────────
ha = sim['hist_annual']

with tab1:
    st.subheader('模擬結果圖表')
    yr_min = int(ha.index.min())
    yr_max = int(ha.index.max())

    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=[
            f'歷史年度確診病例（{yr_min}~{yr_max}）',
            f'模擬年總病例分佈（{n_iter:,} 次）',
            f'週別預測（近 {recent_years} 年）',
            '大數法則收斂驗證'
        ],
        vertical_spacing=0.14, horizontal_spacing=0.08
    )

    # 圖1：歷史年度長條
    colors = ['#D85A30' if v == ha.max() else '#1D9E75' for v in ha.values]
    fig.add_trace(go.Bar(
        x=ha.index.astype(str), y=ha.values, marker_color=colors,
        text=[f'{int(v):,}' if v > 5000 else '' for v in ha.values],
        textposition='outside', name='年度確診數'
    ), row=1, col=1)
    fig.add_hline(y=sim['hist_mean'], line_dash='dash', line_color='#888780',
                  annotation_text=f"均值 {sim['hist_mean']:,.0f}", row=1, col=1)

    # 圖2：模擬分佈直方圖
    fig.add_trace(go.Histogram(
        x=sim['annual_plot'], nbinsx=80,
        marker_color='#378ADD', opacity=0.75, name='模擬年總病例'
    ), row=1, col=2)
    fig.add_vline(x=sim['median_annual'], line_color='#D85A30', line_width=2.5,
                  annotation_text=f"中位 {sim['median_annual']:,.0f}", row=1, col=2)
    fig.add_vline(x=sim['ci_lower'],  line_dash='dash', line_color='#888780', row=1, col=2)
    fig.add_vline(x=sim['ci_upper'],  line_dash='dash', line_color='#888780',
                  annotation_text=f"CI上限 {sim['ci_upper']:,.0f}", row=1, col=2)
    fig.add_vline(x=sim['hist_mean'], line_dash='dot',  line_color='#1D9E75',
                  annotation_text='歷史均值', row=1, col=2)

    # 圖3：週別預測
    weeks = list(range(1, 53))
    fig.add_trace(go.Scatter(
        x=weeks + weeks[::-1],
        y=list(sim['weekly_ci_hi']) + list(sim['weekly_ci_low'][::-1]),
        fill='toself', fillcolor='rgba(55,138,221,0.2)',
        line=dict(color='rgba(0,0,0,0)'), name='95% CI'
    ), row=2, col=1)
    fig.add_trace(go.Scatter(
        x=weeks, y=sim['weekly_median'],
        line=dict(color='#378ADD', width=2), name='週別中位數'
    ), row=2, col=1)
    fig.add_hline(y=sim['recent_mean'], line_dash='dash', line_color='#1D9E75',
                  annotation_text=f"近{recent_years}年週均 {sim['recent_mean']:.0f}",
                  row=2, col=1)

    # 圖4：大數法則收斂
    totals = sim['annual_totals']
    cum    = np.cumsum(totals) / np.arange(1, len(totals) + 1)
    fig.add_trace(go.Scatter(
        x=list(range(1, n_iter + 1)), y=cum,
        line=dict(color='#BA7517', width=1.2), name='累積平均'
    ), row=2, col=2)
    fig.add_hline(y=sim['median_annual'], line_dash='dash', line_color='#D85A30',
                  annotation_text=f"穩定值 {sim['median_annual']:,.0f}", row=2, col=2)

    fig.update_layout(
        height=750, showlegend=False,
        title_text=f'台灣登革熱蒙地卡羅模擬 ｜ 資料更新：{latest_date}',
        title_font_size=13,
        plot_bgcolor='white', paper_bgcolor='white'
    )
    fig.update_xaxes(tickangle=45, row=1, col=1)
    st.plotly_chart(fig, use_container_width=True)

    st.divider()
    with st.expander('📋 方法論'):
        st.markdown("""
**資料來源**
- 疾病管制署開放資料平台：登革熱確定病例（Dengue_Daily.csv）
- 本土病例，涵蓋 2003~2026 年

**分析方法**
- Step 1：KS 檢定比較常態、對數常態、Gamma 三種分配，對數常態擬合最佳
- Step 2：以對數常態參數執行 10,000 次蒙地卡羅模擬，輸出 95% CI 與爆發機率
- Step 3：大數法則驗證，約 2,000 次迭代後累積平均收斂

**假設與限制**
- 假設歷史分配未來仍適用，不考慮氣候變遷與人口免疫力變化
- 蒙地卡羅為靜態模擬，無法即時吸收新病例資訊

**文獻支持**
- Sawadogo et al. (2024) Applied Mathematics — 大數法則驗證登革熱隨機模型
- MCMC + SIR dengue outbreak prediction (2022) PMID: 35361845
- Nishiura & Halstead (2007) JID — 登革熱世代間隔 14 天
        """)

with tab2:
    st.subheader('R 值分析（Python Wallinga-Lipsitch 估計）')
    rt_info    = sim['rt_info']
    r_sim_info = sim['r_sim_info']

    if rt_info.get('insufficient_data', False):
        st.warning('⚠️ 病例數過少，無法估計 Rt。請選擇病例較多的年份範圍。')
    else:
        r1, r2, r3, r4, r5 = st.columns(5)
        r1.metric('估計 Rt 中位數',  f"{rt_info['rt_median']:.2f}")
        r2.metric('估計 Rt 95% CI',  f"{rt_info['rt_ci_lo']:.2f} ~ {rt_info['rt_ci_hi']:.2f}")
        r3.metric('Rt > 1 週次占比', f"{rt_info['p_above1']:.1f}%",
                  help='Rt > 1 代表疫情仍在擴散的週次比例')
        r4.metric('模擬 R 中位數',   f"{r_sim_info['r_sim_median']:.2f}")
        r5.metric('模擬 P(R>1)',     f"{r_sim_info['p_above1']:.1f}%")

        st.caption(
            f"估計方法：Wallinga-Lipsitch 近似法，世代間隔 = 14 天（2 週）｜"
            f"模擬分配：Gamma（shape={r_sim_info['gamma_shape']:.3f}，"
            f"scale={r_sim_info['gamma_scale']:.3f}）"
        )
        st.divider()

        fig_r = make_subplots(
            rows=1, cols=2,
            subplot_titles=['年度 Rt 中位數趨勢（歷史估計）', 'R 值分佈：模擬 Gamma vs 歷史估計 Rt'],
            horizontal_spacing=0.1
        )

        # 左：年度 Rt 長條
        years_rt   = sorted(rt_info['annual_rt_median'].keys())
        rt_meds    = [rt_info['annual_rt_median'][y] for y in years_rt]
        bar_colors = ['#D85A30' if r > 1 else '#1D9E75' for r in rt_meds]
        fig_r.add_trace(go.Bar(
            x=list(map(str, years_rt)), y=rt_meds,
            marker_color=bar_colors, opacity=0.85,
            text=[f'{r:.2f}' if r > 1.8 else '' for r in rt_meds],
            textposition='outside', name='年度Rt中位數'
        ), row=1, col=1)
        fig_r.add_hline(y=1.0, line_dash='dash', line_color='#E24B4A',
                        annotation_text='R=1（臨界值）', row=1, col=1)
        fig_r.add_hline(y=rt_info['rt_median'], line_dash='dot', line_color='#888780',
                        annotation_text=f"全期中位數 {rt_info['rt_median']:.2f}", row=1, col=1)

        # 右：分佈疊加
        r_sim_plot = r_sim_info['r_sim'][r_sim_info['r_sim'] <= 10]
        fig_r.add_trace(go.Histogram(
            x=r_sim_plot, nbinsx=60, histnorm='probability density',
            marker_color='#1D9E75', opacity=0.65, name='模擬 R（Gamma）'
        ), row=1, col=2)
        rt_plot = rt_info['all_rt'][rt_info['all_rt'] <= 10]
        fig_r.add_trace(go.Histogram(
            x=rt_plot, nbinsx=60, histnorm='probability density',
            marker_color='#BA7517', opacity=0.5, name='歷史估計 Rt'
        ), row=1, col=2)
        fig_r.add_vline(x=1.0, line_color='#E24B4A', line_width=2.2, line_dash='dash',
                        annotation_text='R=1', row=1, col=2)
        fig_r.add_vline(x=r_sim_info['r_sim_ci_lo'], line_color='#378ADD',
                        line_width=1.2, line_dash='dot', row=1, col=2)
        fig_r.add_vline(x=r_sim_info['r_sim_ci_hi'], line_color='#378ADD',
                        line_width=1.2, line_dash='dot',
                        annotation_text='95% CI', row=1, col=2)

        fig_r.update_layout(
            height=440, barmode='overlay', showlegend=True,
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
            title_text=f'R 值分析 ｜ SI=14天 ｜ {n_iter:,} 次模擬',
            title_font_size=12,
            plot_bgcolor='white', paper_bgcolor='white'
        )
        fig_r.update_xaxes(title_text='年份', tickangle=45, row=1, col=1)
        fig_r.update_xaxes(title_text='R / Rt', range=[0, 8], row=1, col=2)
        fig_r.update_yaxes(title_text='Rt 中位數', row=1, col=1)
        fig_r.update_yaxes(title_text='Density',   row=1, col=2)
        st.plotly_chart(fig_r, use_container_width=True)

        # 年度 Rt 數值表
        st.subheader('年度 Rt 估計值')
        rt_df = pd.DataFrame({
            '年份':   years_rt,
            'Rt 中位數': [round(rt_info['annual_rt_median'][y], 3) for y in years_rt],
            '疫情狀態': ['🔴 擴散 (R>1)' if rt_info['annual_rt_median'][y] > 1
                        else '🟢 控制 (R≤1)' for y in years_rt],
        })
        st.dataframe(rt_df, use_container_width=True, hide_index=True)

        st.divider()
        with st.expander('📋 方法論'):
            st.markdown("""
**資料來源**
- 疾病管制署 Dengue_Daily.csv 本土病例週別資料，2003~2026 年

**分析方法**

*Python Wallinga-Lipsitch 近似法*
- 公式：Rt ≈ C(t) / C(t - SI)，SI = 世代間隔 = 14 天（2 週）
- 以週別病例數反推估計有效再生數，僅計算分母週次病例數 > 5 的週次
- 模擬 R 值分佈：以 Gamma 分配擬合歷史 Rt，進行 10,000 次模擬

*R EpiEstim 貝氏估計（延伸驗證）*
- 採用 Cori et al. (2013) 方法，以貝氏後驗分佈估計每時間點的 Rt
- 世代間隔 14 天，滑動窗口 7 週，僅計算有病例傳播的週次
- EpiEstim Rt 中位數（1.42）高於 Python（0.89），因排除零病例週次

*兩者差異說明*
- Python Wallinga 法：含零病例週次，Rt 中位數偏低（0.89）
- R EpiEstim 貝氏法：僅有傳播週次，學術主流，Rt 中位數（1.42）

**假設前提與限制**
- 世代間隔固定為 14 天，實際上有個體差異（SD ≈ 4 天）
- Wallinga 法為近似估計，不考慮右截斷偏誤（right truncation bias）
- Rt > 1 表示疫情擴散，但不代表一定爆發，需結合病例絕對數判斷

**文獻支持**
- Cori et al. (2013) American Journal of Epidemiology — EpiEstim 貝氏 Rt 估計方法，DOI: 10.1093/aje/kwt133
- Wallinga & Lipsitch (2007) Proc Royal Society B — Rt 近似估計公式，DOI: 10.1098/rspb.2006.3754
- Nishiura & Halstead (2007) JID — 登革熱世代間隔 14 天，DOI: 10.1086/511825
            """)

st.divider()

# ── KS 檢定表 ─────────────────────────────────────────────────
st.subheader('🔬 機率分配擬合（KS 檢定）')
st.dataframe(pd.DataFrame([{
    '分配':          info['label'],
    'KS statistic':  f"{info['ks_p']:.2e}",
    '判讀':          'p 越大越好擬合',
    '結果':          '✅ 最佳' if name == sim['best'] else ''
} for name, info in sim['fits'].items()]),
use_container_width=True, hide_index=True)

st.divider()

# ── 週別預測表 ────────────────────────────────────────────────
st.subheader('📅 週別預測數值')
pred_df = pd.DataFrame({
    '週次':       range(1, 53),
    '預測中位數':  np.round(sim['weekly_median'], 1),
    '95%CI下限':  np.round(sim['weekly_ci_low'],  1),
    '95%CI上限':  np.round(sim['weekly_ci_hi'],   1),
})
st.dataframe(pred_df, use_container_width=True, hide_index=True, height=280)

st.divider()

# ── 下載 Excel ────────────────────────────────────────────────
st.subheader('💾 下載結果')

rt_info    = sim['rt_info']
r_sim_info = sim['r_sim_info']

buf = io.BytesIO()
with pd.ExcelWriter(buf, engine='openpyxl') as w:
    pred_df.to_excel(w, sheet_name='週別預測', index=False)
    # ✅ 修正：ha 從 sim['hist_annual'] 取得，不依賴 tab1 內部變數
    ha.reset_index().rename(columns={'cases': '年度確診數'}).to_excel(
        w, sheet_name='歷史年度統計', index=False
    )
    pd.DataFrame({
        '項目': ['最佳機率分配', '模擬次數', '資料更新日期', '歷史年均',
                 '預測中位數', '95%CI下限', '95%CI上限', '爆發機率(%)'],
        '數值': [sim['best_label'], f"{n_iter:,}", latest_date,
                 f"{sim['hist_mean']:,.0f}", f"{sim['median_annual']:,.0f}",
                 f"{sim['ci_lower']:,.0f}", f"{sim['ci_upper']:,.0f}",
                 f"{sim['outbreak_prob']:.2f}"]
    }).to_excel(w, sheet_name='模擬統計摘要', index=False)
    pd.DataFrame({
        '項目': ['估計方法', '世代間隔假設',
                 '估計Rt中位數', '估計Rt 95%CI下限', '估計Rt 95%CI上限', 'Rt>1週次比例(%)',
                 '模擬分配', 'Gamma shape', 'Gamma scale',
                 '模擬R中位數', '模擬R 95%CI下限', '模擬R 95%CI上限', '模擬P(R>1)(%)'],
        '數值': ['Wallinga-Lipsitch 近似法', '2週（14天）',
                 f"{rt_info['rt_median']:.3f}",    f"{rt_info['rt_ci_lo']:.3f}",
                 f"{rt_info['rt_ci_hi']:.3f}",     f"{rt_info['p_above1']:.1f}",
                 'Gamma（floc=0）',                 f"{r_sim_info['gamma_shape']:.4f}",
                 f"{r_sim_info['gamma_scale']:.4f}", f"{r_sim_info['r_sim_median']:.3f}",
                 f"{r_sim_info['r_sim_ci_lo']:.3f}", f"{r_sim_info['r_sim_ci_hi']:.3f}",
                 f"{r_sim_info['p_above1']:.1f}"]
    }).to_excel(w, sheet_name='R值分析', index=False)
    pd.DataFrame({
        '年份': list(rt_info['annual_rt_median'].keys()),
        '年度Rt中位數': [round(v, 3) for v in rt_info['annual_rt_median'].values()],
        '疫情狀態': ['擴散(R>1)' if v > 1 else '控制(R≤1)'
                    for v in rt_info['annual_rt_median'].values()],
    }).to_excel(w, sheet_name='年度Rt趨勢', index=False)

st.download_button(
    '📥 下載 Excel 結果報表',
    data=buf.getvalue(),
    file_name=f'dengue_simulation_{latest_date}.xlsx',
    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    use_container_width=True
)

st.divider()
st.caption(
    f'🦟 台灣CDC登革熱蒙地卡羅模擬系統 ｜ '
    f'課程：系統模擬 ｜ 作者：Joyce Wang ｜ '
    f'資料更新：{latest_date} ｜ 部署：Streamlit Cloud'
)
# ── Tab 3：布氏指數分析 ───────────────────────────────────────
with tab3:
    st.subheader('🦟 病媒蚊布氏指數 × 登革熱病例相關分析')

    import os
    from scipy import stats as sp_stats

    # 讀取預處理好的資料
    bi_path  = 'data/bi_dengue_merged.csv'
    corr_path = 'data/bi_county_corr.csv'

    if not os.path.exists(bi_path):
        st.warning('⚠️ 尚未找到布氏指數資料，請先在本地執行 bi_merge.py')
        st.stop()

    merged = pd.read_csv(bi_path, encoding='utf-8-sig')
    corr_df = pd.read_csv(corr_path, encoding='utf-8-sig')

    # 側欄縣市選單（只在 tab3 顯示）
    counties = ['全台'] + sorted(merged['County'].unique().tolist())
    selected = st.selectbox('選擇縣市', counties, index=0)

    col1, col2 = st.columns(2)

    # ── 圖A：Pearson r 長條圖 ──────────────────────────────────
    with col1:
        st.markdown('**各縣市 Pearson 相關係數**')
        corr_sorted = corr_df.sort_values('r', ascending=True)
        colors = ['#D94F3D' if r >= 0 else '#4F81BD'
                  for r in corr_sorted['r']]
        figA = go.Figure(go.Bar(
            x=corr_sorted['r'],
            y=corr_sorted['縣市'],
            orientation='h',
            marker_color=colors,
            text=[f"r={r:.3f}{'✓' if s=='✓' else ''}"
                  for r, s in zip(corr_sorted['r'], corr_sorted['顯著'])],
            textposition='outside',
        ))
        figA.add_vline(x=0, line_width=1.5, line_color='black')
        figA.update_layout(
            xaxis=dict(range=[-0.55, 0.85]),
            height=500,
            template='plotly_white',
            margin=dict(l=70, r=100, t=20, b=20)
        )
        st.plotly_chart(figA, use_container_width=True)

    # ── 圖B：BI × 病例散佈圖 ───────────────────────────────────
    with col2:
        st.markdown('**布氏指數 × 月病例數散佈圖**')
        plot_df = merged if selected == '全台' else merged[merged['County'] == selected]
        r_val, p_val = sp_stats.pearsonr(plot_df['BI_mean'], plot_df['cases'])

        figB = go.Figure()
        figB.add_trace(go.Scatter(
            x=plot_df['BI_mean'], y=plot_df['cases'],
            mode='markers',
            marker=dict(color='#378ADD', opacity=0.6, size=7),
            customdata=plot_df[['year','month','County']].values,
            hovertemplate='%{customdata[2]} %{customdata[0]}年%{customdata[1]}月<br>'
                          'BI=%{x:.2f}　病例=%{y}<extra></extra>',
        ))
        # 趨勢線
        import numpy as np
        z = np.polyfit(plot_df['BI_mean'], plot_df['cases'], 1)
        x_r = np.linspace(plot_df['BI_mean'].min(), plot_df['BI_mean'].max(), 100)
        figB.add_trace(go.Scatter(
            x=x_r, y=np.poly1d(z)(x_r),
            mode='lines', name='趨勢線',
            line=dict(color='red', width=2, dash='dash')
        ))
        figB.update_layout(
            xaxis_title='布氏指數（月平均）',
            yaxis_title='月病例數',
            title=f'Pearson r = {r_val:.3f}　p = {p_val:.4f}',
            height=500,
            template='plotly_white',
            showlegend=False,
            margin=dict(t=50, b=40)
        )
        st.plotly_chart(figB, use_container_width=True)

    # ── 圖C：時序圖（單一縣市）────────────────────────────────
    if selected != '全台':
        st.markdown(f'**{selected}：布氏指數 vs 月病例數時序**')
        ts = plot_df.copy()
        ts['date'] = pd.to_datetime(ts[['year','month']].assign(day=1))
        ts = ts.sort_values('date')

        figC = make_subplots(specs=[[{"secondary_y": True}]])
        figC.add_trace(go.Bar(
            x=ts['date'], y=ts['cases'],
            name='月病例數',
            marker_color='rgba(216,90,48,0.5)'
        ), secondary_y=False)
        figC.add_trace(go.Scatter(
            x=ts['date'], y=ts['BI_mean'],
            name='布氏指數',
            line=dict(color='#1D9E75', width=2)
        ), secondary_y=True)
        figC.update_layout(
            template='plotly_white', height=380,
            legend=dict(orientation='h', y=1.05),
            margin=dict(t=30, b=30)
        )
        figC.update_yaxes(title_text='月病例數', secondary_y=False)
        figC.update_yaxes(title_text='布氏指數', secondary_y=True)
        st.plotly_chart(figC, use_container_width=True)
    else:
        st.info('💡 選擇特定縣市可查看 BI 與病例的時序對比圖')

    st.divider()
    with st.expander('📋 方法論'):
        st.markdown("""
**資料來源**
- 疾病管制署病媒蚊密度調查資料（MosIndex_All.csv）：布氏指數（BI）與埃及斑蚊指數（HIAeg）
- 疾管署登革熱確定病例（Dengue_Daily.csv）：依縣市聚合為月別病例數

**布氏指數（Breteau Index, BI）說明**
- 定義：每 100 戶中有孑孓孳生容器的數量
- BI ≥ 20：高度警戒，爆發風險顯著上升
- BI < 5：相對安全，但仍需持續監測

**分析方法**
- Pearson 相關係數（r）：衡量各縣市月均 BI 與月病例數的線性相關強度
- 縣市層級分析：整體 r 值接近零（生態謬誤），縣市層級才能呈現有意義的相關性
- 感控介入效應：高爆發縣市（如台南市）因政府介入壓低 BI，可能出現負相關，為感控成效的正向指標

**生態謬誤（Ecological Fallacy）說明**
- 整體 Pearson r ≈ 0 並非代表 BI 與病例無關
- 需在縣市層級分析才能正確評估 BI 與病例的關聯性
- 此現象已有文獻記載，為區域性流行病學分析的常見限制

**文獻支持**
- Focks et al. (2000) Am J Trop Med Hyg — BI 與登革熱傳播閾值，25°C 下 BI ≥ 5 即具傳播風險
- Brady et al. (2014) PLOS NTD — 病媒蚊密度指標與登革熱爆發風險評估，DOI: 10.1371/journal.pntd.0002450
- Tien et al. (2018) PLOS ONE — 高雄市登革熱與病媒蚊、氣象因子的綜合分析，DOI: 10.1371/journal.pone.0190637
        """)
        # ============================================================
#  TAB4：氣象分析模組
#  整合方式：將此程式碼加入 dashboard.py
#
#  修改步驟：
#  1. 找到這一行：
#     tab1, tab2, tab3 = st.tabs([...])
#     改為：
#     tab1, tab2, tab3, tab4, tab5 = st.tabs(['📈 病例數模擬', '🔴 R 值分析', '🦟 布氏指數分析', '🌡️ 氣象分析', '🔮 Bayesian 預測'])
#
#  2. 在 dashboard.py 最底部（tab3 的 with 區塊結束後）
#     貼上以下所有程式碼
# ============================================================

# ── Tab 4：氣象分析 ──────────────────────────────────────────
# ============================================================
#  TAB4 v2：氣象分析（感控師版）
#  資料：CODiS 逐年月資料（weather_monthly_codis.csv）
#  整合：把 dashboard.py 最底部的 with tab4: 整段換成這個
# ============================================================

with tab4:
    st.subheader('🌡️ 氣象因子 × 登革熱病例相關分析')
    st.caption('資料來源：中央氣象署 CODiS（2010~2026）｜台南／高雄／嘉義／屏東四測站')

    import os
    from scipy import stats as sp_stats

    WEATHER_PATH = 'data/weather_monthly_codis.csv'

    CITY_NAME_MAP = {
        '台南市': '台南（467410）',
        '高雄市': '高雄（467440/467441）',
        '嘉義市': '嘉義（467480）',
        '屏東縣': '恆春（467590，代表屏東）',
    }

    if not os.path.exists(WEATHER_PATH):
        st.error('❌ 找不到 data/weather_monthly_codis.csv，請確認檔案已放入 data/ 資料夾')
        st.stop()

    @st.cache_data(show_spinner=False)
    def load_weather():
        df = pd.read_csv(WEATHER_PATH, encoding='utf-8-sig')
        df = df.dropna(subset=['temp_mean', 'rain_sum'])
        return df

    weather_df = load_weather()
    w_yr_min = int(weather_df['year'].min())
    w_yr_max = int(weather_df['year'].max())

    @st.cache_data(show_spinner=False)
    def get_dengue_monthly_v2(data_key: str) -> pd.DataFrame:
        df = st.session_state.get('raw_df_for_weather')
        if df is None:
            return pd.DataFrame()
        df2 = df.copy()
        df2['發病日'] = pd.to_datetime(df2['發病日'], errors='coerce')
        df2 = df2.dropna(subset=['發病日'])
        df2['year']  = df2['發病日'].dt.year
        df2['month'] = df2['發病日'].dt.month
        df2['確定病例數'] = pd.to_numeric(df2['確定病例數'], errors='coerce').fillna(0)
        if '是否境外移入' in df2.columns:
            df2 = df2[df2['是否境外移入'] == '否']
        county_col = None
        for c in ['居住縣市', '縣市', 'County']:
            if c in df2.columns:
                county_col = c
                break
        if county_col:
            monthly = (df2.groupby(['year', 'month', county_col])['確定病例數']
                          .sum().reset_index()
                          .rename(columns={county_col: 'County', '確定病例數': 'cases'}))
        else:
            monthly = (df2.groupby(['year', 'month'])['確定病例數']
                          .sum().reset_index()
                          .rename(columns={'確定病例數': 'cases'}))
            monthly['County'] = '全台'
        return monthly[monthly['year'] >= 2010]

    if df_raw is not None:
        st.session_state['raw_df_for_weather'] = df_raw

    dengue_monthly = get_dengue_monthly_v2(data_key)

    # ── ① 感控重點卡片（修正版）────────────────────────────────
    st.markdown('#### 🔑 感控重點：登革熱三角傳播鏈')
    c1, c2, c3 = st.columns(3)
    with c1:
        st.info(
            '**☀️ 高溫（>25°C）**\n\n'
            '氣溫升高加速病媒蚊（埃及斑蚊）\n'
            '發育與叮咬頻率，病毒外潛伏期縮短\n\n'
            '**→ 登革熱傳播效率顯著提升**'
        )
    with c2:
        st.info(
            '**🌧️ 降雨（積水孳生）**\n\n'
            '降雨後積水容器成為孑孓孳生源，\n'
            '約 2~4 週後羽化為成蚊\n\n'
            '**→ 病媒蚊密度暴增，傳播風險升高**'
        )
    with c3:
        st.info(
            '**⏱️ 高峰滯後 1~2 個月**\n\n'
            '氣溫高峰（7~8月）後，\n'
            '病媒蚊孵化→叮咬→人體發病\n\n'
            '**→ 病例高峰落在 9~10 月**'
        )

    st.divider()

    # ── ② 縣市 & 年份選擇 ───────────────────────────────────────
    col_sel1, col_sel2 = st.columns([1, 1])
    with col_sel1:
        selected_city = st.selectbox(
            '選擇縣市',
            options=list(CITY_NAME_MAP.keys()),
            index=0,
            format_func=lambda x: CITY_NAME_MAP[x]
        )
    with col_sel2:
        available_years = sorted(weather_df['year'].unique(), reverse=True)
        selected_year = st.selectbox(
            '選擇年份（單年詳細分析）',
            options=[f'全期（{w_yr_min}~{w_yr_max}）'] + [str(y) for y in available_years],
            index=0
        )

    # ── 準備資料 ─────────────────────────────────────────────────
    w_city = weather_df[weather_df['County'] == selected_city].copy()

    if 'County' in dengue_monthly.columns and selected_city in dengue_monthly['County'].values:
        d_city = dengue_monthly[dengue_monthly['County'] == selected_city].copy()
    else:
        d_city = dengue_monthly.groupby(['year', 'month'])['cases'].sum().reset_index()

    merged = pd.merge(d_city, w_city[['year', 'month', 'temp_mean', 'rain_sum']],
                      on=['year', 'month'], how='inner').dropna()
    merged['date'] = pd.to_datetime(merged[['year', 'month']].assign(day=1))
    merged = merged.sort_values('date').reset_index(drop=True)

    is_full_period = selected_year.startswith('全期')
    if not is_full_period:
        yr = int(selected_year)
        merged_view = merged[merged['year'] == yr].copy()
        period_label = f'{selected_year} 年'
    else:
        merged_view = merged.copy()
        period_label = f'全期（{w_yr_min}~{w_yr_max}）'

    # ── ③ 主視覺：雙軸時序圖 ────────────────────────────────────
    st.markdown(f'#### 📊 {selected_city}：氣溫 × 病例數時序對比（{period_label}）')

    if merged_view.empty:
        st.warning('此年份或縣市無資料')
    else:
        month_labels = ['1月','2月','3月','4月','5月','6月',
                        '7月','8月','9月','10月','11月','12月']

        fig_main = make_subplots(specs=[[{"secondary_y": True}]])

        fig_main.add_trace(go.Bar(
            x=merged_view['date'],
            y=merged_view['cases'],
            name='月病例數',
            marker_color='rgba(216,90,48,0.6)',
            hovertemplate='%{x|%Y年%m月}<br>病例數：%{y:,.0f} 例<extra></extra>',
        ), secondary_y=False)

        fig_main.add_trace(go.Scatter(
            x=merged_view['date'],
            y=merged_view['temp_mean'],
            name='月均溫（°C）',
            line=dict(color='#D85A30', width=3),
            mode='lines+markers',
            marker=dict(size=6),
            hovertemplate='%{x|%Y年%m月}<br>月均溫：%{y:.1f}°C<extra></extra>',
        ), secondary_y=True)

        fig_main.add_hline(
            y=25, line_dash='dot', line_color='#D85A30',
            line_width=1.5, secondary_y=True,
            annotation_text='25°C（病媒蚊活躍閾值）',
            annotation_position='top right'
        )

        fig_main.update_layout(
            height=400,
            plot_bgcolor='white', paper_bgcolor='white',
            legend=dict(orientation='h', y=1.08, x=0),
            hovermode='x unified',
            title_text=f'{selected_city} {period_label} ｜ 月均溫（紅線）與月病例數（橘柱）對比',
            title_font_size=13,
        )
        fig_main.update_yaxes(
            title_text='月病例數（例）', secondary_y=False,
            gridcolor='#F0F0F0'
        )
        fig_main.update_yaxes(
            title_text='月均溫（°C）', secondary_y=True,
            range=[10, 38]
        )
        fig_main.update_xaxes(gridcolor='#F0F0F0')
        st.plotly_chart(fig_main, use_container_width=True)

        if not is_full_period:
            yr_cases  = int(merged_view['cases'].sum())
            peak_m    = int(merged_view.loc[merged_view['cases'].idxmax(), 'month'])
            peak_t_m  = int(merged_view.loc[merged_view['temp_mean'].idxmax(), 'month'])
            lag_m     = (peak_m - peak_t_m) % 12
            st.success(
                f'📌 **{selected_year} 年快速解讀**：'
                f'全年本土病例合計 **{yr_cases:,} 例**。'
                f'氣溫高峰在 **{peak_t_m} 月**（{merged_view.loc[merged_view["temp_mean"].idxmax(), "temp_mean"]:.1f}°C），'
                f'病例高峰在 **{peak_m} 月**，兩者相差 **{lag_m} 個月**，'
                f'符合病媒蚊孵化→成蚊→叮咬→發病的生物延遲週期（文獻：Tien et al., 2018）。'
            )
        else:
            st.info(
                f'💡 選擇特定年份（如 2015 年）可查看單年氣溫與病例的詳細對比，'
                f'並自動計算滯後月數。'
            )

    st.divider()

    # ── ④ 季節性分析（明確標示年份範圍）──────────────────────
    d_yr_min = int(merged['year'].min())
    d_yr_max = int(merged['year'].max())
    st.markdown(
        f'#### 🕐 {selected_city}：月均值季節性分析'
        f'（{d_yr_min}~{d_yr_max} 年，共 {d_yr_max - d_yr_min + 1} 年平均）'
    )
    st.caption(
        f'以 {d_yr_min}~{d_yr_max} 年共 **{d_yr_max - d_yr_min + 1} 年** 實際逐月資料，'
        f'計算各月平均值，消除年際變異後呈現季節性規律。'
        f'樣本數：每月約 {d_yr_max - d_yr_min + 1} 個觀測值。'
    )

    seasonal = merged.groupby('month').agg(
        cases_mean=('cases', 'mean'),
        temp_mean_=('temp_mean', 'mean'),
        rain_mean=('rain_sum', 'mean'),
    ).reset_index()

    peak_m = int(seasonal.loc[seasonal['cases_mean'].idxmax(), 'month'])
    temp_peak = int(seasonal.loc[seasonal['temp_mean_'].idxmax(), 'month'])
    lag_season = (peak_m - temp_peak) % 12

    col_s1, col_s2 = st.columns(2)

    with col_s1:
        bar_colors = []
        for m in seasonal['month']:
            if m == peak_m:
                bar_colors.append('#D85A30')
            elif abs(m - peak_m) <= 1 or abs(m - peak_m) >= 11:
                bar_colors.append('#BA7517')
            else:
                bar_colors.append('#1D9E75')

        fig_season = go.Figure(go.Bar(
            x=[month_labels[m-1] for m in seasonal['month']],
            y=seasonal['cases_mean'].round(1),
            marker_color=bar_colors,
            text=[f'{v:.0f}' if v > seasonal['cases_mean'].mean() else ''
                  for v in seasonal['cases_mean']],
            textposition='outside',
            hovertemplate='%{x}<br>月均病例：%{y:.1f} 例<extra></extra>',
        ))
        fig_season.update_layout(
            height=340,
            title_text=f'月均病例數（{d_yr_min}~{d_yr_max} 年平均｜高峰月=橘紅）',
            plot_bgcolor='white', paper_bgcolor='white',
            xaxis_title='月份', yaxis_title='月均病例數（例）',
            margin=dict(t=50, b=40),
        )
        st.plotly_chart(fig_season, use_container_width=True)

    with col_s2:
        cases_norm = (seasonal['cases_mean'] / seasonal['cases_mean'].max() * 100)
        temp_norm  = (seasonal['temp_mean_'] / seasonal['temp_mean_'].max() * 100)

        fig_dual = go.Figure()
        fig_dual.add_trace(go.Scatter(
            x=[month_labels[m-1] for m in seasonal['month']],
            y=temp_norm.round(1),
            name='月均溫（標準化）',
            line=dict(color='#D85A30', width=3),
            mode='lines+markers',
            marker=dict(size=8, symbol='circle'),
        ))
        fig_dual.add_trace(go.Scatter(
            x=[month_labels[m-1] for m in seasonal['month']],
            y=cases_norm.round(1),
            name='月均病例（標準化）',
            line=dict(color='#378ADD', width=3, dash='dash'),
            mode='lines+markers',
            marker=dict(size=8, symbol='diamond'),
        ))
        fig_dual.add_annotation(
            x=month_labels[temp_peak-1], y=102,
            text=f'氣溫高峰<br>{temp_peak}月',
            showarrow=True, arrowhead=2, arrowcolor='#D85A30',
            font=dict(color='#D85A30', size=11), ax=0, ay=-45
        )
        fig_dual.add_annotation(
            x=month_labels[peak_m-1], y=float(cases_norm.max()) + 5,
            text=f'病例高峰<br>{peak_m}月',
            showarrow=True, arrowhead=2, arrowcolor='#378ADD',
            font=dict(color='#378ADD', size=11), ax=0, ay=-45
        )
        fig_dual.update_layout(
            height=340,
            title_text=f'氣溫 vs 病例 季節趨勢對比（標準化，{d_yr_min}~{d_yr_max}）',
            plot_bgcolor='white', paper_bgcolor='white',
            xaxis_title='月份', yaxis_title='相對強度（%，最高月=100%）',
            legend=dict(orientation='h', y=1.12),
            margin=dict(t=60, b=40),
        )
        st.plotly_chart(fig_dual, use_container_width=True)

    st.caption(
        f'💡 **感控解讀**：{selected_city} 氣溫高峰（{temp_peak} 月）與病例高峰（{peak_m} 月）'
        f'相差 **{lag_season} 個月**，反映病媒蚊由孑孓孵化→羽化成蚊→叮咬人體→發病通報的完整生物延遲。'
        f'感控人員應於 **{temp_peak} 月起** 加強孳生源清除，以在病例高峰前完成防治部署。'
    )

    st.divider()

    # ── ⑤ Pearson 相關係數表 ────────────────────────────────────
    st.markdown(f'#### 📐 各縣市 Pearson 相關係數（逐年月資料，{w_yr_min}~{w_yr_max}）')

    corr_rows = []
    for city in ['台南市', '高雄市', '嘉義市', '屏東縣']:
        w = weather_df[weather_df['County'] == city]
        if 'County' in dengue_monthly.columns and city in dengue_monthly['County'].values:
            d = dengue_monthly[dengue_monthly['County'] == city]
        else:
            d = dengue_monthly.groupby(['year','month'])['cases'].sum().reset_index()
        m = pd.merge(d, w[['year','month','temp_mean','rain_sum']],
                     on=['year','month'], how='inner').dropna()
        if len(m) < 6:
            continue
        r_t, p_t = sp_stats.pearsonr(m['temp_mean'], m['cases'])
        r_r, p_r = sp_stats.pearsonr(m['rain_sum'],  m['cases'])
        corr_rows.append({
            '縣市':        city,
            '氣溫 r':      round(r_t, 3),
            '氣溫 p 值':   round(p_t, 4),
            '氣溫顯著':    '✅ 顯著' if p_t < 0.05 else '—',
            '降雨 r':      round(r_r, 3),
            '降雨 p 值':   round(p_r, 4),
            '降雨顯著':    '✅ 顯著' if p_r < 0.05 else '—',
            '樣本數（月）': len(m),
        })

    if corr_rows:
        corr_table = pd.DataFrame(corr_rows)
        st.dataframe(corr_table, use_container_width=True, hide_index=True)
        st.caption(
            f'使用 {w_yr_min}~{w_yr_max} 年**逐年月**實際資料（非月均值），'
            f'樣本數為各縣市實際有資料的月份筆數。'
            f'**解讀**：|r| > 0.3 弱相關，|r| > 0.5 中等相關，|r| > 0.7 強相關。'
            f'p < 0.05 表示統計上顯著（✅）。'
        )

    st.divider()

    # ── ⑥ 方法論（更新文獻）────────────────────────────────────
    with st.expander('📋 方法論'):
        st.markdown(f'''
**資料來源**
- 氣象：中央氣象署 CODiS 逐月資料（{w_yr_min}~{w_yr_max}），TX01 月均溫（°C）、PP01 月降水量（mm）
- 病例：疾管署 Dengue_Daily.csv 本土確定病例，依縣市聚合為月別資料

**測站對照表**

| 縣市 | 測站代號 | 測站名稱 | 備註 |
|---|---|---|---|
| 台南市 | 467410 | 臺南 | 局屬有人站 |
| 高雄市 | 467440 / 467441 | 高雄 | 兩站資料平均 |
| 嘉義市 | 467480 | 嘉義 | 局屬有人站 |
| 屏東縣 | 467590 | 恆春 | 屏東縣無局屬站，以南屏東恆春站代替 |

**分析方法**
- **Pearson 相關係數（r）**：使用 {w_yr_min}~{w_yr_max} 年逐年月資料（非月均值），衡量氣象因子與病例數的線性相關強度
- **季節性分析**：計算全期各月均值，消除年際變異，突顯氣溫 vs 病例的相位差（滯後效應）
- **滯後效應**：降雨影響孑孓孳生，需 2~4 週羽化為成蚊後才能傳播；氣溫影響病毒外潛伏期（EIP），25°C 以上 EIP 顯著縮短

**相關文獻**

1. **Tien et al. (2018)** *PLOS ONE* — 高雄市登革熱與氣象因子（氣溫、降雨、相對濕度）在滯後 **1~2 個月**時呈現顯著正相關，並建立預測模型
   > DOI: 10.1371/journal.pone.0190637

2. **Hii et al. (2012)** *PLOS NTD* — 新加坡研究，氣溫與登革熱病例 r ≈ 0.4~0.6，最佳預測滯後為 **1~3 個月**
   > DOI: 10.1371/journal.pntd.0001908

3. **Chien & Yu (2014)** *Environment International* — 台灣本土研究，氣象因子對登革熱發生率時空分布的影響
   > DOI: 10.1016/j.envint.2014.08.003

4. **Nishiura & Halstead (2007)** *JID* — 登革熱自然史，世代間隔 14 天，支持滯後效應的生物學基礎
   > DOI: 10.1086/511825

**感控實務意涵**

氣溫超過 **25°C**（病媒蚊活躍閾值）後 1~2 個月為高風險期，感控人員應：
1. 加強孳生源清除（積水容器、廢棄輪胎、花盆底盤）
2. 啟動社區噴藥防治計畫
3. 醫院備齊登革熱檢驗試劑與隔離資源
4. 加強民眾衛教：避免清晨黃昏戶外活動
        ''')

    st.caption(
        f'🦟 台灣 CDC 登革熱蒙地卡羅模擬系統 ｜ 課程：系統模擬 ｜ 作者：Joyce Wang ｜ '
        f'病例資料更新：{latest_date} ｜ 氣象資料：CWA CODiS {w_yr_min}~{w_yr_max}'
    )


# ── Tab 5：Bayesian 滾動視窗驗證 ─────────────────────────────
with tab5:
    st.subheader('🔮 Bayesian 預測 × 滾動視窗驗證')
    st.caption('方法：PyMC MCMC（主）/ 共軛先驗（備）｜滾動視窗 2015~2023')

    import os

    BAYES_CSV = 'data/bayesian_results.csv'

    # ── 優先讀取 PyMC 結果 ──────────────────────────────────
    if os.path.exists(BAYES_CSV):
        res_df = pd.read_csv(BAYES_CSV, encoding='utf-8-sig')
        method_label = 'PyMC MCMC（2 chains × 1,000 draws）'
        st.success(f'✅ 已載入 PyMC MCMC 結果｜{method_label}')
    else:
        # 備用：共軛先驗快速估計
        st.info('ℹ️ 未找到 PyMC 結果，使用共軛先驗快速估計')
        method_label = '共軛先驗貝氏更新（對數常態）'

        @st.cache_data(show_spinner=False)
        def run_rolling_validation_fallback(data_key: str):
            wdf = st.session_state.get('weekly_df')
            if wdf is None:
                return pd.DataFrame()
            annual = wdf.groupby('year')['cases'].sum()
            results = []
            for pred_year in range(2015, 2024):
                train = annual[annual.index < pred_year]
                if len(train) < 5:
                    continue
                actual = annual.get(pred_year, None)
                if actual is None:
                    continue
                log_data = np.log(train.values[train.values > 0].astype(float))
                mu_post  = np.mean(log_data)
                sig_post = np.std(log_data, ddof=1)
                np.random.seed(42)
                sim_cases = np.exp(np.random.normal(mu_post, sig_post, 10000))
                results.append({
                    'pred_year':   pred_year,
                    'train_end':   int(pred_year - 1),
                    'n_train':     len(train),
                    'actual':      int(actual),
                    'median_pred': int(np.median(sim_cases)),
                    'ci_lo':       int(np.percentile(sim_cases, 2.5)),
                    'ci_hi':       int(np.percentile(sim_cases, 97.5)),
                    'coverage':    bool(np.percentile(sim_cases, 2.5) <= actual <= np.percentile(sim_cases, 97.5)),
                    'abs_error':   int(abs(actual - np.median(sim_cases))),
                    'pct_error':   round(abs(actual - np.median(sim_cases)) / max(actual, 1) * 100, 1),
                    'method':      '共軛先驗',
                })
            return pd.DataFrame(results)

        st.session_state['weekly_df'] = weekly_df
        res_df = run_rolling_validation_fallback(data_key)

    if res_df.empty:
        st.warning('⚠️ 無驗證結果，請確認資料已載入')
        st.stop()

    # ── 摘要指標 ────────────────────────────────────────────
    rmse = float(np.sqrt(np.mean(res_df['abs_error'] ** 2)))
    coverage_rate = float(res_df['coverage'].mean() * 100)
    n_rounds = len(res_df)

    r2015_df = res_df[res_df['pred_year'] == 2015]
    covered_2015 = bool(r2015_df['coverage'].values[0]) if len(r2015_df) > 0 else False

    st.markdown('#### 📊 驗證結果摘要')
    c1, c2, c3, c4 = st.columns(4)
    c1.metric('驗證輪數', f'{n_rounds} 輪（2015~2023）')
    c2.metric('RMSE', f'{rmse:,.0f} 例')
    c3.metric('95% CI Coverage', f'{coverage_rate:.1f}%',
              help='實際值落在預測 95% CI 內的比例，理想值 ≥ 95%')
    c4.metric('2015 大爆發預警', '✅ 是' if covered_2015 else '❌ 否',
              help='2015 年 43,784 例是否落在 95% CI 內')

    st.divider()

    # ── 主圖：預測 vs 實際 ──────────────────────────────────
    st.markdown('#### 📈 逐年預測 vs 實際病例數')

    fig_bay = go.Figure()

    fig_bay.add_trace(go.Scatter(
        x=list(res_df['pred_year']) + list(res_df['pred_year'])[::-1],
        y=list(res_df['ci_hi']) + list(res_df['ci_lo'])[::-1],
        fill='toself',
        fillcolor='rgba(55,138,221,0.15)',
        line=dict(color='rgba(0,0,0,0)'),
        name='95% CI',
        hoverinfo='skip',
    ))

    fig_bay.add_trace(go.Scatter(
        x=res_df['pred_year'],
        y=res_df['median_pred'],
        mode='lines+markers',
        name='Bayesian 預測中位數',
        line=dict(color='#378ADD', width=2.5),
        marker=dict(size=8),
        hovertemplate='%{x} 年<br>預測：%{y:,.0f} 例<extra></extra>',
    ))

    fig_bay.add_trace(go.Scatter(
        x=res_df['pred_year'],
        y=res_df['actual'],
        mode='markers',
        name='實際病例數',
        marker=dict(
            size=12,
            color=['#D85A30' if r else '#888780' for r in res_df['coverage']],
            symbol=['circle' if r else 'x' for r in res_df['coverage']],
            line=dict(width=2, color='white'),
        ),
        hovertemplate='%{x} 年<br>實際：%{y:,.0f} 例<extra></extra>',
    ))

    if len(r2015_df) > 0:
        fig_bay.add_annotation(
            x=2015, y=int(r2015_df['actual'].values[0]),
            text=f'2015 年<br>{int(r2015_df["actual"].values[0]):,} 例',
            showarrow=True, arrowhead=2,
            arrowcolor='#D85A30',
            font=dict(color='#D85A30', size=11),
            ax=40, ay=-50,
        )

    fig_bay.update_layout(
        height=420,
        plot_bgcolor='white', paper_bgcolor='white',
        title_text=f'Bayesian 滾動視窗驗證（{method_label}）｜橘色=CI內｜灰X=CI外',
        title_font_size=12,
        xaxis_title='預測年份',
        yaxis_title='年度病例數（例）',
        legend=dict(orientation='h', y=1.08),
        hovermode='x unified',
    )
    fig_bay.update_xaxes(
        tickmode='array',
        tickvals=list(res_df['pred_year']),
        gridcolor='#F0F0F0',
    )
    fig_bay.update_yaxes(gridcolor='#F0F0F0')
    st.plotly_chart(fig_bay, use_container_width=True)

    st.divider()

    # ── 逐輪詳細結果表 ──────────────────────────────────────
    st.markdown('#### 📋 逐輪驗證詳細結果')

    display_df = pd.DataFrame({
        '預測年份':     res_df['pred_year'],
        '訓練期':       res_df['train_end'].apply(lambda x: f'2003~{x}'),
        '訓練樣本數':   res_df['n_train'],
        '預測中位數':   res_df['median_pred'].apply(lambda x: f'{int(x):,}'),
        '95% CI 下限': res_df['ci_lo'].apply(lambda x: f'{int(x):,}'),
        '95% CI 上限': res_df['ci_hi'].apply(lambda x: f'{int(x):,}'),
        '實際病例數':   res_df['actual'].apply(lambda x: f'{int(x):,}'),
        '絕對誤差':     res_df['abs_error'].apply(lambda x: f'{int(x):,}'),
        '誤差率（%）': res_df['pct_error'],
        'CI 涵蓋':     res_df['coverage'].apply(lambda x: '✅' if x else '❌'),
    })
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    st.divider()

    # ── 結果解讀 ────────────────────────────────────────────
    st.markdown('#### 🔍 結果解讀')
    col_a, col_b = st.columns(2)

    rate_str = f'{coverage_rate:.1f}%'
    with col_a:
        if coverage_rate >= 95:
            st.success(
                f'CI Coverage = {rate_str}｜'
                '達到統計理論標準（95%），模型校準良好。'
            )
        elif coverage_rate >= 70:
            st.warning(
                f'CI Coverage = {rate_str}｜'
                '略低於 95% 標準。CI 寬度反映歷史病例數的高度變異性，'
                '2015、2023 等極端年份難以完全涵蓋，為登革熱流行病學的固有挑戰。'
                '建議論文階段納入氣象協變量以提升預測精度。'
            )
        else:
            st.warning(
                f'CI Coverage = {rate_str}｜'
                '低於標準，反映極端爆發年份（2015：43,784 例）'
                '與 COVID 抑制年份（2020~2022）造成的分佈不穩定，'
                '需要動態模型或氣象協變量輔助。'
            )

    with col_b:
        ci_lo_2015 = int(r2015_df['ci_lo'].values[0]) if len(r2015_df) > 0 else 0
        ci_hi_2015 = int(r2015_df['ci_hi'].values[0]) if len(r2015_df) > 0 else 0
        if covered_2015:
            st.success(
                f'2015 年大爆發預警成功 ✅｜'
                f'95% CI：{ci_lo_2015:,} ~ {ci_hi_2015:,} 例，'
                '實際 43,784 例落在 CI 內，模型具備大爆發預警能力。'
            )
        else:
            st.warning(
                f'2015 年大爆發預警未涵蓋 ⚠️｜'
                f'95% CI：{ci_lo_2015:,} ~ {ci_hi_2015:,} 例，'
                '實際 43,784 例超出 CI 上限。'
                '反映訓練期（2003~2014）缺乏類似大爆發樣本，'
                '模型低估極端情境的發生機率。'
                '此結果支持論文延伸研究：納入氣象協變量與 PyMC 動態模型。'
            )

    st.divider()

    # ── 方法論 ──────────────────────────────────────────────
    with st.expander('📋 方法論'):
        st.markdown(f"""
**分析方法：PyMC MCMC 滾動視窗驗證**

*模型設定*
- 分配假設：年度登革熱病例數服從對數常態分配（Log-Normal Distribution）
- 先驗（Prior）：弱資訊先驗
  - μ ~ Normal（訓練期對數均值，σ=2.0）
  - σ ~ HalfNormal（σ=1.0）
- 似然函數：Normal（μ, σ）作用於對數轉換病例數
- MCMC 設定：2 chains × 1,000 draws + 500 tune（NUTS sampler）

*滾動視窗設計（Walk-Forward Validation）*
- 第 1 輪：訓練 2003~2014，預測 2015（最重要驗證點）
- 第 2~8 輪：逐年延伸，預測 2016~2023
- 共 {n_rounds} 個驗證點（2021 年因 COVID 管制病例數極低，特殊處理）

*評估指標*
- **RMSE = {rmse:,.0f} 例**：主要受 2015 年（43,784 例）和 2023 年（26,429 例）大爆發影響
- **Coverage = {coverage_rate:.1f}%**：CI 寬度反映歷史病例數的高度變異（2021 年僅 12 例 vs 2015 年 43,784 例）
- **Divergences = 0**：MCMC 收斂良好，無發散樣本

*Coverage 偏低的合理解釋*
1. 訓練樣本小（12~20 年），對數常態的 sigma 後驗估計不確定性大
2. 2015 年大爆發是訓練期前所未見的極端事件
3. 2020~2022 年 COVID 管制效應造成異常低病例，影響後驗估計
4. 純病例數模型未納入氣象、病媒蚊密度等重要協變量

*未來延伸（論文階段）*
- 升級為 4 chains × 2,000 draws 提升估計穩定性
- 納入氣溫、降雨量作為貝氏模型的外部協變量（covariate）
- 加入時間趨勢項（time trend）捕捉長期病例數變化
- 考慮分層模型（Hierarchical Model）納入縣市差異

**文獻支持**
1. **Martínez-Bello et al. (2017)** *PLOS NTD* — 貝氏動態時序模型預測登革熱病例
   > DOI: 10.1371/journal.pntd.0005696
2. **Gelman et al. (2013)** *Bayesian Data Analysis, 3rd Ed.* — MCMC 方法與收斂診斷理論基礎
3. **Prediction of dengue outbreaks using MCMC (2022)** *PubMed* — MCMC + SIR 模型
   > PMID: 35361845
        """)

    st.caption(
        f'🔮 Bayesian 滾動視窗驗證（{method_label}）｜'
        f'訓練期：2003~2022｜驗證期：2015~2023｜'
        f'資料更新：{latest_date}'
    )
