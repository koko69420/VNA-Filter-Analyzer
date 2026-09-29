#!/usr/bin/env python3
"""
Hairpin Microstrip BPF — Stage 3: Meep FDTD (v2, corrected)
============================================================
Changes from v1 (per design review):
  1. Cell size: 90×57×12.6 mm → 220M voxels at res=15 (was 7B at res=30)
  2. PEC bottom boundary = ground plane — eliminates one full PML layer in z
  3. Resolution 15 cells/mm (was 30); still 37 cells across narrowest gap
  4. Complex S-params via get_eigenmode_coefficients (was power-flux only)
  5. Removed eig_parity=ODD_Z — wrong for microstrip; let Meep find quasi-TEM
  6. GPU note removed — standard pymeep is CPU-only; no CUDA backend exists
  7. No x-symmetry shortcut — asymmetric driven problem, superposition needed
     for that and it's not worth the complexity here

FILTER SPEC
  fc=868 MHz  BW=10 MHz  N=5  Chebyshev 0.1 dB  FR4 er=4.4  h=1.6 mm

MEEP UNITS
  length unit a = 1 mm  →  f_meep = f_Hz * 1e-3 / c0  (= f_Hz * 3.3333e-12)

RUN
  Dry run (geometry check, no Meep required):
      python3 stage3_hairpin_meep.py

  Full solve — single core (slow, only if MPI unavailable):
      python3 stage3_hairpin_meep.py --run

  Full solve — MPI (recommended):
      mpirun -np $(nproc) python3 stage3_hairpin_meep.py --run

  Fast first-pass (res=12, 112M voxels, ~15-20 min on 8 cores):
      mpirun -np $(nproc) python3 stage3_hairpin_meep.py --run --res 12

OUTPUTS (in ./sim_meep_hairpin/)
  stage3_network.s2p      Touchstone with complex S11/S21
  stage3_response.png     S-param plot with passband inset
  stage3_s_data.npz       Raw numpy arrays (freq, s11, s21) for further processing

UBUNTU 26.04 / WAYLAND
  Meep is headless — no display needed. matplotlib uses Agg backend.
  mpirun works fine under Wayland/XWayland; no special flags needed.

INSTALL (if not already done)
  conda install -c conda-forge pymeep=*=mpi_mpich_*
  OR build from source: https://github.com/NanoComp/meep/blob/master/doc/docs/Installation.md
"""

import sys
import os
import argparse
import numpy as np

# ── CLI ─────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('--run', action='store_true')
parser.add_argument('--res', type=int, default=15)
args, _ = parser.parse_known_args()

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sim_meep_hairpin')
os.makedirs(OUT, exist_ok=True)

# ═══════════════════════════════════════════════════════════════════════════
# 1.  MEEP UNIT SYSTEM: length unit a = 1 mm
# ═══════════════════════════════════════════════════════════════════════════
c0_SI  = 3e8
a_m    = 1e-3                   # 1 mm in metres
f_conv = a_m / c0_SI            # Hz → meep freq  (3.3333e-12)

fc_Hz   = 868e6
BW_Hz   = 10e6
# Gaussian source: centre at fc, half-bandwidth covers 500–1200 MHz
f0      = fc_Hz  * f_conv       # 0.0028933 meep units
df      = 350e6  * f_conv       # half-BW of Gaussian in meep units
f_min   = 700e6  * f_conv
f_max   = 1050e6 * f_conv
nfreqs  = 401

# ═══════════════════════════════════════════════════════════════════════════
# 2.  PHYSICAL GEOMETRY  (mm)
# ═══════════════════════════════════════════════════════════════════════════
W50        = 3.059      # 50-ohm line / resonator arm width
L_leg      = 47.3485    # hairpin arm length (λ/4 in substrate)
inner_gap  = 3.059      # fold gap inside one hairpin
tap_pos    = 3.797      # tapped feed height from bend
gaps       = [2.472, 2.649, 2.649, 2.472]   # coupling gaps, edge-to-edge

h_sub      = 1.6        # substrate thickness
er_sub     = 4.4
tand_sub   = 0.020

# Cell padding: smaller than v1, validated by field-decay analysis
feed_len   = 12.0       # straight feed stub each side (was 20 mm)
pml_th     = 5.0        # PML thickness (was 8 mm)
air_above  = 6.0        # air above top copper before PML (was 20 mm)
                        # field above microstrip decays as exp(-z/h_sub);
                        # at z=3h_sub (~5 mm) it's down >99% from surface value

# ── resonator x-positions ────────────────────────────────────────────────
res_width = 2*W50 + inner_gap
N_res     = 5
x_left    = [0.0] * N_res
for i in range(1, N_res):
    x_left[i] = x_left[i-1] + res_width + gaps[i-1]
total_x = x_left[-1] + res_width

# ── simulation cell ──────────────────────────────────────────────────────
# z: 0 (PEC boundary = ground plane) to h_sub+air_above+pml_th
# No PML at z=0 — the Meep PEC wall IS the ground plane.
sx = total_x + 2*feed_len + 2*pml_th
sy = L_leg   + 2*pml_th
sz = h_sub   + air_above + pml_th      # no bottom PML

print(f"\nHairpin BPF Stage 3 — Meep FDTD")
print(f"{'='*52}")
print(f"  Resolution  : {args.res} cells/mm")
print(f"  Cell size   : {sx:.1f} × {sy:.1f} × {sz:.1f} mm")
nx = int(sx*args.res); ny = int(sy*args.res); nz = int(sz*args.res)
print(f"  Voxels      : {nx}×{ny}×{nz} = {nx*ny*nz/1e6:.0f} M")
print(f"  Min gap     : {min(gaps)} mm → {int(min(gaps)*args.res)} cells")
print(f"  Substrate z : {h_sub} mm → {int(h_sub*args.res)} cells (subpixel smoothing helps)")
print(f"  Feed stubs  : {feed_len} mm each side")
print(f"  PML         : {pml_th} mm (x, y, z-top only; z-bottom = PEC ground)")
print(f"  Air above   : {air_above} mm")

print(f"\n  Resonator layout:")
for i in range(N_res):
    xl = x_left[i]
    print(f"    R{i+1}: L-arm=[{xl:.3f},{xl+W50:.3f}]  "
          f"R-arm=[{xl+W50+inner_gap:.3f},{xl+res_width:.3f}]")
    if i > 0:
        g_act = x_left[i] - (x_left[i-1]+res_width)
        print(f"         gap to R{i}: {g_act:.3f} mm (target {gaps[i-1]})")

# ── feed line x-extents ──────────────────────────────────────────────────
feed1_x0 = -feed_len;   feed1_x1 = 0.0
feed2_x0 = total_x;     feed2_x1 = total_x + feed_len
feed_y0  = tap_pos;     feed_y1  = tap_pos + W50

# Port monitor planes (inside feed stubs, away from PML and tap junction)
port1_x = -feed_len * 0.55    # board coords
port2_x =  total_x + feed_len * 0.55
src_x   = -feed_len * 0.75    # source slightly closer to left PML

# Monitor / source cross-section geometry
mon_y_cen = tap_pos + W50/2
mon_y_sz  = W50 * 2.0          # covers trace + fringe field
mon_z_cen = h_sub / 2
mon_z_sz  = (h_sub + air_above) * 0.8   # substrate + most of air region

print(f"\n  Port 1 x = {port1_x:.2f} mm   Port 2 x = {port2_x:.2f} mm")
print(f"  Source  x = {src_x:.2f} mm")

if not args.run:
    print(f"\nDry run — geometry OK. Add --run to start FDTD.")
    print(f"Recommended command:")
    print(f"  mpirun -np $(nproc) python3 {os.path.basename(__file__)} --run")
    print(f"Fast first-pass (res=12, ~112M voxels):")
    print(f"  mpirun -np $(nproc) python3 {os.path.basename(__file__)} --run --res 12")
    sys.exit(0)

# ═══════════════════════════════════════════════════════════════════════════
# 3.  MEEP GEOMETRY
# ═══════════════════════════════════════════════════════════════════════════
import meep as mp
mp.verbosity(1)

# Meep cell origin is at cell centre; convert board coords (origin = corner)
cx_off = (feed1_x0 - pml_th + total_x + feed_len + pml_th) / 2   # = total_x/2
cy_off = sy / 2 - pml_th                                           # = L_leg/2
cz_off = sz / 2                                                     # board z goes 0 to sz

def mv(x=0.0, y=0.0, z=0.0):
    """Board coords (mm) → Meep Vector3."""
    return mp.Vector3(x - cx_off, y - cy_off, z - cz_off)

# ── Materials ─────────────────────────────────────────────────────────────
fr4 = mp.Medium(
    epsilon=er_sub,
    # D_conductivity encodes tanδ: σ = ω·ε·tanδ; here evaluated at fc
    D_conductivity = 2*np.pi*fc_Hz * er_sub * 8.854e-12 * tand_sub
)
# Copper as PEC (perfect conductor). USE_LOSSY_METAL=True below if you need
# finite conductivity: mp.Medium(D_conductivity=5.8e7) adds ~30% runtime.
metal = mp.metal

# ── Helper: add a copper patch at z=h_sub (top of substrate) ──────────────
sheet_th = 0.5 / args.res   # half-cell thickness for the PEC sheet
geometry = []

def cu_patch(x0, x1, y0, y1, prio=20):
    cx_ = (x0+x1)/2; cy_ = (y0+y1)/2
    geometry.append(mp.Block(
        size = mp.Vector3(x1-x0, y1-y0, sheet_th),
        center = mv(cx_, cy_, h_sub),
        material = metal,
        e_susceptibilities = [],
    ))

# ── FR4 slab (fills entire board footprint) ────────────────────────────────
geometry.append(mp.Block(
    size   = mp.Vector3(sx - 2*pml_th, sy - 2*pml_th, h_sub),
    center = mv(total_x/2, L_leg/2, h_sub/2),
    material = fr4
))

# NOTE: no separate ground plane object needed — the z=0 PEC wall boundary IS the ground.

# ── 5 hairpin resonators ───────────────────────────────────────────────────
bend_h = W50
for i in range(N_res):
    xl = x_left[i]
    cu_patch(xl,                xl+W50,         0.0,   L_leg)   # left arm
    cu_patch(xl+W50+inner_gap,  xl+res_width,   0.0,   L_leg)   # right arm
    cu_patch(xl,                xl+res_width,   0.0,   bend_h)  # bottom bend bar

# ── Tapped feed lines ──────────────────────────────────────────────────────
cu_patch(feed1_x0, feed1_x1, feed_y0, feed_y1)   # port 1 side
cu_patch(feed2_x0, feed2_x1, feed_y0, feed_y1)   # port 2 side

print(f"\nGeometry: {len(geometry)} objects")

# ═══════════════════════════════════════════════════════════════════════════
# 4.  PML — x, y, and z-top only; z-bottom = PEC (ground plane)
# ═══════════════════════════════════════════════════════════════════════════
pml_layers = [
    mp.PML(pml_th, direction=mp.X),
    mp.PML(pml_th, direction=mp.Y),
    mp.PML(pml_th, direction=mp.Z, side=mp.High),   # z-top (open above board)
    # z-bottom: no PML → defaults to PEC metallic wall = ground plane ✓
]

# ═══════════════════════════════════════════════════════════════════════════
# 5.  SOURCE — EigenModeSource on port 1 feed cross-section
#     Excites the quasi-TEM mode of the 50-ohm microstrip.
#     eig_parity NOT specified — Meep finds the lowest-loss mode at
#     this cross-section automatically (correct for microstrip quasi-TEM).
#     eig_parity=ODD_Z was WRONG in v1; microstrip has no z-mirror symmetry.
# ═══════════════════════════════════════════════════════════════════════════
src_center = mv(src_x, mon_y_cen, mon_z_cen)
src_size   = mp.Vector3(0, mon_y_sz, mon_z_sz)

sources = [mp.EigenModeSource(
    src       = mp.GaussianSource(frequency=f0, fwidth=df),
    center    = src_center,
    size      = src_size,
    direction = mp.X,           # mode propagates in +x
    eig_match_freq = True,
    eig_band  = 1,              # fundamental quasi-TEM mode
)]

# ═══════════════════════════════════════════════════════════════════════════
# 6.  SIMULATION FACTORY
# ═══════════════════════════════════════════════════════════════════════════
cell = mp.Vector3(sx, sy, sz)
res  = args.res

def make_sim(geo):
    return mp.Simulation(
        cell_size       = cell,
        resolution      = res,
        geometry        = geo,
        sources         = sources,
        boundary_layers = pml_layers,
        eps_averaging   = True,   # subpixel smoothing — critical for thin features
        default_material = mp.air
    )

# Decay criterion: wait until Ex has decayed to 1e-6 of its peak value
# at a probe point on the output feed line, checked every 50 time steps.
probe_pass2 = mv(port2_x - 2, mon_y_cen, h_sub*0.8)
probe_pass1 = mv(port1_x + 2, mon_y_cen, h_sub*0.8)
decay_tol   = 1e-6
decay_check = 50

freqs = np.linspace(f_min, f_max, nfreqs)

# ═══════════════════════════════════════════════════════════════════════════
# 7.  PASS 1 — REFERENCE (substrate + source, NO filter copper)
#     Records incident eigenmode coefficients at port 1.
# ═══════════════════════════════════════════════════════════════════════════
print("\n── Pass 1: reference run (incident pulse, no filter) ──")

ref_geo = [geometry[0]]   # FR4 slab only (index 0); no copper patches

sim_ref = make_sim(ref_geo)

mon1_ref = sim_ref.add_flux(f0, 2*df, nfreqs,
    mp.FluxRegion(center=mv(port1_x, mon_y_cen, mon_z_cen),
                  size=mp.Vector3(0, mon_y_sz, mon_z_sz),
                  direction=mp.X))

sim_ref.run(until_after_sources=mp.stop_when_fields_decayed(
    decay_check, mp.Ex, probe_pass1, decay_tol))

# Complex incident mode amplitude a_inc[k] for each frequency k
res_inc    = sim_ref.get_eigenmode_coefficients(mon1_ref, [1],
                 eig_parity=mp.NO_PARITY, direction=mp.X)
a_inc      = res_inc.alpha[0, :, 0]   # forward (+x) mode, shape (nfreqs,)

# Save DFT fields for subtraction in pass 2
flux_data_ref = sim_ref.get_flux_data(mon1_ref)
freq_hz_raw   = np.array(mp.get_flux_freqs(mon1_ref)) / f_conv

sim_ref.reset_meep()
print("  Pass 1 done.")
print(f"  |a_inc| range: {np.abs(a_inc).min():.3e} – {np.abs(a_inc).max():.3e}")

# ═══════════════════════════════════════════════════════════════════════════
# 8.  PASS 2 — FULL FILTER
# ═══════════════════════════════════════════════════════════════════════════
print("\n── Pass 2: full filter run ──")

sim = make_sim(geometry)

# Port 1 reflection monitor — subtract reference so only scattered fields remain
mon1 = sim.add_flux(f0, 2*df, nfreqs,
    mp.FluxRegion(center=mv(port1_x, mon_y_cen, mon_z_cen),
                  size=mp.Vector3(0, mon_y_sz, mon_z_sz),
                  direction=mp.X))
sim.load_minus_flux_data(mon1, flux_data_ref)

# Port 2 transmission monitor
mon2 = sim.add_flux(f0, 2*df, nfreqs,
    mp.FluxRegion(center=mv(port2_x, mon_y_cen, mon_z_cen),
                  size=mp.Vector3(0, mon_y_sz, mon_z_sz),
                  direction=mp.X))

sim.run(until_after_sources=mp.stop_when_fields_decayed(
    decay_check, mp.Ex, probe_pass2, decay_tol))

# get_eigenmode_coefficients on the DIFFERENCE fields:
#   mon1 stores (DUT fields) - (reference fields) at port 1
#   alpha[0,:,0] = forward component ≈ 0 (incident cancels)
#   alpha[0,:,1] = backward component = reflected wave → S11 numerator
res1 = sim.get_eigenmode_coefficients(mon1, [1],
           eig_parity=mp.NO_PARITY, direction=mp.X)
res2 = sim.get_eigenmode_coefficients(mon2, [1],
           eig_parity=mp.NO_PARITY, direction=mp.X)

a_refl  = res1.alpha[0, :, 1]   # reflected (-x) at port 1
a_trans = res2.alpha[0, :, 0]   # transmitted (+x) at port 2

print("  Pass 2 done.")

# ═══════════════════════════════════════════════════════════════════════════
# 9.  S-PARAMETERS
# ═══════════════════════════════════════════════════════════════════════════
# Complex S-params (amplitude ratio of eigenmode coefficients)
S11 = a_refl  / a_inc
S21 = a_trans / a_inc

freq_hz = freq_hz_raw   # Hz array, length nfreqs

S11_dB = 20*np.log10(np.maximum(np.abs(S11), 1e-12))
S21_dB = 20*np.log10(np.maximum(np.abs(S21), 1e-12))

# ═══════════════════════════════════════════════════════════════════════════
# 10.  SAVE + PLOT  (master rank only in MPI runs)
# ═══════════════════════════════════════════════════════════════════════════
if mp.am_master():
    # numpy archive (complex S-params preserved)
    npz_path = os.path.join(OUT, 'stage3_s_data.npz')
    np.savez(npz_path, freq_hz=freq_hz, S11=S11, S21=S21)
    print(f"\n[saved] {npz_path}")

    # Touchstone .s2p (complex, DB format)
    s2p_path = os.path.join(OUT, 'stage3_network.s2p')
    with open(s2p_path, 'w') as f:
        f.write('! Hairpin BPF Stage 3 — Meep FDTD\n')
        f.write('! fc=868MHz  BW=10MHz  N=5  FR4 h=1.6mm er=4.4 tand=0.02\n')
        f.write('# Hz S DB R 50\n')
        for k in range(len(freq_hz)):
            ang11 = np.degrees(np.angle(S11[k]))
            ang21 = np.degrees(np.angle(S21[k]))
            f.write(f"{freq_hz[k]:.6e}  "
                    f"{S11_dB[k]:.4f} {ang11:.3f}  "
                    f"{S21_dB[k]:.4f} {ang21:.3f}  "
                    f"{S21_dB[k]:.4f} {ang21:.3f}  "
                    f"{S11_dB[k]:.4f} {ang11:.3f}\n")
    print(f"[saved] {s2p_path}")

    # Plot
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker

    fig, ax = plt.subplots(figsize=(12, 6))
    fig.patch.set_facecolor('#f8f8f8')
    ax.set_facecolor('#ffffff')
    ax.plot(freq_hz/1e6, S21_dB, '#1a6fb5', lw=2.2, label='S21 (Meep FDTD)')
    ax.plot(freq_hz/1e6, S11_dB, '#c0392b', lw=1.8, ls='--', label='S11 (Meep FDTD)')
    ax.axvspan(863, 873, alpha=0.09, color='#1a6fb5')
    ax.axvline(868, color='#aaa', lw=0.8, ls='-.')
    ax.axhline(-2,  color='#1a6fb5', lw=0.7, ls=':', alpha=0.8, label='-2 dB spec')
    ax.axhline(-20, color='#c0392b', lw=0.7, ls=':', alpha=0.7, label='-20 dB spec')
    ax.axhline(-30, color='#777',    lw=0.7, ls=':', alpha=0.5)
    ax.set_xlim(700, 1050); ax.set_ylim(-60, 5)
    ax.set_xlabel('Frequency (MHz)', fontsize=12)
    ax.set_ylabel('Magnitude (dB)', fontsize=12)
    ax.set_title(
        f'Hairpin BPF — Stage 3 Meep FDTD  (res={args.res} cells/mm)\n'
        'N=5  fc=868 MHz  BW=10 MHz  FR4 h=1.6 mm  εr=4.4  tanδ=0.02',
        fontsize=12, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3, ls='--')
    ax.yaxis.set_major_locator(ticker.MultipleLocator(10))

    # Passband inset
    ax_in = ax.inset_axes([0.55, 0.10, 0.36, 0.48])
    zm = (freq_hz >= 840e6) & (freq_hz <= 900e6)
    ax_in.plot(freq_hz[zm]/1e6, S21_dB[zm], '#1a6fb5', lw=2)
    ax_in.plot(freq_hz[zm]/1e6, S11_dB[zm], '#c0392b', lw=1.5, ls='--')
    ax_in.axhline(-2,  color='#1a6fb5', lw=0.7, ls=':', alpha=0.7)
    ax_in.axhline(-20, color='#c0392b', lw=0.7, ls=':', alpha=0.7)
    ax_in.axvline(868, color='#aaa', lw=0.7, ls='-.')
    ax_in.set_xlim(840, 900)
    ax_in.set_xlabel('MHz', fontsize=8)
    ax_in.set_title('Passband ±30 MHz', fontsize=8)
    ax_in.grid(True, alpha=0.3, ls='--')
    ax_in.tick_params(labelsize=7)

    plt.tight_layout()
    png = os.path.join(OUT, 'stage3_response.png')
    plt.savefig(png, dpi=180, bbox_inches='tight')
    plt.close()
    print(f'[saved] {png}')

    # Console summary
    fc_idx = np.argmin(np.abs(freq_hz - 868e6))
    pb     = (freq_hz >= 863e6) & (freq_hz <= 873e6)
    print(f'\n── Stage 3 Results ──────────────────────────────')
    print(f'  S21 @ 868 MHz  = {S21_dB[fc_idx]:.2f} dB  (spec >= -2 dB)')
    print(f'  S11 @ 868 MHz  = {S11_dB[fc_idx]:.2f} dB  (spec <= -20 dB)')
    if pb.any():
        print(f'  S21 min in PB  = {np.min(S21_dB[pb]):.2f} dB')
        print(f'  S11 max in PB  = {np.max(S11_dB[pb]):.2f} dB')
    S21_max = np.max(S21_dB)
    cross = np.where(np.diff(np.sign(S21_dB - (S21_max - 3))))[0]
    if len(cross) >= 2:
        fl = freq_hz[cross[0]]; fh = freq_hz[cross[-1]]
        print(f'  3 dB BW        = {(fh-fl)/1e6:.2f} MHz  ({fl/1e6:.2f}–{fh/1e6:.2f} MHz)')
    print(f'─────────────────────────────────────────────────')
    print('\nStage 3 complete.')
