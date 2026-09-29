# 5-Pole Hairpin Microstrip BPF — 868 MHz — MONKEY MODE GUIDE
## Zero assumed knowledge. Every click. Every number. Do it exactly in order.

Specs locked in: f0 = 868 MHz, BW = 10 MHz, N = 5, FR4 board 1.6mm thick, 1oz copper, from JLCPCB.
Two builds: **Build A = plain hairpin (do this one first, get it working, this is the important one)**. **Build B = same filter + DGS slots (do this after A works)**.

Do not skip steps. Do not "just eyeball it." Every number below is either calculated or has a clear instruction on how to get the real number from CST.

---

# PART 0 — Things to have open/ready before you touch CST

1. CST Studio Suite 2019, installed, opens without crashing.
2. A calculator or Excel, for the tiny bits of arithmetic in Part 3.
3. This document, obviously.
4. Coffee. This will take several sittings.

---

# PART 1 — The numbers you need before opening CST at all

These come from filter theory. You don't need to re-derive them, just copy them down somewhere you'll keep referring back to (sticky note, top of your CST project notes, whatever).

### 1.1 Write these down. These are your ONLY targets. Nothing else matters until you hit these.

```
f0        = 868 MHz     (center frequency)
BW        = 10 MHz      (bandwidth)
FBW       = 0.01152     (= BW/f0, just a ratio, no units)

Qe1       = 99.6        (input coupling target)
Qe5       = 99.6        (output coupling target — same number, filter is symmetric)

M12       = 0.00919     (coupling between resonator 1 and 2)
M23       = 0.00700     (coupling between resonator 2 and 3)
M34       = 0.00700     (coupling between resonator 3 and 4 — same as M23)
M45       = 0.00919     (coupling between resonator 4 and 5 — same as M12)
```

Where did these come from? Standard Chebyshev filter tables (0.1dB ripple, N=5) plus two formulas:
`Qe = g0*g1/FBW` and `M(i,i+1) = FBW/sqrt(gi*g(i+1))`. You don't need to redo this — it's done. Just trust these six numbers. Everything you do in CST for the next several hours is aimed at making the simulated filter's behavior match these six numbers.

### 1.2 Substrate numbers. Write these down too.

```
Material       = FR4
Thickness (h)  = 1.6 mm
Copper (t)     = 0.035 mm   (this is what "1 oz copper" means, always, memorize it)
er (dielectric constant) = 4.3
tan d (loss)   = 0.02
```

### 1.3 Starting geometry numbers (calculated by hand, you will REFINE these in CST, they are not final)

```
50-ohm line width (W)        = 3.1 mm
Quarter-wave resonator length = 47.8 mm   (before folding into a U shape)
```

Do not build the filter with these numbers and call it done. These are STARTING POINTS ONLY. Read Part 3 and 4 for why and how you refine them.

---

# PART 2 — Set up the CST project (click by click)

1. Open CST Studio Suite 2019.
2. Click **New Project**.
3. In the wizard: pick **MW & RF & Optical** → **Circuits & Components** is wrong, you want **Planar** or **General Microwave & RF** — pick **"Microstrip Filter"** template if the wizard offers it directly. If it does NOT offer that exact template on your install, instead pick a **blank Microwave Studio (MWS) template** — this is fine, you're building the geometry by hand anyway.
4. Units: set to **mm** for length, **GHz** for frequency, **ns** for time. Do this in the wizard screen, or afterwards via **Home tab → Units**.
5. Frequency range: set **Fmin = 0.7 GHz, Fmax = 1.05 GHz**. This gives you room to see the skirts on both sides of the passband. Do this on the wizard's frequency page, or later via **Simulation tab → Frequency**.
6. Background material: leave as **Normal**.
7. Boundary conditions (Simulation tab → Boundaries, or the wizard boundary page): set **all six faces (Xmin, Xmax, Ymin, Ymax, Zmin, Zmax) to "open (add space)"**. This tells CST "let energy radiate away instead of bouncing off walls," which is correct for a microstrip filter sitting in free space above a ground plane.
8. Click **Finish**. You now have an empty 3D project.

---

# PART 3 — Get the REAL 50-ohm line width using CST's built-in calculator (don't trust the hand calc alone)

1. In CST, go to **Home tab → Macros → Line Calc** (some versions: **Home → Design → Line Calc**, or it's under **Tools**). If you can't find it, search "Line Calc" in the CST search box (top right magnifying glass icon).
2. In the Line Calc window, set **Component: Microstrip**.
3. Under Substrate parameters, enter:
 - Er = 4.3
 - H (substrate height) = 1.6 mm
 - T (conductor thickness) = 0.035 mm
 - Tan Delta = 0.02
4. Under Electrical/Physical, you'll see two modes: **Analysis** (geometry → impedance) or **Synthesis** (impedance → geometry). Pick **Synthesis**.
5. Enter **Z0 = 50 ohm**, **Frequency = 0.868 GHz**.
6. Click **Synthesize** (or equivalent calculate button).
7. Read off the **W (width)** value it gives you. It should be close to our hand-calculated 3.1 mm — if it's wildly different (like off by more than 20%), you typed something wrong, go back and check.
8. **Write down the exact W value CST gives you.** This is your real feed line width going forward, more accurate than the hand calc.

---

# PART 4 — Build and tune ONE hairpin resonator by itself (do not build all 5 yet)

You're building a single "U" shaped piece of copper and finding the exact length that makes it resonate at 868 MHz. Do this before touching the full filter.

### 4.1 Draw the substrate and ground plane

1. Go to **Modeling tab → Shapes → Brick**.
2. Draw a brick for the substrate: 
 - Xrange: -20 to 20 mm (40mm wide, plenty of room)
 - Yrange: -20 to 20 mm
 - Zrange: 0 to 1.6 mm
 - Material: click "New Material", name it **FR4_custom**, set Epsilon = 4.3, Tan Delta (electric) = 0.02, click OK.
3. Draw another brick for the ground plane:
 - Same X/Y range as substrate
 - Zrange: -0.035 to 0 mm (sits right under the substrate, thickness = your copper thickness)
 - Material: use **Copper (annealed)** from CST's material library (search "copper" in material list — pick the lossy one, not PEC, so your loss numbers are realistic).

### 4.2 Draw ONE hairpin resonator on top

This is a U-shape: two straight arms connected by a bend, with total developed (unfolded) length ≈ your quarter-wave length from Part 1.3, adjusted once you tune it.

1. Go to **Modeling tab → Shapes → Polygon** (or build it from bricks — three rectangular bricks: arm 1, bend/bottom piece, arm 2, all connected — bricks are easier for a beginner than a polygon).
2. Build it as 3 bricks on the top of the substrate (Z = 1.6 to 1.635 mm, i.e. sitting on top, thickness = 0.035mm copper):
 - **Arm 1**: a rectangle, width = W (your Line Calc value, e.g. 3.1mm), length ≈ 20mm, running in the Y direction.
 - **Bottom/bend piece**: a rectangle connecting the bottom of arm 1 to the bottom of arm 2, width = W, running in the X direction, length = your chosen fold gap (start with **fold gap = 6mm center-to-center**, meaning this bottom piece is about 6mm long between the arm centerlines).
 - **Arm 2**: mirror of arm 1, parallel to it, 6mm away (center to center), same length ≈20mm, running in Y direction, connected to the other end of the bottom piece.
3. Total copper length end-to-end following the path = arm1 + bottom + arm2. Adjust the individual arm lengths so this total is close to 47.8mm to start. Example split: arm1 = 21mm, bottom = 5.8mm, arm2 = 21mm ≈ 47.8mm total (numbers are illustrative — just make the sum land near 47.8mm).
4. Material for these 3 bricks: same lossy copper as the ground plane.
5. Use **Boolean → Add** (Modeling tab) to merge the 3 bricks into a single solid called "Resonator1" — otherwise CST treats them as separate touching objects which can cause meshing headaches.

### 4.3 Add two weakly-coupled test feed lines (so you can "see" the resonance without loading it down)

1. Draw a straight microstrip line (brick, width = W, thickness 0.035mm, on top of substrate) that runs toward the open end of Arm 1 but **does NOT touch it** — leave a gap of about **2.5mm** between the end of this feed line and the resonator. This gap is deliberately large — you want WEAK coupling right now so the resonance peak you observe is close to the resonator's true unloaded resonance, not shifted by heavy loading.
2. Do the same on the other side (near Arm 2's open end), another feed line, another 2.5mm gap.
3. Each feed line should run out to the edge of your simulation box (X or Y = ±20mm boundary) so you can put a port there.

### 4.4 Add ports

1. Go to **Modeling tab → Ports → Waveguide Port** (or Discrete Port if waveguide port setup is fiddly — discrete port referenced to the ground plane is simpler for a beginner).
2. Place one port at the outer end of each feed line.
3. Set port impedance reference to 50 ohm if using discrete ports.

### 4.5 Run the simulation

1. Go to **Simulation tab → Solvers → Frequency Domain Solver**.
2. Click **Setup Solver**, leave defaults mostly, but under Mesh, choose **Tetrahedral, Adaptive**.
3. Click **Start**.
4. Wait. On a narrowband high-Q structure like this, adaptive meshing may take several passes (CST re-meshes and re-runs until S-parameters stop changing much between passes — this is normal, let it finish, don't cancel early).
5. When done, go to **1D Results → S-Parameters** and plot **S21 (dB)**.

### 4.6 Read the resonance and tune

1. Look at the S21 plot. You should see a peak (resonance) somewhere near 868 MHz — maybe not exactly on it yet.
2. If the peak is **below** 868 MHz → your resonator is too LONG electrically → shorten the arm lengths slightly (try -1mm total, re-run).
3. If the peak is **above** 868 MHz → your resonator is too SHORT → lengthen the arms slightly (+1mm total, re-run).
4. Repeat: adjust length, re-run, check peak, until the peak sits at 868 MHz ± 1MHz.
5. **Write down this final arm length and total resonator length. This is now your locked-in "L_res" for ALL FIVE resonators in the real filter.** All 5 hairpins in the final filter use this same tuned length (they're identical resonators by design).

You just did the hardest conceptual part. Everything below reuses this same tuned resonator shape, five times, with different gaps between them.

---

# PART 5 — Find the gap distances for each coupling (M12, M23, M34, M45)

You need FOUR gap numbers: gap for M12 (=M45, same number reused twice) and gap for M23 (=M34, same number reused twice). So really only **two distinct gap-vs-coupling curves** to generate.

### 5.1 Build a 2-resonator test pair

1. Duplicate your tuned Resonator1 from Part 4 (**Modeling tab → Transform → Translate**, copy it).
2. Place the copy next to the original, separated by a gap. Orient them the standard hairpin-filter way: side by side, open ends adjacent (this is the typical hairpin coupling orientation — arms facing each other across the gap).
3. Remove the test feed lines from Part 4 for this step — OR keep them very weakly coupled (2.5mm+ gap) at the far outer ends only, just enough to excite/observe the pair without swamping the coupling measurement.
4. Set the gap between the two resonators to a **parameter**, not a fixed number: Modeling tab → right click the dimension → **"New Parameter"**, name it `Gap_test`, starting value **1.5mm**.

### 5.2 Run Eigenmode solver (or frequency domain, either works, eigenmode is cleaner for this)

1. Simulation tab → Solvers → **Eigenmode Solver**.
2. Set it to find the **first 2 modes** near 868 MHz.
3. Run it.
4. You'll get two frequencies: **f1 (lower, even mode)** and **f2 (higher, odd mode)**.

### 5.3 Calculate coupling coefficient k from these two numbers

```
k = (f2^2 - f1^2) / (f2^2 + f1^2)
```

Do this in your calculator/Excel with the actual f1, f2 numbers CST gives you (in GHz or MHz, doesn't matter as long as both are the same unit).

### 5.4 Sweep the gap and build a lookup table

1. Use **Parameter Sweep** (Simulation tab → Parameter Sweep, or right-click `Gap_test` → Parameter Sweep).
2. Sweep `Gap_test` across several values: **0.5, 1.0, 1.5, 2.0, 2.5, 3.0 mm**.
3. For EACH value, run the eigenmode solver, get f1/f2, compute k (Part 5.3).
4. Build yourself a little table like this (example numbers — yours will differ, fill in real ones):

```
Gap (mm)  |  k
0.5       |  0.0180
1.0       |  0.0130
1.5       |  0.0092
2.0       |  0.0065
2.5       |  0.0048
3.0       |  0.0035
```

5. You want the gap where **k = 0.00919** (your M12/M45 target) — interpolate between your table rows to find it. In the fake example above, that's right around Gap = 1.5mm.
6. Now do the WHOLE THING AGAIN (Part 5.1-5.5) but this time orient the resonator pair the way resonators 2-3 (or 3-4) will actually sit in the real filter — if their physical orientation/coupling type differs from the 1-2 pair, the gap-vs-k curve will be different, so don't reuse the same curve blindly. Find the gap where **k = 0.00700** (your M23/M34 target).

**Write down both final gap values.** Call them `Gap_12` (used between resonators 1-2 and between 4-5) and `Gap_23` (used between resonators 2-3 and between 3-4).

---

# PART 6 — Find the I/O tap/gap distance for Qe = 99.6

1. Take your single tuned resonator from Part 4, WITH one feed line (just one, not two — you're measuring input coupling alone).
2. Make the feed-to-resonator gap a parameter, call it `Tap_gap`, starting value 1mm.
3. Run **Frequency Domain solver**, look at **S11 (dB)** near 868 MHz — you'll see a dip (resonance).
4. Find the **-3dB bandwidth** of that dip: the two frequencies on either side of the dip where S11 has come back up by 3dB from its minimum. Call these f_low and f_high.
5. Calculate loaded Q: **Qe = f0 / (f_high - f_low)**, using f0=0.868GHz and the bandwidth in the same units.
6. If Qe is too HIGH (weaker coupling than needed) → DECREASE `Tap_gap` (bring feed line closer) → tighter coupling → lower Qe.
7. If Qe is too LOW → INCREASE `Tap_gap`.
8. Repeat: adjust, re-run, recalculate Qe, until Qe = 99.6 ± a few percent.
9. **Write down this final Tap_gap value.** Used identically on both the input (resonator 1) and output (resonator 5) sides.

---

# PART 7 — Assemble the FULL 5-resonator filter

Now you have every number you need:

```
L_res    = [from Part 4.6]
Gap_12   = [from Part 5, used between resonators 1-2 AND 4-5]
Gap_23   = [from Part 5, used between resonators 2-3 AND 3-4]
Tap_gap  = [from Part 6, used at input near resonator 1 AND output near resonator 5]
W        = [from Part 3, the 50-ohm feed line width]
```

1. Start a fresh CST project (or clean up your test project), same substrate/ground plane/boundary/frequency setup as Part 2.
2. Place 5 copies of your tuned hairpin resonator (Part 4) in a row.
3. Space resonator 1↔2 by `Gap_12`. Space 2↔3 by `Gap_23`. Space 3↔4 by `Gap_23`. Space 4↔5 by `Gap_12`. (Symmetric filter, as expected from your symmetric g-values.)
4. Add the input feed line near resonator 1, spaced by `Tap_gap`, running out to a port at the box edge.
5. Add the output feed line near resonator 5, spaced by `Tap_gap`, running out to a port at the box edge.
6. Boolean-add everything into sensible named solids so meshing behaves (substrate, ground, and each resonator/feedline as separate solids is fine — just make sure each individual resonator's 3 bricks are merged like you did in Part 4.2).
7. Make ALL of these into CST **Parameters** if you haven't already (Gap_12, Gap_23, Tap_gap, L_res, W) — this is essential for Part 8.

### 7.1 Run it

1. Frequency Domain Solver, same settings as before, frequency range 0.7-1.05GHz.
2. Plot S21 and S11.
3. Compare against target: passband centered at 868MHz, 10MHz wide, S11 better than about -12dB across that band.

It will probably NOT be perfect on the first try. That's expected and normal. Proceed to Part 8.

---

# PART 8 — Optimize (let CST fix the small errors for you)

1. Simulation tab → **Optimizer**.
2. Add goals:
 - S11 < -12 dB from 863 to 873 MHz
 - S21 peak/center at 868 MHz
3. Select which parameters the optimizer is allowed to change: `Gap_12`, `Gap_23`, `Tap_gap`, and optionally `L_res` by a very small range (±0.3mm) — don't let it change L_res a lot, since you already tuned that carefully, you're just letting it nudge for the mutual loading effect of the full assembled filter (which shifts things slightly vs. the isolated single-resonator test).
4. Set reasonable bounds for each parameter: e.g. ±0.5mm around your Part 5/6 values.
5. Choose algorithm: **Trust Region Framework** first (fast). If it doesn't converge to something acceptable after a reasonable number of iterations, switch to **Genetic Algorithm** (slower, more thorough, better at escaping if Trust Region gets stuck).
6. Click Start. Let it run — this can take a while (each iteration is a full EM simulation).
7. When done, apply the best result found and re-run the full solver once more to confirm the final S-parameters.

**When you hit spec (10MHz passband centered at 868MHz, decent return loss), Build A is DONE.** This is your main, most important deliverable. Save this project file separately and clearly labeled, e.g. `HairpinBPF_868MHz_NoDGS_FINAL.cst`.

---

# PART 9 — Build B: add DGS (do this only after Build A works)

1. **Save a copy** of your finished Build A project first, rename it something like `HairpinBPF_868MHz_DGS.cst`. Never edit your working no-DGS filter directly.
2. Pick where to put the DGS: underneath the feed lines, or underneath the weaker-coupled resonator pair (2-3 or 3-4) — this is the common placement.
3. Draw the DGS shape (simple dumbbell or U-slot) as a **cut into the ground plane** — you'll need to:
 - Select the ground plane brick.
 - Draw a small shape (two square/rectangular heads connected by a thin slot, for a dumbbell — typical dumbbell dimensions to START with: two 3mm x 3mm squares connected by a 0.5mm x 2mm slot, directly underneath the target microstrip line) positioned at Z=0 (top of ground plane, same Z as the ground plane's top face).
 - Use **Boolean → Subtract**: subtract this small shape from the ground plane brick, so it becomes an actual etched slot/hole in the copper.
4. Re-run Frequency Domain Solver.
5. Compare new S21/S11 against your saved Build A results:
 - Go to **Results → 1D Results**, load both result sets (Build A .cst and Build B .cst) or export both as **Touchstone (.s2p)** files (Results → Export → Touchstone) and overlay them in CST's plot combine tool, or in a spreadsheet.
 - Look specifically at: does the passband stay roughly the same (it should)? Does upper-band rejection improve near the 2nd harmonic (~1.736 GHz, i.e. 2×868MHz)? That's the main thing DGS is expected to help with here.
6. If DGS shifted your passband center frequency, you may need to re-tune `Tap_gap`/`Gap_12`/`Gap_23` slightly, or re-optimize (Part 8 again, on the DGS project) — the DGS slot does perturb the line's characteristic impedance a bit, this is expected.

---

# PART 10 — Export for JLCPCB fabrication

1. On your FINAL Build A (and separately, Build B) project, select just the top copper layer (all 5 resonators + feed lines, one merged solid or selected as a group).
2. **File → Export → 2D/3D → DXF**, export just this top copper shape.
3. Open **KiCad**, import the DXF onto a copper layer of a new 2-layer PCB project.
4. Set the KiCad board stackup: FR4, 1.6mm, 1oz copper top and bottom, standard JLCPCB 2-layer default (this matches JLCPCB's process without needing a custom stackup request).
5. **Double check trace widths after DXF import** — DXF export/import can introduce small unit/rounding errors, so measure a known trace (like your feed line) in KiCad and confirm it still reads as your `W` value from Part 3, fix if it drifted.
6. Add SMA edge-launch connector footprints (or your connector of choice) at both port locations, footprint pad width matched to `W`.
7. Run KiCad's DRC (Design Rule Check), fix anything flagged.
8. Generate Gerbers + drill files using JLCPCB's standard export preset in KiCad (Plot → Gerbers, with JLCPCB-compatible layer set, then Generate Drill Files).
9. Zip the Gerber+drill files, upload to JLCPCB, select 2-layer, 1.6mm thickness, 1oz copper (all JLCPCB defaults, no special stackup needed), order.

---

# CHECKLIST — tick these off in order, don't skip ahead

- [ ] Part 1: numbers written down
- [ ] Part 2: CST project created, units/frequency/boundaries set
- [ ] Part 3: real 50-ohm width from Line Calc
- [ ] Part 4: single resonator built and tuned to 868MHz, L_res locked in
- [ ] Part 5: Gap_12 found (k=0.00919), Gap_23 found (k=0.00700)
- [ ] Part 6: Tap_gap found (Qe=99.6)
- [ ] Part 7: full 5-resonator filter assembled, first run done
- [ ] Part 8: optimizer run, spec met, Build A saved as FINAL
- [ ] Part 9: DGS variant built off a COPY, compared against Build A
- [ ] Part 10: DXF exported, KiCad layout done, Gerbers generated, uploaded to JLCPCB

If you get stuck at any single part, stop there and figure that part out before moving forward — don't build on top of a part that isn't actually working yet, you'll just waste time debugging five compounded problems at once instead of one.
