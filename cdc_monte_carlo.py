# ============================================================
#  台灣CDC登革熱蒙地卡羅模擬系統（每週更新版）
#  課程：系統模擬（祝國忠老師）  期中/期末作業用
#  作者：Joyce
#
#  資料來源：政府資料開放平台
#  https://data.gov.tw/dataset/21025
#  每週下載最新 Dengue_Daily.csv 放到同資料夾即可自動更新
# ============================================================

import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy import stats
from datetime import datetime

plt.rcParams['axes.unicode_minus'] = False

def load_dengue_data(csv_path='Dengue_Daily.csv', domestic_only=True, year_start=2003, city_filter=None):
    print(f"[1/4] 讀取資料：{csv_path}")
    try:
        df = pd.read_csv(csv_path, encoding='utf-8-sig', low_memory=False)
    except FileNotFoundError:
        print(f"  [!] 找不到 {csv_path}")
        print(f"  請至 https://data.gov.tw/dataset/21025 下載最新CSV")
        raise

    df['發病日'] = pd.to_datetime(df['發病日'], errors='coerce')
    df = df.dropna(subset=['發病日'])
    df['year'] = df['發病日'].dt.year
    df['week'] = df['發病日'].dt.isocalendar().week.astype(int)
    df['確定病例數'] = pd.to_numeric(df['確定病例數'], errors='coerce').fillna(0)

    if domestic_only and '是否境外移入' in df.columns:
        df = df[df['是否境外移入'] == '否']
        print(f"  本土病例（排除境外移入）")

    df = df[df['year'] >= year_start]
    latest_date = df['發病日'].max().strftime('%Y-%m-%d')
    latest_year = int(df['year'].max())
    print(f"  資料期間：{year_start} ~ {latest_year} 年")
    print(f"  最新資料日期：{latest_date}")

    # ── 縣市篩選 ──────────────────────────────────────────────
    if city_filter and city_filter != '全台灣':
        df_filtered = df[df['居住縣市'] == city_filter].copy()
        print(f"  縣市篩選：{city_filter}")
    else:
        df_filtered = df.copy()

    weekly = (df_filtered.groupby(['year', 'week'])['確定病例數']
              .sum().reset_index()
              .rename(columns={'確定病例數': 'cases'}))
    weekly = weekly[weekly['cases'] > 0].copy()

    annual = weekly.groupby('year')['cases'].sum()
    print(f"\n  年度病例摘要：")
    for yr, cnt in annual.items():
        bar = '█' * min(int(cnt / 3000), 25)
        print(f"  {yr}  {int(cnt):>8,}  {bar}")

    print(f"\n  週別資料：{len(weekly):,} 筆（{weekly['year'].nunique()} 年）")

    # ── 縣市年度比較表（不受篩選影響，永遠計算全台灣）──────
    city_annual = (df.groupby(['居住縣市', 'year'])['確定病例數']
                   .sum().reset_index()
                   .rename(columns={'確定病例數': 'cases'}))

    return weekly, latest_date, city_annual


def analyze_city(city_annual):
    """
    縣市別年度病例分析：
    計算各縣市歷史均值、最高年份、爆發次數（超過縣市P90）
    """
    cities = sorted(city_annual['居住縣市'].unique())
    result = []
    for city in cities:
        sub = city_annual[city_annual['居住縣市'] == city]
        ann = sub.groupby('year')['cases'].sum()
        if len(ann) == 0:
            continue
        p90 = float(np.percentile(ann.values, 90))
        p75 = float(np.percentile(ann.values, 75))
        result.append({
            '縣市':       city,
            '有資料年數':  len(ann),
            '歷史年均':   round(float(ann.mean()), 1),
            '最高年病例': int(ann.max()),
            '最高年份':   int(ann.idxmax()),
            'P75門檻':    round(p75, 0),
            'P90門檻':    round(p90, 0),
            '超P90年次':  int((ann > p90).sum()),
        })
    return pd.DataFrame(result).sort_values('歷史年均', ascending=False).reset_index(drop=True)


def plot_city_comparison(city_annual, save_path='city_comparison.png'):
    """
    縣市別比較圖：
    左：各縣市歷史年均（橫向長條）
    右：前5縣市年度趨勢折線
    """
    print(f"\n[縣市分析] 繪製縣市比較圖")
    city_df = analyze_city(city_annual)
    top5 = city_df.head(5)['縣市'].tolist()

    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    fig.suptitle('Taiwan Dengue - City Comparison Analysis', fontsize=12, fontweight='bold')

    # 左圖：各縣市年均橫向長條
    ax = axes[0]
    colors = ['#D85A30' if c in top5 else '#1D9E75' for c in city_df['縣市']]
    bars = ax.barh(city_df['縣市'], city_df['歷史年均'], color=colors, alpha=0.85, edgecolor='white')
    ax.set_title('Historical Annual Mean Cases by City')
    ax.set_xlabel('Annual Mean Cases')
    ax.grid(True, alpha=0.3, axis='x')
    for bar, val in zip(bars, city_df['歷史年均']):
        if val > 50:
            ax.text(val + 5, bar.get_y() + bar.get_height()/2,
                    f'{val:,.0f}', va='center', fontsize=8)

    # 右圖：前5縣市年度趨勢
    ax = axes[1]
    colors5 = ['#D85A30', '#1D9E75', '#378ADD', '#BA7517', '#888780']
    all_years = sorted(city_annual['year'].unique())
    for city, color in zip(top5, colors5):
        sub = city_annual[city_annual['居住縣市'] == city]
        ann = sub.groupby('year')['cases'].sum().reindex(all_years, fill_value=0)
        ax.plot(ann.index, ann.values, marker='o', markersize=4,
                linewidth=1.8, color=color, label=city, alpha=0.85)
    ax.set_title('Top 5 Cities - Annual Trend')
    ax.set_xlabel('Year')
    ax.set_ylabel('Annual Cases')
    ax.legend(fontsize=9)
    ax.tick_params(axis='x', rotation=45)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')
    print(f"  縣市比較圖儲存：{save_path}")
    plt.close()
    return city_df


def fit_distribution(data):
    fits = {}
    dist_names = {'norm': '常態', 'lognorm': '對數常態', 'gamma': 'Gamma'}
    for name, label in dist_names.items():
        try:
            dist = getattr(stats, name)
            params = dist.fit(data) if name == 'norm' else dist.fit(data, floc=0)
            _, p = stats.kstest(data, name, args=params)
            fits[name] = {'params': params, 'ks_p': p, 'dist': dist, 'label': label}
        except Exception:
            pass
    best = max(fits, key=lambda k: fits[k]['ks_p']) if fits else 'lognorm'
    return fits, best


def estimate_rt(weekly_df, serial_interval_weeks=2):
    """
    從週別病例數反推估計再生數 Rt。
    方法：Wallinga-Lipsitch 近似法
      Rt ≈ C(t) / C(t - SI)
    其中 SI = serial interval（世代間隔），登革熱約 14 天 = 2 週。
    回傳各年 Rt 序列與摘要統計。
    """
    annual = weekly_df.groupby('year')['cases'].sum()
    all_rt = []
    rt_by_year = {}

    for yr in sorted(annual.index):
        yr_df = weekly_df[weekly_df['year'] == yr].sort_values('week')
        cases = yr_df.set_index('week')['cases'].reindex(range(1, 53), fill_value=0).values
        rt_vals = []
        for t in range(serial_interval_weeks, len(cases)):
            denom = cases[t - serial_interval_weeks]
            if denom > 5:           # 分母病例數太少時跳過（估計不穩定）
                rt = cases[t] / denom
                rt_vals.append(rt)
        if rt_vals:
            rt_by_year[yr] = np.array(rt_vals)
            all_rt.extend(rt_vals)

    all_rt = np.array(all_rt)
    all_rt = all_rt[(all_rt > 0) & (all_rt < 20)]   # 去除極端值

    # 年度 Rt 中位數
    annual_rt_median = {yr: float(np.median(v)) for yr, v in rt_by_year.items()}

    return {
        'all_rt': all_rt,
        'rt_by_year': rt_by_year,
        'annual_rt_median': annual_rt_median,
        'rt_median': float(np.median(all_rt)),
        'rt_mean': float(np.mean(all_rt)),
        'rt_ci_lo': float(np.percentile(all_rt, 2.5)),
        'rt_ci_hi': float(np.percentile(all_rt, 97.5)),
        'p_above1': float((all_rt > 1).mean() * 100),
        'serial_interval_weeks': serial_interval_weeks,
    }


def simulate_r_distribution(rt_info, n_iter=10000):
    """
    以估計出的 Rt 資料擬合 Gamma 分配，再模擬 n_iter 次 R 值。
    同時回傳 Gamma 分配參數供報告使用。
    """
    all_rt = rt_info['all_rt']
    # 擬合 Gamma（floc=0 固定位置參數）
    shape, loc, scale = stats.gamma.fit(all_rt, floc=0)
    r_sim = stats.gamma.rvs(shape, loc=loc, scale=scale, size=n_iter)
    r_sim = r_sim[(r_sim > 0) & (r_sim < 20)]
    return {
        'r_sim': r_sim,
        'gamma_shape': shape,
        'gamma_scale': scale,
        'r_sim_median': float(np.median(r_sim)),
        'r_sim_ci_lo': float(np.percentile(r_sim, 2.5)),
        'r_sim_ci_hi': float(np.percentile(r_sim, 97.5)),
        'p_above1': float((r_sim > 1).mean() * 100),
    }


def monte_carlo_simulation(weekly_df, n_iter=10000, recent_years=5):
    print(f"\n[2/4] 蒙地卡羅模擬（{n_iter:,} 次）")

    all_data = weekly_df['cases'].values
    all_data = all_data[all_data > 0]

    max_year = int(weekly_df['year'].max())
    recent_df = weekly_df[weekly_df['year'] >= max_year - recent_years + 1]
    recent_data = recent_df['cases'].values
    recent_data = recent_data[recent_data > 0]

    hist_annual = weekly_df.groupby('year')['cases'].sum()
    hist_mean = hist_annual.mean()

    print(f"  全期資料：{int(weekly_df['year'].min())}~{max_year}，{len(all_data)} 筆")
    print(f"  近{recent_years}年資料：{max_year-recent_years+1}~{max_year}，{len(recent_data)} 筆")
    print(f"  歷史年均：{hist_mean:,.0f} 例")

    fits, best = fit_distribution(all_data)
    r_fits, r_best = fit_distribution(recent_data)
    best_info = fits[best]
    recent_info = r_fits.get(r_best, best_info)

    print(f"\n  分配擬合（KS檢定）：")
    for name, info in fits.items():
        mark = '→ 最佳' if name == best else ''
        print(f"  {info['label']:8s} p={info['ks_p']:.4f}  {mark}")

    annual_totals = np.zeros(n_iter)
    weekly_sims = np.zeros((n_iter, 52))

    for i in range(n_iter):
        ann = np.maximum(0, best_info['dist'].rvs(*best_info['params'], size=52))
        annual_totals[i] = ann.sum()
        weekly_sims[i] = np.maximum(0, recent_info['dist'].rvs(*recent_info['params'], size=52))

    p995 = np.percentile(annual_totals, 99.5)
    annual_plot = annual_totals[annual_totals <= p995]

    ci_lo = np.percentile(annual_totals, 2.5)
    ci_hi = np.percentile(annual_totals, 97.5)
    median_ann = np.median(annual_totals)
    mean_ann = annual_totals.mean()
    outbreak_p = (annual_totals > hist_mean * 1.5).mean() * 100

    # ── R 值估計與模擬 ──────────────────────────────────────
    rt_info = estimate_rt(weekly_df, serial_interval_weeks=2)
    r_sim_info = simulate_r_distribution(rt_info, n_iter=n_iter)

    print(f"\n  ── 模擬結果 ─────────────────────────")
    print(f"  最佳分配  ：{best_info['label']}")
    print(f"  歷史年均  ：{hist_mean:,.0f} 例")
    print(f"  預測中位數：{median_ann:,.0f} 例")
    print(f"  95% CI   ：{ci_lo:,.0f} ~ {ci_hi:,.0f} 例")
    print(f"  爆發機率  ：{outbreak_p:.1f}%")
    print(f"  ────────────────────────────────────")
    print(f"  ── R 值分析 ─────────────────────────")
    print(f"  估計 Rt 中位數：{rt_info['rt_median']:.2f}")
    print(f"  估計 Rt 95%CI ：{rt_info['rt_ci_lo']:.2f} ~ {rt_info['rt_ci_hi']:.2f}")
    print(f"  Rt > 1 比例  ：{rt_info['p_above1']:.1f}%（疫情擴散週次占比）")
    print(f"  模擬 R 中位數：{r_sim_info['r_sim_median']:.2f}")
    print(f"  模擬 R 95%CI ：{r_sim_info['r_sim_ci_lo']:.2f} ~ {r_sim_info['r_sim_ci_hi']:.2f}")
    print(f"  ────────────────────────────────────")

    return {
        'best_label': best_info['label'],
        'n_iter': n_iter,
        'hist_annual': hist_annual,
        'hist_mean': hist_mean,
        'mean_annual': mean_ann,
        'median_annual': median_ann,
        'std_annual': annual_totals.std(),
        'ci_lower': ci_lo,
        'ci_upper': ci_hi,
        'outbreak_prob': outbreak_p,
        'annual_totals': annual_totals,
        'annual_plot': annual_plot,
        'weekly_median': np.median(weekly_sims, axis=0),
        'weekly_ci_low': np.percentile(weekly_sims, 2.5, axis=0),
        'weekly_ci_hi': np.percentile(weekly_sims, 97.5, axis=0),
        'recent_mean': recent_data.mean(),
        'recent_years': recent_years,
        'rt_info': rt_info,
        'r_sim_info': r_sim_info,
    }


def plot_results(sim, latest_date, save_path='simulation_result.png'):
    print(f"\n[3/4] 繪製圖表")
    ha = sim['hist_annual']
    yr_min = int(ha.index.min())
    yr_max = int(ha.index.max())
    rt_info = sim['rt_info']
    r_sim_info = sim['r_sim_info']

    fig, axes = plt.subplots(2, 3, figsize=(20, 11))
    fig.suptitle(
        f'Taiwan Dengue Fever - Monte Carlo Simulation & Rt Analysis ({yr_min}-{yr_max})\n'
        f'{sim["n_iter"]:,} iterations | Best fit: {sim["best_label"]} | '
        f'Data updated: {latest_date}',
        fontsize=11, fontweight='bold'
    )

    # ── 圖1：歷史年度病例 ─────────────────────────────────────
    ax = axes[0, 0]
    colors = ['#D85A30' if v == ha.max() else '#1D9E75' for v in ha.values]
    bars = ax.bar(ha.index.astype(str), ha.values, color=colors, alpha=0.85, edgecolor='white')
    ax.axhline(sim['hist_mean'], color='#888780', linewidth=2, linestyle='--',
               label=f'Mean: {sim["hist_mean"]:,.0f}')
    ax.set_title(f'Historical Annual Dengue Cases ({yr_min}-{yr_max})')
    ax.set_xlabel('Year')
    ax.set_ylabel('Cases')
    ax.legend(fontsize=9)
    ax.tick_params(axis='x', rotation=60)
    ax.grid(True, alpha=0.3, axis='y')
    for bar, val in zip(bars, ha.values):
        if val > 5000:
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 500,
                    f'{int(val):,}', ha='center', va='bottom', fontsize=7, fontweight='bold')

    # ── 圖2：模擬年總病例分佈 ────────────────────────────────
    ax = axes[0, 1]
    ax.hist(sim['annual_plot'], bins=80, color='#378ADD', alpha=0.75, edgecolor='white', linewidth=0.2)
    ax.axvline(sim['median_annual'], color='#D85A30', linewidth=2.5,
               label=f'Median: {sim["median_annual"]:,.0f}')
    ax.axvline(sim['ci_lower'], color='#888780', linewidth=1.8, linestyle='--', label='95% CI')
    ax.axvline(sim['ci_upper'], color='#888780', linewidth=1.8, linestyle='--')
    ax.axvline(sim['hist_mean'], color='#1D9E75', linewidth=1.8, linestyle=':',
               label=f'Hist: {sim["hist_mean"]:,.0f}')
    ax.set_title('Simulated Annual Cases Distribution')
    ax.set_xlabel('Annual Cases')
    ax.set_ylabel('Frequency')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    txt = (f'Median: {sim["median_annual"]:,.0f}\n'
           f'95% CI: {sim["ci_lower"]:,.0f}~{sim["ci_upper"]:,.0f}\n'
           f'Outbreak risk: {sim["outbreak_prob"]:.1f}%')
    ax.text(0.97, 0.97, txt, transform=ax.transAxes, ha='right', va='top', fontsize=9,
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    # ── 圖3：估計 Rt 年度趨勢 ────────────────────────────────
    ax = axes[0, 2]
    years_rt = sorted(rt_info['annual_rt_median'].keys())
    rt_medians = [rt_info['annual_rt_median'][y] for y in years_rt]
    bar_colors = ['#D85A30' if r > 1 else '#1D9E75' for r in rt_medians]
    ax.bar(list(map(str, years_rt)), rt_medians, color=bar_colors, alpha=0.8, edgecolor='white')
    ax.axhline(1.0, color='#E24B4A', linewidth=2, linestyle='--', label='R = 1 (臨界值)')
    ax.axhline(rt_info['rt_median'], color='#888780', linewidth=1.5, linestyle=':',
               label=f"全期中位數 {rt_info['rt_median']:.2f}")
    ax.set_title('Estimated Annual Median Rt\n(Wallinga-Lipsitch, SI=14 days)')
    ax.set_xlabel('Year')
    ax.set_ylabel('Rt')
    ax.tick_params(axis='x', rotation=60)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3, axis='y')
    # 標示高峰年
    for i, (yr, rt) in enumerate(zip(years_rt, rt_medians)):
        if rt > 2.0:
            ax.text(i, rt + 0.05, f'{rt:.1f}', ha='center', va='bottom', fontsize=7, fontweight='bold')

    # ── 圖4：週別預測 ────────────────────────────────────────
    ax = axes[1, 0]
    weeks = range(1, 53)
    ax.fill_between(weeks, sim['weekly_ci_low'], sim['weekly_ci_hi'],
                    alpha=0.2, color='#378ADD', label='95% CI')
    ax.plot(weeks, sim['weekly_median'], color='#378ADD', linewidth=2, label='Median')
    ax.axhline(sim['recent_mean'], color='#1D9E75', linewidth=1.5, linestyle='--',
               label=f'Recent {sim["recent_years"]}Y Mean: {sim["recent_mean"]:.0f}')
    ax.set_title(f'Weekly Forecast - Next 52 Weeks (Recent {sim["recent_years"]} years)')
    ax.set_xlabel('Week')
    ax.set_ylabel('Cases')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # ── 圖5：大數法則收斂 ────────────────────────────────────
    ax = axes[1, 1]
    totals = sim['annual_totals']
    cum = np.cumsum(totals) / np.arange(1, len(totals)+1)
    ax.plot(cum, color='#BA7517', linewidth=1.2, alpha=0.85)
    ax.axhline(sim['median_annual'], color='#D85A30', linewidth=2, linestyle='--',
               label=f'Stable: {sim["median_annual"]:,.0f}')
    ax.set_ylim(0, sim['median_annual'] * 5)
    ax.set_title('Law of Large Numbers - Convergence')
    ax.set_xlabel('Simulation Iterations')
    ax.set_ylabel('Cumulative Mean Annual Cases')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # ── 圖6：模擬 R 值分佈（Gamma）────────────────────────────
    ax = axes[1, 2]
    r_sim = r_sim_info['r_sim']
    # 直方圖：模擬值
    ax.hist(r_sim, bins=80, color='#1D9E75', alpha=0.65,
            edgecolor='white', linewidth=0.2, density=True, label='Simulated R (Gamma)')
    # 疊加：從歷史資料估計的 Rt 分佈
    all_rt = rt_info['all_rt']
    ax.hist(all_rt, bins=80, color='#BA7517', alpha=0.45,
            edgecolor='white', linewidth=0.2, density=True, label='Estimated Rt (observed)')
    # 臨界線
    ax.axvline(1.0, color='#E24B4A', linewidth=2.2, linestyle='--', label='R = 1 (臨界值)')
    # 模擬 95% CI
    ax.axvline(r_sim_info['r_sim_ci_lo'], color='#378ADD', linewidth=1.5, linestyle=':')
    ax.axvline(r_sim_info['r_sim_ci_hi'], color='#378ADD', linewidth=1.5, linestyle=':',
               label=f"模擬 95%CI: {r_sim_info['r_sim_ci_lo']:.2f}~{r_sim_info['r_sim_ci_hi']:.2f}")
    ax.set_title('R Value Distribution\n(Simulated Gamma vs Estimated Rt)')
    ax.set_xlabel('R / Rt')
    ax.set_ylabel('Density')
    ax.set_xlim(0, min(r_sim.max(), 10))
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    txt_r = (f"Simulated R median: {r_sim_info['r_sim_median']:.2f}\n"
             f"Estimated Rt median: {rt_info['rt_median']:.2f}\n"
             f"P(R>1): {r_sim_info['p_above1']:.1f}%")
    ax.text(0.97, 0.97, txt_r, transform=ax.transAxes, ha='right', va='top', fontsize=8,
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.85))

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')
    print(f"  圖表儲存：{save_path}")
    plt.close()


def save_excel(weekly_df, sim, latest_date, path='simulation_output.xlsx'):
    print(f"\n[4/4] 輸出 Excel")
    ha = sim['hist_annual']
    with pd.ExcelWriter(path, engine='openpyxl') as w:
        weekly_df.to_excel(w, sheet_name='歷史週別資料', index=False)
        ha.reset_index().rename(columns={'cases': '年度確診數'}).to_excel(
            w, sheet_name='歷史年度統計', index=False)
        pd.DataFrame({
            '項目': ['最佳機率分配', '模擬次數', '資料更新日期',
                     '資料年份範圍', '歷史年均病例', '預測年度中位數',
                     '預測年度平均', '標準差', '95%CI下限', '95%CI上限', '爆發機率(%)'],
            '數值': [
                sim['best_label'], f"{sim['n_iter']:,}", latest_date,
                f"{int(ha.index.min())}~{int(ha.index.max())}",
                f"{sim['hist_mean']:,.0f}", f"{sim['median_annual']:,.0f}",
                f"{sim['mean_annual']:,.0f}", f"{sim['std_annual']:,.0f}",
                f"{sim['ci_lower']:,.0f}", f"{sim['ci_upper']:,.0f}",
                f"{sim['outbreak_prob']:.2f}",
            ]
        }).to_excel(w, sheet_name='模擬統計摘要', index=False)
        pd.DataFrame({
            '週次': range(1, 53),
            '預測中位數': np.round(sim['weekly_median'], 1),
            '95%CI下限': np.round(sim['weekly_ci_low'], 1),
            '95%CI上限': np.round(sim['weekly_ci_hi'], 1),
        }).to_excel(w, sheet_name='週別預測', index=False)
        # R 值分析表
        rt_info = sim['rt_info']
        r_sim_info = sim['r_sim_info']
        pd.DataFrame({
            '項目': [
                '估計方法', '世代間隔假設',
                '估計 Rt 中位數', '估計 Rt 95%CI 下限', '估計 Rt 95%CI 上限',
                'Rt > 1 週次比例(%)',
                '模擬分配', 'Gamma shape', 'Gamma scale',
                '模擬 R 中位數', '模擬 R 95%CI 下限', '模擬 R 95%CI 上限',
                '模擬 P(R>1)(%)',
            ],
            '數值': [
                'Wallinga-Lipsitch 近似法', f"{rt_info['serial_interval_weeks']} 週（14 天）",
                f"{rt_info['rt_median']:.3f}",
                f"{rt_info['rt_ci_lo']:.3f}",
                f"{rt_info['rt_ci_hi']:.3f}",
                f"{rt_info['p_above1']:.1f}",
                'Gamma（floc=0）',
                f"{r_sim_info['gamma_shape']:.4f}",
                f"{r_sim_info['gamma_scale']:.4f}",
                f"{r_sim_info['r_sim_median']:.3f}",
                f"{r_sim_info['r_sim_ci_lo']:.3f}",
                f"{r_sim_info['r_sim_ci_hi']:.3f}",
                f"{r_sim_info['p_above1']:.1f}",
            ]
        }).to_excel(w, sheet_name='R值分析', index=False)
        # 年度 Rt 中位數
        pd.DataFrame({
            '年份': list(rt_info['annual_rt_median'].keys()),
            '年度Rt中位數': [round(v, 3) for v in rt_info['annual_rt_median'].values()],
        }).to_excel(w, sheet_name='年度Rt趨勢', index=False)
    print(f"  Excel 儲存：{path}")


def main():
    print("=" * 55)
    print("  台灣CDC登革熱蒙地卡羅模擬系統（每週更新版）")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 55)
    print()
    print("  【每週更新步驟】")
    print("  1. 至 https://data.gov.tw/dataset/21025")
    print("  2. 下載最新 Dengue_Daily.csv")
    print("  3. 放到本資料夾覆蓋舊檔")
    print("  4. 重新執行此程式")
    print("=" * 55)

    weekly_df, latest_date, city_annual = load_dengue_data(
        csv_path='Dengue_Daily.csv',
        domestic_only=True,
        year_start=2003,
        city_filter=None          # 改成縣市名稱可篩選，例如 '台南市'
    )
    sim = monte_carlo_simulation(weekly_df, n_iter=10000, recent_years=5)
    plot_results(sim, latest_date, save_path='simulation_result.png')
    city_df = plot_city_comparison(city_annual, save_path='city_comparison.png')
    save_excel(weekly_df, sim, latest_date, path='simulation_output.xlsx')

    # 縣市統計加入 Excel
    from openpyxl import load_workbook
    wb = load_workbook('simulation_output.xlsx')
    with pd.ExcelWriter('simulation_output.xlsx', engine='openpyxl', mode='a',
                        if_sheet_exists='replace') as w:
        city_df.to_excel(w, sheet_name='縣市別統計', index=False)

    print()
    print("完成！輸出檔案：")
    print("  simulation_result.png  → 六格分析圖（含R值）")
    print("  city_comparison.png    → 縣市比較圖")
    print("  simulation_output.xlsx → 統計數據報告（含縣市別統計）")
    print("=" * 55)


if __name__ == '__main__':
    main()
