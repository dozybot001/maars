import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import interp1d

df = pd.read_csv('consolidated_benchmark.csv')
mus = df['mu'].unique()
methods = ['DP5', 'BDF', 'Radau']

# Target tolerance (log10 space)
target_log_tol = -6

plt.figure(figsize=(10, 6))

for method in methods:
    work_vals = []
    valid_mus = []
    for mu in mus:
        subset = df[(df['mu'] == mu) & (df['method'] == method)]
        if len(subset) < 2: continue
        
        # log10(error) vs log10(time)
        try:
            f = interp1d(np.log10(subset['tol']), np.log10(subset['time']), fill_value="extrapolate")
            work_vals.append(10**f(target_log_tol))
            valid_mus.append(mu)
        except:
            continue
            
    plt.plot(valid_mus, work_vals, 'o-', label=method)

plt.xscale('log')
plt.yscale('log')
plt.xlabel('Stiffness Parameter (mu)')
plt.ylabel('Execution Time (s) for Tol=1e-6')
plt.title('Method Efficiency vs Stiffness (Fixed Tolerance 1e-6)')
plt.legend()
plt.grid(True, which="both", ls="-", alpha=0.5)
plt.savefig('efficiency_vs_stiffness.png')

# Find crossing mu
# Interpolate DP5 and BDF times as a function of mu
dp5_data = df[(df['method'] == 'DP5')]
bdf_data = df[(df['method'] == 'BDF')]

# Group by mu and interpolate for 1e-6
def get_work_at_tol(data, mu, tol):
    subset = data[data['mu'] == mu]
    if len(subset) < 2: return np.nan
    f = interp1d(np.log10(subset['tol']), np.log10(subset['time']), fill_value="extrapolate")
    return 10**f(np.log10(tol))

mu_fine = np.logspace(-1, 2, 100)
work_dp5 = [get_work_at_tol(dp5_data, m, 1e-6) for m in mus]
work_bdf = [get_work_at_tol(bdf_data, m, 1e-6) for m in mus]

# Interpolate over mu
f_mu_dp5 = interp1d(np.log10(mus), np.log10(work_dp5), fill_value="extrapolate")
f_mu_bdf = interp1d(np.log10(mus), np.log10(work_bdf), fill_value="extrapolate")

mu_range = np.logspace(-1, 2, 1000)
diff_mu = f_mu_dp5(np.log10(mu_range)) - f_mu_bdf(np.log10(mu_range))
idx = np.where(np.diff(np.sign(diff_mu)))[0]

if len(idx) > 0:
    switching_mu = mu_range[idx[0]]
    print(f"Efficiency switching point (stiffness): mu ≈ {switching_mu:.2f}")
else:
    print("No switching point found in mu range [0.1, 100]")

print("Efficiency plots and analysis complete.")
