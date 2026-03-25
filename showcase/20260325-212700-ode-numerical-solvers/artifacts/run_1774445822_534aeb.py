import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp

def vdp_lienard(t, y, mu):
    return [mu * (y[0] - y[0]**3 / 3.0 - y[1]), y[0] / mu]

mu = 1000000
t_end = 2.0 * (3.0 - 2.0 * np.log(2.0)) * mu
y0 = [2.0, 2/3.0]

print("Trying Radau for 10^6 with 1e-8 tolerance...")
sol = solve_ivp(lambda t, y: vdp_lienard(t, y, mu), (0, t_end), y0, 
                method='Radau', atol=1e-8, rtol=1e-8)
print(f"Status: {sol.status}, steps: {len(sol.t)}")
if sol.status == 0:
    print(f"Last t: {sol.t[-1]}")
