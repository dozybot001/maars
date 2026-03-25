import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp
import os

def vdp_lienard(t, y, mu):
    return [mu * (y[0] - y[0]**3 / 3.0 - y[1]), y[0] / mu]

def vdp_lienard_jac(t, y, mu):
    return [[mu * (1 - y[0]**2), -mu], [1.0 / mu, 0]]

mu = 1000000
t_end = 2.0 * (3.0 - 2.0 * np.log(2.0)) * mu
x0, z0 = 2.0, 2/3.0
y0 = [x0, z0]

print("Trying Radau for 10^6 with 1e-8 tolerance...")
sol = solve_ivp(vdp_lienard, (0, t_end), y0, method='Radau', 
                jac=lambda t, y: vdp_lienard_jac(t, y, mu),
                atol=1e-8, rtol=1e-8)
print(f"Status: {sol.status}, steps: {len(sol.t)}")

if sol.status == 0:
    print("Success at 1e-8!")
else:
    print("Trying LSODA...")
    sol = solve_ivp(vdp_lienard, (0, t_end), y0, method='LSODA', 
                    atol=1e-8, rtol=1e-8)
    print(f"LSODA Status: {sol.status}, steps: {len(sol.t)}")
