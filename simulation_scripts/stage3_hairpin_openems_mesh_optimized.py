#!/usr/bin/env python3
"""
Hairpin Microstrip BPF — Stage 3: openEMS Full-Wave FDTD Simulation
=====================================================================
Builds the EXACT physical geometry validated in Stage 2 (lossless circuit
model gave 0.00 dB at fc -> topology + synthesis confirmed correct).

FILTER SPEC
  fc = 868 MHz   BW = 10 MHz   N = 5   Chebyshev 0.1 dB ripple
  Substrate: FR4  er=4.4  h=1.6mm  t=35um copper  tand=0.02

GEOMETRY (from Stage 1/2 synthesis, do not change without re-deriving)
  W50          = 3.059  mm   (50 ohm line width on this substrate)
  L_leg        = 47.3485 mm  (each hairpin arm, ~lambda/4)
  inner_gap    = 3.059  mm   (fold gap between the two arms of one resonator, = W)
  coupling gaps (edge-to-edge, adjacent resonators):
      g12 = g45 = 2.472 mm
      g23 = g34 = 2.649 mm
  tap_pos      = 3.797  mm   (feed tap height from the bend, resonators 1 & 5 only)

LAYOUT
  5 hairpin resonators in a row along x, each a "U" opening upward in +y,
  bend (short connecting bar) at y=0, open arm ends at y=L_leg.
  Resonator i occupies a block of width (2*W50 + inner_gap); adjacent
  resonators separated by the coupling gap g_i.  Port 1 feeds resonator 1's
  outer (left) arm via a tapped 50-ohm line at y=tap_pos; port 2 symmetric
  on resonator 5's outer (right) arm.

RUN
  python3 stage3_hairpin_openems.py
  Expect 30-90 min on a modern multicore CPU at the mesh resolution below.
  View geometry first with AppCSXCAD on the .xml dumped to Sim_Path/ before
  committing to a full run (see bottom of this file).

UBUNTU 26.04 LTS / WAYLAND NOTE
  AppCSXCAD's VTK-based 3D view can be unstable under native Wayland.
  If it fails to open or renders blank, force XWayland for that one process:
      GDK_BACKEND=x11 AppCSXCAD geometry.xml
  This does not affect the FDTD solver itself, which is headless.
"""

import os
import sys
import numpy as np

# ── openEMS / CSXCAD imports ────────────────────────────────────────────
try:
    from CSXCAD import ContinuousStructure
    from openEMS import openEMS
    from openEMS.physical_constants import C0
except ImportError:
    sys.exit(
        "openEMS python bindings not found.\n"
        "Install on Ubuntu 26.04 via the official build script:\n"
        "  git clone --recursive https://github.com/thliebig/openEMS-Project.git\n"
        "  cd openEMS-Project && ./update_openEMS.sh ~/opt/openEMS --python\n"
        "Then add to your shell rc:\n"
        "  export PYTHONPATH=$PYTHONPATH:~/opt/openEMS/lib/python3.XX/site-packages\n"
        "  export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:~/opt/openEMS/lib\n"
        "(swap python3.XX for your actual python version, check with `python3 --version`)"
    )

# ═══════════════════════════════════════════════════════════════════════
# 1. UNITS, PATHS, SWEEP
# ═══════════════════════════════════════════════════════════════════════
unit = 1e-3   # all geometry below is in mm

Sim_Path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sim_hairpin_bpf')
Sim_CSX  = 'hairpin_bpf.xml'
os.makedirs(Sim_Path, exist_ok=True)

f0      = 868e6        # center frequency (excitation center)
fc_bw   = 350e6         # excitation bandwidth (covers 518-1218 MHz -> safely spans 700-1050 sweep)
f_start = 700e6
f_stop  = 1050e6

# ═══════════════════════════════════════════════════════════════════════
# 2. SUBSTRATE / MATERIAL PROPERTIES
# ═══════════════════════════════════════════════════════════════════════
er        = 4.4
h_sub     = 1.6     # mm
t_cu      = 0.035   # mm copper thickness
tand      = 0.020
cu_kappa  = 5.8e7   # S/m, copper bulk conductivity (used if lossy metal enabled)

USE_LOSSY_METAL = False  # True = finite-conductivity copper sheet (slower, more accurate)
                          # False = PEC (faster first pass; dielectric loss still included)

# ═══════════════════════════════════════════════════════════════════════
# 3. VALIDATED STAGE 1/2 GEOMETRY (mm)
# ═══════════════════════════════════════════════════════════════════════
W50        = 3.059      # 50 ohm line / resonator arm width
L_leg      = 47.3485    # hairpin arm length
inner_gap  = 3.059      # fold gap inside one resonator (between its 2 arms)
tap_pos    = 3.797      # feed tap height from bend (y=0) on R1 / R5 outer arms

# coupling gaps between adjacent resonators (edge-to-edge), in synthesis order
gaps = [2.472, 2.649, 2.649, 2.472]   # g12, g23, g34, g45

bend_h     = W50         # height of the bottom connecting bar = trace width
feed_len   = 15.0        # mm, straight 50-ohm feed line stub length out to each port
board_clear = 8.0        # mm, extra substrate/ground clearance around the structure

# ── derive resonator block geometry ─────────────────────────────────────
res_width = 2*W50 + inner_gap     # x-extent of one hairpin (both arms + fold gap)
N_res     = 5

x_left = [0.0]*N_res
x_left[0] = 0.0
for i in range(1, N_res):
    x_left[i] = x_left[i-1] + res_width + gaps[i-1]

total_x = x_left[-1] + res_width
total_y = L_leg

print(f"Resonator block width   = {res_width:.4f} mm")
print(f"Total resonator span x  = {total_x:.4f} mm")
print(f"Total resonator span y  = {total_y:.4f} mm")
print(f"Resonator x_left list   = {[f'{x:.3f}' for x in x_left]}")

# board extents (with feed lines + clearance)
board_x0 = -feed_len - board_clear
board_x1 = total_x + feed_len + board_clear
board_y0 = -board_clear
board_y1 = total_y + board_clear

# ═══════════════════════════════════════════════════════════════════════
# 4. CSX STRUCTURE SETUP
# ═══════════════════════════════════════════════════════════════════════
CSX = ContinuousStructure()
FDTD = openEMS(NrTS=3000000, EndCriteria=1e-4)
FDTD.SetCSX(CSX)
mesh = CSX.GetGrid()
mesh.SetDeltaUnit(unit)

FDTD.SetGaussExcite(f0, fc_bw)
FDTD.SetBoundaryCond(['PML_8', 'PML_8', 'PML_8', 'PML_8', 'PEC', 'PML_8'])
# x-min/x-max: PML, y-min/y-max: PML, z-min: PEC (ground plane handled separately
# but z-min boundary set PEC is harmless extra margin below ground), z-max: PML (open above board)

# ── Materials ────────────────────────────────────────────────────────────
substrate = CSX.AddMaterial('FR4', epsilon=er, kappa=tand*2*np.pi*f0*er*8.854e-12)

if USE_LOSSY_METAL:
    copper = CSX.AddConductingSheet('copper', conductivity=cu_kappa, thickness=t_cu)
    gnd    = CSX.AddConductingSheet('gnd',    conductivity=cu_kappa, thickness=t_cu)
else:
    copper = CSX.AddMetal('copper')
    gnd    = CSX.AddMetal('gnd')

# ── Substrate slab ───────────────────────────────────────────────────────
substrate.AddBox(
    priority=0,
    start=[board_x0, board_y0, 0],
    stop =[board_x1, board_y1, h_sub]
)

# ── Ground plane (bottom of substrate) ──────────────────────────────────
gnd.AddBox(
    priority=10,
    start=[board_x0, board_y0, 0],
    stop =[board_x1, board_y1, 0]
)

# ═══════════════════════════════════════════════════════════════════════
# 5. HAIRPIN RESONATORS (top copper, z = h_sub)
# ═══════════════════════════════════════════════════════════════════════
z_top = h_sub

def add_box_xy(metal_obj, x0, x1, y0, y1, prio=20):
    metal_obj.AddBox(priority=prio, start=[x0, y0, z_top], stop=[x1, y1, z_top])

resonator_boxes = []  # keep coords for reference / sanity plotting

for i in range(N_res):
    xl  = x_left[i]
    # left arm
    la_x0, la_x1 = xl, xl + W50
    # right arm
    ra_x0, ra_x1 = xl + W50 + inner_gap, xl + 2*W50 + inner_gap
    # arms run from y=0 (bend) to y=L_leg (open end)
    add_box_xy(copper, la_x0, la_x1, 0.0, L_leg)
    add_box_xy(copper, ra_x0, ra_x1, 0.0, L_leg)
    # bottom bend bar joining the two arms
    add_box_xy(copper, la_x0, ra_x1, 0.0, bend_h)
    resonator_boxes.append((la_x0, la_x1, ra_x0, ra_x1))
    print(f"  R{i+1}: left arm x=[{la_x0:.3f},{la_x1:.3f}]  "
          f"right arm x=[{ra_x0:.3f},{ra_x1:.3f}]  y=[0,{L_leg:.3f}]")

# ═══════════════════════════════════════════════════════════════════════
# 6. TAPPED FEED LINES (port 1 -> R1 left arm, port 2 -> R5 right arm)
# ═══════════════════════════════════════════════════════════════════════
# Feed line 1: horizontal 50-ohm line from x=board_x0+board_clear/2 up to the
# outer edge of R1's left arm, at height y = tap_pos .. tap_pos+W50
r1_la_x0, r1_la_x1, _, _ = resonator_boxes[0]
feed1_x0 = -feed_len
feed1_x1 = r1_la_x0
feed1_y0 = tap_pos
feed1_y1 = tap_pos + W50
add_box_xy(copper, feed1_x0, feed1_x1, feed1_y0, feed1_y1, prio=20)

_, _, r5_ra_x0, r5_ra_x1 = resonator_boxes[-1]
feed2_x0 = r5_ra_x1
feed2_x1 = r5_ra_x1 + feed_len
feed2_y0 = tap_pos
feed2_y1 = tap_pos + W50
add_box_xy(copper, feed2_x0, feed2_x1, feed2_y0, feed2_y1, prio=20)

print(f"\nFeed line 1 (port 1): x=[{feed1_x0:.3f},{feed1_x1:.3f}]  y=[{feed1_y0:.3f},{feed1_y1:.3f}]")
print(f"Feed line 2 (port 2): x=[{feed2_x0:.3f},{feed2_x1:.3f}]  y=[{feed2_y0:.3f},{feed2_y1:.3f}]")

# ═══════════════════════════════════════════════════════════════════════
# 8. MESH – deterministic explicit lines (no smoothing, no refinement)
# ═══════════════════════════════════════════════════════════════════════
# X-direction:
#   conductor edges + feed edges + coupling gap edges → fine cluster
#   then 2 mm background
critical_x_edges = set()
for (la0, la1, ra0, ra1) in resonator_boxes:
    critical_x_edges.update([la0, la1, ra0, ra1])
critical_x_edges.update([feed1_x0, feed1_x1, feed2_x0, feed2_x1])

x_lines = set()
for e in critical_x_edges:
    x_lines.update([
    e-0.40,
    e-0.35,
    e-0.30,
    e-0.25,
    e-0.20,
    e-0.15,
    e-0.10,
    e-0.05,
    e,
    e+0.05,
    e+0.10,
    e+0.15,
    e+0.20,
    e+0.25,
    e+0.30,
    e+0.35,
    e+0.40
    ])

# coarse background every 2 mm across the whole board range
x_coarse = np.arange(board_x0, board_x1 + 1.0, 1.0)
x_lines.update(x_coarse)
x_lines.update([board_x0, board_x1])   # ensure boundaries
x_lines = sorted(x_lines)
mesh.AddLine('x', x_lines)

# Y-direction:
#   critical heights: 0, bend_h, tap_pos, tap_pos+W50, L_leg
#   fine cluster around them, 0.5 mm inside resonator, 2 mm outside
critical_y = [0.0, bend_h, tap_pos, tap_pos+W50, L_leg]
y_lines = set()
for yc in critical_y:
    y_lines.update([
    yc-0.40,
    yc-0.35,
    yc-0.30,
    yc-0.25,
    yc-0.20,
    yc-0.15,
    yc-0.10,
    yc-0.05,
    yc,
    yc+0.05,
    yc+0.10,
    yc+0.15,
    yc+0.20,
    yc+0.25,
    yc+0.30,
    yc+0.35,
    yc+0.40
])

# 0.5 mm spacing only inside the resonator region
y_fine = np.arange(0.0, L_leg + 0.2, 0.2)
y_lines.update(y_fine)

# 2 mm spacing outside the resonator
y_coarse_lower = np.arange(board_y0, 0.0, 1.0)
y_coarse_upper = np.arange(L_leg, board_y1 + 1.0, 1.0)
y_lines.update(y_coarse_lower)
y_lines.update(y_coarse_upper)
y_lines.update([board_y0, board_y1])
y_lines = sorted(y_lines)
mesh.AddLine('y', y_lines)

# Z-direction:
#   explicit list from ground to 25 mm air; include PML extension below ground
z_lines = set()
z_lines.add(-board_clear)            # margin for lower PML
z_explicit = [
    # Around the PCB (very fine)
    0.00,
    0.05,
    0.10,
    0.15,
    0.20,
    0.25,
    0.30,
    0.35,
    0.40,
    0.50,
    0.60,
    0.70,
    0.80,
    0.90,
    1.00,
    1.10,
    1.20,
    1.30,
    1.40,
    1.50,
    1.60,

    # Above the PCB
    1.80,
    2.00,
    2.20,
    2.50,
    2.80,
    3.10,
    3.50,
    4.00,
    4.50,
    5.00,
    5.50,
    6.00,
    6.50,
    7.00,
    7.50,
    8.00,
    9.00,
    10.0,
    11.0,
    12.0,
    13.0,
    14.0,
    15.0,
    16.0,
    18.0,
    20.0,
    22.0,
    24.0,
    25.0
]
z_lines.update(z_explicit)
z_lines = sorted(z_lines)
mesh.AddLine('z', z_lines)

print(f"X mesh lines: {len(x_lines)}")
print(f"Y mesh lines: {len(y_lines)}")
print(f"Z mesh lines: {len(z_lines)}")
print(f"Estimated mesh cells: {(len(x_lines)-1)*(len(y_lines)-1)*(len(z_lines)-1):,}")

# ═══════════════════════════════════════════════════════════════════════
# 7. PORTS — microstrip line ports (MSL), propagating in +/-x, E-field in z
# ═══════════════════════════════════════════════════════════════════════
port_meas_shift = feed_len / 3.0   # mm, distance from port plane to S-param ref plane

ports = []

# Port 1: excited, propagates in +x direction into the filter
# NOTE: prop_dir and exc_dir are positional-only in the Cython binding —
# passing them as keywords raises "takes at least 6 positional arguments".
port1 = FDTD.AddMSLPort(
    1, copper,
    [feed1_x0, feed1_y0, z_top],
    [feed1_x0 + 0.1, feed1_y1, 0],   # thin slice at the line's outer end, full substrate height
    'x', 'z',
    excite=1,
    FeedShift=feed_len/4.0,
    MeasPlaneShift=port_meas_shift,
    priority=50
)
ports.append(port1)

# Port 2: passive (excite=0), propagates in -x direction
port2 = FDTD.AddMSLPort(
    2, copper,
    [feed2_x1, feed2_y0, z_top],
    [feed2_x1 - 0.1, feed2_y1, 0],
    'x', 'z',
    excite=0,
    FeedShift=feed_len/4.0,
    MeasPlaneShift=port_meas_shift,
    priority=50
)
ports.append(port2)

# ═══════════════════════════════════════════════════════════════════════
# 9. NF2FF (not required for a 2-port filter, skipped) — write geometry,
#    run solver, post-process
# ═══════════════════════════════════════════════════════════════════════
CSX_file = os.path.join(Sim_Path, Sim_CSX)
CSX.Write2XML(CSX_file)
print(f"\nGeometry written to: {CSX_file}")
print("Inspect it first with:")
print(f"  AppCSXCAD {CSX_file}")
print("(if blank/crashes under native Wayland: GDK_BACKEND=x11 AppCSXCAD <file>)\n")

RUN_SIM = '--run' in sys.argv
if not RUN_SIM:
    print("Dry run only — geometry + mesh + ports built and written to XML.")
    print("Re-run with --run to start the FDTD solver:")
    print(f"  python3 {os.path.basename(__file__)} --run")
    sys.exit(0)

print("Starting FDTD solver (this will take 30-90+ minutes)...")
FDTD.Run(
    Sim_Path,
    cleanup=False,
    verbose=3,
    engine="multithreaded",
    numThreads=12,
)

# ═══════════════════════════════════════════════════════════════════════
# 10. POST-PROCESSING
# ═══════════════════════════════════════════════════════════════════════
freq = np.linspace(f_start, f_stop, 401)

port1.CalcPort(Sim_Path, freq)
port2.CalcPort(Sim_Path, freq)

print("Port1 attributes:")
print([x for x in dir(port1) if not x.startswith("_")])

print("\nPort2 attributes:")
print([x for x in dir(port2) if not x.startswith("_")])

s11 = port1.uf_ref / port1.uf_inc

# Candidate 1
s21_a = port2.uf_ref / port1.uf_inc

# Candidate 2
s21_b = port2.uf_inc / port1.uf_inc     # uses incident wave at port 1 vs reflected/transmitted wave at port 2

s11_dB = 20*np.log10(np.maximum(np.abs(s11), 1e-12))
s21a_dB = 20*np.log10(np.maximum(np.abs(s21_a), 1e-12))
s21b_dB = 20*np.log10(np.maximum(np.abs(s21_b), 1e-12))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(11, 6))
ax.plot(freq/1e6, s11_dB, '#c0392b', lw=1.8, label='S11 (openEMS)')
ax.plot(freq/1e6, s21a_dB, "#2bc046", label="S21 candidate A")
ax.plot(freq/1e6, s21b_dB, "#2bc046", label="S21 candidate B")
ax.axvspan((868-5), (868+5), alpha=0.08, color='#1a6fb5')
ax.axvline(868, color='#aaa', lw=0.8, ls='-.')
ax.axhline(-2, color='#1a6fb5', lw=0.7, ls=':', alpha=0.7)
ax.axhline(-20, color='#c0392b', lw=0.7, ls=':', alpha=0.7)
ax.set_xlabel('Frequency (MHz)')
ax.set_ylabel('Magnitude (dB)')
ax.set_ylim(-60, 5)
ax.set_title('Hairpin BPF — Stage 3 openEMS FDTD result')
ax.legend()
ax.grid(True, alpha=0.3, ls='--')
plt.tight_layout()
plt.savefig(os.path.join(Sim_Path, 'stage3_response.png'), dpi=180)
print(f"\n[saved] {Sim_Path}/stage3_response.png")

# Touchstone export (plain text, no external dependency)
s2p_path = os.path.join(Sim_Path, 'stage3_network.s2p')
with open(s2p_path, 'w') as f:
    f.write("# Hz S RI R 50\n")
    for k, fk in enumerate(freq):
        f.write(f"{fk:.6e} {s11[k].real:.6e} {s11[k].imag:.6e} "
                f"{s21[k].real:.6e} {s21[k].imag:.6e} "
                f"{s21[k].real:.6e} {s21[k].imag:.6e} "
                f"{s11[k].real:.6e} {s11[k].imag:.6e}\n")
print(f"[saved] {s2p_path}")

fc_idx = np.argmin(np.abs(freq - 868e6))
print(f"\nS21 @ 868 MHz = {s21_dB[fc_idx]:.2f} dB")
print(f"S11 @ 868 MHz = {s11_dB[fc_idx]:.2f} dB")
print("\nStage 3 complete.")