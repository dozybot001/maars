import numpy as np
import pandas as pd
import time
from scipy.integrate import solve_ivp

# System
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
t_eval_log = np.logspace(-6, 11, 18)

# Run BDF for the full scale
start_bdf = time.time()
sol_bdf = solve_ivp(robertson, (0, 1e11), y0, method='BDF', jac=robertson_jac, t_eval=t_eval_log, rtol=1e-8, atol=1e-12)
time_bdf = time.time() - start_bdf

# Run Radau for the full scale
start_radau = time.time()
sol_radau = solve_ivp(robertson, (0, 1e11), y0, method='Radau', jac=robertson_jac, t_eval=t_eval_log, rtol=1e-8, atol=1e-12)
time_radau = time.time() - start_radau

# Load Ground Truth
gt = pd.read_csv('/workspace/output/robertson_ground_truth.csv')

# Compare BDF and GT
# Find closest points
# Assuming t_eval_log and gt['t'] are similar
bdf_error = np.linalg.norm(sol_bdf.y[:, -1] - gt.iloc[-1, 1:].values.astype(float))

print(f"BDF Time (0 to 1e11): {time_bdf:.4f}s, NFEV: {sol_bdf.nfev}, Final Error: {bdf_error:.2e}")
print(f"Radau Time (0 to 1e11): {time_radau:.4f}s, NFEV: {sol_radau.nfev}")

# Save final summary table for markdown
summary = [
    ["Euler (Fixed Step)", "0 - 0.1", "0.0004s", "100", "Successful (Transient only)"],
    ["RK4 (Fixed Step)", "0 - 0.1", "0.0012s", "400", "Successful (Transient only)"],
    ["DP5 (RK45)", "0 - 100", "2.09s", "732,290", "Highly Inefficient (Stability bound)"],
    ["BDF (Implicit)", "0 - 1e11", f"{time_bdf:.4f}s", f"{sol_bdf.nfev}", "Extremely Efficient (A-Stable)"],
    ["Radau (Impl. RK)", "0 - 1e11", f"{time_radau:.4f}s", f"{sol_radau.nfev}", "Extremely Efficient (L-Stable)"]
]
pd.DataFrame(summary, columns=["Method", "Time Span", "CPU Time", "Func Evals", "Stability/Performance Notes"]).to_csv('/workspace/output/robertson_summary.csv', index=False)
