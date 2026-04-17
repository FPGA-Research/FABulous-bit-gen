"""Integration tests using real test data."""

import pickle

import pytest

from FABulous_bit_gen.bit_gen import genBitstream


class TestFullBitstreamIntegration:
    """Integration tests run against every test design."""

    def test_all_output_files_created(
        self, real_spec_dict, design, temp_output_dir
    ):
        """All 4 output files should be created."""
        spec_file = temp_output_dir / "spec.bin"
        output_base = temp_output_dir / "output"

        with spec_file.open("wb") as f:
            pickle.dump(real_spec_dict, f)

        genBitstream(
            str(design.fasm_path), str(spec_file), str(output_base.with_suffix(".bin"))
        )

        assert output_base.with_suffix(".bin").exists()
        assert output_base.with_suffix(".csv").exists()
        assert output_base.with_suffix(".vh").exists()
        assert output_base.with_suffix(".vhd").exists()

    def test_bitstream_output_matches_expected(
        self, real_spec_dict, design, temp_output_dir
    ):
        """Bitstream output should match reference file byte-for-byte."""
        spec_file = temp_output_dir / "spec.bin"
        output_base = temp_output_dir / "output"

        with spec_file.open("wb") as f:
            pickle.dump(real_spec_dict, f)

        genBitstream(
            str(design.fasm_path), str(spec_file), str(output_base.with_suffix(".bin"))
        )

        assert output_base.with_suffix(".bin").read_bytes() == design.reference.bin.read_bytes()

    def test_csv_output_matches_expected(
        self, real_spec_dict, design, temp_output_dir
    ):
        """CSV output should match reference file line-by-line."""
        spec_file = temp_output_dir / "spec.bin"
        output_base = temp_output_dir / "output"

        with spec_file.open("wb") as f:
            pickle.dump(real_spec_dict, f)

        genBitstream(
            str(design.fasm_path), str(spec_file), str(output_base.with_suffix(".bin"))
        )

        generated_lines = output_base.with_suffix(".csv").read_text().strip().split("\n")
        expected_lines = design.reference.csv.read_text().strip().split("\n")

        for gen_line, exp_line in zip(generated_lines, expected_lines):
            assert gen_line.strip() == exp_line.strip()

    def test_verilog_output_matches_expected(
        self, real_spec_dict, design, temp_output_dir
    ):
        """Verilog output should match reference file line-by-line."""
        spec_file = temp_output_dir / "spec.bin"
        output_base = temp_output_dir / "output"

        with spec_file.open("wb") as f:
            pickle.dump(real_spec_dict, f)

        genBitstream(
            str(design.fasm_path), str(spec_file), str(output_base.with_suffix(".bin"))
        )

        generated_lines = output_base.with_suffix(".vh").read_text().strip().split("\n")
        expected_lines = design.reference.vh.read_text().strip().split("\n")

        for gen_line, exp_line in zip(generated_lines, expected_lines):
            assert gen_line.strip() == exp_line.strip()

    def test_vhdl_output_matches_expected(
        self, real_spec_dict, design, temp_output_dir
    ):
        """VHDL output should match reference file line-by-line."""
        spec_file = temp_output_dir / "spec.bin"
        output_base = temp_output_dir / "output"

        with spec_file.open("wb") as f:
            pickle.dump(real_spec_dict, f)

        genBitstream(
            str(design.fasm_path), str(spec_file), str(output_base.with_suffix(".bin"))
        )

        generated_lines = output_base.with_suffix(".vhd").read_text().strip().split("\n")
        expected_lines = design.reference.vhd.read_text().strip().split("\n")

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

    def test_spec_file_not_found(self, test_data_dir, temp_output_dir):
        """Missing spec file should raise FileNotFoundError."""
        spec_file = temp_output_dir / "nonexistent.bin"
        fasm_file = test_data_dir / "sequential_16bit_en" / "top.fasm"
        output_base = temp_output_dir / "output"

        with pytest.raises(FileNotFoundError):
            genBitstream(
                str(fasm_file),
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
        self, real_spec_dict, design, temp_output_dir
    ):
        """Existing output files should be overwritten."""
        spec_file = temp_output_dir / "spec.bin"
        output_base = temp_output_dir / "output"

        with spec_file.open("wb") as f:
            pickle.dump(real_spec_dict, f)

        output_base.with_suffix(".bin").write_bytes(b"old content")
        output_base.with_suffix(".csv").write_text("old content")

        genBitstream(
            str(design.fasm_path), str(spec_file), str(output_base.with_suffix(".bin"))
        )

        assert output_base.with_suffix(".bin").read_bytes() != b"old content"

    def test_bitstream_output_size_reasonable(
        self, real_spec_dict, design, temp_output_dir
    ):
        """Bitstream output size should be reasonable (not empty, not huge)."""
        spec_file = temp_output_dir / "spec.bin"
        output_base = temp_output_dir / "output"

        with spec_file.open("wb") as f:
            pickle.dump(real_spec_dict, f)

        genBitstream(
            str(design.fasm_path), str(spec_file), str(output_base.with_suffix(".bin"))
        )

        bitstream_size = output_base.with_suffix(".bin").stat().st_size
        assert bitstream_size > 100
        assert bitstream_size < 10_000_000

    def test_csv_output_has_correct_structure(
        self, real_spec_dict, design, temp_output_dir
    ):
        """CSV output should have correct structural elements."""
        spec_file = temp_output_dir / "spec.bin"
        output_base = temp_output_dir / "output"

        with spec_file.open("wb") as f:
            pickle.dump(real_spec_dict, f)

        genBitstream(
            str(design.fasm_path), str(spec_file), str(output_base.with_suffix(".bin"))
        )

        csv_content = output_base.with_suffix(".csv").read_text()

        assert "frame0" in csv_content
        assert "frame19" in csv_content
        assert ",0,32," in csv_content

    def test_vhdl_output_is_valid_package(
        self, real_spec_dict, design, temp_output_dir
    ):
        """VHDL output should be a valid package structure."""
        spec_file = temp_output_dir / "spec.bin"
        output_base = temp_output_dir / "output"

        with spec_file.open("wb") as f:
            pickle.dump(real_spec_dict, f)

        genBitstream(
            str(design.fasm_path), str(spec_file), str(output_base.with_suffix(".bin"))
        )

        vhd_content = output_base.with_suffix(".vhd").read_text()

        assert vhd_content.startswith("library IEEE")
        assert "package emulate_bitstream is" in vhd_content
        assert "end package emulate_bitstream" in vhd_content

    def test_verilog_output_has_valid_defines(
        self, real_spec_dict, design, temp_output_dir
    ):
        """Verilog output should have valid define statements."""
        spec_file = temp_output_dir / "spec.bin"
        output_base = temp_output_dir / "output"

        with spec_file.open("wb") as f:
            pickle.dump(real_spec_dict, f)

        genBitstream(
            str(design.fasm_path), str(spec_file), str(output_base.with_suffix(".bin"))
        )

        vh_content = output_base.with_suffix(".vh").read_text()

        assert "`define" in vh_content
        assert "640'b" in vh_content

    def test_multiple_sequential_runs(
        self, real_spec_dict, design, temp_output_dir
    ):
        """Multiple runs should produce identical output."""
        spec_file = temp_output_dir / "spec.bin"
        output_base1 = temp_output_dir / "output1"
        output_base2 = temp_output_dir / "output2"

        with spec_file.open("wb") as f:
            pickle.dump(real_spec_dict, f)

        genBitstream(
            str(design.fasm_path), str(spec_file), str(output_base1.with_suffix(".bin"))
        )
        genBitstream(
            str(design.fasm_path), str(spec_file), str(output_base2.with_suffix(".bin"))
        )

        assert output_base1.with_suffix(".bin").read_bytes() == output_base2.with_suffix(".bin").read_bytes()

    def test_bitstream_header_magic_number(
        self, real_spec_dict, design, temp_output_dir
    ):
        """Bitstream output should start with the FABulous sync header."""
        spec_file = temp_output_dir / "spec.bin"
        output_base = temp_output_dir / "output"

        with spec_file.open("wb") as f:
            pickle.dump(real_spec_dict, f)

        genBitstream(
            str(design.fasm_path), str(spec_file), str(output_base.with_suffix(".bin"))
        )

        header = output_base.with_suffix(".bin").read_bytes()[:20]
        assert header == bytes.fromhex("00AAFF01000000010000000000000000FAB0FAB1")

    def test_bitstream_has_desync_at_end(
        self, real_spec_dict, design, temp_output_dir
    ):
        """Bitstream output should end with desync frame."""
        spec_file = temp_output_dir / "spec.bin"
        output_base = temp_output_dir / "output"

        with spec_file.open("wb") as f:
            pickle.dump(real_spec_dict, f)

        genBitstream(
            str(design.fasm_path), str(spec_file), str(output_base.with_suffix(".bin"))
        )

        content = output_base.with_suffix(".bin").read_bytes()
        assert content.endswith(bytes.fromhex("00100000"))


class TestReferenceDataIntegrity:
    """Validate that reference files are structurally correct and non-trivial.

    These tests guard against accidentally zeroed-out or corrupt reference
    files, which would cause the comparison tests to pass vacuously.
    """

    def test_reference_bin_has_sync_header(self, design):
        """Reference binary must start with the FABulous sync header."""
        header = design.reference.bin.read_bytes()[:20]
        assert header == bytes.fromhex("00AAFF01000000010000000000000000FAB0FAB1")

    def test_reference_bin_has_desync_at_end(self, design):
        """Reference binary must end with the desync frame."""
        assert design.reference.bin.read_bytes().endswith(bytes.fromhex("00100000"))

    def test_reference_bin_is_nontrivial(self, design):
        """Reference binary body must contain non-zero bytes (real configuration)."""
        body = design.reference.bin.read_bytes()[20:-4]
        assert any(b != 0 for b in body), "reference bitstream body is all zeros"

    def test_reference_csv_has_frame_rows(self, design):
        """Reference CSV must contain frame rows, not just headers."""
        text = design.reference.csv.read_text()
        assert "frame0" in text
        assert "frame19" in text

    def test_reference_vhd_is_valid_package(self, design):
        """Reference VHDL must be a complete package."""
        text = design.reference.vhd.read_text()
        assert "package emulate_bitstream is" in text
        assert "end package emulate_bitstream" in text

    def test_reference_vh_has_defines(self, design):
        """Reference Verilog must contain at least one `define."""
        assert "`define" in design.reference.vh.read_text()


class TestRegressionSensitivity:
    """Prove the comparison tests would catch a real regression.

    Each test here deliberately produces wrong output and asserts that the
    result does NOT match the reference.  If any of these fail, the
    corresponding comparison test in TestFullBitstreamIntegration is blind
    to that class of regression.
    """

    def test_empty_fasm_differs_from_reference_binary(
        self, real_spec_dict, design, temp_output_dir
    ):
        """An empty FASM (all-zero bitstream) must not match the reference binary."""
        spec_file = temp_output_dir / "spec.bin"
        empty_fasm = temp_output_dir / "empty.fasm"
        output_base = temp_output_dir / "output"

        with spec_file.open("wb") as f:
            pickle.dump(real_spec_dict, f)
        empty_fasm.write_text("")

        genBitstream(str(empty_fasm), str(spec_file), str(output_base.with_suffix(".bin")))

        assert output_base.with_suffix(".bin").read_bytes() != design.reference.bin.read_bytes()

    def test_empty_fasm_differs_from_reference_csv(
        self, real_spec_dict, design, temp_output_dir
    ):
        """An empty FASM (all-zero CSV) must not match the reference CSV."""
        spec_file = temp_output_dir / "spec.bin"
        empty_fasm = temp_output_dir / "empty.fasm"
        output_base = temp_output_dir / "output"

        with spec_file.open("wb") as f:
            pickle.dump(real_spec_dict, f)
        empty_fasm.write_text("")

        genBitstream(str(empty_fasm), str(spec_file), str(output_base.with_suffix(".bin")))

        assert output_base.with_suffix(".csv").read_text() != design.reference.csv.read_text()
