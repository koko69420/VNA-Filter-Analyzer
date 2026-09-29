"""
Hairpin Microstrip Bandpass Filter — Stage 1: Synthesis
========================================================
Target specs:
  Centre frequency  fc  = 868 MHz
  3 dB bandwidth    BW  = 10 MHz  (863–873 MHz)
  Filter order      N   = 5  (Chebyshev, 0.1 dB ripple)
  System impedance  Z0  = 50 Ω
  Substrate         FR4, h = 1.6 mm, εr = 4.4, tan δ = 0.020

Outputs (all saved to ./results/):
  stage1_s_params.png      — ideal S11 / S21 response
  stage1_group_delay.png   — group delay across band
  stage1_dimensions.txt    — every physical dimension you need for KiCad / openEMS
  stage1_network.s2p       — Touchstone file for import into Qucs-S
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")          # headless — no display required
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import skrf
from pathlib import Path

# ─────────────────────────────────────────────────────────
# 0.  OUTPUT DIRECTORY
# ─────────────────────────────────────────────────────────
OUT = Path("results")
OUT.mkdir(exist_ok=True)

# ─────────────────────────────────────────────────────────
# 1.  DESIGN PARAMETERS
# ─────────────────────────────────────────────────────────
fc   = 868e6          # centre frequency [Hz]
BW   = 10e6           # 3 dB bandwidth [Hz]
N    = 5              # filter order
Z0   = 50.0           # system impedance [Ω]
Ar   = 0.1            # passband ripple [dB]  — Chebyshev

# Substrate (FR4)
er   = 4.4            # relative permittivity
h    = 1.6e-3         # substrate height [m]
t    = 35e-6          # copper thickness [m] (1 oz)
tand = 0.020          # loss tangent

# Derived
FBW  = BW / fc        # fractional bandwidth
print(f"\n{'='*54}")
print(f"  Hairpin BPF — Stage 1 Synthesis")
print(f"{'='*54}")
print(f"  fc  = {fc/1e6:.1f} MHz")
print(f"  BW  = {BW/1e6:.1f} MHz   (FBW = {FBW*100:.4f} %)")
print(f"  N   = {N}")
print(f"  Z0  = {Z0} Ω")
print(f"  Ar  = {Ar} dB  (Chebyshev)")
print(f"{'='*54}")

# ─────────────────────────────────────────────────────────
# 2.  CHEBYSHEV LOWPASS PROTOTYPE  g-values
#     Classic closed-form recursion (Matthaei / Pozar)
# ─────────────────────────────────────────────────────────
def chebyshev_g(N, Ar):
    """
    Compute N+2 prototype element values g0..g_{N+1}
    for a Chebyshev LPF with passband ripple Ar [dB].
    """
    epsilon = np.sqrt(10 ** (Ar / 10) - 1)
    beta    = np.log(1 / np.tanh(Ar / (17.37)))   # = ln(coth(Ar_Np/2))
    gamma   = np.sinh(beta / (2 * N))

    g = np.zeros(N + 2)
    g[0] = 1.0
    g[1] = 2 * np.sin(np.pi / (2 * N)) / gamma

    for k in range(2, N + 1):
        num = 4 * np.sin((2*k - 1)*np.pi / (2*N)) * np.sin((2*k - 3)*np.pi / (2*N))
        den = gamma**2 + np.sin((k - 1)*np.pi / N)**2
        g[k] = num / (den * g[k - 1])

    # Last element
    if N % 2 == 0:
        g[N + 1] = (1 / np.tanh(beta / 4)) ** 2
    else:
        g[N + 1] = 1.0

    return g

g = chebyshev_g(N, Ar)
print(f"\n  Lowpass prototype g-values:")
for i, gi in enumerate(g):
    print(f"    g[{i}] = {gi:.6f}")

# ─────────────────────────────────────────────────────────
# 3.  COUPLING COEFFICIENTS  &  EXTERNAL Q
#     (Coupled-resonator BPF theory — Hong & Lancaster)
# ─────────────────────────────────────────────────────────
# Coupling matrix M (inter-resonator, N-1 values)
M = np.zeros(N - 1)
for i in range(N - 1):
    M[i] = FBW / np.sqrt(g[i + 1] * g[i + 2])

# External Q (input and output)
Qe_in  = g[0] * g[1]  / FBW
Qe_out = g[N] * g[N+1]/ FBW

print(f"\n  Coupling coefficients M[i,i+1]:")
for i, mi in enumerate(M):
    print(f"    M[{i+1},{i+2}] = {mi:.6f}")
print(f"\n  External Q:")
print(f"    Qe_in  = {Qe_in:.4f}")
print(f"    Qe_out = {Qe_out:.4f}")

# ─────────────────────────────────────────────────────────
# 4.  MICROSTRIP SYNTHESIS
#     Resonator line: 50 Ω, λ/2 at fc
#     Hammerstad & Jensen closed-form synthesis
# ─────────────────────────────────────────────────────────
c0 = 3e8  # speed of light

def microstrip_synthesis(Z0_target, er, h, t=35e-6):
    """
    Synthesise microstrip W for a given Z0.
    Returns (W, er_eff) using Hammerstad & Jensen.
    """
    A = (Z0_target / 60) * np.sqrt((er + 1) / 2) + ((er - 1) / (er + 1)) * (0.23 + 0.11 / er)
    B = 377 * np.pi / (2 * Z0_target * np.sqrt(er))

    W_h_A = 8 * np.exp(A) / (np.exp(2 * A) - 2)   # W/h for narrow strip
    W_h_B = 2 / np.pi * (B - 1 - np.log(2*B - 1) + (er - 1)/(2*er) * (np.log(B - 1) + 0.39 - 0.61/er))

    # Choose the correct regime
    if W_h_A < 2:
        W_h = W_h_A
    else:
        W_h = W_h_B

    W = W_h * h

    # Effective permittivity (Hammerstad & Jensen)
    F = 1 / np.sqrt(1 + 12 * h / W)
    er_eff = (er + 1) / 2 + ((er - 1) / 2) * F

    return W, er_eff

def microstrip_impedance(W, er, h):
    """
    Analyse microstrip: return (Z0, er_eff).
    """
    W_h = W / h
    er_eff = (er + 1)/2 + (er - 1)/2 / np.sqrt(1 + 12/W_h)
    if W_h <= 1:
        Z0 = (60 / np.sqrt(er_eff)) * np.log(8 / W_h + W_h / 4)
    else:
        Z0 = (120 * np.pi) / (np.sqrt(er_eff) * (W_h + 1.393 + 0.667 * np.log(W_h + 1.444)))
    return Z0, er_eff

# 50 Ω resonator line
W50, er_eff = microstrip_synthesis(Z0, er, h, t)
Z0_check, _ = microstrip_impedance(W50, er, h)

lambda_g = c0 / (fc * np.sqrt(er_eff))   # guided wavelength [m]
L_res    = lambda_g / 2                   # half-wave resonator length [m]
L_leg    = L_res / 2                      # each hairpin leg [m] (before bending)

print(f"\n  Microstrip (50 Ω resonator line):")
print(f"    W      = {W50*1e3:.4f} mm  (check Z0 = {Z0_check:.2f} Ω)")
print(f"    εr_eff = {er_eff:.4f}")
print(f"    λg     = {lambda_g*1e3:.3f} mm")
print(f"    L_res  = {L_res*1e3:.3f} mm  (full half-wave)")
print(f"    L_leg  = {L_leg*1e3:.3f} mm  (each hairpin arm)")

# ─────────────────────────────────────────────────────────
# 5.  RESONATOR SPACING FROM COUPLING COEFFICIENTS
#
#  In a hairpin filter, inter-resonator coupling is set by the
#  CENTRE-TO-CENTRE spacing d between adjacent resonators.
#  The coupling coefficient is:
#      M ≈ (Ze - Zo) / (Ze + Zo)
#  where Ze, Zo are the even/odd-mode impedances of the
#  parallel-coupled section (Hammerstad simplified model).
#
#  For small M (narrow BW), d is LARGE — resonators are
#  well-separated.  This is physically correct.
#
#  Feed coupling uses the tapped-line method (better for high Qe).
# ─────────────────────────────────────────────────────────

def coupled_mstrip_Ze_Zo(d, W, er, h):
    """Even/odd mode Z for coupled microstrip strips
    with centre-to-centre spacing d, strip width W."""
    s   = max(d - W, 1e-9)      # edge-to-edge gap
    s_h = s / h
    W_h = W / h
    # Single-strip quantities
    if W_h <= 1:
        er_s = (er+1)/2 + (er-1)/2*(1/np.sqrt(1+12/W_h) + 0.04*(1-W_h)**2)
        Z0_s = 60/np.sqrt(er_s)*np.log(8/W_h + W_h/4)
    else:
        er_s = (er+1)/2 + (er-1)/2/np.sqrt(1+12/W_h)
        Z0_s = 120*np.pi/(np.sqrt(er_s)*(W_h+1.393+0.667*np.log(W_h+1.444)))
    # Impedance split (Pozar coupled-line approximation)
    delta = Z0_s * 0.347 * np.exp(-2.455*s_h) * (1 + 0.5*np.exp(-0.55*W_h))
    Ze = Z0_s + delta
    Zo = Z0_s - delta
    return max(Ze, Z0_s), max(Zo, 1.0)

def spacing_from_M(M_target, Z0, er, h, W):
    """Find centre-to-centre spacing d [m] for coupling coeff M_target."""
    Ze_t = Z0 * np.sqrt((1+M_target)/(1-M_target))
    Zo_t = Z0 * np.sqrt((1-M_target)/(1+M_target))
    lo   = W + 0.005*h
    hi   = W + 50*h
    def res(d):
        Ze, Zo = coupled_mstrip_Ze_Zo(d, W, er, h)
        return (Ze-Zo)/(Ze+Zo) - M_target
    r_lo, r_hi = res(lo), res(hi)
    if r_lo * r_hi > 0:
        # M_target below model floor — scan and return closest
        ds   = np.linspace(lo, hi, 1000)
        rs   = np.array([res(d) for d in ds])
        return ds[np.argmin(np.abs(rs))], Ze_t, Zo_t
    for _ in range(80):
        mid = (lo+hi)/2
        if res(mid)*res(lo) < 0: hi = mid
        else: lo = mid
    return (lo+hi)/2, Ze_t, Zo_t

print(f"\n  Resonator spacings (centre-to-centre between hairpins):")
spacings = []
gaps     = []
for i, mi in enumerate(M):
    Ze_t = Z0 * np.sqrt((1+mi)/(1-mi))
    Zo_t = Z0 * np.sqrt((1-mi)/(1+mi))
    d, _, _ = spacing_from_M(mi, Z0, er, h, W50)
    s_edge  = d - W50
    spacings.append(d)
    gaps.append(s_edge)
    print(f"    Res {i+1}-{i+2} : M={mi:.5f}  Ze={Ze_t:.2f} Ω  Zo={Zo_t:.2f} Ω"
          f"  →  d={d*1e3:.3f} mm  s_edge={s_edge*1e3:.3f} mm")

# Tapped-line feed (preferred for high Qe)
# sin²(π * t / L_res) = π / (2 * Qe)
tap_arg = np.pi / (2 * Qe_in)
if tap_arg <= 1.0:
    tap_ratio = np.arcsin(np.sqrt(tap_arg)) / np.pi
    tap_pos   = tap_ratio * L_res
else:
    tap_ratio = 0.5
    tap_pos   = L_res / 2
print(f"\n  Feed coupling — tapped-line method:")
print(f"    Qe_in   = {Qe_in:.4f}")
print(f"    Tap pos = {tap_pos*1e3:.3f} mm from shorted end of resonator")
print(f"    (= {tap_ratio*100:.2f} % of full resonator length {L_res*1e3:.3f} mm)")

# ─────────────────────────────────────────────────────────
# 6.  SUMMARY TABLE OF PHYSICAL DIMENSIONS
# ─────────────────────────────────────────────────────────
hairpin_inner_gap = W50   # gap between the two legs of the same hairpin

print(f"\n{'='*54}")
print(f"  PHYSICAL DIMENSIONS SUMMARY")
print(f"{'='*54}")
print(f"  Substrate")
print(f"    Material  : FR4")
print(f"    h         : {h*1e3:.2f} mm")
print(f"    εr        : {er}")
print(f"    tan δ     : {tand}")
print(f"    Cu t      : {t*1e6:.0f} µm  (1 oz)")
print(f"\n  Resonator (all 5 identical — 50 Ω)")
print(f"    Line width  W  : {W50*1e3:.4f} mm")
print(f"    Leg length  L  : {L_leg*1e3:.4f} mm  (each arm)")
print(f"    Inner gap      : {hairpin_inner_gap*1e3:.4f} mm  (between legs of same resonator)")
print(f"\n  Inter-resonator spacings")
for i in range(len(spacings)):
    print(f"    d[{i+1},{i+2}]  c-c={spacings[i]*1e3:.3f} mm   edge={gaps[i]*1e3:.3f} mm")
print(f"\n  Feed coupling — tapped line")
print(f"    Qe_in    : {Qe_in:.4f}")
print(f"    Qe_out   : {Qe_out:.4f}")
print(f"    Tap pos  : {tap_pos*1e3:.3f} mm from shorted resonator end")
print(f"\n  Notes")
print(f"    - Spacings are FIRST-PASS. EM sim (Stage 3) will refine them.")
print(f"    - Add ~{0.5*W50*1e3:.2f} mm bend correction to L_leg for the U-turn.")
print(f"    - Min gap for JLCPCB standard process: 0.15 mm.")
print(f"{'='*54}\n")

# ─────────────────────────────────────────────────────────
# 7.  IDEAL CIRCUIT-LEVEL S-PARAMETER RESPONSE
#     Build the BPF as a lumped-distributed ladder using
#     coupled-resonator theory and compute S-params analytically.
# ─────────────────────────────────────────────────────────
freq_GHz = np.linspace(0.7, 1.05, 4000)
freq_Hz  = freq_GHz * 1e9
omega    = 2 * np.pi * freq_Hz
omega_c  = 2 * np.pi * fc

# Bandpass frequency transformation Ω = (1/FBW)*(ω/ω0 - ω0/ω)
Omega = (1 / FBW) * (freq_Hz / fc - fc / freq_Hz)

# Chebyshev transfer function |S21|² = 1 / (1 + ε²·T_N²(Ω))
epsilon_c = np.sqrt(10 ** (Ar / 10) - 1)
T_N = np.where(
    np.abs(Omega) >= 1,
    np.cosh(N * np.arccosh(np.clip(np.abs(Omega), 1, None))),
    np.cos(N  * np.arccos(np.clip(Omega, -1, 1)))
)

S21_sq = 1 / (1 + epsilon_c**2 * T_N**2)
S21_dB = 10 * np.log10(np.maximum(S21_sq, 1e-20))
S11_sq = 1 - S21_sq
S11_dB = 10 * np.log10(np.maximum(S11_sq, 1e-20))

# Group delay = -d(phase)/dω  (numerical derivative of S21 phase)
phase_S21 = np.unwrap(np.angle(np.sqrt(S21_sq) * np.exp(1j * Omega * 0)))
# Use a simple analytical approximation for group delay in passband
# dΩ/dω = (1/FBW)*(1/ω0 + ω0/ω²)
dOmega_domega = (1 / FBW) * (1 / (2 * np.pi * fc) + (2 * np.pi * fc) / omega**2)
# d|S21|/dΩ for group delay estimate
with np.errstate(divide='ignore', invalid='ignore'):
    sinh_arg  = N * np.arccosh(np.abs(Omega))
    dTN_dOmega = np.where(
        np.abs(Omega) >= 1,
        N * np.sinh(np.minimum(sinh_arg, 500)) / np.sqrt(np.maximum(Omega**2 - 1, 1e-15)),
        N * np.sin(N * np.arccos(np.clip(Omega, -1, 1))) / np.sqrt(np.maximum(1 - Omega**2, 1e-15))
    )

numerator    = 2 * epsilon_c**2 * T_N * dTN_dOmega * dOmega_domega
group_delay  = numerator / (2 * np.pi * (1 + epsilon_c**2 * T_N**2)**2)
group_delay_ns = np.abs(group_delay) * 1e9   # convert to ns (rough magnitude)

# ─────────────────────────────────────────────────────────
# 8.  PLOT 1 — S-PARAMETER RESPONSE
# ─────────────────────────────────────────────────────────
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
fig.patch.set_facecolor("#f8f8f8")

# ── S11 / S21 ──
ax1.set_facecolor("#ffffff")
ax1.plot(freq_GHz * 1000, S21_dB, color="#1a6fb5", lw=2.0, label="S21 (Insertion loss)")
ax1.plot(freq_GHz * 1000, S11_dB, color="#c0392b", lw=1.5, linestyle="--", label="S11 (Return loss)")

# Spec lines
ax1.axhline(-2,  color="#1a6fb5", lw=0.8, linestyle=":", alpha=0.7, label="S21 ≥ −2 dB spec")
ax1.axhline(-20, color="#c0392b", lw=0.8, linestyle=":", alpha=0.7, label="S11 ≤ −20 dB spec")
ax1.axhline(-30, color="gray",    lw=0.8, linestyle=":", alpha=0.7, label="Stopband ≤ −30 dB")

# Passband shading
pb_lo = (fc - BW/2) / 1e9
pb_hi = (fc + BW/2) / 1e9
ax1.axvspan(pb_lo*1000, pb_hi*1000, alpha=0.10, color="#1a6fb5", label="Passband ±5 MHz")
ax1.axvline(fc/1e6, color="#888888", lw=0.8, linestyle="-.", alpha=0.6)

ax1.set_ylim(-80, 5)
ax1.set_ylabel("Magnitude (dB)", fontsize=11)
ax1.set_title(f"Hairpin BPF — Ideal Chebyshev Response\n"
              f"N={N}, fc={fc/1e6:.0f} MHz, BW={BW/1e6:.0f} MHz, "
              f"Ar={Ar} dB, Z0={Z0} Ω", fontsize=12, fontweight="bold")
ax1.legend(fontsize=9, loc="lower right")
ax1.grid(True, alpha=0.35, linestyle="--")
ax1.yaxis.set_major_locator(ticker.MultipleLocator(10))

# Annotate passband
ax1.annotate(f"fc = {fc/1e6:.0f} MHz",
             xy=(fc/1e6, -5), xytext=(fc/1e6 + 20, -15),
             fontsize=8.5, arrowprops=dict(arrowstyle="->", lw=0.8),
             bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.8))

# ── Group delay ──
ax2.set_facecolor("#ffffff")
ax2.plot(freq_GHz * 1000, group_delay_ns, color="#16a085", lw=2.0, label="Group delay")
ax2.axvspan(pb_lo*1000, pb_hi*1000, alpha=0.10, color="#1a6fb5")
ax2.axvline(fc/1e6, color="#888888", lw=0.8, linestyle="-.", alpha=0.6)
ax2.set_ylim(bottom=0)
ax2.set_ylabel("Group delay (ns)", fontsize=11)
ax2.set_xlabel("Frequency (MHz)", fontsize=11)
ax2.legend(fontsize=9, loc="upper right")
ax2.grid(True, alpha=0.35, linestyle="--")

# X-axis: MHz not GHz
ax2.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{x:.0f}"))

plt.tight_layout()
plt.savefig(OUT / "stage1_s_params.png", dpi=180, bbox_inches="tight")
plt.close()
print(f"  [saved] results/stage1_s_params.png")

# ─────────────────────────────────────────────────────────
# 9.  PLOT 2 — PASSBAND ZOOM
# ─────────────────────────────────────────────────────────
fig2, ax3 = plt.subplots(figsize=(10, 5))
fig2.patch.set_facecolor("#f8f8f8")
ax3.set_facecolor("#ffffff")

# Narrow zoom: ±30 MHz around fc
mask = (freq_Hz > fc - 30e6) & (freq_Hz < fc + 30e6)
ax3.plot(freq_Hz[mask]/1e6, S21_dB[mask], color="#1a6fb5", lw=2.0, label="S21")
ax3.plot(freq_Hz[mask]/1e6, S11_dB[mask], color="#c0392b", lw=1.5, linestyle="--", label="S11")

ax3.axhline(-2,  color="#1a6fb5", lw=0.8, linestyle=":", alpha=0.8)
ax3.axhline(-20, color="#c0392b", lw=0.8, linestyle=":", alpha=0.8)
ax3.axvspan(pb_lo*1e3, pb_hi*1e3, alpha=0.10, color="#1a6fb5")
ax3.axvline(fc/1e6, color="#888888", lw=0.8, linestyle="-.", alpha=0.6)

# Annotate band edges
ax3.axvline((fc - BW/2)/1e6, color="#1a6fb5", lw=0.8, linestyle="--", alpha=0.5)
ax3.axvline((fc + BW/2)/1e6, color="#1a6fb5", lw=0.8, linestyle="--", alpha=0.5)
ax3.text((fc - BW/2)/1e6 - 0.5, -35, f"{(fc-BW/2)/1e6:.0f} MHz",
         ha="right", fontsize=8, color="#1a6fb5")
ax3.text((fc + BW/2)/1e6 + 0.5, -35, f"{(fc+BW/2)/1e6:.0f} MHz",
         ha="left", fontsize=8, color="#1a6fb5")

ax3.set_xlim((fc - 30e6)/1e6, (fc + 30e6)/1e6)
ax3.set_ylim(-80, 5)
ax3.set_xlabel("Frequency (MHz)", fontsize=11)
ax3.set_ylabel("Magnitude (dB)", fontsize=11)
ax3.set_title("Passband detail — ±30 MHz around fc", fontsize=12, fontweight="bold")
ax3.legend(fontsize=9)
ax3.grid(True, alpha=0.35, linestyle="--")
ax3.yaxis.set_major_locator(ticker.MultipleLocator(10))

plt.tight_layout()
plt.savefig(OUT / "stage1_passband_zoom.png", dpi=180, bbox_inches="tight")
plt.close()
print(f"  [saved] results/stage1_passband_zoom.png")

# ─────────────────────────────────────────────────────────
# 10.  TOUCHSTONE S2P OUTPUT  (ideal 2-port network)
#      Build as skrf Network for import into Qucs-S
# ─────────────────────────────────────────────────────────
S21_lin = np.sqrt(S21_sq) * np.exp(1j * 0)    # phase = 0 (ideal)
S11_lin = np.sqrt(S11_sq) * np.exp(1j * np.pi) # reflected out of phase
S_data  = np.zeros((len(freq_Hz), 2, 2), dtype=complex)
S_data[:, 0, 0] = S11_lin
S_data[:, 0, 1] = S21_lin
S_data[:, 1, 0] = S21_lin   # reciprocal
S_data[:, 1, 1] = S11_lin   # symmetric

freq_obj = skrf.Frequency.from_f(freq_Hz, unit="hz")
ntwk     = skrf.Network(frequency=freq_obj, s=S_data, z0=50)
ntwk.write_touchstone(str(OUT / "stage1_network.s2p"))
print(f"  [saved] results/stage1_network.s2p")

# ─────────────────────────────────────────────────────────
# 11.  TEXT REPORT
# ─────────────────────────────────────────────────────────
report_lines = [
    "HAIRPIN MICROSTRIP BPF — STAGE 1 SYNTHESIS REPORT",
    "=" * 52,
    "",
    "TARGET SPECIFICATIONS",
    f"  Centre frequency   fc  = {fc/1e6:.1f} MHz",
    f"  3 dB bandwidth     BW  = {BW/1e6:.1f} MHz",
    f"  Passband           {(fc-BW/2)/1e6:.1f} – {(fc+BW/2)/1e6:.1f} MHz",
    f"  Fractional BW      FBW = {FBW*100:.4f} %",
    f"  Filter order       N   = {N}",
    f"  Return loss        ≤ -20 dB in passband",
    f"  Insertion loss     ≥ -2 dB in passband",
    f"  Stopband atten.    ≤ -30 dB outside passband",
    "",
    "PROTOTYPE",
    f"  Type     : Chebyshev, {Ar} dB ripple",
    f"  g-values : " + "  ".join([f"g[{i}]={v:.5f}" for i, v in enumerate(g)]),
    "",
    "COUPLING MATRIX",
] + [f"  M[{i+1},{i+2}] = {m:.6f}" for i, m in enumerate(M)] + [
    f"  Qe_in  = {Qe_in:.4f}",
    f"  Qe_out = {Qe_out:.4f}",
    "",
    "SUBSTRATE (FR4)",
    f"  h  = {h*1e3:.2f} mm",
    f"  εr = {er}",
    f"  tan δ = {tand}",
    f"  Cu t  = {t*1e6:.0f} µm",
    "",
    "RESONATOR DIMENSIONS",
    f"  Line width  W = {W50*1e3:.4f} mm  (50 Ω)",
    f"  εr_eff        = {er_eff:.4f}",
    f"  Guided λ      = {lambda_g*1e3:.3f} mm",
    f"  Half-wave L   = {L_res*1e3:.3f} mm",
    f"  Hairpin arm   = {L_leg*1e3:.3f} mm  (add ~{0.5*W50*1e3:.2f} mm bend correction)",
    f"  Inner gap     = {hairpin_inner_gap*1e3:.4f} mm  (between legs of same resonator)",
    "",
    "INTER-RESONATOR SPACINGS  (first-pass — refine in EM sim)",
] + [f"  d[{i+1},{i+2}] c-c={spacings[i]*1e3:.3f} mm  edge={gaps[i]*1e3:.3f} mm" for i in range(len(spacings))] + [
    f"  Feed: tapped line, tap_pos = {tap_pos*1e3:.3f} mm from shorted end",
    "",
    "OUTPUT FILES",
    "  results/stage1_s_params.png       — full frequency S11/S21",
    "  results/stage1_passband_zoom.png  — passband detail",
    "  results/stage1_network.s2p        — Touchstone for Qucs-S",
    "  results/stage1_dimensions.txt     — this file",
    "",
    "NEXT STEPS",
    "  Stage 2 : Import stage1_network.s2p into Qucs-S.",
    "            Replace ideal elements with MLIN/MCOUPLED models.",
    "            Use dimensions above as starting values.",
    "  Stage 3 : openEMS FDTD simulation with exact geometry.",
    "            Optimise gaps — especially s[1,2] and s[4,5]",
    "            which are most sensitive to fabrication tolerance.",
]

report_text = "\n".join(report_lines)
with open(OUT / "stage1_dimensions.txt", "w") as f:
    f.write(report_text)
print(f"  [saved] results/stage1_dimensions.txt")

print(f"\n  Stage 1 complete. All outputs in ./results/\n")
