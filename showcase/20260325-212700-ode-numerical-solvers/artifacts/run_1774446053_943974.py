import pandas as pd
import numpy as np

df = pd.read_csv('consolidated_benchmark.csv')

# Let's inspect mu=0.1
print("Mu=0.1 data:")
print(df[df['mu'] == 0.1].pivot(index='tol', columns='method', values=['nfev', 'time', 'error']))

# Re-run switching point logic with 'time' instead of 'nfev'
from scipy.interpolate import interp1d

mus = df['mu'].unique()
switching_points = []

for mu in mus:
    subset = df[df['mu'] == mu]
    # We compare DP5 and BDF
    dp5 = subset[subset['method'] == 'DP5'].sort_values('error')
    bdf = subset[subset['method'] == 'BDF'].sort_values('error')
    
    if len(dp5) < 2 or len(bdf) < 2:
        continue
    
    # log space for error and time
    log_err_dp5 = np.log10(dp5['error'].values)
    log_time_dp5 = np.log10(dp5['time'].values)
    log_err_bdf = np.log10(bdf['error'].values)
    log_time_bdf = np.log10(bdf['time'].values)
    
    f_dp5 = interp1d(log_err_dp5, log_time_dp5, bounds_error=False, fill_value="extrapolate")
    f_bdf = interp1d(log_err_bdf, log_time_bdf, bounds_error=False, fill_value="extrapolate")
    
    common_errors = np.linspace(min(log_err_dp5.min(), log_err_bdf.min()), 
                                max(log_err_dp5.max(), log_err_bdf.max()), 1000)
    diff = f_dp5(common_errors) - f_bdf(common_errors)
    
    idx = np.where(np.diff(np.sign(diff)))[0]
    
    if len(idx) > 0:
        log_err_switch = common_errors[idx[0]]
        time_switch = 10**f_dp5(log_err_switch)
        switching_points.append({
            'mu': mu,
            'switching_error': 10**log_err_switch,
            'switching_time': time_switch,
            'state': 'crossover'
        })
    else:
        # Which one is faster?
        if f_dp5(common_errors).mean() < f_bdf(common_errors).mean():
            switching_points.append({'mu': mu, 'state': 'Explicit faster'})
        else:
            switching_points.append({'mu': mu, 'state': 'Implicit faster'})

sw_df = pd.DataFrame(switching_points)
print("\nSwitching Points (based on Time):")
print(sw_df)
sw_df.to_csv('efficiency_switching_points_time.csv', index=False)
