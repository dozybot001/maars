import pandas as pd
for name in ["harmonic", "lorenz", "vdp", "robertson"]:
    df = pd.read_csv(f"/workspace/output/{name}_ground_truth.csv")
    print(f"{name}: First t={df['t'].iloc[0]}, Last t={df['t'].iloc[-1]}, Points={len(df)}")
