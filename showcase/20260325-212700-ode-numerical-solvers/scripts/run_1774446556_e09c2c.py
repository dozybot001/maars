import pandas as pd
import matplotlib.pyplot as plt

# Load data
rk45 = pd.read_csv('robertson_steps_RK45.csv')
radau = pd.read_csv('robertson_steps_Radau.csv')

print(f"RK45: max t = {rk45['t'].max()}, total steps = {len(rk45)}")
print(f"Radau: max t = {radau['t'].max()}, total steps = {len(radau)}")

# Plotting
plt.figure(figsize=(12, 6))

# Subplot 1: Step size vs Time (Log-Log)
plt.subplot(1, 2, 1)
plt.loglog(rk45['t'], rk45['dt'], label='RK45 (Explicit)', alpha=0.7)
plt.loglog(radau['t'], radau['dt'], label='Radau (Implicit)', alpha=0.7)
plt.xlabel('Time (t)')
plt.ylabel('Step size (dt)')
plt.title('Step Size Evolution (Log-Log)')
plt.legend()
plt.grid(True, which="both", ls="-", alpha=0.2)

# Subplot 2: Step size vs Step Index
plt.subplot(1, 2, 2)
plt.plot(rk45.index, rk45['dt'], label='RK45 (Explicit)', alpha=0.7)
plt.plot(radau.index, radau['dt'], label='Radau (Implicit)', alpha=0.7)
plt.xlabel('Step Index')
plt.ylabel('Step size (dt)')
plt.yscale('log')
plt.title('Step Size vs Step Index')
plt.legend()
plt.grid(True, which="both", ls="-", alpha=0.2)

plt.tight_layout()
plt.savefig('step_size_comparison_analysis.png')
plt.show()

# Calculate statistics
stats = {
    'Method': ['RK45', 'Radau'],
    'Min dt': [rk45['dt'].min(), radau['dt'].min()],
    'Max dt': [rk45['dt'].max(), radau['dt'].max()],
    'Avg dt': [rk45['dt'].mean(), radau['dt'].mean()],
    'Final t': [rk45['t'].iloc[-1], radau['t'].iloc[-1]]
}
print("\nStep Size Statistics:")
print(pd.DataFrame(stats))
