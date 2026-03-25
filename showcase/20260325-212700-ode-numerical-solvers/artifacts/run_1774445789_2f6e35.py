import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp
import os

def vdp_lienard(t, y, mu):
    return [mu * (y[0] - y[0]**3 / 3.0 - y[1]), y[0] / mu]

def vdp_lienard_jac(t, y, mu):
    return [[mu * (1 - y[0]**2), -mu],
            [1.0 / mu, 0]]

mu = 1000000
t_end = 2.2 * (3.0 - 2.0 * np.log(2.0)) * mu + 10.0
x0 = 2.0
z0 = x0 - x0**3 / 3.0
y0 = [x0, z0]
t_span = (0, t_end)

print(f"Testing BDF for mu={mu}...")
sol = solve_ivp(vdp_lienard, t_span, y0, method='BDF', 
                jac=lambda t, y: vdp_lienard_jac(t, y, mu),
                args=(mu,), atol=1e-10, rtol=1e-10)
print(f"BDF Status: {sol.status}, nfev: {sol.nfev}")

if sol.status != 0:
    print("Trying Radau with 1e-9...")
    sol = solve_ivp(vdp_lienard, t_span, y0, method='Radau', 
                    jac=lambda t, y: vdp_lienard_jac(t, y, mu),
                    args=(mu,), atol=1e-9, rtol=1e-9)
    print(f"Radau 1e-9 Status: {sol.status}, nfev: {sol.nfev}")
