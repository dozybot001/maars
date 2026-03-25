import numpy as np
from scipy.integrate import solve_ivp

def vdp_deriv(t, y, mu):
    return [y[1], mu * (1 - y[0]**2) * y[1] - y[0]]

def vdp_jac(t, y, mu):
    return [[0, 1],
            [-2 * mu * y[0] * y[1] - 1, mu * (1 - y[0]**2)]]

mu = 1e6
t_end = 1.614 * mu + 7.0
sol = solve_ivp(vdp_deriv, (0, t_end), [2.0, 0.0], method='Radau', jac=vdp_jac,
                args=(mu,), rtol=1e-9, atol=1e-11)
print(f"Success: {sol.success}")
print(f"Message: {sol.message}")
print(f"Number of points: {len(sol.t)}")
if sol.success:
    print(f"Last t: {sol.t[-1]}")
