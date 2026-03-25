import pandas as pd
import numpy as np

# Load VDP explicit results
try:
    vdp_exp = pd.read_csv('vdp_explicit_benchmark_v2.csv')
    print("VDP Explicit Data Head:")
    print(vdp_exp.head())
except:
    vdp_exp = pd.read_csv('benchmark_results.csv')
    print("VDP Explicit Data (from benchmark_results.csv):")
    print(vdp_exp.head())

# Load VDP implicit results
vdp_imp = pd.read_csv('vdp_implicit_summary.csv')
print("\nVDP Implicit Summary:")
print(vdp_imp)

# Load Robertson results
rob_bench = pd.read_csv('robertson_benchmarks.csv')
print("\nRobertson Benchmarks:")
print(rob_bench)

# Load Comprehensive results for more context
comp_bench = pd.read_csv('final_comprehensive_benchmarks.csv')
print("\nComprehensive Benchmarks (Tail):")
print(comp_bench.tail())

# Analysis 1: Efficiency Gain for VDP mu=100
# Filter for DP5 (explicit) and BDF (implicit) at mu=100
vdp_mu100_exp = vdp_exp[(vdp_exp['mu'] == 100) & (vdp_exp['solver'] == 'DP5')]['nfev'].mean()
vdp_mu100_imp = vdp_imp[(vdp_imp['mu'] == 100) & (vdp_imp['solver'] == 'BDF')]['avg_nfev'].mean()
gain_vdp_100 = vdp_mu100_exp / vdp_mu100_imp if vdp_mu100_imp > 0 else np.nan

print(f"\nEfficiency Gain (NFEV ratio) for VDP mu=100 (DP5 vs BDF): {gain_vdp_100:.2f}")

# Analysis 2: Efficiency Gain for Robertson
rob_exp_nfev = 1e6 # Assumption based on task output saying it failed/timed out at 1M
rob_radau_nfev = rob_bench[rob_bench['solver'] == 'Radau']['nfev'].iloc[0]
gain_rob = rob_exp_nfev / rob_radau_nfev
print(f"Efficiency Gain (NFEV ratio) for Robertson (RK45 vs Radau, estimated): {gain_rob:.2f}")

# Analysis 3: Step-size collapse visualization data
# For Robertson, RK45 dt ~ 1e-3, Radau dt ~ 1e10 (at late times)
dt_ratio_rob = 1e10 / 1e-3
print(f"Step-size ratio (Implicit/Explicit) for Robertson (late time): {dt_ratio_rob:.2e}")
