import pandas as pd

rk45_steps = pd.read_csv('/workspace/output/robertson_steps_RK45.csv')
radau_steps = pd.read_csv('/workspace/output/robertson_steps_Radau.csv')

print("RK45 first 5 steps:")
print(rk45_steps.head())
print("RK45 last 5 steps (up to t=10):")
print(rk45_steps.tail())

print("\nRadau first 5 steps:")
print(radau_steps.head())
print("Radau steps near t=10:")
print(radau_steps[radau_steps['t'] < 20].tail())

# Calculate average step size for RK45 at the end
avg_dt_rk45 = rk45_steps['dt'].tail(100).mean()
print(f"\nRK45 avg dt near t=10: {avg_dt_rk45}")

# Calculate Radau step size at t=10^11
print(f"Radau last dt: {radau_steps['dt'].iloc[-1]}")
