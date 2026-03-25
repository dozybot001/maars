import numpy as np
import pandas as pd
from mpmath import mp
import os

# Set precision to roughly 128-bit (approx 38-40 decimal digits)
mp.dps = 40

def solve_system(name, func, y0, t_list):
    print(f"Solving {name}...")
    # mpmath.odeint uses a high-order Taylor series method
    # It returns a function handle or values depending on input
    # Here we use it to get values at specific points
    results = []
    
    # mpmath.odeint can be used as: f = odeint(lambda t, y: ..., y0, [t0, t1, ...])
    # However, for a sequence of points, we can call it once for the whole sequence
    # to maintain internal state efficiency if possible, 
    # but mpmath.odeint(f, y0, t_list) returns a list of values.
    
    # Ensure y0 is a list of mpf
    y0_mp = [mp.mpf(val) for val in y0]
    
    # Solve
    sol_list = mp.odeint(func, y0_mp, t_list)
    
    # Convert to standard floats for storage (but keeping high prec if needed)
    # Actually, we save as strings in CSV to preserve full precision for ground truth comparison
    # But for ease of use, we might also provide a float version.
    # Let's save as strings.
    
    data = []
    for i, t in enumerate(t_list):
        row = [str(t)] + [str(val) for val in sol_list[i]]
        data.append(row)
    
    columns = ['t'] + [f'y{j}' for j in range(len(y0))]
    df = pd.DataFrame(data, columns=columns)
    
    filename = f"/workspace/output/{name}_ground_truth.csv"
    df.to_csv(filename, index=False)
    print(f"Saved {name} to {filename}")
    return filename

# 1. Harmonic Oscillator
def harmonic_f(t, y):
    # dy/dt = v, dv/dt = -x
    return [y[1], -y[0]]

t_harmonic = [mp.mpf(x)/10 for x in range(201)] # 0 to 20, step 0.1
y0_harmonic = [1.0, 0.0]

# 2. Lorenz System
def lorenz_f(t, y):
    sigma, rho, beta = 10, 28, 8/3
    x, y, z = y[0], y[1], y[2]
    dxdt = sigma * (y - x)
    dydt = x * (rho - z) - y
    dzdt = x * y - beta * z
    return [dxdt, dydt, dzdt]

t_lorenz = [mp.mpf(x)/100 for x in range(5001)] # 0 to 50, step 0.01
y0_lorenz = [1.0, 1.0, 1.0]

# 3. Van der Pol (mu=1000)
def vdp_f(t, y):
    mu = 1000
    x1, x2 = y[0], y[1]
    dx1dt = x2
    dx2dt = mu * (1 - x1**2) * x2 - x1
    return [dx1dt, dx2dt]

# VDP with mu=1000 is slow with Taylor methods if steps are large.
# We take 2001 points from 0 to 2000.
t_vdp = [mp.mpf(x) for x in range(2001)]
y0_vdp = [2.0, 0.0]

# 4. Robertson Problem
def robertson_f(t, y):
    y1, y2, y3 = y[0], y[1], y[2]
    dy1dt = -0.04 * y1 + 1e4 * y2 * y3
    dy2dt = 0.04 * y1 - 1e4 * y2 * y3 - 3e7 * y2**2
    dy3dt = 3e7 * y2**2
    return [dy1dt, dy2dt, dy3dt]

# Logarithmic points for Robertson
# From 0 to 1e11.
t_robertson = [0] + [mp.power(10, x/2) for x in range(-12, 23)] # 10^-6 to 10^11, 2 pts per decade
t_robertson = sorted(list(set(t_robertson)))
y0_robertson = [1.0, 0.0, 0.0]

# Create output dir
os.makedirs("/workspace/output", exist_ok=True)

# Run solutions
# Note: VDP and Robertson might be very slow in high precision Taylor. 
# We'll monitor or adjust if needed.
solve_system("harmonic", harmonic_f, y0_harmonic, t_harmonic)
solve_system("lorenz", lorenz_f, y0_lorenz, t_lorenz)
# For VDP and Robertson, we limit time or points if it takes too long for the environment.
# But let's try.
solve_system("vdp", vdp_f, y0_vdp, t_vdp)
solve_system("robertson", robertson_f, y0_robertson, t_robertson)
