import numpy as np
import pandas as pd
import os

def format_val(val):
    return "{:.35g}".format(val)

def rk4_step(f, t, y, h):
    k1 = h * f(t, y)
    k2 = h * f(t + h/2, y + k1/2)
    k3 = h * f(t + h/2, y + k2/2)
    k4 = h * f(t + h, y + k3)
    return y + (k1 + 2*k2 + 2*k3 + k4) / 6

def solve_explicit(name, f, y0, t_start, t_end, h, save_interval):
    y = np.array(y0, dtype=np.longdouble)
    t = np.longdouble(t_start)
    h = np.longdouble(h)
    results = [[float(t)] + [format_val(val) for val in y]]
    
    # We add 1 to ensure we reach the end
    steps = int(round((t_end - t_start) / float(h)))
    for i in range(1, steps + 1):
        y = rk4_step(f, t, y, h)
        t += h
        if i % save_interval == 0:
            results.append([float(t)] + [format_val(val) for val in y])
    
    df = pd.DataFrame(results, columns=['t'] + [f'y{j}' for j in range(len(y0))])
    df.to_csv(f"/workspace/output/{name}_ground_truth.csv", index=False)
    return len(df)

def implicit_euler_step(f, t, y, h, tol=1e-32):
    y_next = y.copy()
    h = np.longdouble(h)
    t_next = t + h
    for _ in range(100):
        res = y_next - y - h * f(t_next, y_next)
        if np.linalg.norm(res.astype(np.float64)) < float(tol): break
        J = np.zeros((len(y), len(y)), dtype=np.longdouble)
        eps = np.longdouble(1e-15)
        for j in range(len(y)):
            y_eps = y_next.copy()
            y_eps[j] += eps
            J[:, j] = (f(t_next, y_eps) - f(t_next, y_next)) / eps
        M = np.eye(len(y), dtype=np.longdouble) - h * J
        delta = np.linalg.solve(M.astype(np.float64), res.astype(np.float64)).astype(np.longdouble)
        y_next -= delta
    return y_next

def solve_stiff(name, f, y0, t_list):
    y = np.array(y0, dtype=np.longdouble)
    results = [[float(t_list[0])] + [format_val(val) for val in y]]
    for i in range(len(t_list)-1):
        t_start, t_end = t_list[i], t_list[i+1]
        n_steps = 200
        h = (np.longdouble(t_end) - np.longdouble(t_start)) / n_steps
        curr_t = np.longdouble(t_start)
        for _ in range(n_steps):
            y = implicit_euler_step(f, curr_t, y, h)
            curr_t += h
        results.append([float(t_end)] + [format_val(val) for val in y])
    df = pd.DataFrame(results, columns=['t'] + [f'y{j}' for j in range(len(y0))])
    df.to_csv(f"/workspace/output/{name}_ground_truth.csv", index=False)
    return len(df)

# Final run
def harmonic_f(t, y): return np.array([y[1], -y[0]], dtype=np.longdouble)
def lorenz_f(t, y):
    s, r, b = 10.0, 28.0, 8.0/3.0
    return np.array([s*(y[1]-y[0]), y[0]*(r-y[2])-y[1], y[0]*y[1]-b*y[2]], dtype=np.longdouble)
def vdp_f(t, y): return np.array([y[1], 1000.0*(1-y[0]**2)*y[1]-y[0]], dtype=np.longdouble)
def robertson_f(t, y):
    return np.array([-0.04*y[0] + 1e4*y[1]*y[2], 0.04*y[0] - 1e4*y[1]*y[2] - 3e7*y[1]**2, 3e7*y[1]**2], dtype=np.longdouble)

os.makedirs("/workspace/output", exist_ok=True)
p1 = solve_explicit("harmonic", harmonic_f, [1.0, 0.0], 0, 20, 0.001, 100)
p2 = solve_explicit("lorenz", lorenz_f, [1.0, 1.0, 1.0], 0, 50, 0.0001, 100)
p3 = solve_stiff("vdp", vdp_f, [2.0, 0.0], np.linspace(0, 2000, 41))
p4 = solve_stiff("robertson", robertson_f, [1.0, 0.0, 0.0], [0] + [10**x for x in range(-6, 12)])

print(f"Points: {p1}, {p2}, {p3}, {p4}")
