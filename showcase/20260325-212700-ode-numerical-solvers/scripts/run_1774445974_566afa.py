import pandas as pd
df = pd.read_csv("/workspace/output/implicit_benchmark.csv")
# Show summary for mu=1000
summary = df[df['mu'] == 1000].groupby(['method']).agg({
    'nfev': 'mean',
    'time': 'mean',
    'mean_err': 'mean'
}).reset_index()
print("Summary for mu=1000:")
print(summary)

# Compare efficiency (error/nfev)
df['efficiency'] = df['mean_err'] * df['nfev']
print("\nEfficiency comparison (low is better):")
print(df.groupby(['method', 'mu'])['efficiency'].mean().unstack())
