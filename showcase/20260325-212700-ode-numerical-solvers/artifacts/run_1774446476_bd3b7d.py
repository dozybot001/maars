import numpy as np
import pandas as pd
import time
import matplotlib.pyplot as plt
from scipy.integrate import solve_ivp
from scipy.interpolate import interp1d
import os

# 1. Define ODE systems
def harmonic_oscillator(t, y):
    return [y[1], -y[0]]

def lorenz_system(t, y, sigma=10, rho=28, beta=8/3):
    x, y, z = y
    return [sigma * (y - x), x * (rho - z) - y, x * y - beta * z]

def vdp_system(t, y, mu=100):
    return [y[1], mu * (1 - y[0]**2) * y[1] - y[0]]

def robertson_system(t, y):
    y1, y2, y3 = y
    dy1 = -0.04 * y1 + 1e4 * y2 * y3
    dy2 = 0.04 * y1 - 1e4 * y2 * y3 - 3e7 * y2**2
    dy3 = 3e7 * y2**2
    return [dy1, dy2, dy3]

# 2. Fixed-step Solvers
def forward_euler(fun, t_span, y0, h):
    t_eval = np.arange(t_span[0], t_span[1] + h, h)
    y = np.zeros((len(t_eval), len(y0)))
    y[0] = y0
    nfev = 0
    for i in range(len(t_eval) - 1):
        y[i+1] = y[i] + h * np.array(fun(t_eval[i], y[i]))
        nfev += 1
    return t_eval, y, nfev

def rk4(fun, t_span, y0, h):
    t_eval = np.arange(t_span[0], t_span[1] + h, h)
    y = np.zeros((len(t_eval), len(y0)))
    y[0] = y0
    nfev = 0
    for i in range(len(t_eval) - 1):
        t, curr_y = t_eval[i], y[i]
        k1 = np.array(fun(t, curr_y))
        k2 = np.array(fun(t + h/2, curr_y + h/2 * k1))
        k3 = np.array(fun(t + h/2, curr_y + h/2 * k2))
        k4 = np.array(fun(t + h, curr_y + h * k3))
        y[i+1] = curr_y + (h/6) * (k1 + 2*k2 + 2*k3 + k4)
        nfev += 4
    return t_eval, y, nfev

# 3. Benchmark helper
def run_benchmark(name, fun, ground_truth_file, solvers_config):
    # Load ground truth
    df_gt = pd.read_csv(ground_truth_file)
    t_ref = df_gt['t'].values
    y_ref = df_gt.iloc[:, 1:].values
    
    t_span = [t_ref[0], t_ref[-1]]
    y0 = y_ref[0]
    
    results = []
    
    for solver_name, config in solvers_config:
        for param in config['params']:
            start_time = time.time()
            try:
                if solver_name == 'Euler':
                    t_eval, y_sol, nfev = forward_euler(fun, t_span, y0, param)
                elif solver_name == 'RK4':
                    t_eval, y_sol, nfev = rk4(fun, t_span, y0, param)
                else:
                    # Scipy solvers
                    # Use a denser t_eval or just t_ref for error calculation
                    sol = solve_ivp(fun, t_span, y0, method=solver_name, rtol=param, atol=param/100)
                    t_eval, y_sol, nfev = sol.t, sol.y.T, sol.nfev
                    if not sol.success:
                        continue
                
                wall_time = time.time() - start_time
                
                # Interpolate to compare with ground truth
                f_interp = interp1d(t_eval, y_sol, axis=0, bounds_error=False, fill_value="extrapolate")
                y_at_ref = f_interp(t_ref)
                
                error = np.sqrt(np.mean((y_at_ref - y_ref)**2))
                results.append({
                    'System': name,
                    'Solver': solver_name,
                    'Param': param,
                    'nfev': nfev,
                    'time': wall_time,
                    'error': error
                })
            except Exception as e:
                print(f"Error running {solver_name} on {name}: {e}")
                continue
            
    return pd.DataFrame(results)

# Solvers configuration
configs_general = [
    ('Euler', {'params': [1e-3, 5e-4, 2e-4]}),
    ('RK4', {'params': [1e-2, 5e-3, 2e-3]}),
    ('RK45', {'params': [1e-4, 1e-6, 1e-8]}),
    ('BDF', {'params': [1e-4, 1e-6, 1e-8]}),
    ('Radau', {'params': [1e-4, 1e-6, 1e-8]})
]

all_results = []

# System 1: Harmonic
if os.path.exists('harmonic_ground_truth.csv'):
    print("Benchmarking Harmonic...")
    all_results.append(run_benchmark('Harmonic', harmonic_oscillator, 'harmonic_ground_truth.csv', configs_general))

# System 2: Lorenz
if os.path.exists('lorenz_ground_truth.csv'):
    print("Benchmarking Lorenz...")
    lorenz_configs = [
        ('Euler', {'params': [1e-4, 5e-5, 2e-5]}),
        ('RK4', {'params': [1e-3, 5e-4, 2e-4]}),
        ('RK45', {'params': [1e-6, 1e-8, 1e-10]}),
        ('BDF', {'params': [1e-6, 1e-8, 1e-10]}),
        ('Radau', {'params': [1e-6, 1e-8, 1e-10]})
    ]
    all_results.append(run_benchmark('Lorenz', lorenz_system, 'lorenz_ground_truth.csv', lorenz_configs))

# System 3: Van der Pol (mu=100)
if os.path.exists('vdp_ground_truth.csv'):
    print("Benchmarking VDP...")
    vdp_configs = [
        ('RK45', {'params': [1e-4, 1e-6, 1e-8]}),
        ('BDF', {'params': [1e-4, 1e-6, 1e-8]}),
        ('Radau', {'params': [1e-4, 1e-6, 1e-8]})
    ]
    all_results.append(run_benchmark('VDP (mu=100)', lambda t, y: vdp_system(t, y, 100), 'vdp_ground_truth.csv', vdp_configs))

# System 4: Robertson
if os.path.exists('robertson_ground_truth.csv'):
    print("Benchmarking Robertson...")
    rob_configs = [
        ('BDF', {'params': [1e-4, 1e-6, 1e-8]}),
        ('Radau', {'params': [1e-4, 1e-6, 1e-8]}),
        ('LSODA', {'params': [1e-4, 1e-6, 1e-8]})
    ]
    all_results.append(run_benchmark('Robertson', robertson_system, 'robertson_ground_truth.csv', rob_configs))

if all_results:
    df_final = pd.concat(all_results)
    df_final.to_csv('final_comprehensive_benchmarks.csv', index=False)

    # Plotting
    systems = df_final['System'].unique()
    num_systems = len(systems)
    fig, axes = plt.subplots(num_systems, 2, figsize=(16, 6 * num_systems))
    if num_systems == 1:
        axes = axes.reshape(1, 2)

    for i, system in enumerate(systems):
        df_sys = df_final[df_final['System'] == system]
        
        # Error vs NFEV
        ax = axes[i, 0]
        for solver in df_sys['Solver'].unique():
            df_sol = df_sys[df_sys['Solver'] == solver]
            df_sol = df_sol.sort_values('nfev')
            ax.loglog(df_sol['nfev'], df_sol['error'], 'o-', label=solver)
        ax.set_title(f'{system}: Global Error vs NFEV')
        ax.set_xlabel('Function Evaluations (NFEV)')
        ax.set_ylabel('Global Error (RMSE)')
        ax.legend()
        ax.grid(True, which="both", ls="-", alpha=0.3)
        
        # Error vs Time
        ax = axes[i, 1]
        for solver in df_sys['Solver'].unique():
            df_sol = df_sys[df_sys['Solver'] == solver]
            df_sol = df_sol.sort_values('time')
            ax.loglog(df_sol['time'], df_sol['error'], 'o-', label=solver)
        ax.set_title(f'{system}: Global Error vs Wall-clock Time')
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Global Error (RMSE)')
        ax.legend()
        ax.grid(True, which="both", ls="-", alpha=0.3)

    plt.tight_layout()
    plt.savefig('comprehensive_wpd_final.png')
    print("Generated comprehensive_wpd_final.png")
else:
    print("No results to plot.")
