import pandas as pd
import os

# Check the vdp_refs directory and a sample file
base_path = "/workspace/output"
# 1_4_1_1 said /workspace/output/vdp_refs/
path = os.path.join(base_path, "vdp_refs")
if os.path.exists(path):
    print(f"Directory {path} exists.")
    files = os.listdir(path)
    print(f"Files: {files}")
    sample = pd.read_csv(os.path.join(path, "vdp_ref_mu_100.csv"))
    print(sample.head())
else:
    print(f"Directory {path} does NOT exist. Checking {base_path}")
    files = os.listdir(base_path)
    print(f"Files in {base_path}: {files}")
    # Maybe vdp_ground_truth.csv is the one?
    if "vdp_ground_truth.csv" in files:
        sample = pd.read_csv(os.path.join(base_path, "vdp_ground_truth.csv"))
        print("vdp_ground_truth.csv head:")
        print(sample.head())
