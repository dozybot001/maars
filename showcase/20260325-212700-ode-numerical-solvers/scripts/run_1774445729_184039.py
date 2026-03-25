import numpy as np
import pandas as pd
import time
from scipy.integrate import solve_ivp
import matplotlib.pyplot as plt

# Robertson Problem Definition
def robertson(t, y):
    y1, y2, y3 = y
    dy1 = -0.04 * y1 + 1e4 * y2 * y3
    dy2 = 0.04 * y1 - 1e4 * y2 * y3 - 3e7 * y2**2
    dy3 = 3e7 * y2**2
    return [dy1, dy2, dy3]

def robertson_jac(t, y):
    y1, y2, y3 = y
    jac = np.zeros((3, 3))
    jac[0, 0] = -0.04
    jac[0, 1] = 1e4 * y3
    jac[0, 2] = 1e4 * y2
    jac[1, 0] = 0.04
    jac[1, 1] = -1e4 * y3 - 6e7 * y2
    jac[1, 2] = -1e4 * y2
    jac[2, 0] = 0
    jac[2, 1] = 6e7 * y2
    jac[2, 2] = 0
    return jac

y0 = [1.0, 0.0, 0.0]

def euler_fixed(fun, t_span, y0, h):
    t_start, t_end = t_span
    t = t_start
    y = np.array(y0)
    steps = 0
    start_time = time.time()
    while t < t_end:
        y_next = y + h * np.array(fun(t, y))
        t += h
        steps += 1
        y = y_next
        if np.any(np.isnan(y)) or np.any(np.abs(y) > 1e10):
            return {'success': False, 'steps': steps, 'time': time.time() - start_time, 'reason': 'Instability'}
        if steps > 100000:
            return {'success': False, 'steps': steps, 'time': time.time() - start_time, 'reason': 'Max Steps'}
    return {'success': True, 'steps': steps, 'time': time.time() - start_time}

def benchmark_solvers():
    benchmarks = []
    
    # 1. Long range [0, 1e5] - Implicit Solvers
    t_long = (0, 1e5)
    for name, method in [('BDF', 'BDF'), ('Radau', 'Radau')]:
        start = time.time()
        sol = solve_ivp(robertson, t_long, y0, method=method, jac=robertson_jac, rtol=1e-6, atol=1e-9)
        benchmarks.append({
            'Solver': name,
            'Range': '0-1e5',
            'Success': sol.success,
            'Time (s)': time.time() - start,
            'NFEV': sol.nfev,
            'NJEV': getattr(sol, 'njev', 0),
            'Steps': len(sol.t)
        })
        
    # 2. Medium range [0, 1e2] - Adaptive Explicit (DP5)
    t_med = (0, 1e2)
    start = time.time()
    sol_dp5 = solve_ivp(robertson, t_med, y0, method='RK45', rtol=1e-6, atol=1e-9)
    benchmarks.append({
        'Solver': 'DP5 (RK45)',
        'Range': '0-1e2',
        'Success': sol_dp5.success,
        'Time (s)': time.time() - start,
        'NFEV': sol_dp5.nfev,
        'NJEV': 0,
        'Steps': len(sol_dp5.t)
    })
    
    # 3. Short range [0, 0.1] - Fixed Step Explicit
    t_short = (0, 0.1)
    # Trying various h for Euler
    for h in [1e-3, 1e-5]:
        res = euler_fixed(robertson, t_short, y0, h)
        benchmarks.append({
            'Solver': f'Euler (h={h})',
            'Range': '0-0.1',
            'Success': res.get('success', False),
            'Time (s)': res['time'],
            'NFEV': res['steps'],
            'NJEV': 0,
            'Steps': res['steps']
        })
        
    return pd.DataFrame(benchmarks)

df_bench = benchmark_solvers()
print(df_bench)
df_bench.to_csv('/workspace/output/robertson_benchmarks.csv', index=False)

# Visualizing Stiffness
# We'll plot the step sizes for BDF vs RK45 (DP5) to show why implicit is better
sol_bdf = solve_ivp(robertson, (0, 1e5), y0, method='BDF', jac=robertson_jac)
sol_dp5 = solve_ivp(robertson, (0, 1e2), y0, method='RK45')

plt.figure(figsize=(10, 5))
plt.subplot(1, 2, 1)
plt.loglog(sol_bdf.t[:-1], np.diff(sol_bdf.t), label='BDF Step Size')
plt.xlabel('Time')
plt.ylabel('Step Size')
plt.title('BDF Adaptive Steps (Stiff)')
plt.legend()

plt.subplot(1, 2, 2)
plt.loglog(sol_dp5.t[:-1], np.diff(sol_dp5.t), label='DP5 Step Size', color='orange')
plt.xlabel('Time')
plt.ylabel('Step Size')
plt.title('DP5 Adaptive Steps (Stiff)')
plt.legend()
plt.tight_layout()
plt.savefig('/workspace/output/robertson_step_sizes.png')
