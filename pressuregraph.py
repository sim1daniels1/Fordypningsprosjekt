import pandas as pd
import matplotlib.pyplot as plt

# --- adjust to your file name ---
df = pd.read_csv("20x_test_pressure.csv", names=["time_ms", "pressure_kPa"])

# Convert time to seconds (optional)
# Ensure the input columns are numeric (coerce non-numeric to NaN), then drop rows with missing values
df["time_ms"] = pd.to_numeric(df["time_ms"], errors="coerce")
df["pressure_kPa"] = pd.to_numeric(df["pressure_kPa"], errors="coerce")
df = df.dropna(subset=["time_ms", "pressure_kPa"])
df["time_s"] = df["time_ms"] / 1000.0


# --- Plot 2: Pressure vs time ---
plt.figure(figsize=(12,4))
plt.plot(df["time_s"], df["pressure_kPa"], lw=1.5)
plt.xlabel("Time [s]")
plt.ylabel("Pressure [kPa]")
plt.title("Pressure vs Time")
plt.grid(True)
plt.tight_layout()
plt.show()