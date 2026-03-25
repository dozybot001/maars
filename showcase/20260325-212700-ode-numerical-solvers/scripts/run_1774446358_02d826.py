import pandas as pd
summary = pd.read_csv('vdp_implicit_summary.csv')
print(summary.to_markdown())
