import numpy as np
import pandas as pd
import time
from scipy.integrate import solve_ivp
import matplotlib.pyplot as plt
import os

def vdp(t, y, mu):
    return [y[1], mu * (1 - y[0]**2) * y[1] - y[0]]

def vdp_jac(t, y, mu):
    return [[0, 1],
            [-2 * mu * y[0] * y[1] - 1, mu * (1 - y[0]**2)]]

def get_reference(mu):
    # Load reference from the directory found in previous step
    path = f"/workspace/output/vdp_refs/vdp_ref_mu_{mu}.csv"
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    return df

def run_benchmark():
    mus = [1, 10, 100, 1000]
    tols = [1e-3, 1e-4, 1e-5, 1e-6, 1e-7]
    
    results = []
    
    for mu in mus:
        ref_df = get_reference(mu)
        if ref_df is None:
            print(f"Ref for mu={mu} not found.")
            continue
        
        t_span = (ref_df['t'].iloc[0], ref_df['t'].iloc[-1])
        y0 = [ref_df['x'].iloc[0], ref_df['dx_dt'].iloc[0]]
        t_eval = ref_df['t'].values
        ref_y = ref_df[['x', 'dx_dt']].values
        
        # Benchmark solve_ivp methods
        for method in ['BDF', 'Radau']:
            for tol in tols:
                start_time = time.time()
                sol = solve_ivp(vdp, t_span, y0, method=method, jac=vdp_jac,
                               args=(mu,), rtol=tol, atol=tol*1e-3, t_eval=t_eval)
                elapsed = time.time() - start_time
                
                if sol.success:
                    # Calculate Global Error (at the end point or RMS)
                    # Use relative error if possible, but absolute difference from reference is safer
                    err = np.linalg.norm(sol.y.T - ref_y, axis=1)
                    max_err = np.max(err)
                    mean_err = np.mean(err)
                    
                    results.append({
                        'mu': mu,
                        'method': method,
                        'tol': tol,
                        'nfev': sol.nfev,
                        'njev': sol.njev,
                        'nsteps': len(sol.t),
                        'time': elapsed,
                        'max_err': max_err,
                        'mean_err': mean_err
                    })

    # Manual Rosenbrock Implementation (ROS2 - simplified for benchmark)
    # Using fixed step sizes for simplicity in this implementation but capturing the cost
    # Actually, we can just do a very basic adaptive step for ROS2
    def solve_ros2(mu, t_span, y0, t_eval, tol):
        # ROS2 coefficients (L-stable)
        gamma = 1 - 1/np.sqrt(2)
        
        t = t_span[0]
        y = np.array(y0)
        h = 0.01 / (1 + np.log10(mu+1)) # Initial guess
        
        ts = [t]
        ys = [y]
        nfev = 0
        njev = 0
        
        # We'll use a very simple adaptive step size controller
        while t < t_span[1]:
            if t + h > t_span[1]:
                h = t_span[1] - t
            
            # Jacobian
            J = np.array(vdp_jac(t, y, mu))
            njev += 1
            W = np.eye(2) - gamma * h * J
            
            # Stage 1
            f0 = np.array(vdp(t, y, mu))
            nfev += 1
            k1 = np.linalg.solve(W, f0)
            
            # Stage 2
            f1 = np.array(vdp(t + 0.5*h, y + 0.5*h*k1, mu))
            nfev += 1
            # ROS2: (I - ghJ) k2 = f(y + 0.5hk1) - ghJ k1
            rhs2 = f1 - gamma * h * (J @ k1)
            k2 = np.linalg.solve(W, rhs2)
            
            y_new = y + h * k2
            
            # Error estimation (very crude for this mock)
            # Normally we'd use a pair, here we just check if it's too large
            # For the benchmark, let's use a fixed-step comparison at the required density
            y = y_new
            t += h
            ts.append(t)
            ys.append(y)
            
        # Interpolate to t_eval
        ys_arr = np.array(ys)
        ts_arr = np.array(ts)
        # Simple linear interpolation
        from scipy.interpolate import interp1d
        f_int = interp1d(ts_arr, ys_arr, axis=0, fill_value="extrapolate")
        y_interp = f_int(t_eval)
        return y_interp, nfev, njev

    # Add a representative Rosenbrock run
    for mu in mus:
        ref_df = get_reference(mu)
        t_eval = ref_df['t'].values
        ref_y = ref_df[['x', 'dx_dt']].values
        y0 = [ref_df['x'].iloc[0], ref_df['dx_dt'].iloc[0]]
        t_span = (t_eval[0], t_eval[-1])
        
        # Benchmark simple ROS2 (Fixed steps chosen to give comparable nfev)
        for steps in [1000, 5000, 20000]:
            h = (t_span[1] - t_span[0]) / steps
            start_time = time.time()
            # Simple ROS2 Fixed Step
            y = np.array(y0)
            t = t_span[0]
            nfev = 0
            njev = 0
            cur_ys = [y]
            cur_ts = [t]
            gamma = 1 - 1/np.sqrt(2)
            for _ in range(steps):
                J = np.array(vdp_jac(t, y, mu))
                njev += 1
                W = np.eye(2) - gamma * h * J
                f0 = np.array(vdp(t, y, mu))
                k1 = np.linalg.solve(W, f0)
                f1 = np.array(vdp(t + 0.5*h, y + 0.5*h*k1, mu))
                rhs2 = f1 - gamma * h * (J @ k1)
                k2 = np.linalg.solve(W, rhs2)
                y = y + h * k2
                t += h
                nfev += 2
                cur_ys.append(y)
                cur_ts.append(t)
            
            elapsed = time.time() - start_time
            from scipy.interpolate import interp1d
            f_int = interp1d(np.array(cur_ts), np.array(cur_ys), axis=0, fill_value="extrapolate")
            y_interp = f_int(t_eval)
            err = np.linalg.norm(y_interp - ref_y, axis=1)
            results.append({
                'mu': mu,
                'method': 'Rosenbrock (ROS2)',
                'tol': h, # Using h as 'tol' indicator
                'nfev': nfev,
                'njev': njev,
                'nsteps': steps,
                'time': elapsed,
                'max_err': np.max(err),
                'mean_err': np.mean(err)
            })

    df_results = pd.DataFrame(results)
    df_results.to_csv("/workspace/output/implicit_benchmark.csv", index=False)
    print("Benchmark complete. Results saved to implicit_benchmark.csv")
    
    # Plotting
    for mu in mus:
        plt.figure(figsize=(10, 6))
        mu_data = df_results[df_results['mu'] == mu]
        for method in mu_data['method'].unique():
            m_data = mu_data[mu_data['method'] == method]
            # Work-precision: error vs nfev
            plt.loglog(m_data['nfev'], m_data['mean_err'], 'o-', label=method)
        
        plt.title(f"Work-Precision Curve (Van der Pol, mu={mu})")
        plt.xlabel("Number of Function Evaluations (Nfev)")
        plt.ylabel("Mean Global Error")
        plt.legend()
        plt.grid(True, which="both", ls="-", alpha=0.5)
        plt.savefig(f"/workspace/output/work_precision_mu_{mu}.png")
        plt.close()

run_benchmark()
