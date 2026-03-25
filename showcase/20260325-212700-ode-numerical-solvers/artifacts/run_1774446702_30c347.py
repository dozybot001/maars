import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Load the consolidated data
df = pd.read_csv('final_comprehensive_benchmarks.csv')

# Normalize column names to lowercase for consistency
df.columns = [c.lower() for c in df.columns]

# Rename columns if necessary (e.g., 'error' to 'rmse')
if 'error' in df.columns and 'rmse' not in df.columns:
    df.rename(columns={'error': 'rmse'}, inplace=True)

# Generating Work-Precision Diagrams
fig, axes = plt.subplots(2, 2, figsize=(15, 12))
systems = df['system'].unique()
colors = {'RK45': 'blue', 'RK4': 'cyan', 'Euler': 'black', 'BDF': 'green', 'Radau': 'red', 'LSODA': 'orange'}
markers = {'RK45': 'o', 'RK4': 's', 'Euler': 'x', 'BDF': '^', 'Radau': 'v', 'LSODA': 'D'}

for i, system in enumerate(systems):
    ax = axes[i//2, i%2]
    subset = df[df['system'] == system]
    for solver in subset['solver'].unique():
        solver_data = subset[subset['solver'] == solver]
        # Sort by nfev to make lines
        solver_data = solver_data.sort_values('nfev')
        ax.plot(solver_data['nfev'], solver_data['rmse'], marker=markers.get(solver, 'o'), 
                label=solver, color=colors.get(solver, 'gray'), markersize=8)
    
    ax.set_xscale('log')
    ax.set_yscale('log')
    ax.set_title(f'WPD: {system}')
    ax.set_xlabel('Log(Cost) - NFEV')
    ax.set_ylabel('Log(Error) - RMSE')
    ax.legend()
    ax.grid(True, which="both", ls="-", alpha=0.5)

plt.tight_layout()
plt.savefig('synthesis_wpd_final.png')

# Output data for recommendation matrix analysis
print("Mean metrics by system and solver:")
summary = df.groupby(['system', 'solver'])[['nfev', 'rmse']].mean()
print(summary)
