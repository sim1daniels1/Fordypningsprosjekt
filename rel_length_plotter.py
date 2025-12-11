import csv
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, MaxNLocator
import pandas as pd

csv_path = "finaltest_12floors_new_boxing_yellow.csv"

# --- Settings ---
FPS = 30.25        # frames per second
TRIM_START_S = 0  # must match pressure plot for alignment
OUTFILE = "finaltest_12floors_new_yellow_length.csv"   # <-- trimmed CSV output


# === Load original CSV ===
df = pd.read_csv(csv_path)

frames = df["Frame"].to_numpy()
heights_px = df["Height_yellow_px"].to_numpy()

# Time in seconds
times_s = frames / FPS

# --- Determine which rows to keep ---
mask = times_s >= TRIM_START_S

# Apply trim to the DataFrame (NO extra columns added)
df_trimmed = df[mask].reset_index(drop=True)

# === Save trimmed CSV with ORIGINAL formatting ===
df_trimmed.to_csv(OUTFILE, index=False)
print(f"Trimmed CSV saved to: {OUTFILE}")

# === Plot (using trimmed data only) ===
t_trim = times_s[mask] - TRIM_START_S
h_trim = heights_px[mask]

# Define L0 from trimmed data
L0 = h_trim[0]
rel_plot = 100 * (h_trim - L0) / L0

fig, ax = plt.subplots(figsize=(14, 6))
ax.plot(t_trim, rel_plot, label="Relative length change (%)")
ax.set_title("Relative Object Length Change Over Time (trimmed)")
ax.set_xlabel("Time [s]")
ax.set_ylabel("Relative Length Change (%)")
ax.grid(True)

def pct_fmt(x, pos):
    if abs(x) < 0.0005:
        x = 0
    return f"{x:.0f}%"

ax.yaxis.set_major_formatter(FuncFormatter(pct_fmt))
ax.yaxis.set_major_locator(MaxNLocator(6))

plt.tight_layout()
plt.show()
