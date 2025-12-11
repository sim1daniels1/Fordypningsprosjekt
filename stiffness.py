import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# ============================================================
# USER INPUTS — fill these values for your specimens
# ============================================================

GEOM = {
    "20x": {
        "A":  np.pi * (695e-6)**2 ,    # m^2
        "L0": 3096e-6,    # m
        "h0": 3096e-6,    # m (usually same as L0)
        "P0_kPa": 100 # baseline pressure
    },
    "80deg-12floors": {
        "A":  np.pi * (2795e-6)**2 ,   # m^2
        "L0": 12500e-6,
        "h0": 12500e-6,
        "P0_kPa": 75
    },
    "80deg-6floors": {
        "A":  np.pi * (2795e-6)**2 ,
        "L0": 6650e-6,
        "h0": 6650e-6,
        "P0_kPa": 75
    }
}

# ============================================================
# Load exported data (from your global compression plot)
# ============================================================

df = pd.read_csv("kresling_pressure_compression_export.csv")

specimens = df["specimen"].unique()

results = []   # store stiffness values for LaTeX table

# ============================================================
# Function to compute stiffness from slope
# ============================================================

def compute_stiffness(c_pct, P_kPa, A, L0, h0, P0_kPa):
    # Linear fit: P = m*c + b
    m_kPa_per_pct, b = np.polyfit(c_pct, P_kPa, 1)

    # Convert slope to equivalent stiffness
    m_Pa_per_pct = m_kPa_per_pct * 1e3
    k_eq = A * m_Pa_per_pct * 100.0 / L0  # N/m

    # Gas stiffness
    P0_Pa = P0_kPa * 1e3
    k_gas = (P0_Pa * A) / h0

    # Structural stiffness
    k_K = k_eq - k_gas

    return m_kPa_per_pct, k_eq, k_gas, k_K


# ============================================================
# Compute stiffness per specimen
# ============================================================

for name in specimens:
    data = df[df["specimen"] == name]

    c = data["compression_pct"].to_numpy()
    P = data["pressure_kPa"].to_numpy()

    A  = GEOM[name]["A"]
    L0 = GEOM[name]["L0"]
    h0 = GEOM[name]["h0"]
    P0 = GEOM[name]["P0_kPa"]

    m, k_eq, k_gas, k_K = compute_stiffness(c, P, A, L0, h0, P0)

    results.append((name, m, k_eq, k_gas, k_K))

# ============================================================
# Print LaTeX-ready table rows
# ============================================================

print("\nLaTeX Table Rows:")
print("Specimen & $m$ [kPa/\\%] & $k_{eq}$ [N/m] & $k_{gas}$ [N/m] & $k_{K}$ [N/m] \\\\")
for name, m, k_eq, k_gas, k_K in results:
    print(f"{name} & {m:.3f} & {k_eq:.2e} & {k_gas:.2e} & {k_K:.2e} \\\\")

# ============================================================
# Stiffness Plot per specimen
# ============================================================

fig, ax = plt.subplots(figsize=(8, 5))

names = [r[0] for r in results]
kKs   = [r[4] for r in results]   # kresling stiffness

ax.bar(names, kKs, color=["#4C72B0", "#55A868", "#C44E52"])

ax.set_ylabel("Kresling stiffness $k_K$ [N/m]")
ax.set_title("Structural stiffness of Kresling specimens")
plt.grid(axis="y", alpha=0.3)
plt.tight_layout()
plt.show()
