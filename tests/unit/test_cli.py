"""Tests for bit_gen CLI entry point."""

import pytest

from fabulous_bit_gen.bit_gen import bit_gen


class TestBitGenCLI:
    """Test suite for bit_gen() CLI function."""

    def test_valid_genbitstream_calls_genbitstream(self, mocker) -> None:
        """Valid genBitstream subcommand should call genBitstream function."""
        mock_gen = mocker.patch("fabulous_bit_gen.bit_gen.genBitstream")
        mocker.patch(
            "sys.argv",
            ["bit_gen", "genBitstream", "test.fasm", "spec.bin", "output.bin"],
        )

        bit_gen()

        mock_gen.assert_called_once_with("test.fasm", "spec.bin", "output.bin")

    def test_missing_fasm_argument_exits(self, mocker) -> None:
        """Missing FASM file argument should exit with code 2."""
        mocker.patch("sys.argv", ["bit_gen", "genBitstream", "spec.bin", "output.bin"])

        with pytest.raises(SystemExit) as exc_info:
            bit_gen()

        assert exc_info.value.code == 2

    def test_missing_spec_argument_exits(self, mocker) -> None:
        """Missing spec file argument should exit with code 2."""
        mocker.patch("sys.argv", ["bit_gen", "genBitstream", "test.fasm"])

        with pytest.raises(SystemExit) as exc_info:
            bit_gen()

        assert exc_info.value.code == 2

    def test_missing_output_argument_exits(self, mocker) -> None:
        """Missing output file argument should exit with code 2."""
        mocker.patch("sys.argv", ["bit_gen", "genBitstream", "test.fasm", "spec.bin"])

        with pytest.raises(SystemExit) as exc_info:
            bit_gen()

        assert exc_info.value.code == 2

    def test_flag_as_fasm_argument_exits(self, mocker) -> None:
        """A flag-like string in the FASM argument position should exit with code 2."""
        mocker.patch(
            "sys.argv",
            ["bit_gen", "genBitstream", "-flag", "spec.bin", "output.bin"],
        )

        with pytest.raises(SystemExit) as exc_info:
            bit_gen()

        assert exc_info.value.code == 2

    def test_flag_as_spec_argument_exits(self, mocker) -> None:
        """A flag-like string in the spec argument position should exit with code 2."""
        mocker.patch(
            "sys.argv",
            ["bit_gen", "genBitstream", "test.fasm", "-flag", "output.bin"],
        )

        with pytest.raises(SystemExit) as exc_info:
            bit_gen()

        assert exc_info.value.code == 2

    def test_flag_as_output_argument_exits(self, mocker) -> None:
        """A flag-like string in the output argument position should exit with code
        2."""
        mocker.patch(
            "sys.argv",
            ["bit_gen", "genBitstream", "test.fasm", "spec.bin", "-flag"],
        )

        with pytest.raises(SystemExit) as exc_info:
            bit_gen()

        assert exc_info.value.code == 2

    def test_help_flag_exits_with_zero(self, mocker) -> None:
        """--help should print usage and exit with code 0."""
        mocker.patch("sys.argv", ["bit_gen", "--help"])

        with pytest.raises(SystemExit) as exc_info:
            bit_gen()

        assert exc_info.value.code == 0

    def test_h_flag_exits_with_zero(self, mocker) -> None:
        """-h should print usage and exit with code 0."""
        mocker.patch("sys.argv", ["bit_gen", "-h"])

        with pytest.raises(SystemExit) as exc_info:
            bit_gen()

        assert exc_info.value.code == 0

    def test_no_subcommand_does_not_call_genbitstream(self, mocker) -> None:
        """No subcommand should print help without calling genBitstream."""
        mock_gen = mocker.patch("fabulous_bit_gen.bit_gen.genBitstream")
        mocker.patch("sys.argv", ["bit_gen"])

        bit_gen()

        mock_gen.assert_not_called()


class TestBitGenCLIFaultCases:
    """Fault case tests for bit_gen() CLI function."""

    def test_extra_arguments_after_valid_args_exits(self, mocker) -> None:
        """Extra positional arguments beyond the required three should exit with code
        2."""
        mocker.patch(
            "sys.argv",
            ["bit_gen", "genBitstream", "test.fasm", "spec.bin", "output.bin", "extra"],
        )

        with pytest.raises(SystemExit) as exc_info:
            bit_gen()

        assert exc_info.value.code == 2

    def test_unknown_subcommand_exits(self, mocker) -> None:
        """Unknown subcommand should exit with code 2."""
        mocker.patch("sys.argv", ["bit_gen", "unknownCommand"])

        with pytest.raises(SystemExit) as exc_info:
            bit_gen()

        assert exc_info.value.code == 2

    def test_genbitstream_with_no_arguments_exits(self, mocker) -> None:
        """GenBitstream subcommand with no arguments should exit with code 2."""
        mocker.patch("sys.argv", ["bit_gen", "genBitstream"])

        with pytest.raises(SystemExit) as exc_info:
            bit_gen()

        assert exc_info.value.code == 2

    def test_genbitstream_with_only_one_argument_exits(self, mocker) -> None:
        """GenBitstream with only one argument should exit with code 2."""
        mocker.patch("sys.argv", ["bit_gen", "genBitstream", "test.fasm"])

        with pytest.raises(SystemExit) as exc_info:
            bit_gen()

        assert exc_info.value.code == 2

    def test_genbitstream_with_only_two_arguments_exits(self, mocker) -> None:
        """GenBitstream with only two arguments should exit with code 2."""
        mocker.patch("sys.argv", ["bit_gen", "genBitstream", "test.fasm", "spec.bin"])

        with pytest.raises(SystemExit) as exc_info:
            bit_gen()

        assert exc_info.value.code == 2


class TestBitGenCLIEdgeCases:
    """Edge case tests for bit_gen() CLI function."""

    def test_arguments_with_special_characters(self, mocker) -> None:
        """Arguments with special characters should be preserved."""
        mock_gen = mocker.patch("fabulous_bit_gen.bit_gen.genBitstream")
        mocker.patch(
            "sys.argv",
            [
                "bit_gen",
                "genBitstream",
                "test-file_v1.fasm",
                "spec_file.bin",
                "out_v2.bin",
            ],
        )

        bit_gen()

        mock_gen.assert_called_once_with(
            "test-file_v1.fasm", "spec_file.bin", "out_v2.bin"
        )

    def test_arguments_with_dots_in_filename(self, mocker) -> None:
        """Arguments with multiple dots in filename should work."""
        mock_gen = mocker.patch("fabulous_bit_gen.bit_gen.genBitstream")
        mocker.patch(
            "sys.argv",
            ["bit_gen", "genBitstream", "test.v1.fasm", "spec.v2.bin", "out.v3.bin"],
        )

        bit_gen()

        mock_gen.assert_called_once_with("test.v1.fasm", "spec.v2.bin", "out.v3.bin")

    def test_program_name_with_path(self, mocker) -> None:
        """Program name with path should not affect parsing."""
        mock_gen = mocker.patch("fabulous_bit_gen.bit_gen.genBitstream")
        mocker.patch(
            "sys.argv",
            [
                "/usr/local/bin/bit_gen",
                "genBitstream",
                "test.fasm",
                "spec.bin",
                "output.bin",
            ],
        )

        bit_gen()

        mock_gen.assert_called_once_with("test.fasm", "spec.bin", "output.bin")

    def test_very_long_filename(self, mocker) -> None:
        """Very long filename should be accepted."""
        mock_gen = mocker.patch("fabulous_bit_gen.bit_gen.genBitstream")
        long_name = "a" * 255 + ".fasm"
        mocker.patch(
            "sys.argv",
            ["bit_gen", "genBitstream", long_name, "spec.bin", "output.bin"],
        )

        bit_gen()

        mock_gen.assert_called_once_with(long_name, "spec.bin", "output.bin")

    def test_unicode_filename(self, mocker) -> None:
        """Unicode filename should be accepted."""
        mock_gen = mocker.patch("fabulous_bit_gen.bit_gen.genBitstream")
        mocker.patch(
            "sys.argv",
            ["bit_gen", "genBitstream", "test_αβγ.fasm", "spec.bin", "output.bin"],
        )

        bit_gen()

        mock_gen.assert_called_once_with("test_αβγ.fasm", "spec.bin", "output.bin")

    def test_subcommand_help_exits_with_zero(self, mocker) -> None:
        """GenBitstream --help should print subcommand usage and exit with code 0."""
        mocker.patch("sys.argv", ["bit_gen", "genBitstream", "--help"])

        with pytest.raises(SystemExit) as exc_info:
            bit_gen()

        assert exc_info.value.code == 0
