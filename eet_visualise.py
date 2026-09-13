import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.rcParams.update({
    "font.size": 9,
    "axes.grid": True,
    "grid.alpha": 0.3,
})

BASE = os.path.dirname(os.path.abspath(__file__))
varsf = os.path.join(BASE, "arsenal_2025_26_eet_vars.csv")
predf = os.path.join(BASE, "arsenal_2025_26_predictions.csv")
out_png = os.path.join(BASE, "arsenal_2025_26_plots.png")

df = pd.read_csv(varsf)
pred = pd.read_csv(predf)
m = pred.merge(df, on=["date", "comp", "opp"], sort=False)
m["x"] = np.arange(len(m))
if "edge" in m.columns and "EDGE" not in m.columns:
    m["EDGE"] = m["edge"]

fig, axes = plt.subplots(3, 2, figsize=(12, 13))

ax = axes[0, 0]
ax.plot(m["x"], m["ES"], label="ES (momentum)", color="#d62728", lw=1.4)
ax.plot(m["x"], m["EO"], label="EO (raw emotion)", color="#1f77b4", lw=1.4, alpha=0.9)
ax.axhline(0, color="black", lw=0.6)
ax.set_title("Emotional trajectory over the season")
ax.set_xlabel("match index (chronological)")
ax.legend(loc="best")

ax = axes[0, 1]
ax.plot(m["x"], m["RP"], label="RP (pride pressure)", color="#2ca02c", lw=1.4)
ax.plot(m["x"], m["TS"], label="TS (tension stock)", color="#ff7f0e", lw=1.4)
ax.axhline(0, color="black", lw=0.6)
ax.set_title("Pressure accumulators (RP, TS)")
ax.legend(loc="best")

ax = axes[1, 0]
wins = m[m["result"] == "win"]
nw = m[m["result"] != "win"]
ax.scatter(wins["x"], wins["EDGE"], color="#2ca02c", s=28, alpha=0.75, label="win")
ax.scatter(nw["x"], nw["EDGE"], color="#d62728", s=28, alpha=0.9, label="draw/loss")
ax.axhline(0, color="black", lw=0.6)
ax.set_title("EDGE by match outcome")
ax.legend(loc="best")

ax = axes[1, 1]
ax.scatter(m["win_p"], m["y"], color="#1f77b4", s=30, alpha=0.7)
ax.plot([0.2, 0.9], [0.2, 0.9], "--", color="gray", lw=1)
ax.set_xlim(0.2, 0.9)
ax.set_ylim(-0.05, 1.05)
ax.set_title("Predicted win probability vs binary outcome")
ax.set_xlabel("predicted win_p")

# calibration curve
ax = axes[2, 0]
bins = np.quantile(m["win_p"], np.linspace(0, 1, 7))
bins = np.unique(np.concatenate([bins, np.linspace(0.3, 0.8, 7)]))
idx = np.digitize(m["win_p"], bins).clip(1, len(bins) - 1)
xc, yc = [], []
for b in np.unique(idx):
    sel = idx == b
    xc.append(m.loc[sel, "win_p"].mean())
    yc.append(m.loc[sel, "y"].mean())
ax.plot(xc, yc, "o-", color="#8c564b", lw=1.5, label="observed")
ax.plot([0, 1], [0, 1], "--", color="gray", lw=1, label="perfect")
ax.set_xlim(0.3, 0.8)
ax.set_ylim(0.0, 1.0)
ax.set_title("Calibration curve")
ax.legend(loc="best")

ax = axes[2, 1]
grp = m.groupby(np.floor(m["EO"] / 5) * 5)["y"].agg(["mean", "count"])
ax.bar(grp.index.astype(str), grp["mean"], color="#9d9552", alpha=0.8)
ax.set_title("Observed win rate by EO bucket")
ax.set_xlabel("EO bucket (lower edge)")
ax.tick_params(axis="x", rotation=45)

fig.suptitle("Arsenal 2025/26 - EET V2.3 visualisation", fontsize=12)
fig.tight_layout(rect=[0, 0, 1, 0.97])
fig.savefig(out_png, dpi=150)
print("wrote", out_png)