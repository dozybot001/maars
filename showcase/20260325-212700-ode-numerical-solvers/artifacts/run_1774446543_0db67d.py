import pandas as pd

try:
    df_bench = pd.read_csv('final_comprehensive_benchmarks.csv')
    print("Final Comprehensive Benchmarks:")
    print(df_bench.head(10))
except:
    print("final_comprehensive_benchmarks.csv not found")

try:
    df_switch = pd.read_csv('efficiency_switching_points.csv')
    print("\nEfficiency Switching Points:")
    print(df_switch)
except:
    print("efficiency_switching_points.csv not found")

try:
    df_summary = pd.read_csv('efficiency_switching_summary.csv')
    print("\nEfficiency Switching Summary:")
    print(df_summary)
except:
    print("efficiency_switching_summary.csv not found")

try:
    df_vdp = pd.read_csv('vdp_implicit_benchmark_results.csv')
    print("\nVDP Implicit Benchmarks:")
    print(df_vdp.head())
except:
    print("vdp_implicit_benchmark_results.csv not found")
