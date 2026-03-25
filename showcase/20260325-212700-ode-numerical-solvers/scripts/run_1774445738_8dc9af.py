import pandas as pd
df = pd.read_csv('/workspace/output/benchmark_results_1_3.csv')
print(df.to_markdown())
