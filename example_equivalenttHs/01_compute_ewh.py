"""Compute the Equivalent Wave Height (EWH) for the f1-f2 frequency band from the local spectra
subset produced by `00_fetch_spectra.py`.

EWH_f1-f2 = 4 * sqrt( integral_0^2pi integral_f1^f2 SPEC(f, theta) df d(theta) )

The direction integral is a rectangle-rule sum over the 24 uniform direction bins (exact for a
periodic function sampled on a uniform grid covering the full circle). The frequency integral is
a trapezoidal integration between the two selected frequency bin centers (decided with the user,
see AGENTS.md).

# %%
"""

# Numbered script filenames (00_, 01_, ...) are a deliberate project convention (see AGENTS.md).
# pylint: disable=invalid-name

import sys

import numpy as np
import xarray as xr
from loguru import logger
from tqdm import tqdm

from constants import EWH_OUTPUT_DIR, F1_HZ, F2_HZ, FETCH_OUTPUT_DIR, TARGET_DATE
from logging_setup import setup_logging


def compute_ewh(
    spec: np.ndarray, freq_values_hz: np.ndarray, direction_values_deg: np.ndarray
) -> np.ndarray:
    """Compute EWH_f1-f2 from a 2D wave spectrum sampled at exactly 2 frequency bins.

    Args:
        spec: Spectral density array, shape (..., n_freq, n_direction), units m**2/Hz (per
            direction bin, i.e. m**2 s as stored in the source NetCDF), with n_freq == 2.
        freq_values_hz: The 2 frequency bin centers (Hz), monotonically increasing.
        direction_values_deg: The direction bin centers (degrees), uniformly spaced and
            covering the full circle (0-360 degrees).

    Returns:
        EWH values, shape equal to `spec.shape[:-2]` (the leading/broadcast dimensions).
    """
    assert spec.shape[-2] == freq_values_hz.shape[0], (
        "spec's second-to-last axis must match freq_values_hz"
    )
    assert spec.shape[-1] == direction_values_deg.shape[0], (
        "spec's last axis must match direction_values_deg"
    )
    assert freq_values_hz.shape[0] == 2, "compute_ewh only supports exactly 2 frequency bins"
    assert freq_values_hz[1] > freq_values_hz[0], "freq_values_hz must be increasing"

    n_directions = direction_values_deg.shape[0]
    sorted_directions = np.sort(direction_values_deg)
    direction_steps_deg = np.diff(sorted_directions)
    assert np.allclose(direction_steps_deg, direction_steps_deg[0], atol=1e-2), (
        "direction bins must be uniformly spaced"
    )
    full_circle_deg = direction_steps_deg[0] * n_directions
    assert abs(full_circle_deg - 360.0) < 1e-2, (
        f"direction bins must cover the full circle (360 deg), got {full_circle_deg:.3f} deg"
    )
    dtheta_rad = 2.0 * np.pi / n_directions

    direction_integrated = np.nansum(spec, axis=-1) * dtheta_rad  # shape (..., n_freq)
    freq_integrated = np.trapezoid(direction_integrated, x=freq_values_hz, axis=-1)
    ewh = 4.0 * np.sqrt(np.clip(freq_integrated, 0.0, None))
    return ewh


def compute_ewh_dataset(subset_path: str) -> xr.Dataset:
    """Load a local spectra subset and compute EWH_f1-f2 for every time step and grid point.

    Args:
        subset_path: Path to the local NetCDF subset produced by `00_fetch_spectra.py`.

    Returns:
        A Dataset with dims (time, x), variables `ewh` (m), `longitude`, `latitude` (both (x,)).
    """
    logger.info("Loading local spectra subset from {}", subset_path)
    with xr.open_dataset(subset_path) as ds:
        assert "SPEC" in ds.data_vars, "Expected variable 'SPEC' not found in local subset"
        assert ds.sizes.get("y") == 1, f"Expected a single 'y' index, found {ds.sizes.get('y')}"
        assert ds.sizes.get("freq") == 2, f"Expected 2 freq bins, found {ds.sizes.get('freq')}"
        assert ds.sizes.get("direction") == 24, (
            f"Expected 24 direction bins, found {ds.sizes.get('direction')}"
        )

        freq_values = ds["freq"].to_numpy()
        direction_values = ds["direction"].to_numpy()
        n_times = ds.sizes["time"]
        logger.info(
            "Computing EWH for {} time steps, {} spatial points, freq bins={}",
            n_times,
            ds.sizes["x"],
            freq_values,
        )

        ewh_per_time = []
        for time_index in tqdm(range(n_times), desc="Computing EWH per hour", unit="hour"):
            spec_at_time = ds["SPEC"].isel(time=time_index, y=0).to_numpy()  # (x, freq, direction)
            ewh_at_time = compute_ewh(spec_at_time, freq_values, direction_values)  # (x,)
            n_valid = np.sum(~np.isnan(ewh_at_time))
            logger.debug(
                "time_index={} valid_points={}/{} ewh_min={:.4f} ewh_max={:.4f} ewh_mean={:.4f}",
                time_index,
                n_valid,
                ewh_at_time.shape[0],
                np.nanmin(ewh_at_time),
                np.nanmax(ewh_at_time),
                np.nanmean(ewh_at_time),
            )
            ewh_per_time.append(ewh_at_time)

        ewh_array = np.stack(ewh_per_time, axis=0)  # (time, x)
        assert ewh_array.shape == (n_times, ds.sizes["x"])

        result = xr.Dataset(
            data_vars={
                "ewh": (
                    ("time", "x"),
                    ewh_array,
                    {"units": "m", "long_name": "Equivalent Wave Height"},
                ),
            },
            coords={
                "time": ds["time"].to_numpy(),
                "x": ds["x"].to_numpy(),
                "longitude": ("x", ds["longitude"].isel(y=0).to_numpy()),
                "latitude": ("x", ds["latitude"].isel(y=0).to_numpy()),
            },
            attrs={
                "f1_hz": float(freq_values[0]),
                "f2_hz": float(freq_values[1]),
                "description": "Equivalent Wave Height integrated over the f1-f2 frequency band",
            },
        )
        return result


def main() -> int:
    """Compute and save EWH_f1-f2 for TARGET_DATE from the local spectra subset.

    Returns:
        Process exit code: 0 on success, 1 on failure.
    """
    setup_logging("01_compute_ewh")
    subset_path = (
        FETCH_OUTPUT_DIR / f"SPC{TARGET_DATE}_subset_f{F1_HZ:.6f}-{F2_HZ:.6f}.nc"
    )
    logger.info("Starting EWH computation, reading subset from {}", subset_path)
    try:
        assert subset_path.exists(), (
            f"Subset file not found: {subset_path}. Run 00_fetch_spectra.py first."
        )
        result = compute_ewh_dataset(str(subset_path))
        EWH_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = EWH_OUTPUT_DIR / f"EWH_{TARGET_DATE}.nc"
        result.to_netcdf(output_path)
        logger.info("Saved EWH dataset to {}", output_path)
    except Exception:  # noqa: BLE001 -- top-level catch-all so the script always exits cleanly
        logger.exception("Failed to compute EWH dataset")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

# %%
