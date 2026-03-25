import numpy as np
from scipy.integrate import solve_ivp
import os
import pandas as pd

def vdp_deriv(t, y, mu):
    return [y[1], mu * (1 - y[0]**2) * y[1] - y[0]]

def vdp_jac(t, y, mu):
    return [[0, 1],
            [-2 * mu * y[0] * y[1] - 1, mu * (1 - y[0]**2)]]

def get_period_estimate(mu):
    if mu < 10:
        return 7.0
    else:
        return 1.614 * mu + 7.0

mus = [1, 10, 100, 1000, 1e4, 1e5, 1e6]
results_dir = "/workspace/output/vdp_refs"
os.makedirs(results_dir, exist_ok=True)

summary = []

for mu in mus:
    print(f"Solving for mu={mu}...")
    t_end = get_period_estimate(mu) * 1.5 # 1.5 periods to be safe
    t_span = (0, t_end)
    y0 = [2.0, 0.0]
    
    # Use Radau with Jacobian
    try:
        sol = solve_ivp(vdp_deriv, t_span, y0, method='Radau', jac=vdp_jac,
                        args=(mu,), rtol=1e-11, atol=1e-13)
        
        if sol.success:
            filename = f"vdp_mu_{int(mu)}.npz"
            filepath = os.path.join(results_dir, filename)
            np.savez(filepath, t=sol.t, y=sol.y)
            summary.append({
                "mu": mu,
                "n_points": len(sol.t),
                "t_end_reached": sol.t[-1],
                "status": "Success",
                "filename": filename
            })
        else:
            summary.append({
                "mu": mu,
                "status": f"Failed: {sol.message}",
                "filename": None
            })
    except Exception as e:
        summary.append({
            "mu": mu,
            "status": f"Error: {str(e)}",
            "filename": None
        })

df_summary = pd.DataFrame(summary)
print(df_summary)
df_summary.to_csv(os.path.join(results_dir, "reference_summary.csv"), index=False)
