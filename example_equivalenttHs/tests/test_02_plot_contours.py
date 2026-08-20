"""Tests for `plot_ewh_contour_for_hour` in `02_plot_contours.py`, using synthetic data."""

from pathlib import Path

import numpy as np
import pytest

from tests.conftest import import_task_script

plot_contours = import_task_script("02_plot_contours.py")


def test_build_masked_triangulation_masks_long_bridge_triangles() -> None:
    """A single distant outlier point must be masked out of all triangles touching it."""
    # A small, dense 3x3 grid (edges ~1 unit) plus one far-away outlier point (~100 units away):
    # any triangle connecting the cluster to the outlier has an edge far longer than the
    # cluster's median edge length, and must be masked.
    grid_x, grid_y = np.meshgrid(np.arange(3.0), np.arange(3.0))
    cluster_x = grid_x.ravel()
    cluster_y = grid_y.ravel()
    outlier_x = np.array([100.0])
    outlier_y = np.array([100.0])
    projected_x = np.concatenate([cluster_x, outlier_x])
    projected_y = np.concatenate([cluster_y, outlier_y])
    outlier_index = len(projected_x) - 1

    triangulation = plot_contours.build_masked_triangulation(projected_x, projected_y)

    assert triangulation.mask is not None
    triangles_touching_outlier = np.any(triangulation.triangles == outlier_index, axis=1)
    assert np.all(triangulation.mask[triangles_touching_outlier])
    assert not np.all(triangulation.mask)


def test_plot_ewh_contour_for_hour_saves_file_and_reports_stats(tmp_path: Path) -> None:
    """The plotting function must save a PNG and return the correct (min, max, mean)."""
    n_points = 50
    rng = np.random.default_rng(seed=0)
    longitude = rng.uniform(-10, 10, n_points)
    latitude = rng.uniform(50, 70, n_points)
    ewh = np.linspace(0.0, 2.0, n_points)

    output_path = tmp_path / "test_contour.png"
    ewh_min, ewh_max, ewh_mean = plot_contours.plot_ewh_contour_for_hour(
        longitude, latitude, ewh, "1995-02-01 00:00", str(output_path)
    )

    assert output_path.exists()
    assert output_path.stat().st_size > 0
    assert ewh_min == 0.0
    assert ewh_max == 2.0
    assert ewh_mean == np.mean(ewh)


def test_plot_ewh_contour_for_hour_ignores_nan_points(tmp_path: Path) -> None:
    """NaN (masked/land) points must be excluded from the plotted stats."""
    rng = np.random.default_rng(seed=1)
    n_points = 20
    longitude = rng.uniform(-10, 10, n_points)
    latitude = rng.uniform(50, 70, n_points)
    ewh = np.linspace(1.0, 3.0, n_points)
    ewh[[2, 7, 15]] = np.nan

    output_path = tmp_path / "test_contour_nan.png"
    ewh_min, ewh_max, ewh_mean = plot_contours.plot_ewh_contour_for_hour(
        longitude, latitude, ewh, "1995-02-01 00:00", str(output_path)
    )

    assert ewh_min == np.nanmin(ewh)
    assert ewh_max == np.nanmax(ewh)
    assert ewh_mean == pytest.approx(np.nanmean(ewh))
