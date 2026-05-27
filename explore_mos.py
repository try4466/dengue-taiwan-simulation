# explore_mos.py
import pandas as pd

print("讀取中，請稍候...")
df = pd.read_csv('data/MosIndex_All.csv', encoding='utf-8-sig', nrows=10)

print("\n=== 欄位名稱 ===")
for i, col in enumerate(df.columns.tolist()):
    print(f"  {i}: {col}")

print("\n=== 前3筆資料 ===")
print(df.head(3).to_string())

print("\n=== 資料型別 ===")
print(df.dtypes)