import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp
import os

def vdp_standard(t, y, mu):
    return [y[1], mu * (1 - y[0]**2) * y[1] - y[0]]

def vdp_standard_jac(t, y, mu):
    return [[0, 1], 
            [-2 * mu * y[0] * y[1] - 1, mu * (1 - y[0]**2)]]

def vdp_lienard(t, y, mu):
    return [mu * (y[0] - y[0]**3 / 3.0 - y[1]), y[0] / mu]

def vdp_lienard_jac(t, y, mu):
    return [[mu * (1 - y[0]**2), -mu],
            [1.0 / mu, 0]]

def generate_vdp_reference(mu, t_end, num_points=2000):
    tol = 1e-13 if mu < 1e5 else 1e-11
    
    if mu < 10:
        y0 = [2.0, 0.0]
        def fun(t, y): return vdp_standard(t, y, mu)
        def jac(t, y): return vdp_standard_jac(t, y, mu)
        t_span = (0, t_end)
        t_eval = np.linspace(0, t_end, num_points)
        
        sol = solve_ivp(fun, t_span, y0, method='Radau', t_eval=t_eval, 
                        jac=jac, atol=tol, rtol=tol)
        df = pd.DataFrame({'t': sol.t, 'x': sol.y[0], 'dx_dt': sol.y[1]})
    else:
        x0 = 2.0
        z0 = x0 - x0**3 / 3.0
        y0 = [x0, z0]
        def fun(t, y): return vdp_lienard(t, y, mu)
        def jac(t, y): return vdp_lienard_jac(t, y, mu)
        t_span = (0, t_end)
        t_eval = np.linspace(0, t_end, num_points)
        
        sol = solve_ivp(fun, t_span, y0, method='Radau', t_eval=t_eval, 
                        jac=jac, atol=tol, rtol=tol, first_step=1e-6/mu if mu>0 else None)
        
        x = sol.y[0]
        z = sol.y[1]
        dx_dt = mu * (x - x**3 / 3.0 - z)
        df = pd.DataFrame({'t': sol.t, 'x': x, 'dx_dt': dx_dt})
    
    return df, sol.nfev, sol.status

mu_values = [0, 1, 10, 100, 1000, 10000, 100000, 1000000]
stats = []

for mu in mu_values:
    if mu == 0: t_end = 20.0
    elif mu < 10: t_end = 20.0 + 3.0 * mu
    else: t_end = 2.2 * (3.0 - 2.0 * np.log(2.0)) * mu + 10.0
    
    print(f"Solving mu={mu}...")
    df, nfev, status = generate_vdp_reference(mu, t_end)
    filename = f"/workspace/output/vdp_refs/vdp_ref_mu_{mu}.csv"
    df.to_csv(filename, index=False)
    stats.append({'mu': mu, 'nfev': nfev, 'status': status, 'file': filename})
    print(f"  Done. fev: {nfev}, Status: {status}")

print(pd.DataFrame(stats))
