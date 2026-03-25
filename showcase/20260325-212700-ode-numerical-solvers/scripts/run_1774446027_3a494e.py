import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.integrate import solve_ivp
import time

def vdp(t, y, mu):
    return [y[1], mu * (1 - y[0]**2) * y[1] - y[0]]

def get_error(sol, t_eval, y_ref):
    # Interpolate sol to t_eval if necessary
    from scipy.interpolate import interp1d
    if sol.t.shape[0] < 2: return np.inf
    f = interp1d(sol.t, sol.y, axis=1, fill_value="extrapolate")
    y_interp = f(t_eval)
    return np.sqrt(np.mean((y_interp - y_ref)**2))

mus = [0.1, 1.0, 10.0, 100.0]
results = []

for mu in mus:
    t_span = (0, 20 + 3 * mu)
    t_eval = np.linspace(t_span[0], t_span[1], 2000)
    
    # Ground truth
    sol_ref = solve_ivp(vdp, t_span, [2.0, 0.0], args=(mu,), method='Radau', rtol=1e-12, atol=1e-12, t_eval=t_eval)
    y_ref = sol_ref.y

    # Benchmarking Explicit (DP5)
    for tol in [1e-3, 1e-4, 1e-5, 1e-6, 1e-7, 1e-8, 1e-9]:
        start = time.time()
        sol = solve_ivp(vdp, t_span, [2.0, 0.0], args=(mu,), method='RK45', rtol=tol, atol=tol/1000)
        elapsed = time.time() - start
        if sol.success:
            err = get_error(sol, t_eval, y_ref)
            results.append({'mu': mu, 'method': 'DP5', 'tol': tol, 'nfev': sol.nfev, 'error': err, 'time': elapsed})

    # Benchmarking Implicit (BDF)
    for tol in [1e-3, 1e-4, 1e-5, 1e-6, 1e-7, 1e-8]:
        start = time.time()
        sol = solve_ivp(vdp, t_span, [2.0, 0.0], args=(mu,), method='BDF', rtol=tol, atol=tol/1000)
        elapsed = time.time() - start
        if sol.success:
            err = get_error(sol, t_eval, y_ref)
            results.append({'mu': mu, 'method': 'BDF', 'tol': tol, 'nfev': sol.nfev, 'error': err, 'time': elapsed})

    # Benchmarking Implicit (Radau)
    for tol in [1e-3, 1e-4, 1e-5, 1e-6, 1e-7, 1e-8]:
        start = time.time()
        sol = solve_ivp(vdp, t_span, [2.0, 0.0], args=(mu,), method='Radau', rtol=tol, atol=tol/1000)
        elapsed = time.time() - start
        if sol.success:
            err = get_error(sol, t_eval, y_ref)
            results.append({'mu': mu, 'method': 'Radau', 'tol': tol, 'nfev': sol.nfev, 'error': err, 'time': elapsed})

df = pd.DataFrame(results)
df.to_csv('consolidated_benchmark.csv', index=False)

# Create WPDs
for mu in mus:
    plt.figure(figsize=(10, 6))
    subset = df[df['mu'] == mu]
    for method in subset['method'].unique():
        m_data = subset[subset['method'] == method].sort_values('error')
        plt.loglog(m_data['error'], m_data['nfev'], 'o-', label=method)
    
    plt.xlabel('Global RMSE')
    plt.ylabel('Work (NFEV)')
    plt.title(f'Work-Precision Diagram (mu={mu})')
    plt.legend()
    plt.grid(True, which="both", ls="-", alpha=0.5)
    plt.savefig(f'wpd_mu_{mu}.png')
    plt.close()

print("Consolidated benchmark data and WPD plots generated.")
