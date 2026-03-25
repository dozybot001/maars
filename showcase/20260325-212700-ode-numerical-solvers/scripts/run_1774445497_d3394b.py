import numpy as np
import pandas as pd
import os

def rk4_step(f, t, y, h):
    k1 = h * f(t, y)
    k2 = h * f(t + h/2, y + k1/2)
    k3 = h * f(t + h/2, y + k2/2)
    k4 = h * f(t + h, y + k3)
    return y + (k1 + 2*k2 + 2*k3 + k4) / 6

def solve_explicit(name, f, y0, t_start, t_end, h, save_interval):
    print(f"Solving {name} with RK4 (h={h})...")
    y = np.array(y0, dtype=np.longdouble)
    t = np.longdouble(t_start)
    h = np.longdouble(h)
    results = [[float(t)] + [str(val) for val in y]]
    
    steps = int((t_end - t_start) / h)
    for i in range(1, steps + 1):
        y = rk4_step(f, t, y, h)
        t += h
        if i % save_interval == 0:
            results.append([float(t)] + [str(val) for val in y])
    
    df = pd.DataFrame(results, columns=['t'] + [f'y{j}' for j in range(len(y0))])
    filename = f"/workspace/output/{name}_ground_truth.csv"
    df.to_csv(filename, index=False)
    print(f"Saved {name} to {filename}")
    return df

# Stiff solver: Implicit Euler with Newton iteration
def implicit_euler_step(f, t, y, h, jac=None, tol=1e-30, max_iter=100):
    y_next = y.copy()
    h = np.longdouble(h)
    t_next = t + h
    for _ in range(max_iter):
        # g(y_next) = y_next - y - h * f(t_next, y_next) = 0
        res = y_next - y - h * f(t_next, y_next)
        if np.linalg.norm(res.astype(np.float64)) < float(tol):
            break
        
        # Approximate Jacobian if not provided
        if jac is None:
            J = np.zeros((len(y), len(y)), dtype=np.longdouble)
            eps = np.longdouble(1e-15)
            for j in range(len(y)):
                y_eps = y_next.copy()
                y_eps[j] += eps
                J[:, j] = (f(t_next, y_eps) - f(t_next, y_next)) / eps
        else:
            J = jac(t_next, y_next)
        
        # Newton step: y_next = y_next - (I - hJ)^-1 * res
        M = np.eye(len(y), dtype=np.longdouble) - h * J
        delta = np.linalg.solve(M.astype(np.float64), res.astype(np.float64)).astype(np.longdouble)
        y_next -= delta
    return y_next

def solve_stiff(name, f, y0, t_list, tol=1e-30):
    print(f"Solving {name} (Stiff) with Implicit Euler...")
    y = np.array(y0, dtype=np.longdouble)
    results = [[float(t_list[0])] + [str(val) for val in y]]
    
    for i in range(len(t_list)-1):
        t_start = t_list[i]
        t_end = t_list[i+1]
        # Use smaller internal steps for accuracy if interval is large
        # For simplicity in ground truth, we use the interval as step 
        # but for Robertson we need to be careful.
        # Let's use 100 internal steps between each requested t point.
        h_internal = (np.longdouble(t_end) - np.longdouble(t_start)) / 100
        curr_t = np.longdouble(t_start)
        for _ in range(100):
            y = implicit_euler_step(f, curr_t, y, h_internal, tol=tol)
            curr_t += h_internal
        results.append([float(t_end)] + [str(val) for val in y])
        if i % 5 == 0: print(f"Progress: {i}/{len(t_list)}")
            
    df = pd.DataFrame(results, columns=['t'] + [f'y{j}' for j in range(len(y0))])
    filename = f"/workspace/output/{name}_ground_truth.csv"
    df.to_csv(filename, index=False)
    print(f"Saved {name} to {filename}")
    return df

# 1. Harmonic
def harmonic_f(t, y):
    return np.array([y[1], -y[0]], dtype=np.longdouble)

# 2. Lorenz
def lorenz_f(t, y):
    sigma, rho, beta = 10.0, 28.0, 8.0/3.0
    x, y, z = y[0], y[1], y[2]
    return np.array([sigma*(y-x), x*(rho-z)-y, x*y-beta*z], dtype=np.longdouble)

# 3. Van der Pol
def vdp_f(t, y):
    mu = 1000.0
    x1, x2 = y[0], y[1]
    return np.array([x2, mu*(1-x1**2)*x2-x1], dtype=np.longdouble)

# 4. Robertson
def robertson_f(t, y):
    y1, y2, y3 = y[0], y[1], y[2]
    return np.array([-0.04*y1 + 1e4*y2*y3,
                     0.04*y1 - 1e4*y2*y3 - 3e7*y2**2,
                     3e7*y2**2], dtype=np.longdouble)

os.makedirs("/workspace/output", exist_ok=True)

# Run non-stiff
solve_explicit("harmonic", harmonic_f, [1.0, 0.0], 0, 20, 0.001, 100) # Save every 0.1
solve_explicit("lorenz", lorenz_f, [1.0, 1.0, 1.0], 0, 50, 0.0001, 100) # Save every 0.01

# Run stiff
t_vdp_list = np.linspace(0, 2000, 41)
solve_stiff("vdp", vdp_f, [2.0, 0.0], t_vdp_list)

t_robertson_list = [0] + [10**x for x in range(-6, 12)]
solve_stiff("robertson", robertson_f, [1.0, 0.0, 0.0], t_robertson_list)
