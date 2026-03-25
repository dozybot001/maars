import numpy as np
import time
from scipy.integrate import solve_ivp
import matplotlib.pyplot as plt
import pandas as pd

# 1. 系统定义
def harmonic_oscillator(t, y):
    q, p = y
    return [p, -q]

def lorenz_system(t, y, sigma=10, rho=28, beta=8/3):
    x, y, z = y
    return [sigma * (y - x), x * (rho - z) - y, x * y - beta * z]

# 2. 参考解生成
def get_harmonic_ref(t_eval, y0):
    # q(t) = q0*cos(t) + p0*sin(t)
    # p(t) = -q0*sin(t) + p0*cos(t)
    q0, p0 = y0
    q_ref = q0 * np.cos(t_eval) + p0 * np.sin(t_eval)
    p_ref = -q0 * np.sin(t_eval) + p0 * np.cos(t_eval)
    return np.vstack([q_ref, p_ref])

def get_lorenz_ref(t_span, y0, t_eval):
    # 使用 DOP853 和极高精度作为参考解
    sol = solve_ivp(lorenz_system, t_span, y0, method='DOP853', 
                     atol=1e-14, rtol=1e-14, t_eval=t_eval)
    return sol.y

# 3. 基准测试函数
def benchmark_solver(system_func, t_span, y0, method, t_eval, ref_y, tolerances):
    results = []
    for tol in tolerances:
        start_time = time.perf_counter()
        sol = solve_ivp(system_func, t_span, y0, method=method, 
                         atol=tol, rtol=tol, t_eval=t_eval)
        end_time = time.perf_counter()
        
        exec_time = end_time - start_time
        nfev = sol.nfev
        
        # 计算全局误差 (RMSE)
        # 如果解提前终止（如发散），则填充 NaN
        if sol.status == 0 and sol.y.shape == ref_y.shape:
            rmse = np.sqrt(np.mean((sol.y - ref_y)**2))
        else:
            rmse = np.nan
            
        results.append({
            'method': method,
            'tol': tol,
            'nfev': nfev,
            'exec_time': exec_time,
            'rmse': rmse,
            'status': sol.status
        })
    return results

# 4. 执行测试
# --- 谐振子 ---
t_span_ho = (0, 20)
y0_ho = [1.0, 0.0]
t_eval_ho = np.linspace(t_span_ho[0], t_span_ho[1], 1000)
ref_ho = get_harmonic_ref(t_eval_ho, y0_ho)

# --- 洛伦兹 ---
t_span_lorenz = (0, 25) # 混沌系统在 T=25 后的参考解可能因容限限制而失效
y0_lorenz = [1.0, 1.0, 1.0]
t_eval_lorenz = np.linspace(t_span_lorenz[0], t_span_lorenz[1], 2500)
ref_lorenz = get_lorenz_ref(t_span_lorenz, y0_lorenz, t_eval_lorenz)

methods = ['RK45', 'RK23', 'DOP853', 'LSODA']
tols = [1e-3, 1e-4, 1e-5, 1e-6, 1e-7, 1e-8, 1e-9, 1e-10]

all_results = []

print("Benchmarking Harmonic Oscillator...")
for m in methods:
    res = benchmark_solver(harmonic_oscillator, t_span_ho, y0_ho, m, t_eval_ho, ref_ho, tols)
    for r in res:
        r['system'] = 'Harmonic'
        all_results.append(r)

print("Benchmarking Lorenz System...")
for m in methods:
    res = benchmark_solver(lorenz_system, t_span_lorenz, y0_lorenz, m, t_eval_lorenz, ref_lorenz, tols)
    for r in res:
        r['system'] = 'Lorenz'
        all_results.append(r)

df = pd.DataFrame(all_results)
df.to_csv('benchmark_results_task2.csv', index=False)

# 5. 绘图 (Work-Precision Diagram)
def plot_wpd(df_sys, sys_name, filename):
    plt.figure(figsize=(10, 6))
    for method in df_sys['method'].unique():
        subset = df_sys[df_sys['method'] == method]
        plt.loglog(subset['nfev'], subset['rmse'], 'o-', label=method)
    
    plt.title(f'Work-Precision Diagram: {sys_name}')
    plt.xlabel('Number of Function Evaluations (NFE)')
    plt.ylabel('Global RMSE')
    plt.grid(True, which="both", ls="-", alpha=0.5)
    plt.legend()
    plt.savefig(filename)
    plt.close()

plot_wpd(df[df['system'] == 'Harmonic'], 'Harmonic Oscillator', 'wpd_harmonic.png')
plot_wpd(df[df['system'] == 'Lorenz'], 'Lorenz System', 'wpd_lorenz.png')

print("Benchmark complete. Results saved to benchmark_results_task2.csv and PNG files.")
