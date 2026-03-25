import numpy as np
from scipy.integrate import solve_ivp

def get_jac(t, y):
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

sol = solve_ivp(lambda t, y: [-0.04*y[0] + 1e4*y[1]*y[2], 0.04*y[0] - 1e4*y[1]*y[2] - 3e7*y[1]**2, 3e7*y[1]**2], 
                [0, 1e11], [1, 0, 0], method='Radau', t_eval=[1e-4, 1, 100, 1e6])

for i in range(len(sol.t)):
    t = sol.t[i]
    y = sol.y[:, i]
    J = get_jac(t, y)
    evals = np.linalg.eigvals(J)
    evals_sorted = np.sort(np.abs(evals))
    print(f"t={t:.1e}, Absolute Eigenvalues: {evals_sorted}")
    # The smallest is essentially zero. The ratio of the two non-zero ones:
    ratio = evals_sorted[2] / evals_sorted[1]
    print(f"Stiffness Ratio (L2/L1): {ratio:.2e}")
