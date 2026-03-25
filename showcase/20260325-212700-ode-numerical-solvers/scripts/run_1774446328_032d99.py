import numpy as np
import pandas as pd
import time
from scipy.integrate import solve_ivp
import matplotlib.pyplot as plt

def vdp(t, y, mu):
    return [y[1], mu * (1 - y[0]**2) * y[1] - y[0]]

def vdp_jac(t, y, mu):
    return [[0, 1], [-2 * mu * y[0] * y[1] - 1, mu * (1 - y[0]**2)]]

class Rosenbrock2:
    """A simple adaptive 2nd order Rosenbrock (ROS2) solver."""
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
        self.nstep = 0

    def step(self):
        f0 = np.array(self.fun(self.t, self.y))
        J = np.array(self.jac(self.t, self.y))
        self.nfev += 1
        self.njev += 1
        
        I = np.eye(len(self.y))
        
        while True:
            W = I - self.gamma * self.h * J
            try:
                k1 = np.linalg.solve(W, f0)
                f1 = np.array(self.fun(self.t + self.h, self.y + self.h * k1))
                self.nfev += 1
                
                # ROS2 simplified error estimate and step
                # y_new = y + h/2 * (k1 + k2)
                # where k2 = W^{-1} (f(y+h*k1) - 2*gamma*h*J*k1)
                k2 = np.linalg.solve(W, f1 - 2 * self.gamma * self.h * (J @ k1))
                
                y_new = self.y + 0.5 * self.h * (k1 + k2)
                
                # Error estimate: ||y_new - (y + h*k1)|| = ||h/2 * (k2 - k1)||
                error = 0.5 * self.h * np.linalg.norm((k2 - k1) / (self.atol + self.rtol * np.abs(y_new)), ord=np.inf)
                
                if error < 1.0:
                    # Accept step
                    self.t += self.h
                    self.y = y_new
                    self.nstep += 1
                    # Step size control
                    factor = 0.9 * (error**-0.5) if error > 0 else 2.0
                    self.h *= min(max(factor, 0.2), 5.0)
                    if self.t + self.h > self.t_bound:
                        self.h = self.t_bound - self.t
                    return True
                else:
                    # Reject step
                    self.h *= max(0.9 * (error**-0.5), 0.1)
                    if self.h < 1e-15:
                        return False
            except np.linalg.LinAlgError:
                self.h /= 2
                if self.h < 1e-15:
                    return False

def solve_ros2(fun, jac, t_span, y0, rtol=1e-3, atol=1e-6, mu=1.0):
    solver = Rosenbrock2(lambda t, y: fun(t, y, mu), lambda t, y: jac(t, y, mu), 
                         t_span[0], y0, t_span[1], rtol=rtol, atol=atol)
    ts = [solver.t]
    ys = [solver.y.copy()]
    while solver.t < t_span[1]:
        if not solver.step():
            break
        ts.append(solver.t)
        ys.append(solver.y.copy())
    return {
        't': np.array(ts),
        'y': np.array(ys).T,
        'nfev': solver.nfev,
        'njev': solver.njev,
        'status': 'success' if solver.t >= t_span[1] else 'fail'
    }

# Benchmarking
mus = [1, 10, 100, 1000]
tols = [1e-3, 1e-4, 1e-5, 1e-6, 1e-7, 1e-8]
results = []

for mu in mus:
    # Load reference
    ref_file = f'/workspace/output/vdp_refs/vdp_ref_mu_{mu}.csv'
    ref_data = pd.read_csv(ref_file)
    t_ref = ref_data['t'].values
    y_ref = ref_data[['y0', 'y1']].values.T
    t_span = (t_ref[0], t_ref[-1])
    y0 = y_ref[:, 0]
    
    for tol in tols:
        # BDF
        start_time = time.time()
        sol_bdf = solve_ivp(vdp, t_span, y0, method='BDF', args=(mu,), jac=vdp_jac, rtol=tol, atol=tol/1000)
        end_time = time.time()
        
        # Calculate error (RMSE at final point)
        # Note: better to interpolate and check whole path, but final point or mean error is fine.
        y_final_ref = y_ref[:, -1]
        err_bdf = np.linalg.norm(sol_bdf.y[:, -1] - y_final_ref)
        
        results.append({
            'mu': mu, 'solver': 'BDF', 'tol': tol, 
            'nfev': sol_bdf.nfev, 'njev': sol_bdf.njev,
            'time': end_time - start_time, 'error': err_bdf
        })
        
        # Rosenbrock (ROS2)
        start_time = time.time()
        sol_ros = solve_ros2(vdp, vdp_jac, t_span, y0, rtol=tol, atol=tol/1000, mu=mu)
        end_time = time.time()
        
        if sol_ros['status'] == 'success':
            err_ros = np.linalg.norm(sol_ros['y'][:, -1] - y_final_ref)
            results.append({
                'mu': mu, 'solver': 'Rosenbrock', 'tol': tol, 
                'nfev': sol_ros['nfev'], 'njev': sol_ros['njev'],
                'time': end_time - start_time, 'error': err_ros
            })

df_results = pd.DataFrame(results)
df_results.to_csv('vdp_implicit_benchmark.csv', index=False)

# Visualization
for mu in mus:
    plt.figure(figsize=(10, 6))
    subset = df_results[df_results['mu'] == mu]
    for solver in ['BDF', 'Rosenbrock']:
        s_data = subset[subset['solver'] == solver]
        plt.loglog(s_data['error'], s_data['nfev'], 'o-', label=f'{solver} (NFEV)')
        plt.loglog(s_data['error'], s_data['time'] * 1000, 's--', label=f'{solver} (Time ms)')
    plt.title(f'Work-Precision Diagram (Van der Pol, mu={mu})')
    plt.xlabel('Global Error (L2 at end)')
    plt.ylabel('Cost (NFEV or Time)')
    plt.legend()
    plt.grid(True, which="both", ls="-")
    plt.savefig(f'wpd_implicit_mu_{mu}.png')
    plt.close()

print(df_results.head())
