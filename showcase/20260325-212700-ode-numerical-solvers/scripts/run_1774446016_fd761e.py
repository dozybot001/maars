import pandas as pd

try:
    explicit_df = pd.read_csv('vdp_explicit_benchmark_v2.csv')
    print("Explicit Benchmark Data:")
    print(explicit_df.head())
    print(explicit_df.columns)
except Exception as e:
    print(f"Error reading explicit CSV: {e}")

try:
    implicit_df = pd.read_csv('implicit_benchmark.csv')
    print("\nImplicit Benchmark Data:")
    print(implicit_df.head())
    print(implicit_df.columns)
except Exception as e:
    print(f"Error reading implicit CSV: {e}")
