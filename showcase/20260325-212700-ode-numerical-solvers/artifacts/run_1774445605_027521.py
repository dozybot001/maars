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

# Initial conditions and time span
y0 = [1.0, 0.0, 0.0]
t_span = (0, 1e4) # Benchmark range

# 1. Euler Method (Fixed Step)
def euler_fixed(fun, t_span, y0, h):
    t_start, t_end = t_span
    t = t_start
    y = np.array(y0)
    ts = [t]
    ys = [y.copy()]
    n_steps = 0
    start_time = time.time()
    while t < t_end:
        y += h * np.array(fun(t, y))
        t += h
        n_steps += 1
        if np.any(np.isnan(y)) or np.any(np.isinf(y)) or n_steps > 1e6: # Timeout/Stability check
            break
    end_time = time.time()
    return {
        'method': 'Euler',
        'success': t >= t_end,
        'time': end_time - start_time,
        'nfev': n_steps,
        't_final': t,
        'y_final': y
    }

# 2. RK4 Method (Fixed Step)
def rk4_fixed(fun, t_span, y0, h):
    t_start, t_end = t_span
    t = t_start
    y = np.array(y0)
    n_steps = 0
    start_time = time.time()
    while t < t_end:
        k1 = np.array(fun(t, y))
        k2 = np.array(fun(t + h/2, y + h/2 * k1))
        k3 = np.array(fun(t + h/2, y + h/2 * k2))
        k4 = np.array(fun(t + h, y + h * k3))
        y += (h/6) * (k1 + 2*k2 + 2*k3 + k4)
        t += h
        n_steps += 1
        if np.any(np.isnan(y)) or np.any(np.isinf(y)) or n_steps > 1e6:
            break
    end_time = time.time()
    return {
        'method': 'RK4',
        'success': t >= t_end,
        'time': end_time - start_time,
        'nfev': n_steps * 4,
        't_final': t,
        'y_final': y
    }

results = []

# Benchmarking Implicit Solvers (Full range)
methods_ivp = [
    ('BDF', 'BDF'),
    ('Radau', 'Radau'),
    ('DP5', 'RK45')
]

for name, method in methods_ivp:
    start = time.time()
    sol = solve_ivp(robertson, t_span, y0, method=method, jac=robertson_jac, rtol=1e-4, atol=1e-7)
    duration = time.time() - start
    results.append({
        'Method': name,
        'Success': sol.success,
        'CPU Time (s)': duration,
        'Steps': len(sol.t),
        'Function Evals': sol.nfev,
        'Jac Evals': getattr(sol, 'njev', 0),
        'Final Y': sol.y[:, -1]
    })

# Benchmarking Explicit Solvers
# Euler and RK4 are very likely to fail on [0, 1e4] unless h is tiny.
# I will try a step size that is "reasonable" for a non-stiff problem and show failure.
h_test = 1e-4 # Even this might be too large for stability at some point
euler_res = euler_fixed(robertson, t_span, y0, h_test)
results.append({
    'Method': 'Euler (h=1e-4)',
    'Success': euler_res['success'],
    'CPU Time (s)': euler_res['time'],
    'Steps': euler_res['nfev'],
    'Function Evals': euler_res['nfev'],
    'Jac Evals': 0,
    'Final Y': euler_res['y_final']
})

rk4_res = rk4_fixed(robertson, t_span, y0, h_test)
results.append({
    'Method': 'RK4 (h=1e-4)',
    'Success': rk4_res['success'],
    'CPU Time (s)': rk4_res['time'],
    'Steps': rk4_res['nfev'] // 4,
    'Function Evals': rk4_res['nfev'],
    'Jac Evals': 0,
    'Final Y': rk4_res['y_final']
})

# Display Results
df = pd.DataFrame(results)
print(df[['Method', 'Success', 'CPU Time (s)', 'Function Evals', 'Jac Evals']])

# Plotting the solution for BDF to verify
sol_bdf = solve_ivp(robertson, (0, 1e4), y0, method='BDF', jac=robertson_jac)
plt.figure(figsize=(10, 6))
plt.semilogx(sol_bdf.t + 1e-6, sol_bdf.y[0], label='y1 (A)')
plt.semilogx(sol_bdf.t + 1e-6, sol_bdf.y[1]*1e4, label='y2 (B) x 1e4')
plt.semilogx(sol_bdf.t + 1e-6, sol_bdf.y[2], label='y3 (C)')
plt.xlabel('Time (log scale)')
plt.ylabel('Concentration')
plt.title('Robertson Problem Solution (BDF)')
plt.legend()
plt.grid(True)
plt.savefig('/workspace/output/robertson_solution.png')

# Detailed Stability analysis for RK4/Euler
# Try to find a stable step size or demonstrate oscillation
def check_stability():
    h_stable = 1e-6
    res = rk4_fixed(robertson, (0, 0.1), y0, h_stable)
    print(f"\nRK4 on [0, 0.1] with h={h_stable}: Success={res['success']}, Final Y2={res['y_final'][1]}")

check_stability()
