"""
run_bayesian_pymc.py
本機執行 PyMC MCMC 滾動視窗驗證
產生 data/bayesian_results.csv 供 Streamlit tab5 讀取

執行方式：
    python run_bayesian_pymc.py

執行時間：約 10~30 分鐘（視電腦速度）
"""

import pymc as pm
import numpy as np
import pandas as pd
import os
import warnings
warnings.filterwarnings('ignore')

# ── 設定 ──────────────────────────────────────────────────────
OUTPUT_CSV = 'data/bayesian_results.csv'
DENGUE_CSV = 'data/Dengue_Daily.csv'

CHAINS   = 2       # MCMC chains（2 條夠用，4 條更穩但較慢）
DRAWS    = 1000    # 每條 chain 抽樣次數
TUNE     = 500     # 暖機次數
SEED     = 42

# ── 讀取登革熱資料 ────────────────────────────────────────────
def load_annual_cases():
    print('📂 讀取登革熱資料...')
    df = pd.read_csv(DENGUE_CSV, encoding='utf-8-sig', low_memory=False)
    df['發病日'] = pd.to_datetime(df['發病日'], errors='coerce')
    df = df.dropna(subset=['發病日'])
    df['year'] = df['發病日'].dt.year
    df['確定病例數'] = pd.to_numeric(df['確定病例數'], errors='coerce').fillna(0)

    # 只取本土病例
    if '是否境外移入' in df.columns:
        df = df[df['是否境外移入'] == '否']

    annual = df.groupby('year')['確定病例數'].sum()
    annual = annual[annual.index >= 2003]
    print(f'✅ 年度資料：{int(annual.index.min())}~{int(annual.index.max())}，共 {len(annual)} 年')
    return annual

# ── PyMC MCMC 單輪驗證 ────────────────────────────────────────
def run_mcmc_single(train_data: np.ndarray, pred_year: int, seed: int = 42):
    """
    以 PyMC 對對數常態分配進行 MCMC 推論
    train_data：訓練期年度病例數（陣列）
    回傳：預測中位數、2.5%、97.5% 分位數
    """
    log_data = np.log(train_data[train_data > 0].astype(float))

    with pm.Model() as model:
        # 先驗（弱資訊先驗）
        mu    = pm.Normal('mu',    mu=np.mean(log_data), sigma=2.0)
        sigma = pm.HalfNormal('sigma', sigma=1.0)

        # 似然函數
        obs = pm.Normal('obs', mu=mu, sigma=sigma, observed=log_data)

        # MCMC 取樣
        trace = pm.sample(
            draws=DRAWS,
            tune=TUNE,
            chains=CHAINS,
            random_seed=seed,
            progressbar=True,
            return_inferencedata=True,
        )

    # 後驗預測
    mu_samples    = trace.posterior['mu'].values.flatten()
    sigma_samples = trace.posterior['sigma'].values.flatten()

    # 從後驗分配預測下一年
    np.random.seed(seed)
    pred_log  = np.random.normal(mu_samples, sigma_samples)
    pred_cases = np.exp(pred_log)

    return {
        'median': float(np.median(pred_cases)),
        'ci_lo':  float(np.percentile(pred_cases, 2.5)),
        'ci_hi':  float(np.percentile(pred_cases, 97.5)),
        'mean':   float(np.mean(pred_cases)),
        'std':    float(np.std(pred_cases)),
        'mu_mean':    float(mu_samples.mean()),
        'sigma_mean': float(sigma_samples.mean()),
    }

# ── 主程式：9 輪滾動視窗驗證 ────────────────────────────────
def main():
    print('\n' + '='*55)
    print('PyMC MCMC 滾動視窗驗證')
    print(f'設定：{CHAINS} chains × {DRAWS} draws + {TUNE} tune')
    print('='*55)

    annual = load_annual_cases()
    predict_years = list(range(2015, 2024))
    results = []

    for i, pred_year in enumerate(predict_years):
        print(f'\n{"─"*50}')
        print(f'第 {i+1}/9 輪：訓練 2003~{pred_year-1}，預測 {pred_year}')
        print(f'{"─"*50}')

        train = annual[annual.index < pred_year].values
        actual = annual.get(pred_year, None)

        if actual is None:
            print(f'  ⚠️ {pred_year} 年無資料，跳過')
            continue

        try:
            pred = run_mcmc_single(train, pred_year, seed=SEED+i)

            coverage = pred['ci_lo'] <= actual <= pred['ci_hi']
            abs_err  = abs(actual - pred['median'])
            pct_err  = round(abs_err / max(actual, 1) * 100, 1)

            results.append({
                'pred_year':   pred_year,
                'train_end':   pred_year - 1,
                'n_train':     len(train),
                'actual':      int(actual),
                'median_pred': int(pred['median']),
                'mean_pred':   int(pred['mean']),
                'ci_lo':       int(pred['ci_lo']),
                'ci_hi':       int(pred['ci_hi']),
                'std_pred':    int(pred['std']),
                'coverage':    coverage,
                'abs_error':   int(abs_err),
                'pct_error':   pct_err,
                'mu_post':     round(pred['mu_mean'], 4),
                'sigma_post':  round(pred['sigma_mean'], 4),
                'method':      f'PyMC MCMC ({CHAINS} chains × {DRAWS} draws)',
            })

            print(f'  實際：{int(actual):,} 例')
            print(f'  預測中位數：{int(pred["median"]):,} 例')
            print(f'  95% CI：{int(pred["ci_lo"]):,} ~ {int(pred["ci_hi"]):,}')
            print(f'  CI 涵蓋：{"✅" if coverage else "❌"}')
            print(f'  誤差率：{pct_err:.1f}%')

        except Exception as e:
            print(f'  ❌ 錯誤：{e}')
            continue

    if not results:
        print('\n❌ 無結果，請檢查資料')
        return

    # ── 計算整體指標 ────────────────────────────────────────
    res_df = pd.DataFrame(results)
    rmse = float(np.sqrt(np.mean(res_df['abs_error'] ** 2)))
    coverage_rate = float(res_df['coverage'].mean() * 100)

    print(f'\n{"="*55}')
    print('驗證結果摘要')
    print(f'{"="*55}')
    print(f'RMSE：{rmse:,.0f} 例')
    print(f'Coverage：{coverage_rate:.1f}%')
    print(f'2015 大爆發預警：{"✅" if res_df[res_df["pred_year"]==2015]["coverage"].values[0] else "❌"}')

    # ── 儲存結果 ────────────────────────────────────────────
    os.makedirs('data', exist_ok=True)
    res_df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
    print(f'\n✅ 結果已儲存至 {OUTPUT_CSV}')
    print(f'{"="*55}\n')

if __name__ == '__main__':
    main()
