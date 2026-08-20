# AI_REASONING

Complex reasoning and decisions worth remembering for future sessions on this project.

## Why trapezoidal integration for the frequency axis

`f1_hz` and `f2_hz` were chosen by the user to land exactly on two adjacent discrete bins of the
model's logarithmically-spaced `freq` array (index 3 and 4 of 30). With only 2 data points in the
band, there is no way to do a higher-order (e.g. Simpson's) integration; the two realistic options
were:
1. Trapezoidal integration between the two bin centers (`(f2-f1) * (S(f1)+S(f2))/2`).
2. A "band-sum" convention common in ocean wave modeling, where each discrete frequency bin
   represents a band of width equal to half the distance to its two neighbors, and one *sums*
   `S(f_i) * df_i` over the bins that fall inside `[f1, f2]` — this would require also reading
   neighboring bins (index 2 and 5) to compute `df_3` and `df_4`.

The user chose option 1 (trapezoidal) for simplicity and because it matches the shape of the
continuous integral in the original formula more directly. This is documented in `AGENTS.md`,
`DOCUMENTATION.md`, and decided explicitly with the user on 2026-08-18 — if a different frequency
band is chosen later (e.g. one spanning more than 2 discrete bins), this integration method should
be revisited (`np.trapezoid` naturally extends to more points, so the code itself does not need to
change, only this assumption should be re-examined for a wider band).

## Why the direction integral is a plain rectangle-rule sum

The 24 direction bins are uniformly spaced (15 degrees each) and cover the full 360-degree circle.
For a periodic function sampled on a uniform grid over exactly one period, the rectangle/midpoint
rule is *exact* for band-limited functions (this is the basis of the discrete Fourier transform /
trapezoidal rule equivalence on a periodic domain) — there is no benefit to a more complex scheme
here, and using one would add complexity without improving accuracy.

## Why 00_fetch_spectra.py subsets before saving locally

The full daily spectra file is ~2 GB (30 frequency bins x 24 directions x 28713 points x 24 hours).
Since only 2 frequency bins are needed for this frequency band, selecting them via OPeNDAP
(`ds.sel(freq=[f1, f2], method="nearest")`) *before* loading into memory reduces the transferred
data to ~130 MB, without any loss of information relevant to this calculation. If a different,
wider frequency band is chosen in the future, this subsetting step should be revisited (it may
need to select more than 2 bins, and downstream code assumes exactly 2 — see `compute_ewh()`'s
assertions in `01_compute_ewh.py`).

## Known limitation: contour plot projection

Documented in `README.md` and `DOCUMENTATION.md` section 5. Flagged to the user but not fixed in
this iteration (would need a new dependency, `cartopy`, and a discussion). Revisit if the user
wants publication-quality maps or asks about the odd shape/extent of the contour plots.

## Resolved: contour plot projection and Delaunay bridge artifacts

Followed up on the item above: user approved adding `cartopy` and using `NorthPolarStereo()`.
After switching projections, a second, distinct artifact remained: large purple background
patches over land regions with no data (e.g. Canada, Siberia), far outside the real grid
footprint. Investigated by plotting a raw lon/lat scatter of all 28713 points, confirming the
NORA3 grid is a dense, near-global Northern Hemisphere ocean grid, shaped like a multi-armed
star/cross due to separate ocean basins (Atlantic/Pacific/Arctic) split by continents, with land
points genuinely absent from the grid (not just NaN-filled).

Root cause: `tricontourf`'s default Delaunay triangulation always fills the *entire convex hull*
of the input points. On a non-convex domain (several disconnected ocean-basin branches), this
creates spurious long "bridge" triangles connecting distant, unrelated points (e.g. Norway to
Alaska) — a well-known limitation of naive Delaunay-based contouring.

Quantified the fix: computed the edge-length distribution of the raw triangulation in projected
(stereographic, meters) coordinates. Found median edge length ~39 km, 95th percentile ~54.5 km,
then a sharp jump to ~228 km at the 99th percentile — a clean, well-separated gap between real
grid edges and bridge artifacts. Chose `MAX_EDGE_LENGTH_FACTOR = 3.0` (median x 3 ~ 118 km cutoff)
as a threshold safely between the 95th and 99th percentiles, giving a wide margin on both sides.
Implemented as `build_masked_triangulation()`: builds a `matplotlib.tri.Triangulation` on
projected coordinates, computes each triangle's longest edge, and masks out any triangle above
the threshold before passing to `tricontourf`.

Verified visually: the resulting plots show the correct ocean-basin shapes (e.g. Iceland renders
as a hole in the color field, Canadian Arctic archipelago channels are correctly excluded), with
no more spurious background patches over unrelated land regions. Also hit and fixed a secondary
issue: `ax.gridlines(draw_labels=True, ...)` crashes near the pole in `NorthPolarStereo`
(`shapely.errors.GEOSException`); resolved with `draw_labels=False`.

This is considered fully resolved; `README.md`/`DOCUMENTATION.md` updated to describe the
solution instead of listing it as an open limitation.
