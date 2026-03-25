import pandas as pd
df = pd.read_csv('final_comprehensive_benchmarks.csv')
# Display summary of best and worst performance for each system
summary = df.groupby(['System', 'Solver']).agg({'error': 'min', 'nfev': 'min', 'time': 'min'}).reset_index()
print(summary)
