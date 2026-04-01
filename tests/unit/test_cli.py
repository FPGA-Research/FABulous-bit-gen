"""Tests for bit_gen CLI entry point."""

import sys
from unittest.mock import patch

import pytest

from FABulous_bit_gen.bit_gen import bit_gen


class TestBitGenCLI:
    """Test suite for bit_gen() CLI function."""

    def test_valid_genbitstream_calls_genbitstream(self, mocker):
        """Valid -genBitstream args should call genBitstream function."""
        mock_gen = mocker.patch("FABulous_bit_gen.bit_gen.genBitstream")
        mocker.patch(
            "sys.argv",
            ["bit_gen", "-genBitstream", "test.fasm", "spec.bin", "output.bin"],
        )

        bit_gen()

        mock_gen.assert_called_once_with("test.fasm", "spec.bin", "output.bin")

    def test_flag_case_insensitive(self, mocker):
        """-genBitstream flag should work regardless of case."""
        mock_gen = mocker.patch("FABulous_bit_gen.bit_gen.genBitstream")
        mocker.patch(
            "sys.argv",
            ["bit_gen", "-GENBITSTREAM", "test.fasm", "spec.bin", "output.bin"],
        )

        bit_gen()

        mock_gen.assert_called_once_with("test.fasm", "spec.bin", "output.bin")

    def test_arguments_whitespace_stripped(self, mocker):
        """Arguments should be stripped of whitespace."""
        mock_gen = mocker.patch("FABulous_bit_gen.bit_gen.genBitstream")
        mocker.patch(
            "sys.argv",
            ["bit_gen", "-genBitstream", " test.fasm ", " spec.bin ", " output.bin "],
        )

        bit_gen()

        mock_gen.assert_called_once_with("test.fasm", "spec.bin", "output.bin")

    def test_missing_fasm_argument_raises_valueerror(self, mocker):
        """Missing FASM file argument should raise ValueError."""
        mocker.patch("sys.argv", ["bit_gen", "-genBitstream", "spec.bin", "output.bin"])

        with pytest.raises(ValueError):
            bit_gen()

    def test_missing_spec_argument_raises_valueerror(self, mocker):
        """Missing spec file argument should raise ValueError."""
        mocker.patch("sys.argv", ["bit_gen", "-genBitstream", "test.fasm"])

        with pytest.raises(ValueError):
            bit_gen()

    def test_missing_output_argument_raises_valueerror(self, mocker):
        """Missing output file argument should raise ValueError."""
        mocker.patch("sys.argv", ["bit_gen", "-genBitstream", "test.fasm", "spec.bin"])

        with pytest.raises(ValueError):
            bit_gen()

    def test_flag_as_fasm_argument_raises_valueerror(self, mocker):
        """Flag in FASM argument position should raise ValueError."""
        mocker.patch(
            "sys.argv", ["bit_gen", "-genBitstream", "-flag", "spec.bin", "output.bin"]
        )

        with pytest.raises(ValueError):
            bit_gen()

    def test_flag_as_spec_argument_raises_valueerror(self, mocker):
        """Flag in spec argument position should raise ValueError."""
        mocker.patch(
            "sys.argv", ["bit_gen", "-genBitstream", "test.fasm", "-flag", "output.bin"]
        )

        with pytest.raises(ValueError):
            bit_gen()

    def test_flag_as_output_argument_raises_valueerror(self, mocker):
        """Flag in output argument position should raise ValueError."""
        mocker.patch(
            "sys.argv", ["bit_gen", "-genBitstream", "test.fasm", "spec.bin", "-flag"]
        )

        with pytest.raises(ValueError):
            bit_gen()

    def test_help_flag_outputs_help_message(self, mocker):
        """-help flag should output help message."""
        mock_logger = mocker.patch("FABulous_bit_gen.bit_gen.logger")
        mocker.patch("sys.argv", ["bit_gen", "-help"])

        bit_gen()

        mock_logger.info.assert_called()

    def test_h_flag_outputs_help_message(self, mocker):
        """-h flag should output help message."""
        mock_logger = mocker.patch("FABulous_bit_gen.bit_gen.logger")
        mocker.patch("sys.argv", ["bit_gen", "-h"])

        bit_gen()

        mock_logger.info.assert_called()

    def test_no_flag_no_action(self, mocker):
        """No recognized flag should result in no action."""
        mock_gen = mocker.patch("FABulous_bit_gen.bit_gen.genBitstream")
        mocker.patch("sys.argv", ["bit_gen"])

        bit_gen()

        mock_gen.assert_not_called()


class TestBitGenCLIFaultCases:
    """Fault case tests for bit_gen() CLI function."""

    def test_extra_arguments_after_valid_args(self, mocker):
        """Extra arguments after valid args should be ignored."""
        mock_gen = mocker.patch("FABulous_bit_gen.bit_gen.genBitstream")
        mocker.patch(
            "sys.argv",
            [
                "bit_gen",
                "-genBitstream",
                "test.fasm",
                "spec.bin",
                "output.bin",
                "extra",
            ],
        )

        bit_gen()

        mock_gen.assert_called_once_with("test.fasm", "spec.bin", "output.bin")

    def test_genbitstream_flag_with_leading_spaces(self, mocker):
        """Flag with leading spaces should still be recognized."""
        mock_gen = mocker.patch("FABulous_bit_gen.bit_gen.genBitstream")
        mocker.patch(
            "sys.argv",
            ["bit_gen", "  -genBitstream  ", "test.fasm", "spec.bin", "output.bin"],
        )

        bit_gen()

        mock_gen.assert_called_once_with("test.fasm", "spec.bin", "output.bin")

    def test_unknown_flag_ignored(self, mocker):
        """Unknown flag should be ignored (no error, no action)."""
        mock_gen = mocker.patch("FABulous_bit_gen.bit_gen.genBitstream")
        mocker.patch("sys.argv", ["bit_gen", "-unknownFlag"])

        bit_gen()

        mock_gen.assert_not_called()

    def test_only_flag_no_arguments_raises_valueerror(self, mocker):
        """Only -genBitstream flag with no arguments should raise ValueError."""
        mocker.patch("sys.argv", ["bit_gen", "-genBitstream"])

        with pytest.raises(ValueError):
            bit_gen()

    def test_genbitstream_with_only_one_argument_raises_valueerror(self, mocker):
        """-genBitstream with only one argument should raise ValueError."""
        mocker.patch("sys.argv", ["bit_gen", "-genBitstream", "test.fasm"])

        with pytest.raises(ValueError):
            bit_gen()

    def test_genbitstream_with_only_two_arguments_raises_valueerror(self, mocker):
        """-genBitstream with only two arguments should raise ValueError."""
        mocker.patch("sys.argv", ["bit_gen", "-genBitstream", "test.fasm", "spec.bin"])

        with pytest.raises(ValueError):
            bit_gen()


class TestBitGenCLIEdgeCases:
    """Edge case tests for bit_gen() CLI function."""

    def test_mixed_case_flag_and_args(self, mocker):
        """Mixed case in flag and arguments should work."""
        mock_gen = mocker.patch("FABulous_bit_gen.bit_gen.genBitstream")
        mocker.patch(
            "sys.argv",
            ["bit_gen", "-GenBitStream", "TEST.FASM", "SPEC.BIN", "OUTPUT.BIN"],
        )

        bit_gen()

        mock_gen.assert_called_once_with("TEST.FASM", "SPEC.BIN", "OUTPUT.BIN")

    def test_multiple_help_flags(self, mocker):
        """Multiple help flags should still show help."""
        mock_logger = mocker.patch("FABulous_bit_gen.bit_gen.logger")
        mocker.patch("sys.argv", ["bit_gen", "-help", "-h"])

        bit_gen()

        mock_logger.info.assert_called()

    def test_help_flag_after_unknown_flag(self, mocker):
        """-help after unknown flag should show help."""
        mock_logger = mocker.patch("FABulous_bit_gen.bit_gen.logger")
        mocker.patch("sys.argv", ["bit_gen", "-unknown", "-help"])

        bit_gen()

        mock_logger.info.assert_called()

    def test_arguments_with_special_characters(self, mocker):
        """Arguments with special characters should be preserved."""
        mock_gen = mocker.patch("FABulous_bit_gen.bit_gen.genBitstream")
        mocker.patch(
            "sys.argv",
            [
                "bit_gen",
                "-genBitstream",
                "test-file_v1.fasm",
                "spec_file.bin",
                "out_v2.bin",
            ],
        )

        bit_gen()

        mock_gen.assert_called_once_with(
            "test-file_v1.fasm", "spec_file.bin", "out_v2.bin"
        )

    def test_arguments_with_dots_in_filename(self, mocker):
        """Arguments with multiple dots in filename should work."""
        mock_gen = mocker.patch("FABulous_bit_gen.bit_gen.genBitstream")
        mocker.patch(
            "sys.argv",
            ["bit_gen", "-genBitstream", "test.v1.fasm", "spec.v2.bin", "out.v3.bin"],
        )

        bit_gen()

        mock_gen.assert_called_once_with("test.v1.fasm", "spec.v2.bin", "out.v3.bin")

    def test_program_name_with_path(self, mocker):
        """Program name with path should not affect parsing."""
        mock_gen = mocker.patch("FABulous_bit_gen.bit_gen.genBitstream")
        mocker.patch(
            "sys.argv",
            [
                "/usr/local/bin/bit_gen",
                "-genBitstream",
                "test.fasm",
                "spec.bin",
                "output.bin",
            ],
        )

        bit_gen()

        mock_gen.assert_called_once_with("test.fasm", "spec.bin", "output.bin")

    def test_very_long_filename(self, mocker):
        """Very long filename should be accepted."""
        mock_gen = mocker.patch("FABulous_bit_gen.bit_gen.genBitstream")
        long_name = "a" * 255 + ".fasm"
        mocker.patch(
            "sys.argv",
            ["bit_gen", "-genBitstream", long_name, "spec.bin", "output.bin"],
        )

        bit_gen()

        mock_gen.assert_called_once_with(long_name, "spec.bin", "output.bin")

    def test_unicode_filename(self, mocker):
        """Unicode filename should be accepted."""
        mock_gen = mocker.patch("FABulous_bit_gen.bit_gen.genBitstream")
        mocker.patch(
            "sys.argv",
            ["bit_gen", "-genBitstream", "test_αβγ.fasm", "spec.bin", "output.bin"],
        )

        bit_gen()

        mock_gen.assert_called_once_with("test_αβγ.fasm", "spec.bin", "output.bin")

    def test_genbitstream_substring_in_filename_raises_valueerror(self, mocker):
        """-genBitstream as substring in a filename arg should raise ValueError.

        The outer check uses str(sys.argv) substring match, so a filename like
        'spec-genBitstream-v2.bin' satisfies it, but processedArguments.index()
        then fails to find the flag as a standalone element.
        """
        mocker.patch(
            "sys.argv",
            ["bit_gen", "spec-genBitstream-v2.bin", "output.bin"],
        )

        with pytest.raises(ValueError):
            bit_gen()

    def test_help_not_triggered_by_unrelated_argument_containing_h(self, mocker):
        """-h substring in an unrelated argument should not trigger help output.

        The check uses str(sys.argv) substring match, so arguments like
        '-hashfile' contain '-h' and could spuriously fire the help branch.
        """
        mock_logger = mocker.patch("FABulous_bit_gen.bit_gen.logger")
        mock_gen = mocker.patch("FABulous_bit_gen.bit_gen.genBitstream")
        mocker.patch(
            "sys.argv",
            ["bit_gen", "-genBitstream", "test.fasm", "spec.bin", "output.bin"],
        )

        bit_gen()

        mock_logger.info.assert_not_called()
        mock_gen.assert_called_once()
