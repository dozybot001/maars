import pandas as pd
df = pd.read_csv('benchmark_results_task2.csv')

# 统计每个系统的最佳效率（在给定精度下 NFE 最少的）
print("--- Harmonic Oscillator Summary ---")
print(df[df['system'] == 'Harmonic'].sort_values('rmse').head(10))

print("\n--- Lorenz System Summary ---")
print(df[df['system'] == 'Lorenz'].sort_values('rmse').head(10))

# 比较 RK45 和 DOP853 在高精度下的表现
print("\n--- High Precision Comparison (Tol=1e-10) ---")
print(df[df['tol'] == 1e-10])
