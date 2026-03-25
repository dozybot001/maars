import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp
import os

def generate_vdp_robust():
    mu_values = [0, 1, 10, 100, 1000, 10000, 100000, 1000000]
    os.makedirs('/workspace/output/vdp_refs', exist_ok=True)
    stats = []

    for mu in mu_values:
        print(f"Solving mu={mu}...")
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
            y0 = [2.0, -2.0/3.0] # Correct for dx/dt=0 at x=2
            t_end = 2.5 * (3.0 - 2.0 * np.log(2.0)) * mu + 10.0
            tol = 1e-10 if mu >= 1e6 else 1e-13
        
        # Use dense_output=True instead of t_eval for stability
        sol = solve_ivp(fun, (0, t_end), y0, method='Radau', jac=jac, 
                        dense_output=True, atol=tol, rtol=tol)
        
        t_eval = np.linspace(0, t_end, 5000)
        y_eval = sol.sol(t_eval)
        
        if mu < 10:
            x, dx_dt = y_eval[0], y_eval[1]
        else:
            x = y_eval[0]
            z = y_eval[1]
            dx_dt = mu * (x - x**3/3.0 - z)
        
        df = pd.DataFrame({'t': t_eval, 'x': x, 'dx_dt': dx_dt})
        filename = f"/workspace/output/vdp_refs/vdp_ref_mu_{mu}.csv"
        df.to_csv(filename, index=False)
        stats.append({'mu': mu, 'status': sol.status, 'nfev': sol.nfev, 'file': filename})
        print(f"  Done. Status: {sol.status}")

    return pd.DataFrame(stats)

stats_df = generate_vdp_robust()
print(stats_df)
stats_df.to_csv('/workspace/output/vdp_refs/summary.csv', index=False)
