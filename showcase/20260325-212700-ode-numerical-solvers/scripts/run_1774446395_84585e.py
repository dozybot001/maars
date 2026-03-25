import pandas as pd
if os.path.exists('robertson_summary.csv'):
    df_rob = pd.read_csv('robertson_summary.csv')
    print(df_rob)
else:
    print("robertson_summary.csv not found")
