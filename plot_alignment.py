import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Make text bigger globally
plt.rcParams.update({
    "font.size": 18,
    "axes.titlesize": 20,
    "axes.labelsize": 18
})

# ============================================================
# SETTINGS – change here only
# ============================================================
PRESSURE_CSV = "test5_pressure.csv"          # timestamp_ms,pressure_kPa
LENGTH_CSV   = "test5_yellow_length.csv"     # Frame,Height_yellow_px
FPS          = 30.25

PRESSURE_PEAK_VALUE  = 124.61   # kPa  (first high peak)
HEIGHT_VALLEY_VALUE  = 1158     # px   (first contraction minimum)

TARGET_P0_KPA        = 75.0
P0_TOL_KPA           = 1.0
MIN_P0_SAMPLES       = 10

STAGE1_MAX_PRESSURE  = 150.0
MIN_PRESSURE_TOL     = 5.0
# ============================================================


# ---------- Load pressure ----------
df_p = pd.read_csv(PRESSURE_CSV)
df_p["timestamp_ms"] = pd.to_numeric(df_p["timestamp_ms"], errors="coerce")
df_p["pressure_kPa"] = pd.to_numeric(df_p["pressure_kPa"], errors="coerce")
df_p = df_p.dropna(subset=["timestamp_ms", "pressure_kPa"])
df_p["time_s"] = df_p["timestamp_ms"] / 1000.0

# ---------- Load deformation ----------
df_L = pd.read_csv(LENGTH_CSV)
df_L["Frame"] = pd.to_numeric(df_L["Frame"], errors="coerce")
df_L["Height_yellow_px"] = pd.to_numeric(df_L["Height_yellow_px"], errors="coerce")
df_L = df_L.dropna(subset=["Frame", "Height_yellow_px"])
df_L["time_s"] = df_L["Frame"] / FPS

# ============================================================
# 1) ALIGNMENT
# ============================================================

peak_idx = (df_p["pressure_kPa"] - PRESSURE_PEAK_VALUE).abs().idxmin()
t_peak   = df_p.loc[peak_idx, "time_s"]

valley_idx = (df_L["Height_yellow_px"] - HEIGHT_VALLEY_VALUE).abs().idxmin()
t_valley   = df_L.loc[valley_idx, "time_s"]

delta_t = t_valley - t_peak
df_L["time_aligned_s"] = df_L["time_s"] - delta_t

# ============================================================
# 2) Compute compression (%)
# ============================================================

df_p_sorted = df_p.sort_values("time_s")
df_L_sorted = df_L.sort_values("time_aligned_s")

merged = pd.merge_asof(
    df_L_sorted,
    df_p_sorted[["time_s", "pressure_kPa"]],
    left_on="time_aligned_s",
    right_on="time_s",
    direction="nearest"
)

# Stage 1 selection
over_stage = merged[merged["pressure_kPa"] > STAGE1_MAX_PRESSURE]
if not over_stage.empty:
    t_stage1_end = over_stage["time_aligned_s"].iloc[0]
else:
    t_stage1_end = merged["time_aligned_s"].max()

stage1 = merged[merged["time_aligned_s"] <= t_stage1_end]

candidates = stage1[
    stage1["pressure_kPa"].between(
        TARGET_P0_KPA - P0_TOL_KPA,
        TARGET_P0_KPA + P0_TOL_KPA
    )
]

if len(candidates) >= MIN_P0_SAMPLES:
    H0 = candidates["Height_yellow_px"].median()
else:
    p_min = stage1["pressure_kPa"].min()
    fallback = stage1[
        stage1["pressure_kPa"].between(p_min, p_min + MIN_PRESSURE_TOL)
    ]
    H0 = fallback["Height_yellow_px"].median()

df_L["compression_pct"] = (H0 - df_L["Height_yellow_px"]) / H0 * 100.0

# ============================================================
# 3) Crop to common window
# ============================================================
t_start = max(df_p["time_s"].min(), df_L["time_aligned_s"].min())
t_end   = min(df_p["time_s"].max(), df_L["time_aligned_s"].max())

df_p_crop = df_p[(df_p["time_s"] >= t_start) & (df_p["time_s"] <= t_end)]
df_L_crop = df_L[(df_L["time_aligned_s"] >= t_start) & (df_L["time_aligned_s"] <= t_end)]

# ============================================================
# 4️⃣ EXPORT ALIGNED CSV FOR GLOBAL PLOT
# ============================================================
aligned_df = pd.DataFrame({
    "time_s": df_L_crop["time_aligned_s"].values,
    "pressure_kPa": pd.merge_asof(
        df_L_crop.sort_values("time_aligned_s"),
        df_p_crop[["time_s", "pressure_kPa"]].sort_values("time_s"),
        left_on="time_aligned_s",
        right_on="time_s",
        direction="nearest"
    )["pressure_kPa"].values,
    "compression_pct": df_L_crop["compression_pct"].values
})

OUTFILE = PRESSURE_CSV.replace("_pressure.csv", "_aligned.csv")
aligned_df.to_csv(OUTFILE, index=False)
print(f"\nSaved aligned compression+pressure CSV → {OUTFILE}\n")

# ============================================================
# 5) PLOT 1 – Pressure vs time
# ============================================================
plt.figure(figsize=(12, 4))
plt.plot(df_p_crop["time_s"], df_p_crop["pressure_kPa"], lw=1.5, color="steelblue")
plt.xlabel("Time [s]")
plt.ylabel("Pressure [kPa]")
plt.title("Pressure vs Time")
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()

# ============================================================
# 6) PLOT 2 – Compression vs time
# ============================================================
plt.figure(figsize=(12, 4))
plt.plot(df_L_crop["time_aligned_s"], df_L_crop["compression_pct"],
         lw=1.5, color="darkorange")
plt.xlabel("Time [s]")
plt.ylabel("Compression [%]")
plt.title("Axial Compression vs Time")
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()
