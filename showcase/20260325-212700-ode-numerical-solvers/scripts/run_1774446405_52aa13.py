import pandas as pd
import os

for f in ['robertson_benchmarks.csv', 'consolidated_benchmark.csv']:
    if os.path.exists(f):
        print(f"--- {f} ---")
        df = pd.read_csv(f)
        print(df)
    else:
        print(f"--- {f} NOT FOUND ---")
