import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp
import matplotlib.pyplot as plt
import os

def vdp_standard(t, y, mu):
    """Standard Van der Pol equations."""
    return [y[1], mu * (1 - y[0]**2) * y[1] - y[0]]

def vdp_lienard(t, y, mu):
    """Liénard form of Van der Pol equations, better for large mu."""
    # y[0] = x, y[1] = z
    # dx/dt = mu * (x - x^3/3 - z)
    # dz/dt = x / mu
    return [mu * (y[0] - y[0]**3 / 3.0 - y[1]), y[0] / mu]

def generate_vdp_reference(mu, t_end, num_points=2000):
    # Initial conditions in standard form: y1=2, y2=0
    # In Liénard form: x=2, z = 2 - 8/3 = -2/3
    
    if mu < 10: # Use standard form for small mu to avoid 1/mu issues
        y0 = [2.0, 0.0]
        fun = lambda t, y: vdp_standard(t, y, mu)
        t_span = (0, t_end)
        t_eval = np.linspace(0, t_end, num_points)
        
        sol = solve_ivp(fun, t_span, y0, method='Radau', t_eval=t_eval, 
                        atol=1e-13, rtol=1e-13)
        
        # Convert to standard format [t, x, dx/dt]
        df = pd.DataFrame({
            't': sol.t,
            'x': sol.y[0],
            'dx_dt': sol.y[1]
        })
    else: # Use Liénard form for large mu
        x0 = 2.0
        z0 = x0 - x0**3 / 3.0 # This makes dx/dt = 0 at t=0
        y0 = [x0, z0]
        fun = lambda t, y: vdp_lienard(t, y, mu)
        t_span = (0, t_end)
        t_eval = np.linspace(0, t_end, num_points)
        
        sol = solve_ivp(fun, t_span, y0, method='Radau', t_eval=t_eval, 
                        atol=1e-13, rtol=1e-13)
        
        # Convert back to standard [x, dx/dt]
        # dx/dt = mu * (x - x^3/3 - z)
        x = sol.y[0]
        z = sol.y[1]
        dx_dt = mu * (x - x**3 / 3.0 - z)
        
        df = pd.DataFrame({
            't': sol.t,
            'x': x,
            'dx_dt': dx_dt
        })
        
    return df

# Define mu values
mu_values = [0, 1, 10, 100, 1000, 10000, 100000, 1000000]

# Estimate T_end
# For mu=0, T=2*pi. For large mu, T ~ 1.614 * mu.
# We take 2 periods.
results = {}
os.makedirs('/workspace/output/vdp_refs', exist_ok=True)

for mu in mu_values:
    if mu == 0:
        t_end = 20.0
    elif mu < 10:
        t_end = 20.0 + 2.0 * mu
    else:
        # Period ~ (3 - 2*ln(2)) * mu
        t_end = 2.0 * (3.0 - 2.0 * np.log(2.0)) * mu + 10.0
    
    print(f"Generating reference for mu={mu}, t_end={t_end:.2f}...")
    df = generate_vdp_reference(mu, t_end)
    filename = f"/workspace/output/vdp_refs/vdp_ref_mu_{mu}.csv"
    df.to_csv(filename, index=False)
    results[mu] = filename

# Plotting a subset for verification
plt.figure(figsize=(12, 8))
for i, mu in enumerate([1, 100, 10000]):
    df = pd.read_csv(results[mu])
    plt.subplot(2, 2, i+1)
    plt.plot(df['x'], df['dx_dt'])
    plt.title(f'Phase Portrait (mu={mu})')
    plt.xlabel('x')
    plt.ylabel('dx/dt')
    plt.grid(True)

plt.subplot(2, 2, 4)
for mu in [1, 100, 10000]:
    df = pd.read_csv(results[mu])
    # Normalize time for visualization
    plt.plot(df['t'] / df['t'].max(), df['x'], label=f'mu={mu}')
plt.title('Time Series (Normalized t)')
plt.legend()
plt.grid(True)

plt.tight_layout()
plt.savefig('/workspace/output/vdp_references_plot.png')
print("Plots saved to /workspace/output/vdp_references_plot.png")
