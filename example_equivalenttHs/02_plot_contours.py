"""Plot contour maps of the Equivalent Wave Height (EWH) for the f1-f2 frequency band, for each
hourly time step of TARGET_DATE, from the output of `01_compute_ewh.py`.

The source spatial grid is a flattened, unstructured native WAM grid (not a regular lat/lon
grid), so contours are drawn with `tricontourf` (Delaunay triangulation) rather than `contourf`.
Since the domain covers the North Atlantic up to the high Arctic, plots use a North Polar
Stereographic projection (`cartopy`) rather than plain longitude/latitude axes, to avoid the
severe shape distortion and convex-hull artifacts a flat lon/lat plot would show near the pole.

# %%
"""

# Numbered script filenames (00_, 01_, ...) are a deliberate project convention (see AGENTS.md).
# pylint: disable=invalid-name

import os
import sys
from typing import cast

import matplotlib
import numpy as np
import xarray as xr
from loguru import logger
from tqdm import tqdm

# Headless environments (no X11 display) cannot pop up interactive figure windows: detect this
# before importing pyplot, and force the non-interactive Agg backend in that case.
IS_HEADLESS = not bool(os.environ.get("DISPLAY"))
if IS_HEADLESS:
    matplotlib.use("Agg")

import cartopy.crs as ccrs
import matplotlib.pyplot as plt
import matplotlib.tri as mtri
from cartopy.mpl.geoaxes import GeoAxes

from constants import EWH_OUTPUT_DIR, PLOT_OUTPUT_DIR, TARGET_DATE
from logging_setup import setup_logging

FIGURE_DPI = 150
CONTOUR_LEVELS = 20
MAP_PROJECTION = ccrs.NorthPolarStereo()
DATA_TRANSFORM = ccrs.PlateCarree()
MAP_EXTENT_PADDING_DEG = 3.0

# The source grid is an unstructured ocean-only point cloud with several disconnected branches
# (e.g. separate North Atlantic/North Pacific/Arctic corridors, split by continents). A plain
# Delaunay triangulation bridges across these gaps with spurious long triangles. Such "bridge"
# triangles are masked out by rejecting any triangle with an edge longer than this factor times
# the triangulation's median edge length (found empirically: real grid edges are ~40-55 km,
# bridge edges jump to 200+ km, so this factor gives a wide, robust margin between the two).
MAX_EDGE_LENGTH_FACTOR = 3.0


def normalize_longitude_deg(longitude: np.ndarray) -> np.ndarray:
    """Wrap longitudes to the conventional [-180, 180) degree range.

    Args:
        longitude: Longitudes in degrees, potentially outside [-180, 180) (as found in the
            source dataset, e.g. values down to about -220 degrees).

    Returns:
        Longitudes wrapped to [-180, 180).
    """
    return ((longitude + 180.0) % 360.0) - 180.0


def build_masked_triangulation(
    projected_x: np.ndarray, projected_y: np.ndarray
) -> mtri.Triangulation:
    """Build a Delaunay triangulation with spurious long "bridge" triangles masked out.

    Args:
        projected_x: Point x-coordinates in a projected (metric) coordinate system, shape
            (n_points,).
        projected_y: Point y-coordinates in the same projected system, shape (n_points,).

    Returns:
        A `Triangulation` with `.mask` set to exclude triangles whose longest edge exceeds
        `MAX_EDGE_LENGTH_FACTOR` times the median edge length.
    """
    assert projected_x.shape == projected_y.shape, "projected_x and projected_y must match"
    triangulation = mtri.Triangulation(projected_x, projected_y)
    points = np.column_stack([projected_x, projected_y])
    triangles = triangulation.triangles
    edge_lengths = np.stack(
        [
            np.linalg.norm(points[triangles[:, i]] - points[triangles[:, (i + 1) % 3]], axis=1)
            for i in range(3)
        ],
        axis=1,
    )
    max_edge_per_triangle = edge_lengths.max(axis=1)
    edge_length_threshold = MAX_EDGE_LENGTH_FACTOR * np.median(edge_lengths)
    triangulation.set_mask(max_edge_per_triangle > edge_length_threshold)
    return triangulation


def project_and_triangulate(
    longitude_norm: np.ndarray, latitude_valid: np.ndarray
) -> mtri.Triangulation:
    """Project valid lon/lat points to the map projection and build a masked triangulation.

    Args:
        longitude_norm: Longitudes in [-180, 180) degrees, already filtered to valid points.
        latitude_valid: Latitudes in degrees North, already filtered to valid points.

    Returns:
        A `Triangulation` in projected map coordinates, with bridge triangles masked out.
    """
    projected_points = MAP_PROJECTION.transform_points(
        DATA_TRANSFORM, longitude_norm, latitude_valid
    )
    return build_masked_triangulation(projected_points[:, 0], projected_points[:, 1])


def plot_ewh_contour_for_hour(
    longitude: np.ndarray,
    latitude: np.ndarray,
    ewh: np.ndarray,
    hour_label: str,
    output_path: str,
) -> tuple[float, float, float]:
    """Plot and save a single hourly EWH contour map using masked-triangulation contouring.

    Args:
        longitude: Grid point longitudes, shape (n_points,), degrees East.
        latitude: Grid point latitudes, shape (n_points,), degrees North.
        ewh: EWH values at each grid point, shape (n_points,), meters (may contain NaN for
            masked/land points).
        hour_label: Human-readable hour label used in the plot title, e.g. "1995-02-01 03:00".
        output_path: File path to save the figure to (PNG).

    Returns:
        Tuple of (min, max, mean) EWH over the valid (non-NaN) points, for logging.
    """
    assert longitude.shape == latitude.shape == ewh.shape, (
        "longitude, latitude and ewh must all have the same shape"
    )
    valid_mask = ~np.isnan(ewh)
    assert valid_mask.any(), "All EWH values are NaN, nothing to plot"

    longitude_norm = normalize_longitude_deg(longitude)[valid_mask]
    latitude_valid = latitude[valid_mask]
    ewh_valid = ewh[valid_mask]
    ewh_stats = (float(np.min(ewh_valid)), float(np.max(ewh_valid)), float(np.mean(ewh_valid)))

    triangulation = project_and_triangulate(longitude_norm, latitude_valid)

    fig, mpl_ax = plt.subplots(figsize=(8, 8), subplot_kw={"projection": MAP_PROJECTION})
    # cartopy's subplots() returns a GeoAxes at runtime, but mypy only sees the plain Axes
    # type from matplotlib's stubs, so GeoAxes-only methods below need this explicit cast.
    ax = cast(GeoAxes, mpl_ax)
    ax.set_extent(
        [
            longitude_norm.min() - MAP_EXTENT_PADDING_DEG,
            longitude_norm.max() + MAP_EXTENT_PADDING_DEG,
            latitude_valid.min() - MAP_EXTENT_PADDING_DEG,
            latitude_valid.max() + MAP_EXTENT_PADDING_DEG,
        ],
        crs=DATA_TRANSFORM,
    )
    contour = ax.tricontourf(
        triangulation,
        ewh_valid,
        levels=CONTOUR_LEVELS,
        cmap="viridis",
        transform=MAP_PROJECTION,
    )
    ax.coastlines(resolution="50m", linewidth=0.5)
    ax.gridlines(draw_labels=False, linewidth=0.3, alpha=0.5)
    fig.colorbar(contour, ax=ax, label="EWH (m)", shrink=0.8)
    ax.set_title(f"EWH f1-f2 contour — {hour_label}")
    fig.tight_layout()
    fig.savefig(output_path, dpi=FIGURE_DPI)
    if not IS_HEADLESS:
        plt.show()
    plt.close(fig)
    return ewh_stats


def main() -> int:
    """Plot and save EWH contour maps for every hourly time step of TARGET_DATE.

    Returns:
        Process exit code: 0 on success, 1 on failure.
    """
    setup_logging("02_plot_contours")
    logger.info("Headless environment detected: {}", IS_HEADLESS)
    ewh_path = EWH_OUTPUT_DIR / f"EWH_{TARGET_DATE}.nc"
    try:
        assert ewh_path.exists(), f"EWH file not found: {ewh_path}. Run 01_compute_ewh.py first."
        logger.info("Loading EWH dataset from {}", ewh_path)
        with xr.open_dataset(ewh_path) as ds:
            assert "ewh" in ds.data_vars, "Expected variable 'ewh' not found in EWH dataset"
            longitude = ds["longitude"].to_numpy()
            latitude = ds["latitude"].to_numpy()
            n_times = ds.sizes["time"]

            PLOT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            summary_lines = []
            for time_index in tqdm(range(n_times), desc="Plotting EWH contours", unit="hour"):
                timestamp = ds["time"].isel(time=time_index).to_numpy()
                hour_label = str(np.datetime_as_string(timestamp, unit="m")).replace("T", " ")
                ewh_at_time = ds["ewh"].isel(time=time_index).to_numpy()
                output_path = (
                    PLOT_OUTPUT_DIR
                    / f"02p{time_index + 1:02d}_ewh_contour_hour{time_index:02d}.png"
                )
                ewh_min, ewh_max, ewh_mean = plot_ewh_contour_for_hour(
                    longitude, latitude, ewh_at_time, hour_label, str(output_path)
                )
                logger.info(
                    "hour={} ({}): ewh_min={:.4f} m, ewh_max={:.4f} m, ewh_mean={:.4f} m, "
                    "saved to {}",
                    time_index,
                    hour_label,
                    ewh_min,
                    ewh_max,
                    ewh_mean,
                    output_path,
                )
                summary_lines.append((hour_label, ewh_min, ewh_max, ewh_mean))

            logger.info("Summary of all {} hourly EWH contour maps for {}:", n_times, TARGET_DATE)
            for hour_label, ewh_min, ewh_max, ewh_mean in summary_lines:
                logger.info(
                    "  {}: min={:.4f} m, max={:.4f} m, mean={:.4f} m",
                    hour_label,
                    ewh_min,
                    ewh_max,
                    ewh_mean,
                )
    except Exception:  # noqa: BLE001 -- top-level catch-all so the script always exits cleanly
        logger.exception("Failed to plot EWH contour maps")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

# %%
