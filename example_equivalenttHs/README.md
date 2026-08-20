# Equivalent Wave Height (EWH) from Wave Spectra

Compute and visualize the **Equivalent Wave Height (EWH)** — the wave height associated with a
specific swell frequency band, integrated over all directions — from MET Norway's hindcast 2D
wave spectra (NORA3 / `mywavewam3km_spectra`, WAM model), and plot its spatial contours for a
given day.

See `AGENTS.md` for the full project conventions, and `EquivalentWaveHeigh.pdf` for the original
problem statement. See `DOCUMENTATION.md` for detailed technical documentation.

## What it does

```
EWH_f1-f2 = 4 * sqrt( integral_0^2pi integral_f1^f2 SPEC(f, theta) df d(theta) )
```

For the default frequency band `f1 = 0.04595011 Hz`, `f2 = 0.05559963 Hz` (periods ~18-22 s), this
tracks a specific swell band and reveals where/when it is present in the wave field.

## Quick start

```bash
# 1. Create the environment (only needed once)
mamba env create -f environment.yml

# 2. Run the pipeline, in order
mamba run -n kivm_swell python 00_fetch_spectra.py   # fetch + subset spectra for TARGET_DATE
mamba run -n kivm_swell python 01_compute_ewh.py     # compute EWH_f1-f2 per hour and grid point
mamba run -n kivm_swell python 02_plot_contours.py   # plot hourly EWH contour maps

# Run the test suite
mamba run -n kivm_swell python -m pytest
```

## Project layout

- `constants.py` — shared constants (frequency band, target date, data URLs, output paths).
- `logging_setup.py` — shared loguru logging configuration.
- `00_fetch_spectra.py` → `00_fetch_spectra/` — fetches and subsets the daily spectra NetCDF file.
- `01_compute_ewh.py` → `01_compute_ewh/` — computes EWH_f1-f2 for every hour and grid point.
- `02_plot_contours.py` → `02_plot_contours/` — plots hourly EWH contour maps (PNG figures).
- `tests/` — pytest unit tests for the pure/testable functions in each script.
- `logs/` — timestamped log files from each script run.

## Map projection

The model's spatial grid is a flattened, unstructured point set covering the North Atlantic and
Arctic. Contour maps are drawn with `tricontourf` on a Delaunay triangulation, using a North
Polar Stereographic projection (`cartopy`) to avoid the shape distortion a flat longitude-latitude
plot would show near the pole. Because the real domain is non-convex (separate ocean basins split
by continents), the raw triangulation is post-processed: triangles whose longest edge exceeds
3x the median edge length are masked out, removing spurious "bridge" triangles that would
otherwise connect unrelated, distant regions. See `AI_REASONING.md` / `DISCUSSIONS_LOG.md` for
details on this design decision.
