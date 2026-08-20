"""Fetch and subset the 2D wave-spectra NetCDF file for a given day from MET Norway's THREDDS
server, keeping only the two frequency bins needed for the EWH_f1-f2 calculation.

Downloading only the two frequency bins (instead of all 30) keeps the local subset small
(~130 MB/day instead of ~2 GB/day) while preserving every time step, spatial point, and
direction bin needed by `01_compute_ewh.py`.

# %%
"""

# Numbered script filenames (00_, 01_, ...) are a deliberate project convention (see AGENTS.md).
# pylint: disable=invalid-name

import sys
from pathlib import Path

import xarray as xr
from loguru import logger

from constants import (
    F1_HZ,
    F2_HZ,
    FETCH_OUTPUT_DIR,
    TARGET_DATE,
    THREDDS_OPENDAP_BASE_URL,
)
from logging_setup import setup_logging


def build_opendap_url(date_str: str, base_url: str = THREDDS_OPENDAP_BASE_URL) -> str:
    """Build the OPeNDAP URL of the daily spectra file for a given date.

    Args:
        date_str: Date as an 8-digit string, e.g. "19950201" (YYYYMMDD).
        base_url: THREDDS OPeNDAP base URL for the `mywavewam3km_spectra` dataset.

    Returns:
        The full OPeNDAP URL of the `SPC<date_str>00.nc` file for that day.
    """
    assert len(date_str) == 8 and date_str.isdigit(), (
        f"date_str must be an 8-digit YYYYMMDD string, got {date_str!r}"
    )
    year, month = date_str[:4], date_str[4:6]
    filename = f"SPC{date_str}00.nc"
    return f"{base_url}/{year}/{month}/{filename}"


def fetch_and_save_subset(
    date_str: str,
    freq_min: float,
    freq_max: float,
    output_dir: Path,
) -> Path:
    """Open the remote daily spectra file, subset it to two frequency bins, and save it locally.

    Args:
        date_str: Date as an 8-digit string, e.g. "19950201" (YYYYMMDD).
        freq_min: Lower bound of the frequency band (Hz), selected via nearest match.
        freq_max: Upper bound of the frequency band (Hz), selected via nearest match.
        output_dir: Directory in which to save the local NetCDF subset.

    Returns:
        Path to the saved local NetCDF subset file.
    """
    url = build_opendap_url(date_str)
    logger.info("Opening remote dataset for date={} at url={}", date_str, url)
    with xr.open_dataset(url) as remote_ds:
        logger.debug("Remote dataset dims: {}", dict(remote_ds.sizes))
        assert "SPEC" in remote_ds.data_vars, "Expected variable 'SPEC' not found in remote dataset"
        assert "freq" in remote_ds.coords, "Expected coordinate 'freq' not found in remote dataset"
        assert "direction" in remote_ds.coords, (
            "Expected coordinate 'direction' not found in remote dataset"
        )

        subset = remote_ds.sel(freq=[freq_min, freq_max], method="nearest")
        selected_freqs = subset["freq"].to_numpy()
        logger.info("Selected discrete frequency bins (Hz): {}", selected_freqs)
        assert selected_freqs.shape == (2,), "Expected exactly 2 frequency bins after selection"
        for requested, selected in zip((freq_min, freq_max), selected_freqs):
            assert abs(requested - selected) < 1e-4, (
                f"Requested frequency {requested} did not match a nearby discrete bin "
                f"(closest found: {selected}); check F1_HZ/F2_HZ in constants.py"
            )

        n_directions = subset.sizes["direction"]
        assert n_directions == 24, f"Expected 24 direction bins, found {n_directions}"

        logger.info("Loading subset into memory (~{:.1f} MB)...", subset.nbytes / 1e6)
        subset = subset.load()

        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"SPC{date_str}_subset_f{freq_min:.6f}-{freq_max:.6f}.nc"
        subset.to_netcdf(output_path)
        logger.info("Saved local subset to {}", output_path)
        return output_path


def main() -> int:
    """Fetch and save the frequency-subset spectra file for TARGET_DATE.

    Returns:
        Process exit code: 0 on success, 1 on failure.
    """
    setup_logging("00_fetch_spectra")
    logger.info(
        "Starting fetch for date={}, freq band=[{}, {}] Hz", TARGET_DATE, F1_HZ, F2_HZ
    )
    try:
        output_path = fetch_and_save_subset(TARGET_DATE, F1_HZ, F2_HZ, FETCH_OUTPUT_DIR)
    except Exception:  # noqa: BLE001 -- top-level catch-all so the script always exits cleanly
        logger.exception("Failed to fetch and save spectra subset")
        return 1
    logger.info("Done. Subset saved at: {}", output_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())

# %%
