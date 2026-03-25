import numpy as np
import scipy
import decimal

print(f"Numpy version: {np.__version__}")
print(f"Scipy version: {scipy.__version__}")
print(f"Longdouble precision: {np.finfo(np.longdouble)}")

# Check if we can use decimal for RK4
from decimal import Decimal, getcontext
getcontext().prec = 40
a = Decimal(1) / Decimal(3)
print(f"Decimal(1/3): {a}")
