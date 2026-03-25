import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp
import os
import matplotlib.pyplot as plt

def generate_all_vdp():
    mu_values = [0, 1, 10, 100, 1000, 10000, 100000, 1000000]
    os.makedirs('/workspace/output/vdp_refs', exist_ok=True)
    stats = []

    for mu in mu_values:
        print(f"Generating mu={mu}...")
        if mu == 0:
            def fun(t, y): return [y[1], -y[0]]
            def jac(t, y): return [[0, 1], [-1, 0]]
            y0 = [2.0, 0.0]
            t_end = 20.0
            tol = 1e-13
        elif mu < 10:
            def fun(t, y): return [y[1], mu * (1 - y[0]**2) * y[1] - y[0]]
            def jac(t, y): return [[0, 1], [-2 * mu * y[0] * y[1] - 1, mu * (1 - y[0]**2)]]
            y0 = [2.0, 0.0]
            t_end = 20.0 + 5.0 * mu
            tol = 1e-13
        else:
            def fun(t, y): return [mu * (y[0] - y[0]**3 / 3.0 - y[1]), y[0] / mu]
            def jac(t, y): return [[mu * (1 - y[0]**2), -mu], [1.0 / mu, 0]]
            y0 = [2.0, 2.0 - 8.0/3.0]
            t_end = 2.5 * (3.0 - 2.0 * np.log(2.0)) * mu + 10.0
            tol = 1e-11 if mu >= 1e5 else 1e-13
        
        t_eval = np.linspace(0, t_end, 5000)
        sol = solve_ivp(fun, (0, t_end), y0, method='Radau', jac=jac, t_eval=t_eval, 
                        atol=tol, rtol=tol)
        
        if mu < 10:
            x, dx_dt = sol.y[0], sol.y[1]
        else:
            x = sol.y[0]
            z = sol.y[1]
            dx_dt = mu * (x - x**3/3.0 - z)
        
        df = pd.DataFrame({'t': sol.t, 'x': x, 'dx_dt': dx_dt})
        filename = f"/workspace/output/vdp_refs/vdp_ref_mu_{mu}.csv"
        df.to_csv(filename, index=False)
        stats.append({'mu': mu, 'status': sol.status, 'nfev': sol.nfev, 'file': filename})
        print(f"  Done. Status: {sol.status}, Fev: {sol.nfev}")

    return pd.DataFrame(stats)

stats_df = generate_all_vdp()
stats_df.to_csv('/workspace/output/vdp_refs/summary.csv', index=False)

# Visualization
plt.figure(figsize=(15, 10))
for i, mu in enumerate([1, 1000, 1000000]):
    df = pd.read_csv(f"/workspace/output/vdp_refs/vdp_ref_mu_{mu}.csv")
    plt.subplot(2, 3, i+1)
    plt.plot(df['x'], df['dx_dt'])
    plt.title(f'Phase Portrait mu={mu}')
    plt.subplot(2, 3, i+4)
    plt.plot(df['t'], df['x'])
    plt.title(f'Time Series mu={mu}')
plt.tight_layout()
plt.savefig('/workspace/output/vdp_refs/vdp_plots.png')
print("Completed.")
