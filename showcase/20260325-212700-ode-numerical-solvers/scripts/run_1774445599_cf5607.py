import numpy as np
import pandas as pd
import time
from scipy.integrate import solve_ivp
import matplotlib.pyplot as plt

# --- System Definitions ---

def harmonic_oscillator(t, y):
    x, v = y
    return [v, -x]

def lorenz_system(t, y):
    sigma = 10
    rho = 28
    beta = 8/3
    x, y_val, z = y
    return [sigma * (y_val - x), x * (rho - z) - y_val, x * y_val - beta * z]

# --- Solvers ---

def euler_step(f, t, y, h):
    return y + h * np.array(f(t, y))

def rk4_step(f, t, y, h):
    k1 = np.array(f(t, y))
    k2 = np.array(f(t + h/2, y + h/2 * k1))
    k3 = np.array(f(t + h/2, y + h/2 * k2))
    k4 = np.array(f(t + h, y + h * k3))
    return y + h/6 * (k1 + 2*k2 + 2*k3 + k4)

def fixed_step_solver(f, y0, t_span, h, method='rk4'):
    t0, tf = t_span
    n_steps = int(np.round((tf - t0) / h))
    t = np.linspace(t0, tf, n_steps + 1)
    y = np.zeros((len(t), len(y0)))
    y[0] = y0
    
    nfev = 0
    step_func = rk4_step if method == 'rk4' else euler_step
    fevals_per_step = 4 if method == 'rk4' else 1
    
    start_time = time.perf_counter()
    for i in range(n_steps):
        y[i+1] = step_func(f, t[i], y[i], h)
    end_time = time.perf_counter()
    
    nfev = n_steps * fevals_per_step
    return t, y, nfev, end_time - start_time

# --- Benchmark Utility ---

def benchmark_system(system_name, f, y0, t_span, gt_file):
    print(f"Benchmarking {system_name}...")
    gt = pd.read_csv(gt_file)
    t_gt = gt['t'].values
    y_gt = gt.iloc[:, 1:].values
    
    results = []
    
    # 1. Euler
    for h in [0.01, 0.001, 0.0001]:
        if system_name == 'Lorenz' and h > 0.001: continue # Lorenz might be unstable with large h
        t_sol, y_sol, nfev, wall_time = fixed_step_solver(f, y0, t_span, h, method='euler')
        # Interpolate to gt time points
        y_interp = np.array([np.interp(t_gt, t_sol, y_sol[:, j]) for j in range(y_sol.shape[1])]).T
        rmse = np.sqrt(np.mean((y_interp - y_gt)**2))
        results.append({'Solver': 'Euler', 'h/tol': h, 'nfev': nfev, 'time': wall_time, 'rmse': rmse})

    # 2. RK4
    for h in [0.01, 0.001, 0.0001]:
        t_sol, y_sol, nfev, wall_time = fixed_step_solver(f, y0, t_span, h, method='rk4')
        y_interp = np.array([np.interp(t_gt, t_sol, y_sol[:, j]) for j in range(y_sol.shape[1])]).T
        rmse = np.sqrt(np.mean((y_interp - y_gt)**2))
        results.append({'Solver': 'RK4', 'h/tol': h, 'nfev': nfev, 'time': wall_time, 'rmse': rmse})

    # 3. DP5 (RK45 in scipy)
    for tol in [1e-3, 1e-6, 1e-9]:
        start_time = time.perf_counter()
        sol = solve_ivp(f, t_span, y0, method='RK45', rtol=tol, atol=tol*1e-3, t_eval=t_gt)
        end_time = time.perf_counter()
        rmse = np.sqrt(np.mean((sol.y.T - y_gt)**2))
        results.append({'Solver': 'DP5', 'h/tol': tol, 'nfev': sol.nfev, 'time': end_time - start_time, 'rmse': rmse})
        
    return pd.DataFrame(results)

# --- Execution ---

harmonic_results = benchmark_system('Harmonic', harmonic_oscillator, [1.0, 0.0], [0, 20], 'harmonic_ground_truth.csv')
lorenz_results = benchmark_system('Lorenz', lorenz_system, [1.0, 1.0, 1.0], [0, 50], 'lorenz_ground_truth.csv')

harmonic_results.to_csv('/workspace/output/harmonic_benchmarks.csv', index=False)
lorenz_results.to_csv('/workspace/output/lorenz_benchmarks.csv', index=False)

print("\nHarmonic Oscillator Results:")
print(harmonic_results)
print("\nLorenz System Results:")
print(lorenz_results)
