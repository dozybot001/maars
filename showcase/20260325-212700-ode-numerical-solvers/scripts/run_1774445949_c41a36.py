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
        try:
            f = fun(t_eval[i], y[i], mu)
            nfev += 1
            y[i+1] = y[i] + h * np.array(f)
            if np.any(np.isnan(y[i+1])) or np.any(np.abs(y[i+1]) > 1e6):
                return t_eval[:i+2], y[:i+2], nfev, time.time() - start_time, False
        except:
            return t_eval[:i+2], y[:i+2], nfev, time.time() - start_time, False
    return t_eval, y, nfev, time.time() - start_time, True

def rk4(fun, t_span, y0, h, mu):
    t_eval = np.arange(t_span[0], t_span[1] + h, h)
    y = np.zeros((len(t_eval), len(y0)))
    y[0] = y0
    nfev = 0
    start_time = time.time()
    for i in range(len(t_eval) - 1):
        try:
            t = t_eval[i]
            curr_y = y[i]
            k1 = np.array(fun(t, curr_y, mu))
            k2 = np.array(fun(t + h/2, curr_y + h/2 * k1, mu))
            k3 = np.array(fun(t + h/2, curr_y + h/2 * k2, mu))
            k4 = np.array(fun(t + h, curr_y + h * k3, mu))
            nfev += 4
            y[i+1] = curr_y + (h/6) * (k1 + 2*k2 + 2*k3 + k4)
            if np.any(np.isnan(y[i+1])) or np.any(np.abs(y[i+1]) > 1e6):
                return t_eval[:i+2], y[:i+2], nfev, time.time() - start_time, False
        except:
            return t_eval[:i+2], y[:i+2], nfev, time.time() - start_time, False
    return t_eval, y, nfev, time.time() - start_time, True

mus = [0.1, 1, 10, 100]
h_fixed = 0.001
results = []

fig, axes = plt.subplots(len(mus), 1, figsize=(10, 4*len(mus)))

for idx, mu in enumerate(mus):
    t_end = 20 + 3 * mu
    t_span = (0, t_end)
    y0 = [2.0, 0.0]
    
    # Reference
    ref_sol = solve_ivp(vdp_ode, t_span, y0, args=(mu,), method='Radau', rtol=1e-10, atol=1e-10)
    
    # Solvers
    for name, method in [('Forward Euler', 'fe'), ('RK4', 'rk4'), ('DP5', 'dp5')]:
        if method == 'fe':
            t, y, nfev, wall_time, success = forward_euler(vdp_ode, t_span, y0, h_fixed, mu)
        elif method == 'rk4':
            t, y, nfev, wall_time, success = rk4(vdp_ode, t_span, y0, h_fixed, mu)
        else: # dp5
            st = time.time()
            sol = solve_ivp(vdp_ode, t_span, y0, args=(mu,), method='RK45', rtol=1e-6, atol=1e-9)
            wall_time = time.time() - st
            t, y, nfev, success = sol.t, sol.y.T, sol.nfev, sol.success
            
        if success:
            # Error at the final time point or RMS error
            # Calculate error by interpolating ref to t
            y_ref_at_t = np.array([np.interp(t, ref_sol.t, ref_sol.y[0]), np.interp(t, ref_sol.t, ref_sol.y[1])]).T
            error = np.sqrt(np.mean(np.square(y - y_ref_at_t)))
            # Max error
            max_err = np.max(np.abs(y - y_ref_at_t))
        else:
            error = np.nan
            max_err = np.nan
        
        results.append({
            'mu': mu,
            'solver': name,
            'rmse': error,
            'max_error': max_err,
            'nfev': nfev,
            'time': wall_time,
            'success': success
        })
        
        # Plotting mu=100 specifically to show divergence/stiffness
        if success:
            axes[idx].plot(t, y[:,0], label=f"{name}")
    
    axes[idx].plot(ref_sol.t, ref_sol.y[0], 'k--', label='Reference', alpha=0.5)
    axes[idx].set_title(f"Van der Pol Solution (mu={mu})")
    axes[idx].legend()

plt.tight_layout()
plt.savefig('/workspace/output/vdp_explicit_trajectories.png')

df_results = pd.DataFrame(results)
df_results.to_csv('/workspace/output/vdp_explicit_benchmark_v2.csv', index=False)
print(df_results)
