import pandas as pd
import numpy as np

# Load VDP explicit results
try:
    vdp_exp = pd.read_csv('vdp_explicit_benchmark_v2.csv')
except:
    vdp_exp = pd.read_csv('benchmark_results.csv')

# Load VDP implicit results
vdp_imp = pd.read_csv('vdp_implicit_summary.csv')

# Load Robertson results
rob_bench = pd.read_csv('robertson_benchmarks.csv')

# Analysis 1: Efficiency Gain for VDP mu=100
# Filter for DP5 (explicit) and BDF (implicit) at mu=100
vdp_mu100_exp = vdp_exp[(vdp_exp['mu'] == 100) & (vdp_exp['solver'] == 'DP5')]['nfev'].mean()
vdp_mu100_imp = vdp_imp[(vdp_imp['mu'] == 100) & (vdp_imp['solver'] == 'BDF')]['nfev'].mean()
gain_vdp_100 = vdp_mu100_exp / vdp_mu100_imp

print(f"Efficiency Gain (NFEV ratio) for VDP mu=100 (DP5 vs BDF): {gain_vdp_100:.2f}")

# Analysis 1b: Efficiency Gain for VDP mu=10000
# VDP explicit for mu=10000 probably didn't run or is not in the CSV. 
# But let's check if mu=10.0 exists to see the trend.
vdp_mu10_exp = vdp_exp[(vdp_exp['mu'] == 10) & (vdp_exp['solver'] == 'DP5')]['nfev'].mean()
# Since mu=10 isn't in vdp_imp (only 1, 100, 10000), let's compare mu=1.
vdp_mu1_exp = vdp_exp[(vdp_exp['mu'] == 1.0) & (vdp_exp['solver'] == 'DP5')]['nfev'].mean()
vdp_mu1_imp = vdp_imp[(vdp_imp['mu'] == 1) & (vdp_imp['solver'] == 'BDF')]['nfev'].mean()
gain_vdp_1 = vdp_mu1_exp / vdp_mu1_imp
print(f"Efficiency Gain (NFEV ratio) for VDP mu=1 (DP5 vs BDF): {gain_vdp_1:.2f}")

# Analysis 2: Efficiency Gain for Robertson
# Radau NFEV for full range (1e11)
rob_radau_nfev = rob_bench[rob_bench['Solver'] == 'Radau']['NFEV'].iloc[0]
# RK45 failed at t=100 with 1M NFEV. To reach 1e11, it would take proportional steps.
# Estimated RK45 steps for 1e11: (1e11 / 100) * 1e6 = 1e15 NFEV.
est_gain_rob = 1e15 / rob_radau_nfev
print(f"Estimated Efficiency Gain (NFEV ratio) for Robertson (RK45 vs Radau) over full range: {est_gain_rob:.2e}")

# Analysis 3: Step-size Collapse Quantified
# VDP mu=100: dt ~ 2e-5 for RK4 (as per task 3_1_2), dt ~ 1e-1 for BDF (average)
# Let's check VDP reference steps (3_1_1) for mu=100: 6317 steps for t=171. Avg dt = 0.027.
# RK4 for mu=100: h=2e-5. 
dt_ratio_vdp_100 = 0.027 / 2e-5
print(f"Step-size ratio (Implicit/Explicit) for VDP mu=100: {dt_ratio_vdp_100:.2f}")
