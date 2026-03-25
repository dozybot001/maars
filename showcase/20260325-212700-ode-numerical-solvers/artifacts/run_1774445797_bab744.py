import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp
import os

def generate_vdp_reference_final(mu, t_end, num_points=2000):
    if mu == 0:
        def fun(t, y): return [y[1], -y[0]]
        def jac(t, y): return [[0, 1], [-1, 0]]
        y0 = [2.0, 0.0]
        method = 'Radau'
        tol = 1e-13
    elif mu < 10:
        def fun(t, y): return [y[1], mu * (1 - y[0]**2) * y[1] - y[0]]
        def jac(t, y): return [[0, 1], [-2 * mu * y[0] * y[1] - 1, mu * (1 - y[0]**2)]]
        y0 = [2.0, 0.0]
        method = 'Radau'
        tol = 1e-13
    else:
        # Liénard
        def fun(t, y): return [mu * (y[0] - y[0]**3 / 3.0 - y[1]), y[0] / mu]
        def jac(t, y): return [[mu * (1 - y[0]**2), -mu], [1.0 / mu, 0]]
        x0 = 2.0
        z0 = x0 - x0**3 / 3.0
        y0 = [x0, z0]
        method = 'BDF' if mu >= 1e5 else 'Radau'
        tol = 1e-10 if mu >= 1e5 else 1e-13
    
    t_span = (0, t_end)
    t_eval = np.linspace(0, t_end, num_points)
    
    sol = solve_ivp(fun, t_span, y0, method=method, jac=jac, t_eval=t_eval, 
                    atol=tol, rtol=tol)
    
    if mu < 10:
        df = pd.DataFrame({'t': sol.t, 'x': sol.y[0], 'dx_dt': sol.y[1]})
    else:
        x = sol.y[0]
        z = sol.y[1]
        dx_dt = mu * (x - x**3 / 3.0 - z)
        df = pd.DataFrame({'t': sol.t, 'x': x, 'dx_dt': dx_dt})
    
    return df, sol.nfev, sol.status

mu_values = [0, 1, 10, 100, 1000, 10000, 100000, 1000000]
results = []
os.makedirs('/workspace/output/vdp_refs', exist_ok=True)

for mu in mu_values:
    if mu == 0: t_end = 20.0
    elif mu < 10: t_end = 30.0
    else: t_end = 2.5 * (3.0 - 2.0 * np.log(2.0)) * mu + 10.0
    
    print(f"Final Solving mu={mu}...")
    df, nfev, status = generate_vdp_reference_final(mu, t_end)
    filename = f"/workspace/output/vdp_refs/vdp_ref_mu_{mu}.csv"
    df.to_csv(filename, index=False)
    results.append({'mu': mu, 'nfev': nfev, 'status': status})
    print(f"  Result: Status {status}, fev {nfev}")

print(pd.DataFrame(results))
