with open("/workspace/output/harmonic_ground_truth.csv", "r") as f:
    lines = f.readlines()
    print(lines[1]) # Check the first data line
