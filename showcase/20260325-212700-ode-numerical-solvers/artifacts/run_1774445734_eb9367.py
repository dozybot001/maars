import numpy as np
import pandas as pd
import time
import matplotlib.pyplot as plt
from scipy.integrate import solve_ivp

# --- 1. Define ODE Systems ---

def harmonic_oscillator(t, y):
    # m=1, k=1 => dx/dt = v, dv/dt = -x
    return [y[1], -y[0]]

def lorenz_system(t, y):
    sigma, rho, beta = 10.0, 28.0, 8/3
    x, y, z = y
    dxdt = sigma * (y - x)
    dydt = x * (rho - z) - y
    dzdt = x * y - beta * z
    return [dxdt, dydt, dzdt]

# --- 2. Solver Implementations ---

class Counter:
    def __init__(self, func):
        self.func = func
        self.nfev = 0
    def __call__(self, t, y):
        self.nfev += 1
        return self.func(t, y)

def euler_step(f, t, y, h):
    return y + h * np.array(f(t, y))

def rk4_step(f, t, y, h):
    k1 = np.array(f(t, y))
    k2 = np.array(f(t + h/2, y + h/2 * k1))
    k3 = np.array(f(t + h/2, y + h/2 * k2))
    k4 = np.array(f(t + h, y + h * k3))
    return y + h/6 * (k1 + 2*k2 + 2*k3 + k4)

def fixed_step_solve(f_orig, y0, t_span, h, step_func):
    f = Counter(f_orig)
    t0, tf = t_span
    t_eval = np.arange(t0, tf + h/2, h)
    y = np.zeros((len(t_eval), len(y0)))
    y[0] = y0
    
    start_time = time.perf_counter()
    for i in range(len(t_eval)-1):
        y[i+1] = step_func(f, t_eval[i], y[i], h)
    end_time = time.perf_counter()
    
    return t_eval, y, f.nfev, end_time - start_time

def dp5_solve(f_orig, y0, t_span, rtol=1e-3, atol=1e-6):
    f = Counter(f_orig)
    start_time = time.perf_counter()
    sol = solve_ivp(f, t_span, y0, method='RK45', rtol=rtol, atol=atol)
    end_time = time.perf_counter()
    # solve_ivp also provides sol.t and sol.y
    return sol.t, sol.y.T, f.nfev, end_time - start_time

# --- 3. Benchmark Logic ---

def compute_error(t_eval, y_eval, gt_df):
    # gt_df has columns t, y0, y1, ...
    # We interpolate gt_df onto t_eval to compare
    from scipy.interpolate import interp1d
    
    gt_t = gt_df['t'].values
    gt_y = gt_df.iloc[:, 1:].values
    
    # Create interpolator for ground truth
    interp_func = interp1d(gt_t, gt_y, axis=0, fill_value="extrapolate")
    y_gt_interp = interp_func(t_eval)
    
    # Global Error: RMSE across all components and all time steps
    error = np.sqrt(np.mean((y_eval - y_gt_interp)**2))
    return error

# --- 4. Execution ---

# Load Ground Truths
harmonic_gt = pd.read_csv('/workspace/output/harmonic_ground_truth.csv')
lorenz_gt = pd.read_csv('/workspace/output/lorenz_ground_truth.csv')

results = []

# --- Harmonic Oscillator Benchmarks ---
print("Benchmarking Harmonic Oscillator...")
h_vals = [0.1, 0.05, 0.01]
y0_h = [1.0, 0.0]
t_span_h = [0, 20]

for h in h_vals:
    # Euler
    t, y, nfev, wall = fixed_step_solve(harmonic_oscillator, y0_h, t_span_h, h, euler_step)
    err = compute_error(t, y, harmonic_gt)
    results.append({'System': 'Harmonic', 'Solver': 'Euler', 'Step/Tol': h, 'NFEV': nfev, 'Time': wall, 'Error': err})
    
    # RK4
    t, y, nfev, wall = fixed_step_solve(harmonic_oscillator, y0_h, t_span_h, h, rk4_step)
    err = compute_error(t, y, harmonic_gt)
    results.append({'System': 'Harmonic', 'Solver': 'RK4', 'Step/Tol': h, 'NFEV': nfev, 'Time': wall, 'Error': err})

tols = [1e-3, 1e-6, 1e-9]
for tol in tols:
    t, y, nfev, wall = dp5_solve(harmonic_oscillator, y0_h, t_span_h, rtol=tol, atol=tol/1000)
    err = compute_error(t, y, harmonic_gt)
    results.append({'System': 'Harmonic', 'Solver': 'DP5', 'Step/Tol': tol, 'NFEV': nfev, 'Time': wall, 'Error': err})

# --- Lorenz System Benchmarks ---
print("Benchmarking Lorenz System...")
h_vals_l = [0.01, 0.005, 0.002]
y0_l = [1.0, 1.0, 1.0]
t_span_l = [0, 50]

for h in h_vals_l:
    # Euler
    t, y, nfev, wall = fixed_step_solve(lorenz_system, y0_l, t_span_l, h, euler_step)
    err = compute_error(t, y, lorenz_gt)
    results.append({'System': 'Lorenz', 'Solver': 'Euler', 'Step/Tol': h, 'NFEV': nfev, 'Time': wall, 'Error': err})
    
    # RK4
    t, y, nfev, wall = fixed_step_solve(lorenz_system, y0_l, t_span_l, h, rk4_step)
    err = compute_error(t, y, lorenz_gt)
    results.append({'System': 'Lorenz', 'Solver': 'RK4', 'Step/Tol': h, 'NFEV': nfev, 'Time': wall, 'Error': err})

for tol in tols:
    t, y, nfev, wall = dp5_solve(lorenz_system, y0_l, t_span_l, rtol=tol, atol=tol/1000)
    err = compute_error(t, y, lorenz_gt)
    results.append({'System': 'Lorenz', 'Solver': 'DP5', 'Step/Tol': tol, 'NFEV': nfev, 'Time': wall, 'Error': err})

# --- 5. Save and Plot ---
df = pd.DataFrame(results)
df.to_csv('/workspace/output/benchmark_results_1_3.csv', index=False)

# Plots
for sys in ['Harmonic', 'Lorenz']:
    subset = df[df['System'] == sys]
    plt.figure(figsize=(10, 6))
    for solver in ['Euler', 'RK4', 'DP5']:
        s_subset = subset[subset['Solver'] == solver]
        plt.loglog(s_subset['NFEV'], s_subset['Error'], 'o-', label=solver)
    
    plt.xlabel('Function Evaluations (NFEV)')
    plt.ylabel('Global Error (RMSE)')
    plt.title(f'Efficiency Plot: {sys} System')
    plt.legend()
    plt.grid(True, which="both", ls="-")
    plt.savefig(f'/workspace/output/{sys.lower()}_efficiency.png')
    plt.close()

print("Benchmark complete. Data saved to benchmark_results_1_3.csv")
