import pandas as pd
import os

files = [
    'benchmark_results_1_3.csv',
    'vdp_explicit_benchmark_v2.csv',
    'implicit_benchmark.csv',
    'robertson_benchmarks.csv'
]

dataframes = {}
for f in files:
    if os.path.exists(f):
        dataframes[f] = pd.read_csv(f)
        print(f"--- {f} ---")
        print(dataframes[f].head())
    else:
        print(f"File {f} not found.")
