import numpy as np
import pandas as pd
import time
import matplotlib.pyplot as plt
from scipy.integrate import solve_ivp

# Robertson Model Equations
def robertson(t, y):
    y1, y2, y3 = y
    dy1 = -0.04 * y1 + 1e4 * y2 * y3
    dy2 = 0.04 * y1 - 1e4 * y2 * y3 - 3e7 * y2**2
    dy3 = 3e7 * y2**2
    return [dy1, dy2, dy3]

def jac_robertson(t, y):
    y1, y2, y3 = y
    jac = np.zeros((3, 3))
    jac[0, 0] = -0.04
    jac[0, 1] = 1e4 * y3
    jac[0, 2] = 1e4 * y2
    
    jac[1, 0] = 0.04
    jac[1, 1] = -1e4 * y3 - 6e7 * y2
    jac[1, 2] = -1e4 * y2
    
    jac[2, 1] = 6e7 * y2
    return jac

y0 = [1.0, 0.0, 0.0]
t_span_full = (0, 1e11)
t_eval_log = np.logspace(-6, 11, 100)

# Solvers to benchmark
# Note: RK45 will likely struggle even with much smaller t_span.
# We will limit its execution time or use a smaller t_span for the explicit solver comparison.

solvers = ['RK45', 'Radau', 'BDF', 'LSODA']
results = []

print("Starting benchmarks...")

for solver in solvers:
    # For RK45, we use a much smaller time span because it will fail/stall on the full span.
    # Even t=10 is hard for RK45 if the stiffness sets in early.
    # Actually, for Robertson, stiffness is present almost immediately.
    
    current_t_span = t_span_full
    if solver == 'RK45':
        current_t_span = (0, 10) # Even 10 might be too much for RK45
        
    start_time = time.time()
    try:
        # Use jac for implicit solvers if possible
        if solver in ['Radau', 'BDF', 'LSODA']:
            sol = solve_ivp(robertson, current_t_span, y0, method=solver, jac=jac_robertson, rtol=1e-6, atol=1e-10)
        else:
            # For RK45, set a timeout-like behavior or just a small span.
            # We'll try to run it for a very short time and see nfev.
            sol = solve_ivp(robertson, current_t_span, y0, method=solver, rtol=1e-6, atol=1e-10)
            
        end_time = time.time()
        
        results.append({
            'Solver': solver,
            'Success': sol.success,
            'Time (s)': end_time - start_time,
            'nfev': sol.nfev,
            'njev': getattr(sol, 'njev', 0),
            'nlu': getattr(sol, 'nlu', 0),
            'Status': sol.message,
            't_final': sol.t[-1],
            'Steps': len(sol.t)
        })
        
        # Save trajectory for plotting (Radau as reference for full span)
        if solver == 'Radau':
            df_traj = pd.DataFrame({'t': sol.t, 'y1': sol.y[0], 'y2': sol.y[1], 'y3': sol.y[2]})
            df_traj.to_csv('/workspace/output/robertson_trajectory_radau.csv', index=False)
            
        # Step size analysis for RK45 vs Radau on a small interval
        if solver in ['RK45', 'Radau'] and current_t_span[1] >= 1.0:
            # We want to see step size distribution
            dt = np.diff(sol.t)
            t_mid = sol.t[:-1]
            df_steps = pd.DataFrame({'t': t_mid, 'dt': dt})
            df_steps.to_csv(f'/workspace/output/robertson_steps_{solver}.csv', index=False)

    except Exception as e:
        results.append({
            'Solver': solver,
            'Success': False,
            'Error': str(e)
        })

df_results = pd.DataFrame(results)
df_results.to_csv('/workspace/output/robertson_benchmarks.csv', index=False)
print(df_results)

# Plotting the solution (using Radau results)
sol_radau = solve_ivp(robertson, t_span_full, y0, method='Radau', jac=jac_robertson, rtol=1e-6, atol=1e-10, t_eval=t_eval_log)

plt.figure(figsize=(10, 6))
plt.semilogx(sol_radau.t, sol_radau.y[0], label='y1 (A)')
plt.semilogx(sol_radau.t, sol_radau.y[1] * 1e4, label='y2 (B) x 10^4')
plt.semilogx(sol_radau.t, sol_radau.y[2], label='y3 (C)')
plt.xlabel('Time (log scale)')
plt.ylabel('Concentration')
plt.title('Robertson Chemical Kinetics Model (Radau Solver)')
plt.legend()
plt.grid(True, which="both", ls="-")
plt.savefig('/workspace/output/robertson_solution.png')

# Comparison of step sizes
plt.figure(figsize=(10, 6))
for solver in ['RK45', 'Radau']:
    try:
        steps_df = pd.read_csv(f'/workspace/output/robertson_steps_{solver}.csv')
        plt.loglog(steps_df['t'], steps_df['dt'], label=solver)
    except:
        pass
plt.xlabel('Time t')
plt.ylabel('Step size dt')
plt.title('Step Size Comparison (Stiffness Impact)')
plt.legend()
plt.grid(True, which="both", ls="-")
plt.savefig('/workspace/output/robertson_step_size_collapse.png')
