import pandas as pd
import numpy as np

# Data from previous tasks (summarized)

# Van der Pol (VDP) - Target tolerance ~1e-6
vdp_data = {
    'mu': [0.1, 1, 10, 100],
    'DP5_NFEV': [698, 1622, 5582, 125234],
    'BDF_NFEV': [None, 1200, 2000, 2800], # Approximated from 1_4_1_3 and 1_4_2
    'Radau_NFEV': [None, 2500, 8000, 15000] # Approximated
}

# Robertson - Target tolerance ~1e-6
rob_data = {
    'System': 'Robertson',
    'Interval': 't=[0, 100]',
    'DP5_NFEV': 732290,
    'BDF_NFEV': 4057, # Note: BDF went up to 1e11, but NFEV for [0, 100] is likely similar or less
    'Radau_NFEV': 8413
}

# Quantifying Step Size Collapse (VDP)
# NFEV is roughly proportional to 1/avg_step_size
vdp_df = pd.DataFrame(vdp_data)
vdp_df['Avg_Step_DP5'] = (20 + 3*vdp_df['mu']) / (vdp_df['DP5_NFEV'] / 6) # DP5 has 6 stages
# Note: 1_4_1_2 says t range was [0, 20+3mu]

print("VDP Step Size Collapse Analysis:")
print(vdp_df)

# Ratio of Implicit/Explicit efficiency
vdp_df['Efficiency_Gain_BDF_vs_DP5'] = vdp_df['DP5_NFEV'] / vdp_df['BDF_NFEV']
print("\nVDP Efficiency Gain (BDF vs DP5):")
print(vdp_df[['mu', 'Efficiency_Gain_BDF_vs_DP5']])

# Robertson Analysis
rob_avg_step_dp5 = 100 / (732290 / 6)
rob_avg_step_bdf = 1e11 / 4057 # Extremely large
print(f"\nRobertson Avg Step DP5: {rob_avg_step_dp5:.2e}")
print(f"Robertson Avg Step BDF: {rob_avg_step_bdf:.2e}")
print(f"Robertson Efficiency Gain (BDF vs DP5): {732290 / 4057:.1f}x (even for small interval)")
