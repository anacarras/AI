"""Tests for the pure, network-free functions in `00_fetch_spectra.py`."""

import pytest

from tests.conftest import import_task_script

fetch_spectra = import_task_script("00_fetch_spectra.py")


def test_build_opendap_url_known_date() -> None:
    """The URL must embed year, month, and the `SPC<date>00.nc` filename correctly."""
    url = fetch_spectra.build_opendap_url("19950201", base_url="https://example.org/base")
    assert url == "https://example.org/base/1995/02/SPC1995020100.nc"


def test_build_opendap_url_rejects_malformed_date() -> None:
    """Non-8-digit date strings must be rejected by the input assertion."""
    with pytest.raises(AssertionError):
        fetch_spectra.build_opendap_url("1995-02-01")
