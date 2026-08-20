"""Shared constants for the Equivalent Wave Height (EWH) project.

These constants are used across the numbered task scripts (00, 01, 02) and are kept in one
place so they only need to be edited once. See AGENTS.md and EquivalentWaveHeigh.pdf for the
underlying definitions and the reasoning behind the chosen values.
"""

from pathlib import Path

# Frequency band of interest (Hz, cyclic frequency f = 1 / period).
# These match exactly the discrete `freq` bins (index 3 and 4 of 30) of the source dataset.
F1_HZ = 0.04595011
F2_HZ = 0.05559963

# Day to process (THREDDS filename date stamp, one file already covers the whole day).
TARGET_DATE = "19950201"

# THREDDS OPeNDAP base URL for the wave spectra dataset.
THREDDS_OPENDAP_BASE_URL = (
    "https://thredds.met.no/thredds/dodsC/windsurfer/mywavewam3km_spectra"
)

# Project root and per-task output directories.
PROJECT_ROOT = Path(__file__).resolve().parent
FETCH_OUTPUT_DIR = PROJECT_ROOT / "00_fetch_spectra"
EWH_OUTPUT_DIR = PROJECT_ROOT / "01_compute_ewh"
PLOT_OUTPUT_DIR = PROJECT_ROOT / "02_plot_contours"
LOG_DIR = PROJECT_ROOT / "logs"
