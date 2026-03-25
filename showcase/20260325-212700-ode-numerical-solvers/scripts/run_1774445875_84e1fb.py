import pandas as pd
df = pd.read_csv('/workspace/output/vdp_refs/vdp_ref_mu_1000000.csv')
print(df.head())
print(df.tail())
print(df['x'].describe())
