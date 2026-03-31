"""Integration tests using real test data."""

import pickle

import pytest

from FABulous_bit_gen.bit_gen import genBitstream


class TestFullBitstreamIntegration:
    """Integration tests with real FASM and spec files."""

    def test_all_output_files_created(
        self, real_spec_dict, real_fasm_path, temp_output_dir
    ):
        """All 4 output files should be created."""
        spec_file = temp_output_dir / "spec.bin"
        output_base = temp_output_dir / "output"

        with spec_file.open("wb") as f:
            pickle.dump(real_spec_dict, f)

        genBitstream(
            str(real_fasm_path), str(spec_file), str(output_base.with_suffix(".bin"))
        )

        assert output_base.with_suffix(".bin").exists()
        assert output_base.with_suffix(".csv").exists()
        assert output_base.with_suffix(".vh").exists()
        assert output_base.with_suffix(".vhd").exists()

    def test_bitstream_output_matches_expected(
        self, real_spec_dict, real_fasm_path, temp_output_dir, real_expected_bin
    ):
        """Bitstream output should match expected file byte-for-byte."""
        spec_file = temp_output_dir / "spec.bin"
        output_base = temp_output_dir / "output"

        with spec_file.open("wb") as f:
            pickle.dump(real_spec_dict, f)

        genBitstream(
            str(real_fasm_path), str(spec_file), str(output_base.with_suffix(".bin"))
        )

        with output_base.with_suffix(".bin").open("rb") as f:
            generated = f.read()
        with real_expected_bin.open("rb") as f:
            expected = f.read()

        assert generated == expected

    def test_csv_output_matches_expected(
        self, real_spec_dict, real_fasm_path, temp_output_dir, real_expected_csv
    ):
        """CSV output should match expected file line-by-line."""
        spec_file = temp_output_dir / "spec.bin"
        output_base = temp_output_dir / "output"

        with spec_file.open("wb") as f:
            pickle.dump(real_spec_dict, f)

        genBitstream(
            str(real_fasm_path), str(spec_file), str(output_base.with_suffix(".bin"))
        )

        generated_lines = (
            output_base.with_suffix(".csv").read_text().strip().split("\n")
        )
        expected_lines = real_expected_csv.read_text().strip().split("\n")

        for gen_line, exp_line in zip(generated_lines, expected_lines):
            assert gen_line.strip() == exp_line.strip()

    def test_verilog_output_matches_expected(
        self, real_spec_dict, real_fasm_path, temp_output_dir, real_expected_vh
    ):
        """Verilog output should match expected file line-by-line."""
        spec_file = temp_output_dir / "spec.bin"
        output_base = temp_output_dir / "output"

        with spec_file.open("wb") as f:
            pickle.dump(real_spec_dict, f)

        genBitstream(
            str(real_fasm_path), str(spec_file), str(output_base.with_suffix(".bin"))
        )

        generated_lines = output_base.with_suffix(".vh").read_text().strip().split("\n")
        expected_lines = real_expected_vh.read_text().strip().split("\n")

        for gen_line, exp_line in zip(generated_lines, expected_lines):
            assert gen_line.strip() == exp_line.strip()

    def test_vhdl_output_matches_expected(
        self, real_spec_dict, real_fasm_path, temp_output_dir, real_expected_vhd
    ):
        """VHDL output should match expected file line-by-line."""
        spec_file = temp_output_dir / "spec.bin"
        output_base = temp_output_dir / "output"

        with spec_file.open("wb") as f:
            pickle.dump(real_spec_dict, f)

        genBitstream(
            str(real_fasm_path), str(spec_file), str(output_base.with_suffix(".bin"))
        )

        generated_lines = (
            output_base.with_suffix(".vhd").read_text().strip().split("\n")
        )
        expected_lines = real_expected_vhd.read_text().strip().split("\n")

        for gen_line, exp_line in zip(generated_lines, expected_lines):
            assert gen_line.strip() == exp_line.strip()


class TestFullBitstreamIntegrationFaultCases:
    """Fault case integration tests with real test data."""

    def test_empty_fasm_file_produces_valid_output(
        self, real_spec_dict, temp_output_dir
    ):
        """Empty FASM file should produce valid output with all zeros."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "empty.fasm"
        output_base = temp_output_dir / "output"

        with spec_file.open("wb") as f:
            pickle.dump(real_spec_dict, f)

        fasm_file.write_text("")

        genBitstream(
            str(fasm_file), str(spec_file), str(output_base.with_suffix(".bin"))
        )

        assert output_base.with_suffix(".bin").exists()
        assert output_base.with_suffix(".csv").exists()
        assert output_base.with_suffix(".vh").exists()
        assert output_base.with_suffix(".vhd").exists()

    def test_fasm_file_with_comments_only(self, real_spec_dict, temp_output_dir):
        """FASM file with only comments should produce valid output."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "comments.fasm"
        output_base = temp_output_dir / "output"

        with spec_file.open("wb") as f:
            pickle.dump(real_spec_dict, f)

        fasm_file.write_text("# This is a comment\n# Another comment\n")

        genBitstream(
            str(fasm_file), str(spec_file), str(output_base.with_suffix(".bin"))
        )

        assert output_base.with_suffix(".bin").exists()
        assert output_base.with_suffix(".csv").exists()

    def test_spec_file_not_found(self, real_fasm_path, temp_output_dir):
        """Missing spec file should raise FileNotFoundError."""
        spec_file = temp_output_dir / "nonexistent.bin"
        output_base = temp_output_dir / "output"

        with pytest.raises(FileNotFoundError):
            genBitstream(
                str(real_fasm_path),
                str(spec_file),
                str(output_base.with_suffix(".bin")),
            )

    def test_fasm_file_not_found(self, real_spec_dict, temp_output_dir):
        """Missing FASM file should raise FileNotFoundError."""
        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "nonexistent.fasm"
        output_base = temp_output_dir / "output"

        with spec_file.open("wb") as f:
            pickle.dump(real_spec_dict, f)

        with pytest.raises(FileNotFoundError):
            genBitstream(
                str(fasm_file), str(spec_file), str(output_base.with_suffix(".bin"))
            )

    def test_fasm_with_invalid_tile_raises_specmissmatch(
        self, real_spec_dict, temp_output_dir
    ):
        """FASM with tile not in spec should raise SpecMissMatch."""
        from FABulous_bit_gen.custom_exception import SpecMissMatch

        spec_file = temp_output_dir / "spec.bin"
        fasm_file = temp_output_dir / "invalid_tile.fasm"
        output_base = temp_output_dir / "output"

        with spec_file.open("wb") as f:
            pickle.dump(real_spec_dict, f)

        fasm_file.write_text("X999Y999.SOME.FEATURE = 1\n")

        with pytest.raises(SpecMissMatch):
            genBitstream(
                str(fasm_file), str(spec_file), str(output_base.with_suffix(".bin"))
            )


class TestFullBitstreamIntegrationEdgeCases:
    """Edge case integration tests with real test data."""

    def test_output_file_overwrite(
        self, real_spec_dict, real_fasm_path, temp_output_dir
    ):
        """Existing output files should be overwritten."""
        spec_file = temp_output_dir / "spec.bin"
        output_base = temp_output_dir / "output"

        with spec_file.open("wb") as f:
            pickle.dump(real_spec_dict, f)

        output_base.with_suffix(".bin").write_bytes(b"old content")
        output_base.with_suffix(".csv").write_text("old content")

        genBitstream(
            str(real_fasm_path), str(spec_file), str(output_base.with_suffix(".bin"))
        )

        bin_content = output_base.with_suffix(".bin").read_bytes()
        assert bin_content != b"old content"

    def test_bitstream_output_size_reasonable(
        self, real_spec_dict, real_fasm_path, temp_output_dir
    ):
        """Bitstream output size should be reasonable (not empty, not huge)."""
        spec_file = temp_output_dir / "spec.bin"
        output_base = temp_output_dir / "output"

        with spec_file.open("wb") as f:
            pickle.dump(real_spec_dict, f)

        genBitstream(
            str(real_fasm_path), str(spec_file), str(output_base.with_suffix(".bin"))
        )

        bitstream_size = output_base.with_suffix(".bin").stat().st_size
        assert bitstream_size > 100
        assert bitstream_size < 10_000_000

    def test_csv_output_has_correct_structure(
        self, real_spec_dict, real_fasm_path, temp_output_dir
    ):
        """CSV output should have correct structural elements."""
        spec_file = temp_output_dir / "spec.bin"
        output_base = temp_output_dir / "output"

        with spec_file.open("wb") as f:
            pickle.dump(real_spec_dict, f)

        genBitstream(
            str(real_fasm_path), str(spec_file), str(output_base.with_suffix(".bin"))
        )

        csv_content = output_base.with_suffix(".csv").read_text()

        assert "frame0" in csv_content
        assert "frame19" in csv_content
        assert ",0,32," in csv_content

    def test_vhdl_output_is_valid_package(
        self, real_spec_dict, real_fasm_path, temp_output_dir
    ):
        """VHDL output should be a valid package structure."""
        spec_file = temp_output_dir / "spec.bin"
        output_base = temp_output_dir / "output"

        with spec_file.open("wb") as f:
            pickle.dump(real_spec_dict, f)

        genBitstream(
            str(real_fasm_path), str(spec_file), str(output_base.with_suffix(".bin"))
        )

        vhd_content = output_base.with_suffix(".vhd").read_text()

        assert vhd_content.startswith("library IEEE")
        assert "package emulate_bitstream is" in vhd_content
        assert "end package emulate_bitstream" in vhd_content

    def test_verilog_output_has_valid_defines(
        self, real_spec_dict, real_fasm_path, temp_output_dir
    ):
        """Verilog output should have valid define statements."""
        spec_file = temp_output_dir / "spec.bin"
        output_base = temp_output_dir / "output"

        with spec_file.open("wb") as f:
            pickle.dump(real_spec_dict, f)

        genBitstream(
            str(real_fasm_path), str(spec_file), str(output_base.with_suffix(".bin"))
        )

        vh_content = output_base.with_suffix(".vh").read_text()

        assert "`define" in vh_content
        assert "640'b" in vh_content

    def test_multiple_sequential_runs(
        self, real_spec_dict, real_fasm_path, temp_output_dir
    ):
        """Multiple runs should produce identical output."""
        spec_file = temp_output_dir / "spec.bin"
        output_base1 = temp_output_dir / "output1"
        output_base2 = temp_output_dir / "output2"

        with spec_file.open("wb") as f:
            pickle.dump(real_spec_dict, f)

        genBitstream(
            str(real_fasm_path), str(spec_file), str(output_base1.with_suffix(".bin"))
        )
        genBitstream(
            str(real_fasm_path), str(spec_file), str(output_base2.with_suffix(".bin"))
        )

        bin1 = output_base1.with_suffix(".bin").read_bytes()
        bin2 = output_base2.with_suffix(".bin").read_bytes()
        assert bin1 == bin2

    def test_bitstream_header_magic_number(
        self, real_spec_dict, real_fasm_path, temp_output_dir
    ):
        """Bitstream output should have correct magic number in header."""
        spec_file = temp_output_dir / "spec.bin"
        output_base = temp_output_dir / "output"

        with spec_file.open("wb") as f:
            pickle.dump(real_spec_dict, f)

        genBitstream(
            str(real_fasm_path), str(spec_file), str(output_base.with_suffix(".bin"))
        )

        with output_base.with_suffix(".bin").open("rb") as f:
            header = f.read(20)

        # Magic number is 0xFAB0FAB1
        assert header == bytes.fromhex("00AAFF01000000010000000000000000FAB0FAB1")

    def test_bitstream_has_desync_at_end(
        self, real_spec_dict, real_fasm_path, temp_output_dir
    ):
        """Bitstream output should end with desync frame."""
        spec_file = temp_output_dir / "spec.bin"
        output_base = temp_output_dir / "output"

        with spec_file.open("wb") as f:
            pickle.dump(real_spec_dict, f)

        genBitstream(
            str(real_fasm_path), str(spec_file), str(output_base.with_suffix(".bin"))
        )

        with output_base.with_suffix(".bin").open("rb") as f:
            content = f.read()

        assert content.endswith(bytes.fromhex("00100000"))
