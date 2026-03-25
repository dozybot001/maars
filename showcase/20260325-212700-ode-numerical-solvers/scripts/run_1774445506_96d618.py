import pandas as pd
for name in ["harmonic", "lorenz", "vdp", "robertson"]:
    df = pd.read_csv(f"/workspace/output/{name}_ground_truth.csv")
    print(f"\n--- {name} sample ---")
    print(df.head(3))
    print(f"Total points: {len(df)}")
    # Print the last value of first coordinate to see precision
    print(f"Last y0 (full string): {df.iloc[-1]['y0']}")
