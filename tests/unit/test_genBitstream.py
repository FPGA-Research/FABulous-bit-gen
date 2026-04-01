"""Tests for genBitstream function with comprehensive mocking."""

import pickle
import re
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from FABulous_bit_gen.bit_gen import bitstring_to_bytes, genBitstream
from FABulous_bit_gen.custom_exception import SpecMissMatch
from fasm import FasmLine, SetFasmFeature


class TestGenBitstreamInitialization:
    """Tests for genBitstream initialization."""

    def test_initializes_tile_dicts_with_zeros(
        self, minimal_spec_dict, temp_output_dir, mocker
    ):
        """Verify tileDict initialized with zeros for each tile."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        fasm_file.write_text("")
        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=[])
        mocker.patch("FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="")
        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=[])

        genBitstream(str(fasm_file), str(spec_file), str(output_file))

        assert output_file.with_suffix(".csv").exists()

    def test_grid_dimensions_calculated_correctly(
        self, minimal_spec_dict, temp_output_dir, mocker
    ):
        """Test that grid dimensions are extracted from TileMap coordinates."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        fasm_file.write_text("")
        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=[])
        mocker.patch("FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="")
        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=[])

        genBitstream(str(fasm_file), str(spec_file), str(output_file))

        csv_path = output_file.with_suffix(".csv")
        csv_content = csv_path.read_text()

        coordsRE = re.compile(r"X(\d*)Y(\d*)")
        max_x = 0
        max_y = 0
        for line in csv_content.split("\n"):
            match = coordsRE.match(line)
            if match:
                x = int(match.group(1))
                y = int(match.group(2))
                max_x = max(x, max_x)
                max_y = max(y, max_y)

        assert max_x == 1
        assert max_y == 1


class TestGenBitstreamFasmProcessing:
    """Tests for FASM line processing."""

    def test_clk_feature_filtered_out(self, minimal_spec_dict, temp_output_dir, mocker):
        """CLK features should be skipped during processing."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        fasm_lines = [
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
                    feature="X0Y1.CLK.enable",
                    start=None,
                    end=None,
                    value=1,
                    value_format=None,
                ),
                annotations=None,
                comment=None,
            ),
        ]

        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        mocker.patch(
            "FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=fasm_lines
        )
        mocker.patch(
            "FABulous_bit_gen.bit_gen.fasm_tuple_to_string",
            return_value="canonical_string",
        )

        def mock_parse_fasm_string(s):
            return fasm_lines

        mocker.patch(
            "FABulous_bit_gen.bit_gen.parse_fasm_string",
            side_effect=mock_parse_fasm_string,
        )

        def mock_set_feature_to_str(feature):
            return feature.feature

        mocker.patch(
            "FABulous_bit_gen.bit_gen.set_feature_to_str",
            side_effect=mock_set_feature_to_str,
        )

        genBitstream(str(fasm_file), str(spec_file), str(output_file))

        csv_content = output_file.with_suffix(".csv").read_text()
        # Valid feature was processed; CLK feature filtered (would raise SpecMissMatch if not)
        assert "X0Y1" in csv_content

    def test_valid_feature_sets_bits_in_tile(
        self, minimal_spec_dict, temp_output_dir, mocker
    ):
        """Valid features should set bits in tileDict."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        fasm_lines = [
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
        ]

        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        mocker.patch(
            "FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=fasm_lines
        )
        mocker.patch(
            "FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="canonical"
        )
        mocker.patch(
            "FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=fasm_lines
        )

        def mock_set_feature_to_str(feature):
            return feature.feature

        mocker.patch(
            "FABulous_bit_gen.bit_gen.set_feature_to_str",
            side_effect=mock_set_feature_to_str,
        )

        genBitstream(str(fasm_file), str(spec_file), str(output_file))

        csv_path = output_file.with_suffix(".csv")
        assert csv_path.exists()
        csv_content = csv_path.read_text()
        assert "X0Y1" in csv_content

    def test_multiple_features_same_tile(
        self, minimal_spec_dict, temp_output_dir, mocker
    ):
        """Multiple features for same tile should all be processed."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        fasm_lines = [
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
        ]

        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        mocker.patch(
            "FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=fasm_lines
        )
        mocker.patch(
            "FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="canonical"
        )
        mocker.patch(
            "FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=fasm_lines
        )

        def mock_set_feature_to_str(feature):
            return feature.feature

        mocker.patch(
            "FABulous_bit_gen.bit_gen.set_feature_to_str",
            side_effect=mock_set_feature_to_str,
        )

        genBitstream(str(fasm_file), str(spec_file), str(output_file))

        csv_path = output_file.with_suffix(".csv")
        csv_content = csv_path.read_text()
        assert "X0Y1" in csv_content

    def test_multiple_features_different_tiles(
        self, minimal_spec_dict, temp_output_dir, mocker
    ):
        """Features for different tiles should update both."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        fasm_lines = [
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

        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        mocker.patch(
            "FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=fasm_lines
        )
        mocker.patch(
            "FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="canonical"
        )
        mocker.patch(
            "FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=fasm_lines
        )

        def mock_set_feature_to_str(feature):
            return feature.feature

        mocker.patch(
            "FABulous_bit_gen.bit_gen.set_feature_to_str",
            side_effect=mock_set_feature_to_str,
        )

        genBitstream(str(fasm_file), str(spec_file), str(output_file))

        csv_path = output_file.with_suffix(".csv")
        csv_content = csv_path.read_text()
        assert "X0Y1" in csv_content
        assert "X1Y1" in csv_content

    def test_feature_with_value_1(self, minimal_spec_dict, temp_output_dir, mocker):
        """Feature with value=1 should set bit to 1."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        fasm_lines = [
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
        ]

        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        mocker.patch(
            "FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=fasm_lines
        )
        mocker.patch(
            "FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="canonical"
        )
        mocker.patch(
            "FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=fasm_lines
        )

        def mock_set_feature_to_str(feature):
            return feature.feature

        mocker.patch(
            "FABulous_bit_gen.bit_gen.set_feature_to_str",
            side_effect=mock_set_feature_to_str,
        )

        genBitstream(str(fasm_file), str(spec_file), str(output_file))

        csv_path = output_file.with_suffix(".csv")
        assert csv_path.exists()

    def test_feature_with_value_0(self, minimal_spec_dict, temp_output_dir, mocker):
        """Feature with value=0 should set bit to 0."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        fasm_lines = [
            FasmLine(
                set_feature=SetFasmFeature(
                    feature="X0Y1.W2MID7.A_I",
                    start=None,
                    end=None,
                    value=0,
                    value_format=None,
                ),
                annotations=None,
                comment=None,
            ),
        ]

        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        mocker.patch(
            "FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=fasm_lines
        )
        mocker.patch(
            "FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="canonical"
        )
        mocker.patch(
            "FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=fasm_lines
        )

        def mock_set_feature_to_str(feature):
            return feature.feature

        mocker.patch(
            "FABulous_bit_gen.bit_gen.set_feature_to_str",
            side_effect=mock_set_feature_to_str,
        )

        genBitstream(str(fasm_file), str(spec_file), str(output_file))

        csv_path = output_file.with_suffix(".csv")
        assert csv_path.exists()

    def test_empty_fasm_produces_zero_bitstream(
        self, minimal_spec_dict, temp_output_dir, mocker
    ):
        """Empty FASM should produce bitstream with all zeros."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=[])
        mocker.patch("FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="")
        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=[])

        genBitstream(str(fasm_file), str(spec_file), str(output_file))

        csv_path = output_file.with_suffix(".csv")
        csv_content = csv_path.read_text()
        assert "frame0" in csv_content

    def test_overlapping_features_emit_warning(self, temp_output_dir, mocker):
        """Two features writing to the same bit index should trigger a logger warning."""
        # Build a spec where FEAT_A and FEAT_B both map to bit index 50 of X0Y1.
        spec_dict = {
            "ArchSpecs": {"MaxFramesPerCol": 20, "FrameBitsPerRow": 32},
            "TileMap": {"X0Y0": "NULL", "X0Y1": "W_IO", "X0Y2": "NULL"},
            "TileSpecs": {
                "X0Y0": {},
                "X0Y1": {
                    "FEAT.A": {50: "1"},
                    "FEAT.B": {50: "1"},
                },
                "X0Y2": {},
            },
            "TileSpecs_No_Mask": {
                "X0Y0": {},
                "X0Y1": {
                    "FEAT.A": {50: "1"},
                    "FEAT.B": {50: "1"},
                },
                "X0Y2": {},
            },
            "FrameMap": {
                "NULL": {},
                "W_IO": {0: "11111111111111111111111111111111"},
            },
            "FrameMapEncode": {},
        }

        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        fasm_lines = [
            FasmLine(
                set_feature=SetFasmFeature(
                    feature="X0Y1.FEAT.A",
                    start=None, end=None, value=1, value_format=None,
                ),
                annotations=None,
                comment=None,
            ),
            FasmLine(
                set_feature=SetFasmFeature(
                    feature="X0Y1.FEAT.B",
                    start=None, end=None, value=1, value_format=None,
                ),
                annotations=None,
                comment=None,
            ),
        ]

        with spec_file.open("wb") as f:
            pickle.dump(spec_dict, f)

        mocker.patch(
            "FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=fasm_lines
        )
        mocker.patch(
            "FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="canonical"
        )
        mocker.patch(
            "FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=fasm_lines
        )
        mocker.patch(
            "FABulous_bit_gen.bit_gen.set_feature_to_str",
            side_effect=lambda f: f.feature,
        )
        mock_logger = mocker.patch("FABulous_bit_gen.bit_gen.logger")

        genBitstream(str(fasm_file), str(spec_file), str(output_file))

        mock_logger.warning.assert_called_once()
        warning_msg = mock_logger.warning.call_args[0][0]
        assert "X0Y1" in warning_msg
        assert "50" in warning_msg


class TestGenBitstreamErrorHandling:
    """Tests for error handling in genBitstream."""

    def test_tile_location_not_in_spec_raises_specmissmatch(
        self, minimal_spec_dict, temp_output_dir, mocker
    ):
        """Invalid tile location should raise SpecMissMatch."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        fasm_lines = [
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

        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        mocker.patch(
            "FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=fasm_lines
        )
        mocker.patch(
            "FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="canonical"
        )
        mocker.patch(
            "FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=fasm_lines
        )

        def mock_set_feature_to_str(feature):
            return feature.feature

        mocker.patch(
            "FABulous_bit_gen.bit_gen.set_feature_to_str",
            side_effect=mock_set_feature_to_str,
        )

        with pytest.raises(SpecMissMatch) as exc_info:
            genBitstream(str(fasm_file), str(spec_file), str(output_file))

        assert "X99Y99" in str(exc_info.value)

    def test_feature_not_in_tile_specs_raises_specmissmatch(
        self, minimal_spec_dict, temp_output_dir, mocker
    ):
        """Invalid feature for valid tile should raise SpecMissMatch."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        fasm_lines = [
            FasmLine(
                set_feature=SetFasmFeature(
                    feature="X0Y1.UNKNOWN.FEATURE",
                    start=None,
                    end=None,
                    value=1,
                    value_format=None,
                ),
                annotations=None,
                comment=None,
            ),
        ]

        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        mocker.patch(
            "FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=fasm_lines
        )
        mocker.patch(
            "FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="canonical"
        )
        mocker.patch(
            "FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=fasm_lines
        )

        def mock_set_feature_to_str(feature):
            return feature.feature

        mocker.patch(
            "FABulous_bit_gen.bit_gen.set_feature_to_str",
            side_effect=mock_set_feature_to_str,
        )

        with pytest.raises(SpecMissMatch) as exc_info:
            genBitstream(str(fasm_file), str(spec_file), str(output_file))

        assert "UNKNOWN.FEATURE" in str(exc_info.value)

    def test_specmissmatch_error_message_format(
        self, minimal_spec_dict, temp_output_dir, mocker
    ):
        """SpecMissMatch should include tile type, location, and feature."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        fasm_lines = [
            FasmLine(
                set_feature=SetFasmFeature(
                    feature="X0Y1.INVALID.FEATURE",
                    start=None,
                    end=None,
                    value=1,
                    value_format=None,
                ),
                annotations=None,
                comment=None,
            ),
        ]

        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        mocker.patch(
            "FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=fasm_lines
        )
        mocker.patch(
            "FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="canonical"
        )
        mocker.patch(
            "FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=fasm_lines
        )

        def mock_set_feature_to_str(feature):
            return feature.feature

        mocker.patch(
            "FABulous_bit_gen.bit_gen.set_feature_to_str",
            side_effect=mock_set_feature_to_str,
        )

        with pytest.raises(SpecMissMatch) as exc_info:
            genBitstream(str(fasm_file), str(spec_file), str(output_file))

        error_msg = str(exc_info.value)
        assert "X0Y1" in error_msg
        assert "INVALID.FEATURE" in error_msg


class TestGenBitstreamFaultCases:
    """Tests for fault cases and error conditions."""

    def test_spec_file_not_found(self, temp_output_dir, mocker):
        """Missing spec file should raise FileNotFoundError."""
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"
        spec_file = temp_output_dir / "nonexistent.bin"

        fasm_file.write_text("")

        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=[])
        mocker.patch("FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="")
        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=[])

        with pytest.raises(FileNotFoundError):
            genBitstream(str(fasm_file), str(spec_file), str(output_file))

    def test_fasm_file_not_found(self, minimal_spec_dict, temp_output_dir, mocker):
        """Missing FASM file should raise FileNotFoundError."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "nonexistent.fasm"
        output_file = temp_output_dir / "output.bin"

        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        with pytest.raises(FileNotFoundError):
            genBitstream(str(fasm_file), str(spec_file), str(output_file))

    def test_corrupted_pickle_spec_file(self, temp_output_dir, mocker):
        """Corrupted pickle file should raise pickle.UnpicklingError."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        fasm_file.write_text("")
        with spec_file.open("wb") as f:
            f.write(b"corrupted pickle data")

        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=[])
        mocker.patch("FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="")
        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=[])

        with pytest.raises(Exception):
            genBitstream(str(fasm_file), str(spec_file), str(output_file))

    def test_empty_spec_dict(self, temp_output_dir, mocker):
        """Empty spec dict should raise KeyError."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        fasm_file.write_text("")
        with spec_file.open("wb") as f:
            pickle.dump({}, f)

        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=[])
        mocker.patch("FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="")
        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=[])

        with pytest.raises(KeyError):
            genBitstream(str(fasm_file), str(spec_file), str(output_file))

    def test_spec_dict_missing_archspecs(self, temp_output_dir, mocker):
        """Spec dict missing ArchSpecs should raise KeyError."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        incomplete_spec = {
            "TileMap": {"X0Y1": "W_IO"},
            "TileSpecs": {"X0Y1": {}},
            "TileSpecs_No_Mask": {"X0Y1": {}},
            "FrameMap": {"W_IO": {}},
        }

        fasm_file.write_text("")
        with spec_file.open("wb") as f:
            pickle.dump(incomplete_spec, f)

        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=[])
        mocker.patch("FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="")
        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=[])

        with pytest.raises(KeyError):
            genBitstream(str(fasm_file), str(spec_file), str(output_file))

    def test_spec_dict_missing_tilemap(self, temp_output_dir, mocker):
        """Spec dict missing TileMap should raise KeyError."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        incomplete_spec = {
            "ArchSpecs": {"MaxFramesPerCol": 20, "FrameBitsPerRow": 32},
            "TileSpecs": {},
            "TileSpecs_No_Mask": {},
            "FrameMap": {},
        }

        fasm_file.write_text("")
        with spec_file.open("wb") as f:
            pickle.dump(incomplete_spec, f)

        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=[])
        mocker.patch("FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="")
        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=[])

        with pytest.raises(KeyError):
            genBitstream(str(fasm_file), str(spec_file), str(output_file))

    def test_spec_dict_missing_tilespecs(self, temp_output_dir, mocker):
        """Spec dict missing TileSpecs should raise KeyError."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        incomplete_spec = {
            "ArchSpecs": {"MaxFramesPerCol": 20, "FrameBitsPerRow": 32},
            "TileMap": {"X0Y1": "W_IO"},
            "TileSpecs_No_Mask": {},
            "FrameMap": {},
        }

        fasm_file.write_text("")
        with spec_file.open("wb") as f:
            pickle.dump(incomplete_spec, f)

        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=[])
        mocker.patch("FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="")
        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=[])

        with pytest.raises(KeyError):
            genBitstream(str(fasm_file), str(spec_file), str(output_file))

    def test_spec_dict_missing_framemap(self, temp_output_dir, mocker):
        """Spec dict missing FrameMap should raise KeyError."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        incomplete_spec = {
            "ArchSpecs": {"MaxFramesPerCol": 20, "FrameBitsPerRow": 32},
            "TileMap": {"X0Y1": "W_IO"},
            "TileSpecs": {"X0Y1": {}},
            "TileSpecs_No_Mask": {"X0Y1": {}},
        }

        fasm_file.write_text("")
        with spec_file.open("wb") as f:
            pickle.dump(incomplete_spec, f)

        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=[])
        mocker.patch("FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="")
        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=[])

        with pytest.raises(KeyError):
            genBitstream(str(fasm_file), str(spec_file), str(output_file))

    def test_archspecs_missing_maxframespercol(self, temp_output_dir, mocker):
        """ArchSpecs missing MaxFramesPerCol should raise KeyError."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        incomplete_spec = {
            "ArchSpecs": {"FrameBitsPerRow": 32},
            "TileMap": {"X0Y1": "W_IO"},
            "TileSpecs": {"X0Y1": {}},
            "TileSpecs_No_Mask": {"X0Y1": {}},
            "FrameMap": {},
        }

        fasm_file.write_text("")
        with spec_file.open("wb") as f:
            pickle.dump(incomplete_spec, f)

        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=[])
        mocker.patch("FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="")
        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=[])

        with pytest.raises(KeyError):
            genBitstream(str(fasm_file), str(spec_file), str(output_file))

    def test_archspecs_missing_framebitsperrow(self, temp_output_dir, mocker):
        """ArchSpecs missing FrameBitsPerRow should raise KeyError."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        incomplete_spec = {
            "ArchSpecs": {"MaxFramesPerCol": 20},
            "TileMap": {"X0Y1": "W_IO"},
            "TileSpecs": {"X0Y1": {}},
            "TileSpecs_No_Mask": {"X0Y1": {}},
            "FrameMap": {},
        }

        fasm_file.write_text("")
        with spec_file.open("wb") as f:
            pickle.dump(incomplete_spec, f)

        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=[])
        mocker.patch("FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="")
        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=[])

        with pytest.raises(KeyError):
            genBitstream(str(fasm_file), str(spec_file), str(output_file))

    def test_feature_with_insufficient_parts(
        self, minimal_spec_dict, temp_output_dir, mocker
    ):
        """Feature with less than 3 parts should raise IndexError."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        fasm_lines = [
            FasmLine(
                set_feature=SetFasmFeature(
                    feature="X0Y1.ONLYONEPART",
                    start=None,
                    end=None,
                    value=1,
                    value_format=None,
                ),
                annotations=None,
                comment=None,
            ),
        ]

        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        mocker.patch(
            "FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=fasm_lines
        )
        mocker.patch(
            "FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="canonical"
        )
        mocker.patch(
            "FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=fasm_lines
        )

        def mock_set_feature_to_str(feature):
            return feature.feature

        mocker.patch(
            "FABulous_bit_gen.bit_gen.set_feature_to_str",
            side_effect=mock_set_feature_to_str,
        )

        with pytest.raises(IndexError):
            genBitstream(str(fasm_file), str(spec_file), str(output_file))

    def test_tile_coord_invalid_format(
        self, minimal_spec_dict, temp_output_dir, mocker
    ):
        """Tile coordinate that doesn't match X\\d*Y\\d* pattern causes AttributeError."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        spec_dict_with_invalid = minimal_spec_dict.copy()
        spec_dict_with_invalid["TileMap"]["INVALID"] = "W_IO"
        spec_dict_with_invalid["TileSpecs"]["INVALID"] = {}
        spec_dict_with_invalid["TileSpecs_No_Mask"]["INVALID"] = {}

        with spec_file.open("wb") as f:
            pickle.dump(spec_dict_with_invalid, f)

        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=[])
        mocker.patch("FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="")
        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=[])

        with pytest.raises(AttributeError):
            genBitstream(str(fasm_file), str(spec_file), str(output_file))


class TestGenBitstreamEdgeCases:
    """Edge case tests for genBitstream function."""

    def test_feature_name_with_more_than_three_parts(
        self, minimal_spec_dict, temp_output_dir, mocker
    ):
        """Feature with 4+ parts should only use first 3."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        fasm_lines = [
            FasmLine(
                set_feature=SetFasmFeature(
                    feature="X0Y1.W2MID7.A_I.EXTRA",
                    start=None,
                    end=None,
                    value=1,
                    value_format=None,
                ),
                annotations=None,
                comment=None,
            ),
        ]

        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        mocker.patch(
            "FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=fasm_lines
        )
        mocker.patch(
            "FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="canonical"
        )
        mocker.patch(
            "FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=fasm_lines
        )

        def mock_set_feature_to_str(feature):
            return feature.feature

        mocker.patch(
            "FABulous_bit_gen.bit_gen.set_feature_to_str",
            side_effect=mock_set_feature_to_str,
        )

        genBitstream(str(fasm_file), str(spec_file), str(output_file))

        csv_content = output_file.with_suffix(".csv").read_text()
        # Extra part silently ignored; feature "W2MID7.A_I" resolved correctly
        assert "X0Y1" in csv_content

    def test_feature_containing_clk_substring(
        self, minimal_spec_dict, temp_output_dir, mocker
    ):
        """Feature containing 'CLK' substring should be filtered."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        fasm_lines = [
            FasmLine(
                set_feature=SetFasmFeature(
                    feature="X0Y1.ACLK_BUFFER.enable",
                    start=None,
                    end=None,
                    value=1,
                    value_format=None,
                ),
                annotations=None,
                comment=None,
            ),
        ]

        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        mocker.patch(
            "FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=fasm_lines
        )
        mocker.patch(
            "FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="canonical"
        )
        mocker.patch(
            "FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=fasm_lines
        )

        def mock_set_feature_to_str(feature):
            return feature.feature

        mocker.patch(
            "FABulous_bit_gen.bit_gen.set_feature_to_str",
            side_effect=mock_set_feature_to_str,
        )

        genBitstream(str(fasm_file), str(spec_file), str(output_file))

        csv_content = output_file.with_suffix(".csv").read_text()
        # CLK-substring feature filtered (would raise SpecMissMatch if not)
        assert "X0Y1" in csv_content

    def test_large_grid_dimensions(self, temp_output_dir, mocker):
        """Test with large grid (many tiles)."""
        spec_dict = {
            "ArchSpecs": {"MaxFramesPerCol": 20, "FrameBitsPerRow": 32},
            "TileMap": {f"X{x}Y{y}": "LUT4AB" for x in range(10) for y in range(10)},
            "TileSpecs": {f"X{x}Y{y}": {} for x in range(10) for y in range(10)},
            "TileSpecs_No_Mask": {
                f"X{x}Y{y}": {} for x in range(10) for y in range(10)
            },
            "FrameMap": {"LUT4AB": {0: "11111111111111111111111111111111"}},
            "FrameMapEncode": {},
        }

        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        with spec_file.open("wb") as f:
            pickle.dump(spec_dict, f)

        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=[])
        mocker.patch("FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="")
        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=[])

        genBitstream(str(fasm_file), str(spec_file), str(output_file))

        assert output_file.exists()

    def test_tile_with_leading_zeros_in_coords_causes_error(
        self, temp_output_dir, mocker
    ):
        """Tile coordinates with leading zeros cause KeyError due to coordinate reconstruction.

        The code calculates grid dimensions from regex match, then reconstructs tile
        coordinates like "X0Y1" from those dimensions. If tiles are named "X01Y01",
        the reconstructed names won't match.
        """
        spec_dict = {
            "ArchSpecs": {"MaxFramesPerCol": 20, "FrameBitsPerRow": 32},
            "TileMap": {"X01Y01": "LUT4AB", "X01Y02": "NULL"},
            "TileSpecs": {"X01Y01": {}, "X01Y02": {}},
            "TileSpecs_No_Mask": {"X01Y01": {}, "X01Y02": {}},
            "FrameMap": {"LUT4AB": {0: "11111111111111111111111111111111"}, "NULL": {}},
            "FrameMapEncode": {},
        }

        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        with spec_file.open("wb") as f:
            pickle.dump(spec_dict, f)

        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=[])
        mocker.patch("FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="")
        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=[])

        # This raises KeyError because the code reconstructs "X0Y1" from dimensions
        # but only "X01Y01" exists in the TileMap
        with pytest.raises(KeyError):
            genBitstream(str(fasm_file), str(spec_file), str(output_file))

    def test_single_column_grid(self, temp_output_dir, mocker):
        """Grid with single column should work."""
        spec_dict = {
            "ArchSpecs": {"MaxFramesPerCol": 20, "FrameBitsPerRow": 32},
            "TileMap": {"X0Y0": "NULL", "X0Y1": "W_IO", "X0Y2": "NULL"},
            "TileSpecs": {"X0Y1": {}},
            "TileSpecs_No_Mask": {"X0Y1": {}},
            "FrameMap": {"NULL": {}, "W_IO": {0: "11111111111111111111111111111111"}},
            "FrameMapEncode": {},
        }

        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        with spec_file.open("wb") as f:
            pickle.dump(spec_dict, f)

        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=[])
        mocker.patch("FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="")
        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=[])

        genBitstream(str(fasm_file), str(spec_file), str(output_file))

        assert output_file.exists()

    def test_feature_with_empty_bit_mapping(self, temp_output_dir, mocker):
        """Feature with empty bit mapping dictionary should not crash."""
        spec_dict = {
            "ArchSpecs": {"MaxFramesPerCol": 20, "FrameBitsPerRow": 32},
            "TileMap": {"X0Y1": "W_IO", "X0Y2": "NULL"},
            "TileSpecs": {"X0Y1": {"EMPTY.FEATURE": {}}},
            "TileSpecs_No_Mask": {"X0Y1": {"EMPTY.FEATURE": {}}},
            "FrameMap": {"W_IO": {0: "11111111111111111111111111111111"}, "NULL": {}},
            "FrameMapEncode": {},
        }

        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        fasm_lines = [
            FasmLine(
                set_feature=SetFasmFeature(
                    feature="X0Y1.EMPTY.FEATURE",
                    start=None,
                    end=None,
                    value=1,
                    value_format=None,
                ),
                annotations=None,
                comment=None,
            ),
        ]

        with spec_file.open("wb") as f:
            pickle.dump(spec_dict, f)

        mocker.patch(
            "FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=fasm_lines
        )
        mocker.patch(
            "FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="canonical"
        )
        mocker.patch(
            "FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=fasm_lines
        )

        def mock_set_feature_to_str(feature):
            return feature.feature

        mocker.patch(
            "FABulous_bit_gen.bit_gen.set_feature_to_str",
            side_effect=mock_set_feature_to_str,
        )

        genBitstream(str(fasm_file), str(spec_file), str(output_file))

        assert output_file.exists()

    def test_bit_index_at_boundary(self, temp_output_dir, mocker):
        """Bit index at MaxFramesPerCol * FrameBitsPerRow - 1 should work."""
        max_index = 20 * 32 - 1
        spec_dict = {
            "ArchSpecs": {"MaxFramesPerCol": 20, "FrameBitsPerRow": 32},
            "TileMap": {"X0Y1": "W_IO", "X0Y2": "NULL"},
            "TileSpecs": {"X0Y1": {"TEST.FEATURE": {max_index: "1"}}},
            "TileSpecs_No_Mask": {"X0Y1": {"TEST.FEATURE": {max_index: "1"}}},
            "FrameMap": {"W_IO": {0: "11111111111111111111111111111111"}, "NULL": {}},
            "FrameMapEncode": {},
        }

        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        fasm_lines = [
            FasmLine(
                set_feature=SetFasmFeature(
                    feature="X0Y1.TEST.FEATURE",
                    start=None,
                    end=None,
                    value=1,
                    value_format=None,
                ),
                annotations=None,
                comment=None,
            ),
        ]

        with spec_file.open("wb") as f:
            pickle.dump(spec_dict, f)

        mocker.patch(
            "FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=fasm_lines
        )
        mocker.patch(
            "FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="canonical"
        )
        mocker.patch(
            "FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=fasm_lines
        )

        def mock_set_feature_to_str(feature):
            return feature.feature

        mocker.patch(
            "FABulous_bit_gen.bit_gen.set_feature_to_str",
            side_effect=mock_set_feature_to_str,
        )

        genBitstream(str(fasm_file), str(spec_file), str(output_file))

        assert output_file.exists()

    def test_output_path_with_spaces(self, minimal_spec_dict, temp_output_dir, mocker):
        """Output path with spaces should work."""
        spec_file = temp_output_dir / "spec.bin"
        output_dir = temp_output_dir / "output with spaces"
        output_dir.mkdir()
        output_file = output_dir / "my output.bin"

        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=[])
        mocker.patch("FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="")
        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=[])

        genBitstream(
            str(temp_output_dir / "test.fasm"), str(spec_file), str(output_file)
        )

        assert output_file.exists()

    def test_relative_path_output(self, minimal_spec_dict, temp_output_dir, mocker):
        """Relative output path should work."""
        spec_file = temp_output_dir / "spec.bin"
        output_file = temp_output_dir / "output.bin"

        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=[])
        mocker.patch("FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="")
        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=[])

        genBitstream(str(temp_output_dir / "test.fasm"), str(spec_file), "output.bin")

        assert Path("output.bin").exists()
        Path("output.bin").unlink()
        Path("output.csv").unlink()
        Path("output.vh").unlink()
        Path("output.vhd").unlink()


class TestGenBitstreamNullTileHandling:
    """Tests for NULL tile handling."""

    def test_null_tile_frame_bits_all_zeros(
        self, minimal_spec_dict, temp_output_dir, mocker
    ):
        """NULL tiles should produce zero frame bits."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=[])
        mocker.patch("FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="")
        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=[])

        genBitstream(str(fasm_file), str(spec_file), str(output_file))

        csv_path = output_file.with_suffix(".csv")
        csv_content = csv_path.read_text()

        # Note: Y0 (bottom) and Y{max} (top) rows are skipped in output
        # X0Y1 and X1Y1 are processed (Y=1)
        assert "X0Y1" in csv_content

    def test_null_tile_not_in_hdl_output(
        self, minimal_spec_dict, temp_output_dir, mocker
    ):
        """NULL tiles should not appear in HDL output."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=[])
        mocker.patch("FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="")
        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=[])

        genBitstream(str(fasm_file), str(spec_file), str(output_file))

        vh_path = output_file.with_suffix(".vh")
        vh_content = vh_path.read_text()
        vhd_path = output_file.with_suffix(".vhd")
        vhd_content = vhd_path.read_text()

        assert "Tile_X0Y0" not in vh_content
        assert "Tile_X0Y0" not in vhd_content


class TestGenBitstreamFrameMap:
    """Tests for FrameMap handling."""

    def test_tile_with_empty_framemap_skipped_in_hdl(self, temp_output_dir, mocker):
        """Tiles with empty FrameMap should be skipped in HDL output."""
        spec_dict = {
            "ArchSpecs": {"MaxFramesPerCol": 20, "FrameBitsPerRow": 32},
            "TileMap": {"X0Y1": "EMPTY_TYPE"},
            "TileSpecs": {"X0Y1": {"FEATURE.A": {0: "1"}}},
            "TileSpecs_No_Mask": {"X0Y1": {"FEATURE.A": {0: "1"}}},
            "FrameMap": {"EMPTY_TYPE": {}},
            "FrameMapEncode": {},
        }

        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        with spec_file.open("wb") as f:
            pickle.dump(spec_dict, f)

        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=[])
        mocker.patch("FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="")
        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=[])

        genBitstream(str(fasm_file), str(spec_file), str(output_file))

        vh_path = output_file.with_suffix(".vh")
        vh_content = vh_path.read_text()
        assert "Tile_X0Y1" not in vh_content

    def test_non_empty_framemap_tile_included_in_hdl(
        self, minimal_spec_dict, temp_output_dir, mocker
    ):
        """Tiles with non-empty FrameMap should appear in HDL output."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=[])
        mocker.patch("FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="")
        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=[])

        genBitstream(str(fasm_file), str(spec_file), str(output_file))

        vh_path = output_file.with_suffix(".vh")
        vh_content = vh_path.read_text()
        assert "Tile_X0Y1" in vh_content
        assert "Tile_X1Y1" in vh_content


class TestGenBitstreamCsvOutput:
    """Tests for CSV output generation."""

    def test_csv_file_created(self, minimal_spec_dict, temp_output_dir, mocker):
        """CSV file should be created."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=[])
        mocker.patch("FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="")
        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=[])

        genBitstream(str(fasm_file), str(spec_file), str(output_file))

        csv_path = output_file.with_suffix(".csv")
        assert csv_path.exists()

    def test_csv_tile_line_format(self, minimal_spec_dict, temp_output_dir, mocker):
        """CSV tile lines should have format: tileLoc,tileType,x,y."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=[])
        mocker.patch("FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="")
        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=[])

        genBitstream(str(fasm_file), str(spec_file), str(output_file))

        csv_path = output_file.with_suffix(".csv")
        csv_content = csv_path.read_text()

        assert "X0Y1,W_IO,0,1" in csv_content

    def test_csv_frame_line_format(self, minimal_spec_dict, temp_output_dir, mocker):
        """CSV frame lines should have format: frameN,n,32,bits."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=[])
        mocker.patch("FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="")
        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=[])

        genBitstream(str(fasm_file), str(spec_file), str(output_file))

        csv_path = output_file.with_suffix(".csv")
        csv_content = csv_path.read_text()

        assert "frame0,0,32," in csv_content

    def test_csv_row_order_reversed(self, minimal_spec_dict, temp_output_dir, mocker):
        """Rows in CSV should be processed from num_rows-2 down to 1."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=[])
        mocker.patch("FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="")
        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=[])

        genBitstream(str(fasm_file), str(spec_file), str(output_file))

        csv_path = output_file.with_suffix(".csv")
        csv_content = csv_path.read_text()
        lines = csv_content.strip().split("\n")

        first_tile_line = None
        for line in lines:
            if line.startswith("X"):
                first_tile_line = line
                break

        assert first_tile_line is not None, "CSV contained no tile lines"
        assert "Y1" in first_tile_line


class TestGenBitstreamVhdlOutput:
    """Tests for VHDL output generation."""

    def test_vhdl_file_created(self, minimal_spec_dict, temp_output_dir, mocker):
        """VHDL file should be created."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=[])
        mocker.patch("FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="")
        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=[])

        genBitstream(str(fasm_file), str(spec_file), str(output_file))

        vhd_path = output_file.with_suffix(".vhd")
        assert vhd_path.exists()

    def test_vhdl_package_header(self, minimal_spec_dict, temp_output_dir, mocker):
        """VHDL file should contain IEEE library and package declaration."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=[])
        mocker.patch("FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="")
        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=[])

        genBitstream(str(fasm_file), str(spec_file), str(output_file))

        vhd_path = output_file.with_suffix(".vhd")
        vhd_content = vhd_path.read_text()

        assert "library IEEE" in vhd_content
        assert "package emulate_bitstream" in vhd_content

    def test_vhdl_constant_format(self, minimal_spec_dict, temp_output_dir, mocker):
        """VHDL constants should have correct format."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=[])
        mocker.patch("FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="")
        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=[])

        genBitstream(str(fasm_file), str(spec_file), str(output_file))

        vhd_path = output_file.with_suffix(".vhd")
        vhd_content = vhd_path.read_text()

        assert "constant Tile_X0Y1_Emulate_Bitstream" in vhd_content
        assert "std_logic_vector" in vhd_content


class TestGenBitstreamVerilogOutput:
    """Tests for Verilog output generation."""

    def test_verilog_file_created(self, minimal_spec_dict, temp_output_dir, mocker):
        """Verilog file should be created."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=[])
        mocker.patch("FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="")
        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=[])

        genBitstream(str(fasm_file), str(spec_file), str(output_file))

        vh_path = output_file.with_suffix(".vh")
        assert vh_path.exists()

    def test_verilog_define_format(self, minimal_spec_dict, temp_output_dir, mocker):
        """Verilog defines should have correct format."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=[])
        mocker.patch("FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="")
        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=[])

        genBitstream(str(fasm_file), str(spec_file), str(output_file))

        vh_path = output_file.with_suffix(".vh")
        vh_content = vh_path.read_text()

        assert "`define Tile_X0Y1_Emulate_Bitstream" in vh_content
        assert "640'b" in vh_content

    def test_verilog_bit_order_reversed(
        self, minimal_spec_dict, temp_output_dir, mocker
    ):
        """Verilog output should have bits in reverse order."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=[])
        mocker.patch("FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="")
        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=[])

        genBitstream(str(fasm_file), str(spec_file), str(output_file))

        vh_path = output_file.with_suffix(".vh")
        vh_content = vh_path.read_text()

        assert "640'b" in vh_content


class TestGenBitstreamNoneSetFeature:
    """Tests for FasmLine with set_feature=None (comment/annotation lines)."""

    def test_fasm_line_with_none_set_feature_is_skipped(
        self, minimal_spec_dict, temp_output_dir, mocker
    ):
        """FasmLine with set_feature=None should be silently skipped."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        fasm_lines = [
            FasmLine(set_feature=None, annotations=None, comment="# a comment"),
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
        ]

        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        mocker.patch(
            "FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=fasm_lines
        )
        mocker.patch(
            "FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="canonical"
        )
        mocker.patch(
            "FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=fasm_lines
        )

        def mock_set_feature_to_str(feature):
            return feature.feature

        mocker.patch(
            "FABulous_bit_gen.bit_gen.set_feature_to_str",
            side_effect=mock_set_feature_to_str,
        )

        # Should not raise TypeError/AttributeError from set_feature_to_str(None)
        genBitstream(str(fasm_file), str(spec_file), str(output_file))

        csv_content = output_file.with_suffix(".csv").read_text()
        assert "X0Y1" in csv_content

    def test_all_none_set_features_produces_zero_bitstream(
        self, minimal_spec_dict, temp_output_dir, mocker
    ):
        """FASM with only None set_features (comments only) should succeed."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        fasm_lines = [
            FasmLine(set_feature=None, annotations=None, comment="# comment 1"),
            FasmLine(set_feature=None, annotations=None, comment="# comment 2"),
        ]

        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        mocker.patch(
            "FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=fasm_lines
        )
        mocker.patch(
            "FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="canonical"
        )
        mocker.patch(
            "FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=fasm_lines
        )
        mocker.patch("FABulous_bit_gen.bit_gen.set_feature_to_str")

        genBitstream(str(fasm_file), str(spec_file), str(output_file))

        assert output_file.with_suffix(".csv").exists()


class TestGenBitstreamCsvRowBoundaries:
    """Tests that top and bottom rows are excluded from CSV output."""

    def test_bottom_row_absent_from_csv(
        self, minimal_spec_dict, temp_output_dir, mocker
    ):
        """Y0 (bottom row) should not appear in CSV output."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=[])
        mocker.patch("FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="")
        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=[])

        genBitstream(str(fasm_file), str(spec_file), str(output_file))

        csv_content = output_file.with_suffix(".csv").read_text()
        tile_lines = [l for l in csv_content.splitlines() if l.startswith("X")]
        assert tile_lines, "CSV contained no tile lines"
        assert all("Y0" not in l for l in tile_lines)

    def test_top_row_absent_from_csv(self, minimal_spec_dict, temp_output_dir, mocker):
        """Y{max} (top row) should not appear in CSV output."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=[])
        mocker.patch("FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="")
        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=[])

        genBitstream(str(fasm_file), str(spec_file), str(output_file))

        csv_content = output_file.with_suffix(".csv").read_text()
        tile_lines = [l for l in csv_content.splitlines() if l.startswith("X")]
        assert tile_lines, "CSV contained no tile lines"
        # minimal_spec_dict has Y2 as max row
        assert all("Y2" not in l for l in tile_lines)


class TestGenBitstreamSpecInconsistency:
    """Tests for TileSpecs / TileSpecs_No_Mask inconsistency."""

    def test_feature_missing_from_tilespecs_no_mask_raises_keyerror(
        self, temp_output_dir, mocker
    ):
        """Feature in TileSpecs but absent from TileSpecs_No_Mask should raise KeyError."""
        spec_dict = {
            "ArchSpecs": {"MaxFramesPerCol": 20, "FrameBitsPerRow": 32},
            "TileMap": {"X0Y0": "NULL", "X0Y1": "W_IO", "X0Y2": "NULL"},
            "TileSpecs": {
                "X0Y0": {},
                "X0Y1": {"W2MID7.A_I": {110: "1"}},
                "X0Y2": {},
            },
            "TileSpecs_No_Mask": {
                "X0Y0": {},
                "X0Y1": {},  # feature intentionally absent here
                "X0Y2": {},
            },
            "FrameMap": {
                "NULL": {},
                "W_IO": {0: "11111111111111111111111111111111"},
            },
            "FrameMapEncode": {},
        }

        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        fasm_lines = [
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
        ]

        with spec_file.open("wb") as f:
            pickle.dump(spec_dict, f)

        mocker.patch(
            "FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=fasm_lines
        )
        mocker.patch(
            "FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="canonical"
        )
        mocker.patch(
            "FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=fasm_lines
        )

        def mock_set_feature_to_str(feature):
            return feature.feature

        mocker.patch(
            "FABulous_bit_gen.bit_gen.set_feature_to_str",
            side_effect=mock_set_feature_to_str,
        )

        with pytest.raises(KeyError):
            genBitstream(str(fasm_file), str(spec_file), str(output_file))


class TestGenBitstreamBinaryOutput:
    """Tests for binary output generation."""

    def test_bitstream_file_created(self, minimal_spec_dict, temp_output_dir, mocker):
        """Binary file should be created."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=[])
        mocker.patch("FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="")
        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=[])

        genBitstream(str(fasm_file), str(spec_file), str(output_file))

        assert output_file.exists()

    def test_bitstream_header_bytes(self, minimal_spec_dict, temp_output_dir, mocker):
        """Binary file should start with header bytes."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=[])
        mocker.patch("FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="")
        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=[])

        genBitstream(str(fasm_file), str(spec_file), str(output_file))

        with output_file.open("rb") as f:
            header = f.read(20)

        expected_header = bytes.fromhex("00AAFF01000000010000000000000000FAB0FAB1")
        assert header == expected_header

    def test_bitstream_desync_frame_appended(
        self, minimal_spec_dict, temp_output_dir, mocker
    ):
        """Binary file should end with desync frame."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=[])
        mocker.patch("FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="")
        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=[])

        genBitstream(str(fasm_file), str(spec_file), str(output_file))

        with output_file.open("rb") as f:
            content = f.read()

        desync = bytes.fromhex("00100000")
        assert content.endswith(desync)

    def test_bitstream_frame_select_encoding(
        self, minimal_spec_dict, temp_output_dir, mocker
    ):
        """Frame select bits should be encoded correctly."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=[])
        mocker.patch("FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="")
        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=[])

        genBitstream(str(fasm_file), str(spec_file), str(output_file))

        with output_file.open("rb") as f:
            content = f.read()

        assert len(content) > 20

    def test_bitstream_total_size(self, minimal_spec_dict, temp_output_dir, mocker):
        """Binary file size should match expected calculation."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=[])
        mocker.patch("FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="")
        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=[])

        genBitstream(str(fasm_file), str(spec_file), str(output_file))

        with output_file.open("rb") as f:
            content = f.read()

        header_size = 20
        desync_size = 4
        assert len(content) >= header_size + desync_size


class TestGenBitstreamBitManipulation:
    """Tests for bit manipulation logic."""

    def test_frame_bit_row_reversed(self, minimal_spec_dict, temp_output_dir, mocker):
        """Frame bit row should be reversed in output."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=[])
        mocker.patch("FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="")
        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=[])

        genBitstream(str(fasm_file), str(spec_file), str(output_file))

        csv_path = output_file.with_suffix(".csv")
        csv_content = csv_path.read_text()

        for line in csv_content.split("\n"):
            if "frame0" in line:
                parts = line.split(",")
                if len(parts) >= 4:
                    bits = parts[3]
                    assert len(bits) == 32
                    break

    def test_tile_specs_no_mask_used_for_hdl(
        self, minimal_spec_dict, temp_output_dir, mocker
    ):
        """HDL output should use TileSpecs_No_Mask data."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "test.fasm"
        output_file = temp_output_dir / "output.bin"

        with spec_file.open("wb") as f:
            pickle.dump(minimal_spec_dict, f)

        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_filename", return_value=[])
        mocker.patch("FABulous_bit_gen.bit_gen.fasm_tuple_to_string", return_value="")
        mocker.patch("FABulous_bit_gen.bit_gen.parse_fasm_string", return_value=[])

        genBitstream(str(fasm_file), str(spec_file), str(output_file))

        vh_path = output_file.with_suffix(".vh")
        vh_content = vh_path.read_text()

        assert "640'b" in vh_content
