import numpy as np
from scipy.integrate import solve_ivp
import os
import pandas as pd
import matplotlib.pyplot as plt

def vdp_deriv(t, y, mu):
    return [y[1], mu * (1 - y[0]**2) * y[1] - y[0]]

def vdp_jac(t, y, mu):
    return [[0, 1],
            [-2 * mu * y[0] * y[1] - 1, mu * (1 - y[0]**2)]]

def get_period_estimate(mu):
    if mu < 10:
        return 8.0
    else:
        # T approx (3 - 2ln2) * mu
        return 1.614 * mu + 10.0

mus = [1, 10, 100, 1000, 1e4, 1e5, 1e6]
results_dir = "/workspace/output/vdp_refs"
os.makedirs(results_dir, exist_ok=True)

summary = []

fig, axes = plt.subplots(len(mus), 1, figsize=(10, 2 * len(mus)), constrained_layout=True)

for i, mu in enumerate(mus):
    print(f"Generating reference for mu={mu}...")
    t_end = get_period_estimate(mu)
    t_span = (0, t_end)
    y0 = [2.0, 0.0]
    
    sol = solve_ivp(vdp_deriv, t_span, y0, method='Radau', jac=vdp_jac,
                    args=(mu,), rtol=1e-10, atol=1e-12)
    
    if sol.success:
        filename = f"vdp_mu_{int(mu)}.npz"
        filepath = os.path.join(results_dir, filename)
        np.savez(filepath, t=sol.t, y=sol.y)
        
        summary.append({
            "mu": mu,
            "n_points": len(sol.t),
            "t_end": sol.t[-1],
            "x_final": sol.y[0, -1],
            "status": "Success",
            "filename": filename
        })
        
        # Plotting
        ax = axes[i]
        # For large mu, use scaled time
        if mu >= 1000:
            ax.plot(sol.t / mu, sol.y[0])
            ax.set_xlabel("t / mu")
        else:
            ax.plot(sol.t, sol.y[0])
            ax.set_xlabel("t")
        ax.set_title(f"Van der Pol Oscillator (mu={mu})")
        ax.set_ylabel("x")
        ax.grid(True)
    else:
        print(f"Failed for mu={mu}: {sol.message}")

plt.savefig(os.path.join(results_dir, "vdp_all_mus.png"))
plt.close()

df_summary = pd.DataFrame(summary)
df_summary.to_csv(os.path.join(results_dir, "reference_metadata.csv"), index=False)
print(df_summary)
