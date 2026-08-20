"""Tests for `compute_ewh` and `compute_ewh_dataset` in `01_compute_ewh.py`."""

import numpy as np
import pytest

from tests.conftest import import_task_script

compute_ewh_module = import_task_script("01_compute_ewh.py")
compute_ewh = compute_ewh_module.compute_ewh


def _uniform_directions(n_bins: int) -> np.ndarray:
    """Build n_bins uniformly-spaced direction bin centers covering the full circle."""
    step = 360.0 / n_bins
    return np.arange(n_bins) * step + step / 2.0


def test_compute_ewh_constant_spectrum_matches_closed_form() -> None:
    """For a constant spectral density C, EWH = 4 * sqrt(2*pi*C*(f2-f1)) exactly."""
    f1, f2 = 0.04595011, 0.05559963
    constant_density = 0.5  # m**2 s
    n_directions = 24
    directions = _uniform_directions(n_directions)
    spec = np.full((2, n_directions), constant_density)

    ewh = compute_ewh(spec, np.array([f1, f2]), directions)

    expected = 4.0 * np.sqrt(2.0 * np.pi * constant_density * (f2 - f1))
    assert ewh == pytest.approx(expected, rel=1e-6)


def test_compute_ewh_zero_spectrum_gives_zero() -> None:
    """A zero spectrum everywhere must give exactly zero EWH."""
    directions = _uniform_directions(24)
    spec = np.zeros((2, 24))
    ewh = compute_ewh(spec, np.array([0.045, 0.055]), directions)
    assert ewh == pytest.approx(0.0)


def test_compute_ewh_broadcasts_over_leading_dimensions() -> None:
    """compute_ewh must support extra leading dims (e.g. (time, x, freq, direction))."""
    directions = _uniform_directions(24)
    constant_density = 1.2
    spec = np.full((3, 5, 2, 24), constant_density)
    ewh = compute_ewh(spec, np.array([0.045, 0.055]), directions)
    assert ewh.shape == (3, 5)
    expected = 4.0 * np.sqrt(2.0 * np.pi * constant_density * (0.055 - 0.045))
    assert np.allclose(ewh, expected)


def test_compute_ewh_ignores_nan_direction_bins() -> None:
    """NaN spectral values (e.g. masked/land points) must not propagate to a NaN EWH."""
    directions = _uniform_directions(24)
    spec = np.zeros((2, 24))
    spec[:, 0] = np.nan
    ewh = compute_ewh(spec, np.array([0.045, 0.055]), directions)
    assert np.isfinite(ewh)


def test_compute_ewh_rejects_non_two_frequency_bins() -> None:
    """Only exactly 2 frequency bins are supported (trapezoidal between 2 points)."""
    directions = _uniform_directions(24)
    spec = np.zeros((3, 24))
    with pytest.raises(AssertionError):
        compute_ewh(spec, np.array([0.04, 0.05, 0.06]), directions)


def test_compute_ewh_rejects_non_uniform_directions() -> None:
    """Direction bins that are not uniformly spaced must be rejected."""
    directions = np.array([0.0, 10.0, 40.0])
    spec = np.zeros((2, 3))
    with pytest.raises(AssertionError):
        compute_ewh(spec, np.array([0.045, 0.055]), directions)


def test_compute_ewh_rejects_directions_not_covering_full_circle() -> None:
    """Direction bins spanning less than a full circle must be rejected."""
    directions = np.array([0.0, 10.0, 20.0])  # uniform but only covers 30 deg, not 360
    spec = np.zeros((2, 3))
    with pytest.raises(AssertionError):
        compute_ewh(spec, np.array([0.045, 0.055]), directions)
