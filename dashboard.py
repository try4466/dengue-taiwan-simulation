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
tab1, tab2, tab3 = st.tabs(['📈 病例數模擬', '🔴 R 值分析', '🦟 布氏指數分析'])

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