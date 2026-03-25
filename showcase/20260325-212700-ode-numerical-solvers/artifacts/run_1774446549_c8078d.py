import pandas as pd

# Read a few lines to check the structure
try:
    rk45_steps = pd.read_csv('robertson_steps_RK45.csv')
    print("RK45 steps head:\n", rk45_steps.head())
    print("RK45 steps count:", len(rk45_steps))
except Exception as e:
    print("RK45 steps error:", e)

try:
    radau_steps = pd.read_csv('robertson_steps_Radau.csv')
    print("\nRadau steps head:\n", radau_steps.head())
    print("Radau steps count:", len(radau_steps))
except Exception as e:
    print("Radau steps error:", e)
