import pandas as pd
for name in ["harmonic", "lorenz", "vdp", "robertson"]:
    df = pd.read_csv(f"/workspace/output/{name}_ground_truth.csv")
    print(f"File: {name}_ground_truth.csv | Points: {len(df)}")
    print(f"Sample y0: {df['y0'].iloc[-1]}")
