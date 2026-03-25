import pandas as pd
import numpy as np
from scipy.interpolate import interp1d

df = pd.read_csv('consolidated_benchmark.csv')
mus = df['mu'].unique()
switching_points = []

for mu in mus:
    subset = df[df['mu'] == mu]
    dp5 = subset[subset['method'] == 'DP5'].sort_values('error')
    bdf = subset[subset['method'] == 'BDF'].sort_values('error')
    
    if len(dp5) < 2 or len(bdf) < 2:
        continue
    
    # We want to find error where nfev_dp5 = nfev_bdf
    # In log-log space
    log_err_dp5 = np.log10(dp5['error'].values)
    log_nfev_dp5 = np.log10(dp5['nfev'].values)
    
    log_err_bdf = np.log10(bdf['error'].values)
    log_nfev_bdf = np.log10(bdf['nfev'].values)
    
    # Create interpolation functions
    # Note: nfev is typically monotonic with error (inverse)
    f_dp5 = interp1d(log_err_dp5, log_nfev_dp5, bounds_error=False, fill_value="extrapolate")
    f_bdf = interp1d(log_err_bdf, log_nfev_bdf, bounds_error=False, fill_value="extrapolate")
    
    # Find intersection
    common_errors = np.linspace(min(log_err_dp5.min(), log_err_bdf.min()), 
                                max(log_err_dp5.max(), log_err_bdf.max()), 1000)
    diff = f_dp5(common_errors) - f_bdf(common_errors)
    
    # Find where diff crosses zero
    idx = np.where(np.diff(np.sign(diff)))[0]
    
    if len(idx) > 0:
        log_err_switch = common_errors[idx[0]]
        nfev_switch = 10**f_dp5(log_err_switch)
        switching_points.append({
            'mu': mu,
            'switching_error': 10**log_err_switch,
            'switching_nfev': nfev_switch
        })
    else:
        # Check if one is always better
        if f_dp5(common_errors).mean() < f_bdf(common_errors).mean():
            switching_points.append({'mu': mu, 'comment': 'Explicit always better in range'})
        else:
            switching_points.append({'mu': mu, 'comment': 'Implicit always better in range'})

sw_df = pd.DataFrame(switching_points)
print(sw_df)
sw_df.to_csv('efficiency_switching_points.csv', index=False)
