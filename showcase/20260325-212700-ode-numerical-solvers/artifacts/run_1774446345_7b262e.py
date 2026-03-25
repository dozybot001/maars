import numpy as np
import pandas as pd
import time
from scipy.integrate import solve_ivp
import matplotlib.pyplot as plt
import os

def vdp(t, y, mu):
    return [y[1], mu * (1 - y[0]**2) * y[1] - y[0]]

def vdp_jac(t, y, mu):
    return [[0, 1], [-2 * mu * y[0] * y[1] - 1, mu * (1 - y[0]**2)]]

class Rosenbrock2:
    def __init__(self, fun, jac, t0, y0, t_bound, rtol=1e-3, atol=1e-6, first_step=1e-4):
        self.fun = fun
        self.jac = jac
        self.t = t0
        self.y = np.array(y0, dtype=float)
        self.t_bound = t_bound
        self.rtol = rtol
        self.atol = atol
        self.h = first_step
        self.gamma = 1 - 1/np.sqrt(2)
        self.nfev = 0
        self.njev = 0

    def step(self):
        f0 = np.array(self.fun(self.t, self.y))
        J = np.array(self.jac(self.t, self.y))
        self.nfev += 1
        self.njev += 1
        I = np.eye(len(self.y))
        
        while True:
            if self.h < 1e-16: return False
            W = I - self.gamma * self.h * J
            try:
                k1 = np.linalg.solve(W, f0)
                f1 = np.array(self.fun(self.t + self.h, self.y + self.h * k1))
                self.nfev += 1
                
                # ROS2 step
                rhs2 = f1 - 2 * self.gamma * self.h * (J @ k1)
                k2 = np.linalg.solve(W, rhs2)
                
                y_new = self.y + 0.5 * self.h * (k1 + k2)
                
                # Error estimate
                # E = |y_new - (y + h*k1)| = |h/2 (k2 - k1)|
                error_vec = 0.5 * self.h * (k2 - k1)
                scale = self.atol + self.rtol * np.maximum(np.abs(self.y), np.abs(y_new))
                error = np.linalg.norm(error_vec / scale, ord=np.inf)
                
                if error <= 1.0:
                    self.t += self.h
                    self.y = y_new
                    # Update h
                    factor = 0.9 * (error**-0.5) if error > 0.001 else 2.0
                    self.h *= min(max(factor, 0.2), 5.0)
                    if self.t + self.h > self.t_bound:
                        self.h = self.t_bound - self.t
                    return True
                else:
                    self.h *= max(0.9 * (error**-0.5), 0.1)
            except np.linalg.LinAlgError:
                self.h /= 10

def solve_ros2(fun, jac, t_span, y0, rtol=1e-3, atol=1e-6, mu=1.0):
    solver = Rosenbrock2(lambda t, y: fun(t, y, mu), lambda t, y: jac(t, y, mu), 
                         t_span[0], y0, t_span[1], rtol=rtol, atol=atol)
    while solver.t < t_span[1]:
        if not solver.step(): break
    return {'y_final': solver.y, 'nfev': solver.nfev, 'njev': solver.njev, 'status': 'success' if solver.t >= t_span[1] else 'fail'}

mus = [1, 100, 10000]
tols = [1e-3, 1e-5, 1e-7] # Fewer tolerances to keep it fast but representative
results = []

for mu in mus:
    ref_file = f'/workspace/output/vdp_refs/vdp_ref_mu_{mu}.csv'
    if not os.path.exists(ref_file): continue
    ref_data = pd.read_csv(ref_file)
    y_final_ref = ref_data[['x', 'dx_dt']].values[-1]
    t_span = (ref_data['t'].iloc[0], ref_data['t'].iloc[-1])
    y0 = ref_data[['x', 'dx_dt']].values[0]
    
    for tol in tols:
        # BDF
        st = time.time()
        sol_bdf = solve_ivp(vdp, t_span, y0, method='BDF', args=(mu,), jac=vdp_jac, rtol=tol, atol=tol/100)
        et = time.time()
        err_bdf = np.linalg.norm(sol_bdf.y[:, -1] - y_final_ref)
        results.append({'mu': mu, 'solver': 'BDF', 'tol': tol, 'nfev': sol_bdf.nfev, 'time': et-st, 'error': err_bdf})
        
        # Rosenbrock
        st = time.time()
        sol_ros = solve_ros2(vdp, vdp_jac, t_span, y0, rtol=tol, atol=tol/100, mu=mu)
        et = time.time()
        if sol_ros['status'] == 'success':
            err_ros = np.linalg.norm(sol_ros['y_final'] - y_final_ref)
            results.append({'mu': mu, 'solver': 'Rosenbrock', 'tol': tol, 'nfev': sol_ros['nfev'], 'time': et-st, 'error': err_ros})

df = pd.DataFrame(results)
df.to_csv('vdp_implicit_benchmark_results.csv', index=False)

# Summary table for the report
summary = df.groupby(['mu', 'solver'])[['nfev', 'time', 'error']].mean().reset_index()
summary.to_csv('vdp_implicit_summary.csv', index=False)

# Plots
for mu in mus:
    subset = df[df['mu'] == mu]
    plt.figure()
    for s in ['BDF', 'Rosenbrock']:
        d = subset[subset['solver'] == s]
        plt.loglog(d['error'], d['nfev'], 'o-', label=f'{s} Cost')
    plt.title(f'VDP mu={mu} Benchmark')
    plt.xlabel('Error')
    plt.ylabel('NFEV')
    plt.legend()
    plt.grid(True)
    plt.savefig(f'benchmark_mu_{mu}.png')
