import numpy as np
from scipy.integrate import solve_ivp
import pandas as pd
import matplotlib.pyplot as plt
import os

def vdp_deriv(t, y, mu):
    return [y[1], mu * (1 - y[0]**2) * y[1] - y[0]]

def get_period_estimate(mu):
    if mu < 10:
        return 7.0 # Approx for mu=1 is 6.6
    else:
        # For large mu, T approx (3 - 2ln2) * mu + ...
        return 1.614 * mu + 7.0

mus = [1, 10, 100, 1000, 1e4, 1e5, 1e6]
results_dir = "/workspace/output/vdp_refs"
os.makedirs(results_dir, exist_ok=True)

summary = []

for mu in mus:
    print(f"Solving for mu={mu}...")
    t_span = (0, get_period_estimate(mu) * 1.2) # 1.2 periods
    y0 = [2.0, 0.0]
    
    # Use Radau for stiffness
    # Tight tolerances for "high-precision reference"
    sol = solve_ivp(vdp_deriv, t_span, y0, method='Radau', 
                    args=(mu,), rtol=1e-11, atol=1e-13)
    
    if sol.success:
        filename = f"vdp_mu_{int(mu)}.npz"
        filepath = os.path.join(results_dir, filename)
        np.savez(filepath, t=sol.t, y=sol.y)
        
        summary.append({
            "mu": mu,
            "n_points": len(sol.t),
            "t_end": sol.t[-1],
            "status": "Success",
            "filename": filename
        })
        
        # Plot first 3 to verify
        if mu <= 100:
            plt.figure(figsize=(10, 4))
            plt.plot(sol.t, sol.y[0], label='x(t)')
            plt.title(f"Van der Pol Oscillator (mu={mu})")
            plt.xlabel("t")
            plt.ylabel("x")
            plt.grid(True)
            plt.savefig(os.path.join(results_dir, f"plot_mu_{int(mu)}.png"))
            plt.close()
    else:
        summary.append({
            "mu": mu,
            "status": f"Failed: {sol.message}"
        })

df_summary = pd.DataFrame(summary)
print(df_summary)
df_summary.to_csv(os.path.join(results_dir, "reference_summary.csv"), index=False)
