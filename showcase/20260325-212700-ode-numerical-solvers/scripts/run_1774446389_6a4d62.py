import pandas as pd
import os

files = [
    'harmonic_benchmarks.csv',
    'lorenz_benchmarks.csv',
    'robertson_benchmarks.csv',
    'vdp_explicit_benchmark_v2.csv',
    'vdp_implicit_benchmark_results.csv'
]

for f in files:
    if os.path.exists(f):
        print(f"--- {f} ---")
        df = pd.read_csv(f)
        print(df.head())
        print(df.columns)
    else:
        print(f"--- {f} NOT FOUND ---")
