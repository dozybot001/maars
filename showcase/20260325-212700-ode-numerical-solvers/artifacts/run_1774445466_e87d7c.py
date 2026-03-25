from mpmath import mp
import pandas as pd
import os

# Set precision to roughly 128-bit (approx 38-40 decimal digits)
mp.dps = 40

def solve_system(name, func, y0, t_list):
    print(f"Solving {name}...")
    y0_mp = [mp.mpf(str(val)) for val in y0]
    t_list_mp = [mp.mpf(str(val)) for val in t_list]
    
    # mpmath.odeint returns a generator or a function
    # Let's use it as a generator to collect results
    try:
        # Note: mpmath.odeint(f, y0, t_list) returns values at t_list[1:]
        # We prepend the initial condition
        sol_values = mp.odeint(func, y0_mp, t_list_mp)
        
        # mpmath.odeint(f, y0, [t0, t1, ...]) -> [y(t1), y(t2), ...]
        # Prepend initial condition
        all_sols = [y0_mp] + list(sol_values)
        
        data = []
        for i, t in enumerate(t_list):
            row = [str(t)] + [str(val) for val in all_sols[i]]
            data.append(row)
        
        columns = ['t'] + [f'y{j}' for j in range(len(y0))]
        df = pd.DataFrame(data, columns=columns)
        
        filename = f"/workspace/output/{name}_ground_truth.csv"
        df.to_csv(filename, index=False)
        print(f"Saved {name} to {filename} with {len(df)} points.")
        return filename
    except Exception as e:
        print(f"Error solving {name}: {e}")
        return None

# 1. Harmonic Oscillator
def harmonic_f(t, y):
    return [y[1], -y[0]]

t_harmonic = [x/10.0 for x in range(201)] # 0 to 20, step 0.1
y0_harmonic = [1.0, 0.0]

# 2. Lorenz System
def lorenz_f(t, y):
    sigma, rho, beta = 10.0, 28.0, 8.0/3.0
    x, y, z = y[0], y[1], y[2]
    dxdt = sigma * (y - x)
    dydt = x * (rho - z) - y
    dzdt = x * y - beta * z
    return [dxdt, dydt, dzdt]

t_lorenz = [x/100.0 for x in range(2001)] # Reduce to 20.0 to save time for this run, or try 50
y0_lorenz = [1.0, 1.0, 1.0]

# 3. Van der Pol (mu=1000) - Very stiff
def vdp_f(t, y):
    mu = 1000.0
    x1, x2 = y[0], y[1]
    dx1dt = x2
    dx2dt = mu * (1 - x1**2) * x2 - x1
    return [dx1dt, dx2dt]

# Use fewer points for VDP in high precision due to stiffness
t_vdp = [float(x) for x in range(0, 2001, 50)] # 0 to 2000, step 50
y0_vdp = [2.0, 0.0]

# 4. Robertson Problem - Extremely stiff
def robertson_f(t, y):
    y1, y2, y3 = y[0], y[1], y[2]
    dy1dt = -0.04 * y1 + 10000.0 * y2 * y3
    dy2dt = 0.04 * y1 - 10000.0 * y2 * y3 - 3e7 * y2**2
    dy3dt = 3e7 * y2**2
    return [dy1dt, dy2dt, dy3dt]

t_robertson = [0.0] + [10**x for x in range(-6, 12)] # log scale
y0_robertson = [1.0, 0.0, 0.0]

os.makedirs("/workspace/output", exist_ok=True)

solve_system("harmonic", harmonic_f, y0_harmonic, t_harmonic)
solve_system("lorenz", lorenz_f, y0_lorenz, t_lorenz)
solve_system("vdp", vdp_f, y0_vdp, t_vdp)
solve_system("robertson", robertson_f, y0_robertson, t_robertson)
