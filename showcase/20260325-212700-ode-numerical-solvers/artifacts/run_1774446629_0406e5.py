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

# Analysis 1: Efficiency Gain for VDP
res = []
for mu in [1, 100]:
    exp_nfev = vdp_exp[(vdp_exp['mu'] == mu) & (vdp_exp['solver'] == 'DP5')]['nfev'].mean()
    imp_nfev = vdp_imp[(vdp_imp['mu'] == mu) & (vdp_imp['solver'] == 'BDF')]['nfev'].mean()
    res.append({'mu': mu, 'exp_nfev': exp_nfev, 'imp_nfev': imp_nfev, 'gain': exp_nfev/imp_nfev})

print("VDP Efficiency Gain Results:")
print(pd.DataFrame(res))

# Analysis 2: Robertson Efficiency
# Radau nfev
rob_radau = rob_bench[rob_bench['Solver'] == 'Radau']
radau_nfev = rob_radau['nfev'].iloc[0]
radau_t = rob_radau['t_final'].iloc[0]

# RK45 nfev (at t=10)
rob_rk45 = rob_bench[rob_bench['Solver'] == 'RK45']
rk45_nfev = rob_rk45['nfev'].iloc[0]
rk45_t = rob_rk45['t_final'].iloc[0]

# Normalized NFEV per unit time
rk45_rate = rk45_nfev / rk45_t
radau_rate = radau_nfev / radau_t
gain_rob = rk45_rate / radau_rate

print(f"\nRobertson Efficiency Gain (normalized by time): {gain_rob:.2e}")

# Analysis 3: Step collapse
rk45_steps = rob_rk45['Steps'].iloc[0]
radau_steps = rob_radau['Steps'].iloc[0]
avg_dt_rk45 = rk45_t / rk45_steps
avg_dt_radau = radau_t / radau_steps
dt_ratio = avg_dt_radau / avg_dt_rk45

print(f"Robertson Step-size Collapse Ratio (Avg Dt Implicit / Avg Dt Explicit): {dt_ratio:.2e}")
