import pandas as pd

# Check VDP explicit benchmark
try:
    vdp_exp = pd.read_csv('vdp_explicit_benchmark.csv')
    print("VDP Explicit Benchmark:\n", vdp_exp.head())
except:
    pass

# Check VDP implicit benchmark
try:
    vdp_imp = pd.read_csv('vdp_implicit_benchmark_results.csv')
    print("\nVDP Implicit Benchmark:\n", vdp_imp.head())
except:
    pass
