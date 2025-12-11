import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# ===== Plot style =====
plt.rcParams.update({
    "font.size": 18,
    "axes.titlesize": 20,
    "axes.labelsize": 18
})

# Adjustable display names for legend
DISPLAY_NAMES = {
    "20x_test_aligned.csv": "20x",
    "finaltest_12floors_new_aligned.csv": "80deg-12floors",
    "test5_aligned.csv": "80deg-6floors",
}

# ============================================================
# Per-specimen parameters
# ============================================================
SPECIMENS = [
    # 20x: baseline ~100 kPa, peaks ~200 kPa
    ("20x_test_aligned.csv",
     {"low_thresh_p": 105.0, "amp_min_p": 30.0, "min_spacing_s": 1.5}),
    # 12 floors + 6 floors: baseline ~75 kPa, peaks up to 250 kPa
    ("finaltest_12floors_new_aligned.csv",
     {"low_thresh_p": 90.0, "amp_min_p": 20.0, "min_spacing_s": 1.5}),
    ("test5_aligned.csv",
     {"low_thresh_p": 90.0, "amp_min_p": 20.0, "min_spacing_s": 1.5}),
]

# ---- 20x densification settings ----
N_PRIMARY_20X = 10    # number of highest peaks to keep
N_EXTRA_20X   = 50    # additional samples
P_MIN_20X     = 125.0 # minimum interesting pressure
P_MAX_20X     = 200.0
P_TOL_20X     = 2.0   # ± tolerance for matching levels [kPa]


def get_cycle_starts(time, pressure, low_thresh_p, min_spacing_s):
    """Find cycle start indices based on pressure valleys."""
    t = np.asarray(time)
    p = np.asarray(pressure)

    below = p < low_thresh_p
    raw_starts = []
    in_low = below[0]
    for i in range(1, len(p)):
        if in_low and not below[i]:
            raw_starts.append(i)
        in_low = below[i]

    if not raw_starts:
        return np.array([], dtype=int)

    raw_starts = np.array(raw_starts, dtype=int)

    # enforce minimum spacing in time between starts
    starts = []
    last_t = -np.inf
    for idx in raw_starts:
        if t[idx] - last_t >= min_spacing_s:
            starts.append(idx)
            last_t = t[idx]

    return np.array(starts, dtype=int)


def find_cycle_peaks_pressure(
    time,
    pressure,
    compression,
    low_thresh_p=80.0,
    amp_min_p=20.0,
    min_spacing_s=1.5,
    p_tolerance=1.0,
):
    """
    One representative point per mechanical cycle based on PRESSURE valleys.
    (Used for the 80deg specimens and to get 20x primary peaks.)
    """
    t = np.asarray(time)
    p = np.asarray(pressure)
    c = np.asarray(compression)

    starts = get_cycle_starts(t, p, low_thresh_p, min_spacing_s)
    if len(starts) == 0:
        return np.array([], dtype=int)

    peak_idx = []

    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(p)

        seg_p = p[start:end]
        seg_c = c[start:end]
        if len(seg_p) == 0:
            continue

        p_min = seg_p.min()
        p_max = seg_p.max()

        if p_max - p_min < amp_min_p:
            continue

        near_peak = np.where(seg_p >= p_max - p_tolerance)[0]
        if len(near_peak) == 0:
            continue

        best_rel = near_peak[np.argmax(seg_c[near_peak])]
        peak_idx.append(start + best_rel)

    return np.array(peak_idx, dtype=int)


def densify_20x(
    time,
    pressure,
    compression,
    low_thresh_p,
    amp_min_p,
    min_spacing_s,
    n_primary=N_PRIMARY_20X,
    n_extra=N_EXTRA_20X,
    p_min=P_MIN_20X,
    p_max=P_MAX_20X,
    p_tol=P_TOL_20X,
):
    """
    For 20x:
      - get up to n_primary highest peaks (p >= p_min - p_tol)
      - add n_extra extra points sampled across [p_min, p_max]
        over all cycles (respecting ± p_tol).
    """
    t = np.asarray(time)
    p = np.asarray(pressure)
    c = np.asarray(compression)

    # --- 1) primary peaks: one per cycle, then take top N by pressure ---
    cycle_peaks = find_cycle_peaks_pressure(
        t, p, c,
        low_thresh_p=low_thresh_p,
        amp_min_p=amp_min_p,
        min_spacing_s=min_spacing_s,
        p_tolerance=1.0,
    )

    if len(cycle_peaks) == 0:
        return np.array([], dtype=int)

    # filter to p >= p_min - p_tol
    cycle_peaks = np.array(
        [idx for idx in cycle_peaks if p[idx] >= p_min - p_tol],
        dtype=int
    )
    if len(cycle_peaks) == 0:
        return np.array([], dtype=int)

    # sort by pressure descending and keep up to n_primary
    cycle_peaks_sorted = cycle_peaks[np.argsort(p[cycle_peaks])[::-1]]
    primary_idx = cycle_peaks_sorted[:n_primary]

    # --- 2) extra samples across levels in [p_min, p_max] ---
    starts = get_cycle_starts(t, p, low_thresh_p, min_spacing_s)
    if len(starts) == 0:
        return primary_idx

    # choose levels so that total potential points ~ n_extra
    levels_per_cycle = max(1, n_extra // max(1, len(starts)))
    P_levels = np.linspace(p_min, p_max, levels_per_cycle)

    extra_candidates = []

    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(p)
        seg_p = p[start:end]

        if len(seg_p) == 0:
            continue

        for P_target in P_levels:
            # nearest index in this cycle
            rel_idx = np.argmin(np.abs(seg_p - P_target))
            if np.abs(seg_p[rel_idx] - P_target) <= p_tol:
                extra_candidates.append(start + rel_idx)

    extra_candidates = np.array(list(set(extra_candidates)), dtype=int)  # unique

    # remove ones already in primary
    extra_candidates = np.array(
        [idx for idx in extra_candidates if idx not in primary_idx],
        dtype=int
    )

    if len(extra_candidates) == 0:
        return primary_idx

    # if too many, pick n_extra of them spread evenly in compression
    if len(extra_candidates) > n_extra:
        c_extra = c[extra_candidates]
        order = np.argsort(c_extra)
        extra_sorted = extra_candidates[order]
        # choose n_extra roughly evenly spaced
        positions = np.linspace(0, len(extra_sorted) - 1, n_extra).round().astype(int)
        extra_idx = extra_sorted[positions]
    else:
        extra_idx = extra_candidates

    # combine primary + extra
    all_idx = np.concatenate([primary_idx, extra_idx])
    # ensure unique
    all_idx = np.array(sorted(set(all_idx)), dtype=int)

    return all_idx


# ============================================================
# Build global compression–pressure plot (clean style)
# ============================================================
plt.figure(figsize=(10, 6))

for csv_path, params in SPECIMENS:
    display_name = DISPLAY_NAMES.get(csv_path, csv_path)
    print(f"\n=== Processing {csv_path} ({display_name}) ===")

    df = pd.read_csv(csv_path)

    t = df["time_s"].to_numpy()
    p = df["pressure_kPa"].to_numpy()
    c = df["compression_pct"].to_numpy()

    if "20x" in csv_path:
        idx_use = densify_20x(
            t, p, c,
            low_thresh_p=params["low_thresh_p"],
            amp_min_p=params["amp_min_p"],
            min_spacing_s=params["min_spacing_s"],
        )
    else:
        idx_use = find_cycle_peaks_pressure(
            t, p, c,
            low_thresh_p=params["low_thresh_p"],
            amp_min_p=params["amp_min_p"],
            min_spacing_s=params["min_spacing_s"],
            p_tolerance=1.0,
        )

    print(f"  using {len(idx_use)} points for {display_name}")

    if len(idx_use) == 0:
        print("  (no valid cycles/points found, skipping)")
        continue

    p_use = p[idx_use]
    c_use = c[idx_use]

    # Sort by compression for nicer ordering
    order = np.argsort(c_use)
    c_use = c_use[order]
    p_use = p_use[order]

    # --- scatter (raw data) ---
    plt.scatter(c_use, p_use, s=35, alpha=0.8, label=display_name)

    # --- linear trend line per specimen ---
    if len(c_use) >= 2:
        k, b = np.polyfit(c_use, p_use, 1)  # p ≈ k * c + b
        c_fit = np.linspace(c_use.min(), c_use.max(), 100)
        p_fit = k * c_fit + b
        plt.plot(c_fit, p_fit, linewidth=1.5)

plt.xlabel("Compression [%]")
plt.ylabel("Pressure [kPa]")
plt.title("Compression–Pressure Response")
plt.grid(alpha=0.3)
plt.tight_layout()
plt.legend()
plt.show()

# ============================================================
# Collect global data + slopes for stiffness calculation
# ============================================================

global_rows = []   # for export of all data points
slope_rows  = []   # for export of slopes / specimen info

for csv_path, params in SPECIMENS:
    display_name = DISPLAY_NAMES.get(csv_path, csv_path)

    df = pd.read_csv(csv_path)
    t = df["time_s"].to_numpy()
    p = df["pressure_kPa"].to_numpy()
    c = df["compression_pct"].to_numpy()

    # pick correct cycle-detection rule
    if "20x" in csv_path:
        idx_use = densify_20x(
            t, p, c,
            low_thresh_p=params["low_thresh_p"],
            amp_min_p=params["amp_min_p"],
            min_spacing_s=params["min_spacing_s"],
        )
    else:
        idx_use = find_cycle_peaks_pressure(
            t, p, c,
            low_thresh_p=params["low_thresh_p"],
            amp_min_p=params["amp_min_p"],
            min_spacing_s=params["min_spacing_s"],
            p_tolerance=1.0,
        )

    if len(idx_use) == 0:
        continue

    # Clean and sort
    p_use = p[idx_use]
    c_use = c[idx_use]
    order = np.argsort(c_use)
    c_use = c_use[order]
    p_use = p_use[order]

    # Store all points in export list
    for ci, pi in zip(c_use, p_use):
        global_rows.append({
            "specimen": display_name,
            "compression_pct": ci,
            "pressure_kPa": pi
        })

    # Fit line and store slope
    if len(c_use) >= 2:
        m, b = np.polyfit(c_use, p_use, 1)  # p ≈ m*c + b

        slope_rows.append({
            "specimen": display_name,
            "slope_kPa_per_pct": m,
            "intercept_kPa": b
        })

# Save combined compression–pressure data
df_export = pd.DataFrame(global_rows)
df_export.to_csv("kresling_pressure_compression_export.csv", index=False)
print("Exported: kresling_pressure_compression_export.csv")

# Save slopes for each specimen
df_slopes = pd.DataFrame(slope_rows)
df_slopes.to_csv("kresling_slopes.csv", index=False)
print("Exported: kresling_slopes.csv")
