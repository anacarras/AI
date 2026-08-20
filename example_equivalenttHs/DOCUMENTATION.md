# DOCUMENTATION

Technical documentation for the Equivalent Wave Height (EWH) project. See `README.md` for a quick
overview and `AGENTS.md` for project conventions.

## 1. Scientific background

The Equivalent Wave Height for a frequency band `[f1, f2]` is:

```
EWH_f1-f2 = 4 * sqrt( integral_0^2pi integral_f1^f2 SPEC(f, theta) df d(theta) )
```

where `SPEC(f, theta)` is the 2D wave spectrum (spectral density, m^2/Hz per direction bin), `f`
is the cyclic frequency (Hz), and `theta` is the wave direction (degrees, oceanographic
convention: direction the wave propagates *towards*).

This is the standard significant-wave-height formula (`Hs = 4*sqrt(m0)`, with `m0` the zeroth
spectral moment) restricted to a chosen frequency sub-band, so it isolates the wave height
contributed by a specific swell period range instead of the whole spectrum.

**Important notational note:** the source PDF (`EquivalentWaveHeigh.pdf`) labels the frequency
variable `omega` ("angular frequency"). However, the actual NetCDF `freq` variable in the source
dataset is in `1/s` (Hz, i.e. cyclic frequency `f`), and `f1_hz`/`f2_hz` match it directly with no
rad/s conversion. The code and this documentation consistently use `f` (Hz), not `omega` (rad/s).

## 2. Data source

MET Norway THREDDS server, `mywavewam3km_spectra` dataset (WINDSURFER/NORA3 hindcast, WAM model
cycle 4.7.0), accessed via OPeNDAP:

```
https://thredds.met.no/thredds/dodsC/windsurfer/mywavewam3km_spectra/<YYYY>/<MM>/SPC<YYYYMMDD>00.nc
```

Dataset structure (as of the file used, `SPC1995020100.nc`):

| Variable/dim | Shape / size | Units | Notes |
|---|---|---|---|
| `SPEC` | `(time=24, y=1, x=28713, freq=30, direction=24)` | `m**2 s` (i.e. m^2/Hz) | 2D spectral density |
| `freq` | 30 | `1/s` (Hz) | Logarithmically spaced |
| `direction` | 24 | `degree` | Uniform 15-degree bins, full circle (oceanographic convention) |
| `x` | 28713 | — | Flattened, unstructured native grid index |
| `y` | 1 | — | Dummy dimension (always size 1) |
| `longitude`, `latitude` | `(y=1, x=28713)` | degrees | 2D coordinate arrays over `(y, x)` |
| `time` | 24 | — | One file per day already contains all 24 hourly steps |

Key facts discovered while building the pipeline (verified directly against the live OPeNDAP
endpoint, not assumed):
- One daily file (e.g. `SPC1995020100.nc`) contains **all 24 hourly time steps** for that day —
  no need to fetch one file per hour.
- The chosen `f1_hz = 0.04595011`, `f2_hz = 0.05559963` land **exactly** on two adjacent discrete
  `freq` bins (index 3 and 4 of 30).
- The spatial grid is a **flattened/unstructured point cloud** (not a regular lat/lon grid), so
  contour plotting requires triangulation (`matplotlib.tri.tricontourf`), not `contourf`.

## 3. Numerical integration method

- **Direction integral (`d(theta)`):** rectangle-rule sum over the 24 uniform direction bins,
  each of width `2*pi/24` radians. This is exact for a periodic function sampled uniformly over a
  full period, so no higher-order scheme is needed.
- **Frequency integral (`df`):** trapezoidal integration between the two selected frequency bin
  centers (`np.trapezoid`). Decided with the user (2026-08-18) since only 2 discrete frequency
  points are available in the chosen band; a wider "oceanographic band-sum" convention (weighting
  by half-distance to neighboring bins) was considered and rejected in favor of the simpler,
  more directly interpretable trapezoidal rule.

Implementation: `compute_ewh()` in `01_compute_ewh.py`, unit-tested in
`tests/test_01_compute_ewh.py` against closed-form results for a constant spectral density.

## 4. Pipeline

1. **`00_fetch_spectra.py`**: opens the remote daily file via OPeNDAP, selects only the 2 needed
   frequency bins (`method="nearest"`, with an assertion that the match is exact), loads that
   ~130 MB subset into memory, and saves it locally under `00_fetch_spectra/` as a NetCDF file
   (instead of downloading the full ~2 GB/day file).
2. **`01_compute_ewh.py`**: loads the local subset, computes `EWH_f1-f2` for every hour and every
   grid point (loop over 24 hours with a `tqdm` progress bar; each hour is a single vectorized
   `compute_ewh()` call over all 28713 points), and saves the result (`ewh(time, x)`,
   `longitude(x)`, `latitude(x)`) to `01_compute_ewh/EWH_<date>.nc`.
3. **`02_plot_contours.py`**: loads the EWH dataset and, for each hour, projects grid points to a
   North Polar Stereographic projection (`cartopy`), builds a Delaunay triangulation on the
   projected coordinates, masks out triangles whose longest edge exceeds `MAX_EDGE_LENGTH_FACTOR`
   (3.0) times the median edge length (removing spurious triangles that bridge across land gaps
   between disconnected ocean basins), and plots the masked `tricontourf` map with coastlines,
   saving each to `02_plot_contours/02p<NN>_ewh_contour_hour<HH>.png`, and logs per-hour and
   overall summary statistics (min/max/mean) so the results are readable from logs alone.

## 5. Map projection and triangulation masking

The NORA3 spatial grid is a flattened, unstructured point set (`y=1, x=28713`) covering the North
Atlantic and Arctic as several disconnected ocean-basin "branches" (e.g. separate North
Atlantic/Arctic corridors split by land), with longitude values not normalized to [-180, 180)
(observed range: about -220 to 140 degrees).

Two issues were addressed:
- **Polar distortion**: plotting raw longitude/latitude as Cartesian x/y severely distorts shapes
  near the pole. Fixed by projecting to `cartopy.crs.NorthPolarStereo()` (data supplied in
  `PlateCarree()`), with longitudes normalized to [-180, 180) before plotting.
- **Convex-hull "bridge" artifacts**: `tricontourf`'s default Delaunay triangulation fills the
  *entire convex hull* of the point set. Since the true domain is non-convex, this creates long
  spurious triangles connecting distant, unrelated points across land gaps (e.g. Norway to
  Alaska). Fixed by building the triangulation explicitly in projected (stereographic, meters)
  coordinates via `matplotlib.tri.Triangulation`, computing each triangle's longest edge, and
  masking out any triangle whose longest edge exceeds `MAX_EDGE_LENGTH_FACTOR * median_edge_length`
  (see `build_masked_triangulation()`). The threshold factor (3.0) was chosen empirically: the
  edge-length distribution of the raw triangulation shows a median of about 39 km, a 95th
  percentile of about 54.5 km, then a sharp jump to about 228 km at the 99th percentile — a clean
  separation between real grid edges and bridge artifacts. See `AI_REASONING.md` for the full
  analysis.

Also fixed along the way: `ax.gridlines(draw_labels=True, ...)` in `NorthPolarStereo` crashes near
the pole with a shapely `GEOSException` (`Points of LinearRing do not form a closed linestring`);
worked around by using `draw_labels=False`.

## 6. Testing

`pytest` unit tests cover the pure, network-free functions of each script:
- `build_opendap_url()` — URL construction and input validation.
- `compute_ewh()` — closed-form check against a constant spectral density, broadcasting over
  extra leading dimensions, NaN handling, and rejection of invalid inputs (wrong number of
  frequency bins, non-uniform or incomplete direction bins).
- `build_masked_triangulation()` — a distant outlier point is correctly excluded (all triangles
  touching it are masked), while the well-connected cluster is not fully masked.
- `plot_ewh_contour_for_hour()` — file is saved, returned (min, max, mean) statistics are correct,
  NaN points are excluded from the statistics.

Numbered scripts (e.g. `00_fetch_spectra.py`) are imported into tests via
`tests/conftest.py::import_task_script()` (using `importlib`), since their filenames are not valid
Python module identifiers for a plain `import` statement.

## 7. Environment

See `environment.yml` for the pinned conda-forge package versions. Create with:

```bash
mamba env create -f environment.yml
```
