import pandas as pd

vdp_imp = pd.read_csv('vdp_implicit_summary.csv')
rob_bench = pd.read_csv('robertson_benchmarks.csv')

print("VDP Implicit columns:", vdp_imp.columns.tolist())
print("Robertson columns:", rob_bench.columns.tolist())
