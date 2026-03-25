import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# 1. Load data
try:
    df_cons = pd.read_csv('consolidated_benchmark.csv')
    df_1_3 = pd.read_csv('benchmark_results_1_3.csv')
    df_rob = pd.read_csv('robertson_benchmarks.csv')
except Exception as e:
    print(f"Error loading files: {e}")

# 2. WPD Plotting (VDP focus as it scales)
plt.figure(figsize=(12, 8))
mus = df_cons['mu'].unique()
for mu in mus:
    subset = df_cons[df_cons['mu'] == mu]
    for method in subset['method'].unique():
        m_subset = subset[subset['method'] == method]
        plt.plot(m_subset['error'], m_subset['time'], 'o-', label=f"mu={mu}, {method}")

plt.xscale('log')
plt.yscale('log')
plt.xlabel('Global Error (RMSE)')
plt.ylabel('Execution Time (s)')
plt.title('Work-Precision Diagram (VDP System)')
plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
plt.grid(True, which="both", ls="-", alpha=0.5)
plt.tight_layout()
plt.savefig('wpd_comprehensive.png')

# 3. Efficiency Switching Threshold Analysis
# We want to find the intersection of DP5 and BDF time for different mu
switching_points = []
for mu in mus:
    dp5 = df_cons[(df_cons['mu'] == mu) & (df_cons['method'] == 'DP5')]
    bdf = df_cons[(df_cons['mu'] == mu) & (df_cons['method'] == 'BDF')]
    
    if not dp5.empty and not bdf.empty:
        # Find if there is a crossover in time vs error
        # Interpolate to find intersection or just compare at 1e-6
        t_dp5 = np.interp(1e-6, dp5['error'][::-1], dp5['time'][::-1])
        t_bdf = np.interp(1e-6, bdf['error'][::-1], bdf['time'][::-1])
        switching_points.append({'mu': mu, 't_dp5': t_dp5, 't_bdf': t_bdf, 'winner': 'DP5' if t_dp5 < t_bdf else 'BDF'})

df_switch = pd.DataFrame(switching_points)
print("--- Switching Analysis at Tol=1e-6 ---")
print(df_switch)

# 4. Selection Matrix Construction
# Stiffness: Low (mu=1), Med (mu=30), High (mu=100+), Extreme (Rob)
# Precision: Low (1e-3), Med (1e-6), High (1e-9)

matrix_data = {
    'Stiffness': ['Non-Stiff', 'Moderate Stiffness', 'High Stiffness', 'Extreme Stiffness'],
    'Low Prec (1e-3)': ['DP5', 'DP5/BDF', 'BDF', 'Radau'],
    'Med Prec (1e-6)': ['DP5', 'BDF', 'BDF/Radau', 'Radau'],
    'High Prec (1e-9)': ['DP5/RK4', 'Radau', 'Radau', 'Radau']
}
df_matrix = pd.DataFrame(matrix_data)
df_matrix.to_csv('solver_selection_matrix.csv', index=False)

# Save results
df_switch.to_csv('efficiency_switching_summary.csv', index=False)
