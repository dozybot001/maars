import numpy as np
import pandas as pd
import time
from scipy.integrate import solve_ivp
import matplotlib.pyplot as plt

def vdp_ode(t, y, mu):
    return [y[1], mu * (1 - y[0]**2) * y[1] - y[0]]

def forward_euler(fun, t_span, y0, h, mu):
    t_eval = np.arange(t_span[0], t_span[1] + h, h)
    y = np.zeros((len(t_eval), len(y0)))
    y[0] = y0
    nfev = 0
    start_time = time.time()
    for i in range(len(t_eval) - 1):
        f = fun(t_eval[i], y[i], mu)
        nfev += 1
        y[i+1] = y[i] + h * np.array(f)
        if np.any(np.abs(y[i+1]) > 1e10): # Stability check
            return t_eval[:i+2], y[:i+2], nfev, time.time() - start_time, False
    return t_eval, y, nfev, time.time() - start_time, True

def rk4(fun, t_span, y0, h, mu):
    t_eval = np.arange(t_span[0], t_span[1] + h, h)
    y = np.zeros((len(t_eval), len(y0)))
    y[0] = y0
    nfev = 0
    start_time = time.time()
    for i in range(len(t_eval) - 1):
        t = t_eval[i]
        curr_y = y[i]
        k1 = np.array(fun(t, curr_y, mu))
        k2 = np.array(fun(t + h/2, curr_y + h/2 * k1, mu))
        k3 = np.array(fun(t + h/2, curr_y + h/2 * k2, mu))
        k4 = np.array(fun(t + h, curr_y + h * k3, mu))
        nfev += 4
        y[i+1] = curr_y + (h/6) * (k1 + 2*k2 + 2*k3 + k4)
        if np.any(np.abs(y[i+1]) > 1e10): # Stability check
            return t_eval[:i+2], y[:i+2], nfev, time.time() - start_time, False
    return t_eval, y, nfev, time.time() - start_time, True

def benchmark_vdp():
    mus = [0.1, 1, 10, 100]
    results = []
    h_fixed = 0.001
    
    for mu in mus:
        print(f"Benchmarking mu = {mu}...")
        t_end = 20 + 2 * mu # Heuristic to capture dynamics
        t_span = (0, t_end)
        y0 = [2.0, 0.0]
        
        # Reference Solution (Radau)
        ref_sol = solve_ivp(vdp_ode, t_span, y0, args=(mu,), method='Radau', rtol=1e-12, atol=1e-12)
        t_ref = ref_sol.t
        y_ref = ref_sol.y.T
        
        # 1. Forward Euler
        t_fe, y_fe, nfev_fe, time_fe, success_fe = forward_euler(vdp_ode, t_span, y0, h_fixed, mu)
        if success_fe:
            # Interpolate reference to fe points or vice versa. Reference is usually denser in stiff parts.
            # For simplicity, calculate error at end point if stable, or mean error.
            y_ref_interp = np.array([np.interp(t_fe, t_ref, y_ref[:,0]), np.interp(t_fe, t_ref, y_ref[:,1])]).T
            error_fe = np.linalg.norm(y_fe - y_ref_interp, ord=np.inf)
        else:
            error_fe = np.nan
            
        results.append({'mu': mu, 'solver': 'Forward Euler', 'error': error_fe, 'nfev': nfev_fe, 'time': time_fe, 'success': success_fe})

        # 2. RK4
        t_rk, y_rk, nfev_rk, time_rk, success_rk = rk4(vdp_ode, t_span, y0, h_fixed, mu)
        if success_rk:
            y_ref_interp = np.array([np.interp(t_rk, t_ref, y_ref[:,0]), np.interp(t_rk, t_ref, y_ref[:,1])]).T
            error_rk = np.linalg.norm(y_rk - y_ref_interp, ord=np.inf)
        else:
            error_rk = np.nan
            
        results.append({'mu': mu, 'solver': 'RK4', 'error': error_rk, 'nfev': nfev_rk, 'time': time_rk, 'success': success_rk})

        # 3. DP5 (solve_ivp RK45)
        start_time = time.time()
        dp_sol = solve_ivp(vdp_ode, t_span, y0, args=(mu,), method='RK45', rtol=1e-3, atol=1e-6)
        time_dp = time.time() - start_time
        if dp_sol.success:
            y_ref_interp = np.array([np.interp(dp_sol.t, t_ref, y_ref[:,0]), np.interp(dp_sol.t, t_ref, y_ref[:,1])]).T
            error_dp = np.linalg.norm(dp_sol.y.T - y_ref_interp, ord=np.inf)
        else:
            error_dp = np.nan
        
        results.append({'mu': mu, 'solver': 'DP5', 'error': error_dp, 'nfev': dp_sol.nfev, 'time': time_dp, 'success': dp_sol.success})

    df = pd.DataFrame(results)
    df.to_csv('/workspace/output/vdp_explicit_benchmark.csv', index=False)
    return df

df = benchmark_vdp()
print(df)

# Plotting
plt.figure(figsize=(12, 8))
for solver in ['Forward Euler', 'RK4', 'DP5']:
    subset = df[df['solver'] == solver]
    plt.subplot(2, 2, 1)
    plt.loglog(subset['mu'], subset['error'], marker='o', label=solver)
    plt.title('Global Error vs Mu')
    plt.xlabel('Mu')
    plt.ylabel('Max Error')
    plt.legend()
    
    plt.subplot(2, 2, 2)
    plt.loglog(subset['mu'], subset['nfev'], marker='s', label=solver)
    plt.title('NFEV vs Mu')
    plt.xlabel('Mu')
    plt.ylabel('Function Evals')
    plt.legend()

    plt.subplot(2, 2, 3)
    plt.loglog(subset['mu'], subset['time'], marker='^', label=solver)
    plt.title('Execution Time vs Mu')
    plt.xlabel('Mu')
    plt.ylabel('Time (s)')
    plt.legend()

plt.tight_layout()
plt.savefig('/workspace/output/vdp_explicit_benchmark_plots.png')
