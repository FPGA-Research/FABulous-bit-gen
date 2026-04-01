"""Shared fixtures for FABulous_bit_gen tests."""

import pickle
from pathlib import Path

import pytest

from fasm import FasmLine, SetFasmFeature


@pytest.fixture
def minimal_spec_dict():
    """Minimal spec dict for unit tests.

    Tiles: X0Y0 (NULL - bottom), X0Y1 (W_IO), X1Y1 (LUT4AB), X0Y2 (NULL - top)

    Note: The bitstream generation skips Y0 (bottom) and Y{max} (top) rows.
    So we need tiles at Y2 to ensure Y1 gets processed.
    """
    MaxFramesPerCol = 20
    FrameBitsPerRow = 32
    total_bits = MaxFramesPerCol * FrameBitsPerRow

    return {
        "ArchSpecs": {
            "MaxFramesPerCol": MaxFramesPerCol,
            "FrameBitsPerRow": FrameBitsPerRow,
        },
        "TileMap": {
            "X0Y0": "NULL",
            "X0Y1": "W_IO",
            "X1Y1": "LUT4AB",
            "X0Y2": "NULL",
            "X1Y2": "NULL",
        },
        "TileSpecs": {
            "X0Y1": {
                "W2MID7.A_I": {110: "1", 111: "0"},
                "GND0.A_T": {50: "1"},
            },
            "X1Y1": {
                "LUT4.INIT": {0: "1", 1: "0", 2: "1", 3: "0"},
                "LUT4.MODE": {100: "1"},
            },
            "X0Y0": {},
            "X0Y2": {},
            "X1Y2": {},
        },
        "TileSpecs_No_Mask": {
            "X0Y1": {
                "W2MID7.A_I": {110: "1", 111: "0"},
                "GND0.A_T": {50: "1"},
            },
            "X1Y1": {
                "LUT4.INIT": {0: "1", 1: "0", 2: "1", 3: "0"},
                "LUT4.MODE": {100: "1"},
            },
            "X0Y0": {},
            "X0Y2": {},
            "X1Y2": {},
        },
        "FrameMap": {
            "NULL": {},
            "W_IO": {0: "11111111111111111111111111111111"},
            "LUT4AB": {0: "00000001111111111111111111111011"},
        },
        "FrameMapEncode": {},
    }


@pytest.fixture
def temp_output_dir(tmp_path):
    """Temporary directory for test outputs, auto-cleanup after test."""
    return tmp_path


@pytest.fixture(scope="session")
def test_data_dir():
    """Path to test data directory."""
    return Path(__file__).parent / "test_data"


@pytest.fixture(scope="session")
def expected_output_dir(test_data_dir):
    """Path to expected output files."""
    return test_data_dir / "output"


@pytest.fixture(scope="session")
def real_spec_dict(test_data_dir):
    """Load real bitstream spec from test data."""
    spec_file = test_data_dir / "bitStreamSpec.bin"
    with spec_file.open("rb") as f:
        return pickle.load(f)


@pytest.fixture(scope="session")
def real_fasm_path(test_data_dir):
    """Path to real FASM file from test data."""
    return test_data_dir / "sequential_16bit_en.fasm"


@pytest.fixture(scope="session")
def real_expected_bin(expected_output_dir):
    """Path to expected binary output."""
    return expected_output_dir / "sequential_16bit_en.bin"


@pytest.fixture(scope="session")
def real_expected_csv(expected_output_dir):
    """Path to expected CSV output."""
    return expected_output_dir / "sequential_16bit_en.csv"


@pytest.fixture(scope="session")
def real_expected_vh(expected_output_dir):
    """Path to expected Verilog output."""
    return expected_output_dir / "sequential_16bit_en.vh"


@pytest.fixture(scope="session")
def real_expected_vhd(expected_output_dir):
    """Path to expected VHDL output."""
    return expected_output_dir / "sequential_16bit_en.vhd"


@pytest.fixture
def synthetic_fasm_lines():
    """Synthetic FASM lines for unit testing.

    Returns list of FasmLine objects with set_features.
    """
    return [
        FasmLine(
            set_feature=SetFasmFeature(
                feature="X0Y1.W2MID7.A_I",
                start=None,
                end=None,
                value=1,
                value_format=None,
            ),
            annotations=None,
            comment=None,
        ),
        FasmLine(
            set_feature=SetFasmFeature(
                feature="X0Y1.GND0.A_T",
                start=None,
                end=None,
                value=1,
                value_format=None,
            ),
            annotations=None,
            comment=None,
        ),
        FasmLine(
            set_feature=SetFasmFeature(
                feature="X1Y1.LUT4.INIT",
                start=None,
                end=None,
                value=1,
                value_format=None,
            ),
            annotations=None,
            comment=None,
        ),
    ]


@pytest.fixture
def synthetic_fasm_lines_with_clk():
    """FASM lines including CLK feature (should be filtered)."""
    return [
        FasmLine(
            set_feature=SetFasmFeature(
                feature="X0Y1.W2MID7.A_I",
                start=None,
                end=None,
                value=1,
                value_format=None,
            ),
            annotations=None,
            comment=None,
        ),
        FasmLine(
            set_feature=SetFasmFeature(
                feature="X0Y1.CLK.some_feature",
                start=None,
                end=None,
                value=1,
                value_format=None,
            ),
            annotations=None,
            comment=None,
        ),
    ]


@pytest.fixture
def synthetic_fasm_lines_invalid_tile():
    """FASM lines with invalid tile location."""
    return [
        FasmLine(
            set_feature=SetFasmFeature(
                feature="X99Y99.W2MID7.A_I",
                start=None,
                end=None,
                value=1,
                value_format=None,
            ),
            annotations=None,
            comment=None,
        ),
    ]

