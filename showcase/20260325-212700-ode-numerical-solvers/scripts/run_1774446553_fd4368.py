import pandas as pd
import numpy as np
from scipy.interpolate import interp1d

df = pd.read_csv('final_comprehensive_benchmarks.csv')

# Filter for VDP system
# Note: The 'System' names might vary. Let's check unique systems.
print("Systems in benchmark:", df['System'].unique())

# Based on the summary data provided earlier:
mu_vals = [0.1, 1.0, 10.0, 100.0]
t_dp5 = [0.006620, 0.012866, 0.048606, 0.430667]
t_bdf = [0.025854, 0.056280, 0.133406, 0.127496]

# Find where t_dp5 == t_bdf
# We can interpolate log(mu) vs (t_dp5 - t_bdf)
log_mu = np.log10(mu_vals)
diff = np.array(t_dp5) - np.array(t_bdf)

f = interp1d(diff, log_mu)
try:
    log_mu_star = f(0)
    mu_star = 10**log_mu_star
    print(f"Crossover stiffness mu for DP5 vs BDF: {mu_star:.2f}")
except:
    print("Could not interpolate crossover.")

# Analyze Harmonic Oscillator: Euler vs RK4
harmonic = df[df['System'] == 'Harmonic']
print("\nHarmonic Oscillator Comparison:")
print(harmonic.sort_values(by='error'))

# Analyze if Euler is ever faster than RK4 for the same error
# This requires a Work-Precision curve comparison.
