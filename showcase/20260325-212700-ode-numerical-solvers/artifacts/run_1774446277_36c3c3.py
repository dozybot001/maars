import numpy as np
import scipy.integrate as integrate
import time
import matplotlib.pyplot as plt

def vdp_deriv(t, y, mu):
    return [y[1], mu * (1 - y[0]**2) * y[1] - y[0]]

def forward_euler(f, t_span, y0, n_steps, mu):
    t = np.linspace(t_span[0], t_span[1], n_steps + 1)
    h = (t_span[1] - t_span[0]) / n_steps
    y = np.zeros((n_steps + 1, len(y0)))
    y[0] = y0
    fev = 0
    for i in range(n_steps):
        y[i+1] = y[i] + h * np.array(f(t[i], y[i], mu))
        fev += 1
        if np.any(np.isnan(y[i+1])) or np.any(np.abs(y[i+1]) > 1e6):
            return t[:i+2], y[:i+2], fev, True # Diverged
    return t, y, fev, False

def rk4(f, t_span, y0, n_steps, mu):
    t = np.linspace(t_span[0], t_span[1], n_steps + 1)
    h = (t_span[1] - t_span[0]) / n_steps
    y = np.zeros((n_steps + 1, len(y0)))
    y[0] = y0
    fev = 0
    for i in range(n_steps):
        k1 = np.array(f(t[i], y[i], mu))
        k2 = np.array(f(t[i] + h/2, y[i] + h/2 * k1, mu))
        k3 = np.array(f(t[i] + h/2, y[i] + h/2 * k2, mu))
        k4 = np.array(f(t[i] + h, y[i] + h * k3, mu))
        y[i+1] = y[i] + (h/6) * (k1 + 2*k2 + 2*k3 + k4)
        fev += 4
        if np.any(np.isnan(y[i+1])) or np.any(np.abs(y[i+1]) > 1e6):
            return t[:i+2], y[:i+2], fev, True
    return t, y, fev, False

# Test Config
mus = [0.1, 1.0, 10.0, 100.0]
t_span = (0, 20)
y0 = [2.0, 0.0]

results = []

for mu in mus:
    print(f"Testing mu = {mu}...")
    # Reference solution
    ref_sol = integrate.solve_ivp(vdp_deriv, t_span, y0, args=(mu,), method='Radau', atol=1e-13, rtol=1e-13)
    y_ref_final = ref_sol.y[:, -1]

    # 1. DP5 (RK45) with varying tolerances
    tols = [1e-3, 1e-4, 1e-5, 1e-6, 1e-7, 1e-8]
    for tol in tols:
        start_time = time.time()
        sol = integrate.solve_ivp(vdp_deriv, t_span, y0, args=(mu,), method='RK45', atol=tol, rtol=tol)
        elapsed = time.time() - start_time
        err = np.linalg.norm(sol.y[:, -1] - y_ref_final) if sol.status == 0 else np.nan
        results.append({'mu': mu, 'method': 'DP5', 'tol': tol, 'fev': sol.nfev, 'time': elapsed, 'error': err, 'stable': sol.status == 0})

    # 2. Forward Euler and RK4 with varying step counts
    # Adjust step counts based on mu to find stability limit
    if mu < 10:
        steps_list = [500, 1000, 5000, 10000, 50000]
    elif mu == 10:
        steps_list = [5000, 10000, 50000, 100000, 500000]
    else: # mu = 100
        steps_list = [50000, 100000, 500000, 1000000]

    for steps in steps_list:
        # FE
        start_time = time.time()
        t, y, fev, div = forward_euler(vdp_deriv, t_span, y0, steps, mu)
        elapsed = time.time() - start_time
        err = np.linalg.norm(y[-1] - y_ref_final) if not div else np.nan
        results.append({'mu': mu, 'method': 'Euler', 'steps': steps, 'fev': fev, 'time': elapsed, 'error': err, 'stable': not div})

        # RK4
        start_time = time.time()
        t, y, fev, div = rk4(vdp_deriv, t_span, y0, steps, mu)
        elapsed = time.time() - start_time
        err = np.linalg.norm(y[-1] - y_ref_final) if not div else np.nan
        results.append({'mu': mu, 'method': 'RK4', 'steps': steps, 'fev': fev, 'time': elapsed, 'error': err, 'stable': not div})

# Save results for analysis
import pandas as pd
df = pd.DataFrame(results)
df.to_csv('benchmark_results.csv', index=False)

# Plotting Work-Precision Diagrams
plt.figure(figsize=(12, 10))
for i, mu in enumerate(mus):
    plt.subplot(2, 2, i+1)
    subset = df[df['mu'] == mu]
    for method in ['Euler', 'RK4', 'DP5']:
        m_data = subset[subset['method'] == method].dropna(subset=['error'])
        if not m_data.empty:
            plt.loglog(m_data['fev'], m_data['error'], 'o-', label=method)
    plt.title(f'Work-Precision (mu={mu})')
    plt.xlabel('Number of Function Evaluations')
    plt.ylabel('Global Error at T=20')
    plt.legend()
    plt.grid(True, which="both", ls="-", alpha=0.5)

plt.tight_layout()
plt.savefig('work_precision_diagram.png')
print("Benchmark completed. Results saved to benchmark_results.csv and work_precision_diagram.png")
