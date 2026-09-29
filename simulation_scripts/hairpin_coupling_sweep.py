"""
hairpin_coupling_sweep.py

Sweeps the gap between two identical hairpin resonators in openEMS,
extracts S21, finds the two split resonant peaks, and computes the
coupling coefficient k = (f2^2 - f1^2) / (f2^2 + f1^2) for each gap.

Requirements: openEMS + CSXCAD python bindings (pyEMS / openEMS-Python),
numpy, scipy, matplotlib.

>>> EDIT THE "USER PARAMETERS" SECTION BEFORE RUNNING <<<
The hairpin dimensions below are placeholders. Tune a SINGLE hairpin
resonator first (separate sim) to hit 868 MHz, then plug those final
dimensions in here.
"""

import os
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks

from CSXCAD import ContinuousStructure
from openEMS import openEMS
from openEMS.physical_constants import C0

# ----------------------------------------------------------------------
# USER PARAMETERS
# ----------------------------------------------------------------------
f0          = 868e6        # center frequency (Hz)
fc          = 400e6        # excitation bandwidth (Hz), gaussian pulse around f0
f_start     = 600e6
f_stop      = 1200e6

# Substrate (FR4)
substrate_epsR   = 4.4
substrate_kappa  = (2*np.pi*f0) * substrate_epsR * 8.854e-12 * 0.02   # from tan_delta = 0.02
substrate_thick  = 1.6      # mm
copper_thick     = 0.035    # mm (35 um)

# Hairpin resonator geometry (PLACEHOLDERS -- replace with your tuned values)
# Hairpin = U-shaped half-wavelength line folded into 3 segments.
line_w      = 3.0      # microstrip line width (mm) for ~50 ohm on this substrate
hp_arm_len  = 18.0      # length of each of the two parallel arms (mm)
hp_arm_gap  = 1.5       # gap between the two arms of ONE hairpin (mm)
hp_top_len  = 2*line_w + hp_arm_gap   # length of the connecting top segment (mm)

# Feed / tap configuration: weakly coupled microstrip feed lines, offset
# (tapped) partway down the outer arm, with a small series gap (probe
# coupling) so the ports don't heavily load the resonators.
feed_w        = line_w
feed_len      = 8.0     # mm, length of feed stub running toward resonator
feed_gap      = 0.3     # mm, coupling gap between feed stub end and resonator arm
feed_tap_pos  = 6.0      # mm, distance from the bottom of the arm where the feed couples in

# Inter-resonator gap sweep
gap_list = [0.5, 0.8, 1.2, 1.6, 2.0, 2.5, 3.0, 4.0]   # mm, EDIT to your range

# Mesh resolution
mesh_res = 0.2  # mm, finest mesh cell near metal edges

# Simulation domain margin
air_margin = 15.0  # mm padding above/around the structure

base_path = './sim_hairpin_coupling'


# ----------------------------------------------------------------------
# Geometry builder for one hairpin resonator centered at (x0, y0)
# Orientation: hairpin opens upward (arms run in +y), top bar at +y end.
# Returns list of polygon point arrays placed onto a CSX metal property.
# ----------------------------------------------------------------------
def add_hairpin(csx, metal_prop, x0, y0, mirror=False):
    sign = -1 if mirror else 1
    half_gap = hp_arm_gap / 2.0

    # Left arm (vertical strip)
    x_left_c = x0 - sign * half_gap - sign * (line_w/2.0)
    metal_prop.AddBox(priority=10,
        start=[x_left_c - line_w/2.0, y0, copper_thick],
        stop =[x_left_c + line_w/2.0, y0 + hp_arm_len, copper_thick])

    # Right arm (vertical strip)
    x_right_c = x0 + sign * half_gap + sign * (line_w/2.0)
    metal_prop.AddBox(priority=10,
        start=[x_right_c - line_w/2.0, y0, copper_thick],
        stop =[x_right_c + line_w/2.0, y0 + hp_arm_len, copper_thick])

    # Top connecting bar
    xmin = min(x_left_c, x_right_c) - line_w/2.0
    xmax = max(x_left_c, x_right_c) + line_w/2.0
    metal_prop.AddBox(priority=10,
        start=[xmin, y0 + hp_arm_len - line_w/2.0, copper_thick],
        stop =[xmax, y0 + hp_arm_len + line_w/2.0, copper_thick])

    return x_left_c, x_right_c, y0


def run_one_gap(gap_mm):
    sim_path = os.path.join(base_path, f'gap_{gap_mm:.3f}mm')
    os.makedirs(sim_path, exist_ok=True)

    FDTD = openEMS(EndCriteria=1e-5)
    FDTD.SetGaussExcite((f_start+f_stop)/2, (f_stop-f_start)/2)
    FDTD.SetBoundaryCond(['MUR', 'MUR', 'MUR', 'MUR', 'PEC', 'MUR'])  # PEC at bottom = ground plane side handled via metal layer instead if using full 3D; adjust per your setup

    CSX = ContinuousStructure()
    FDTD.SetCSX(CSX)
    mesh = CSX.GetGrid()
    mesh.SetDeltaUnit(1e-3)  # mm

    # ---- Substrate ----
    substrate = CSX.AddMaterial('FR4', epsilon=substrate_epsR, kappa=substrate_kappa)
    sub_xmin, sub_xmax = -25 - gap_mm, 25 + gap_mm
    sub_ymin, sub_ymax = -5, hp_arm_len + 15
    substrate.AddBox(priority=0,
        start=[sub_xmin, sub_ymin, 0],
        stop =[sub_xmax, sub_ymax, substrate_thick])

    # ---- Ground plane ----
    gnd = CSX.AddMetal('GND')
    gnd.AddBox(priority=5,
        start=[sub_xmin, sub_ymin, 0],
        stop =[sub_xmax, sub_ymax, 0])

    # ---- Top metal (hairpins + feeds) ----
    metal = CSX.AddMetal('Copper')

    # place hairpin 1 (left), hairpin 2 (right), separated by gap_mm
    # x positions: centers separated such that closest arms are gap_mm apart
    res_half_width = hp_arm_gap/2.0 + line_w  # outer edge offset from hairpin center x0
    x0_1 = -(gap_mm/2.0 + res_half_width)
    x0_2 = +(gap_mm/2.0 + res_half_width)
    y0 = 0

    add_hairpin(CSX, metal, x0_1, y0, mirror=False)
    add_hairpin(CSX, metal, x0_2, y0, mirror=True)

    # ---- Weakly coupled feed lines + lumped ports ----
    port_z = substrate_thick
    ports = []

    # Port 1: feed stub coupled to outer (left) arm of hairpin 1
    feed1_x = x0_1 - res_half_width - feed_gap - feed_w/2.0
    metal.AddBox(priority=10,
        start=[feed1_x - feed_w/2.0, feed_tap_pos, copper_thick],
        stop =[feed1_x + feed_w/2.0, feed_tap_pos + feed_len, copper_thick])
    p1 = FDTD.AddLumpedPort(1, 50, [feed1_x - feed_w/2.0, feed_tap_pos + feed_len, 0],
                             [feed1_x + feed_w/2.0, feed_tap_pos + feed_len, substrate_thick],
                             'z', 1.0, priority=5, edges2grid='xy')
    ports.append(p1)

    # Port 2: feed stub coupled to outer (right) arm of hairpin 2
    feed2_x = x0_2 + res_half_width + feed_gap + feed_w/2.0
    metal.AddBox(priority=10,
        start=[feed2_x - feed_w/2.0, feed_tap_pos, copper_thick],
        stop =[feed2_x + feed_w/2.0, feed_tap_pos + feed_len, copper_thick])
    p2 = FDTD.AddLumpedPort(2, 50, [feed2_x - feed_w/2.0, feed_tap_pos + feed_len, 0],
                             [feed2_x + feed_w/2.0, feed_tap_pos + feed_len, substrate_thick],
                             'z', 1.0, priority=5, edges2grid='xy')
    ports.append(p2)

    # ---- Mesh ----
    mesh.AddLine('x', np.arange(sub_xmin-air_margin, sub_xmax+air_margin+1e-9, mesh_res))
    mesh.AddLine('y', np.arange(sub_ymin-air_margin, sub_ymax+air_margin+1e-9, mesh_res))
    mesh.AddLine('z', [0, substrate_thick, substrate_thick+air_margin])
    mesh.SmoothMeshLines('all', mesh_res, ratio=1.4)

    # ---- Air box / open boundary ----
    CSX.AddBox(priority=0, start=[sub_xmin-air_margin, sub_ymin-air_margin, -air_margin],
               stop=[sub_xmax+air_margin, sub_ymax+air_margin, substrate_thick+air_margin])

    CSX.Write2XML(os.path.join(sim_path, 'hairpin.xml'))

    FDTD.Run(sim_path, cleanup=True)

    freq = np.linspace(f_start, f_stop, 1601)
    p1.CalcPort(sim_path, freq)
    p2.CalcPort(sim_path, freq)
    s21 = p2.uf_ref / p1.uf_inc
    return freq, s21


def extract_split_freqs(freq, s21):
    mag_db = 20*np.log10(np.abs(s21) + 1e-12)
    peaks, _ = find_peaks(mag_db, prominence=3)
    if len(peaks) < 2:
        # gap too tight (modes merged) or too loose (one mode buried)
        return None, None
    # take the two strongest peaks
    peaks_sorted = peaks[np.argsort(mag_db[peaks])[::-1]][:2]
    f_peaks = sorted(freq[peaks_sorted])
    return f_peaks[0], f_peaks[1]


def main():
    results = []
    for g in gap_list:
        print(f'--- Running gap = {g} mm ---')
        freq, s21 = run_one_gap(g)
        f1, f2 = extract_split_freqs(freq, s21)
        if f1 is None:
            print(f'  Could not resolve two peaks at gap={g} mm (modes merged or too weak).')
            results.append((g, np.nan))
            continue
        k = (f2**2 - f1**2) / (f2**2 + f1**2)
        print(f'  f1={f1/1e6:.2f} MHz  f2={f2/1e6:.2f} MHz  k={k:.5f}')
        results.append((g, k))

    results = np.array(results)
    np.savetxt(os.path.join(base_path, 'k_vs_gap.csv'), results,
               delimiter=',', header='gap_mm,k', comments='')

    plt.figure()
    plt.semilogy(results[:, 0], np.abs(results[:, 1]), 'o-')
    plt.xlabel('Inter-resonator gap (mm)')
    plt.ylabel('|Coupling coefficient k|')
    plt.title('Hairpin coupling vs spacing @ 868 MHz')
    plt.grid(True, which='both')
    plt.savefig(os.path.join(base_path, 'k_vs_gap.png'), dpi=150)
    plt.show()


if __name__ == '__main__':
    main()
