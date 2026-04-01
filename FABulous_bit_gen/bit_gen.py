#!/usr/bin/env python

"""Bitstream generation utilities for FABulous FPGA fabrics.

This module provides functionality for generating bitstreams from FASM (FPGA Assembly)
files for FABulous FPGA fabrics. It handles the conversion of place-and-route results
into configuration bitstreams that can be loaded onto the FPGA fabric.

The module includes functions for parsing FASM files, processing configuration bits, and
generating the final bitstream output in various formats.
"""

import argparse
import pickle
import re
from pathlib import Path

from loguru import logger

from FABulous_bit_gen.custom_exception import SpecMissMatch

try:
    from fasm import (
        fasm_tuple_to_string,
        parse_fasm_filename,
        parse_fasm_string,
        set_feature_to_str,
    )
except ImportError:
    logger.critical("Could not import fasm. Bitstream generation not supported.")


def bitstring_to_bytes(s: str) -> bytes:
    """Convert binary string to bytes.

    Parameters
    ----------
    s : str
        Binary string (e.g., '10110101')

    Returns
    -------
    bytes
        Byte representation of the binary string
    """
    return int(s, 2).to_bytes((len(s) + 7) // 8, byteorder="big")


def _parse_fasm_to_canon_list(fasm_file: str) -> list:
    """Parse FASM file and return its canonicalised feature list."""
    fasm_lines = parse_fasm_filename(fasm_file)
    canonical_str = fasm_tuple_to_string(fasm_lines, True)
    return list(parse_fasm_string(canonical_str))


def _init_tile_bits(spec_dict: dict) -> tuple:
    """Initialise per-tile bit arrays to all zeros.

    Returns two dicts keyed by tile location: one for the masked bitstream
    and one for the unmasked (No_Mask) bitstream used by HDL emulation.
    """
    frame_bits_per_row = spec_dict["ArchSpecs"]["FrameBitsPerRow"]
    max_frames_per_col = spec_dict["ArchSpecs"]["MaxFramesPerCol"]
    total_bits = max_frames_per_col * frame_bits_per_row

    # Change this so it has the actual right dimensions, initialised as
    # an empty bitstream
    tile_bits = {tile: [0] * total_bits for tile in spec_dict["TileMap"]}
    tile_bits_no_mask = {tile: [0] * total_bits for tile in spec_dict["TileMap"]}
    return tile_bits, tile_bits_no_mask


def _apply_fasm_features(
    canon_list: list,
    spec_dict: dict,
    tile_bits: dict,
    tile_bits_no_mask: dict,
) -> None:
    """Apply FASM feature lines to the tile bit arrays in place."""
    # NOTE: SOME OF THE FOLLOWING METHODS HAVE BEEN CHANGED DUE TO A MODIFIED BITSTREAM
    # SPEC FORMAT
    # Please bear in mind that the tilespecs are now mapped by
    # tile loc and not by cell type
    for line in canon_list:
        if not line.set_feature:
            continue
        if "CLK" in set_feature_to_str(line.set_feature):
            continue

        feature_parts = set_feature_to_str(line.set_feature).split(".")
        tile_loc = feature_parts[0]
        feature_name = ".".join((feature_parts[1], feature_parts[2]))

        if tile_loc not in spec_dict["TileMap"]:
            raise SpecMissMatch(
                f"Tile location {tile_loc} not found in the bitstream spec"
            )

        # Set the necessary bits high
        tile_type = spec_dict["TileMap"][tile_loc]
        if feature_name in spec_dict["TileSpecs"][tile_loc]:
            if spec_dict["TileSpecs"][tile_loc][feature_name]:
                for bit_idx, bit_val in spec_dict["TileSpecs"][tile_loc][feature_name].items():
                    tile_bits[tile_loc][bit_idx] = int(bit_val)
                for bit_idx, bit_val in spec_dict["TileSpecs_No_Mask"][tile_loc][feature_name].items():
                    tile_bits_no_mask[tile_loc][bit_idx] = int(bit_val)
        else:
            raise SpecMissMatch(
                f"Tile type: {tile_type}\n"
                f"with location {tile_loc} and \n"
                f"Feature: {feature_name}\n"
                "found in fasm file was not found in the bitstream spec"
            )


def _compute_grid_size(tile_bits: dict) -> tuple:
    """Compute grid dimensions (num_columns, num_rows) from tile coordinate keys."""
    # Write output string and introduce mask
    coords_re = re.compile(r"X(\d*)Y(\d*)")
    num_columns = 0
    num_rows = 0
    for tile_key in tile_bits:
        coords_match = coords_re.match(tile_key)
        num_columns = max(int(coords_match.group(1)) + 1, num_columns)
        num_rows = max(int(coords_match.group(2)) + 1, num_rows)
    return num_columns, num_rows


def _build_hdl_strings(tile_bits_no_mask: dict, spec_dict: dict) -> tuple:
    """Build Verilog (.vh) and VHDL (.vhd) emulation bitstream constant strings."""
    frame_bits_per_row = spec_dict["ArchSpecs"]["FrameBitsPerRow"]
    max_frames_per_col = spec_dict["ArchSpecs"]["MaxFramesPerCol"]
    total_bits = max_frames_per_col * frame_bits_per_row

    verilog_str = ""
    vhdl_str = (
        "library IEEE;\nuse IEEE.STD_LOGIC_1164.ALL;\n\npackage emulate_bitstream is\n"
    )
    for tile_key, bits in tile_bits_no_mask.items():
        tile_type = spec_dict["TileMap"][tile_key]
        if tile_type == "NULL" or len(spec_dict["FrameMap"][tile_type]) == 0:
            continue

        verilog_str += f"// {tile_key}, {tile_type}\n"
        verilog_str += f"`define Tile_{tile_key}_Emulate_Bitstream {total_bits}'b"

        vhdl_str += f"--{tile_key}, {tile_type}\n"
        vhdl_str += (
            f"constant Tile_{tile_key}_Emulate_Bitstream : std_logic_vector("
            f'{total_bits}-1 downto 0) := "'
        )

        for i in range(total_bits - 1, -1, -1):
            verilog_str += str(bits[i])
            vhdl_str += str(bits[i])
        verilog_str += "\n"
        vhdl_str += '";\n'
    vhdl_str += "end package emulate_bitstream;"
    return verilog_str, vhdl_str


def _build_csv_and_frame_data(
    tile_bits: dict,
    spec_dict: dict,
    num_rows: int,
    num_columns: int,
) -> tuple:
    """Build the CSV output string and the per-column frame byte arrays.

    Returns (csv_str, bit_array) where bit_array[col][frame] holds the
    packed bytes for that column/frame combination.
    """
    frame_bits_per_row = spec_dict["ArchSpecs"]["FrameBitsPerRow"]
    max_frames_per_col = spec_dict["ArchSpecs"]["MaxFramesPerCol"]

    csv_str = ""
    bit_array = [[b"" for _ in range(max_frames_per_col)] for _ in range(num_columns)]

    # Top/bottom rows have no bitstream content (hardcoded throughout FABulous)
    # reversed row order
    for y in range(num_rows - 2, 0, -1):
        for x in range(num_columns):
            tile_key = f"X{x}Y{y}"
            tile_csv = ",".join((tile_key, spec_dict["TileMap"][tile_key], str(x), str(y)))
            tile_csv += "\n"

            for frame_idx in range(max_frames_per_col):
                if spec_dict["TileMap"][tile_key] == "NULL":
                    frame_bit_row = "0" * frame_bits_per_row
                else:
                    start = frame_bits_per_row * frame_idx
                    frame_bit_row = "".join(
                        map(str, tile_bits[tile_key][start : start + frame_bits_per_row])
                    )[::-1]

                tile_csv += ",".join((
                    f"frame{frame_idx}",
                    str(frame_idx),
                    str(frame_bits_per_row),
                    frame_bit_row,
                ))
                tile_csv += "\n"

                bit_array[x][frame_idx] += bitstring_to_bytes(frame_bit_row)

            csv_str += tile_csv + "\n"

    return csv_str, bit_array


def _build_binary_bitstream(bit_array: list, num_columns: int) -> bytes:
    """Assemble the final binary bitstream from per-column frame data.

    Prepends the FABulous sync header and appends the desync frame.
    """
    bitstream = bytes.fromhex("00AAFF01000000010000000000000000FAB0FAB1")

    for col in range(num_columns):
        for frame_idx in range(20):
            col_idx_reversed = f"{col:05b}"[::-1]
            frame_select = ["0"] * 32

            for k in range(-5, 0, 1):
                frame_select[k] = col_idx_reversed[k]
            frame_select[frame_idx] = "1"
            frame_select_str = ("".join(frame_select))[::-1]

            bitstream += bitstring_to_bytes(frame_select_str)
            bitstream += bit_array[col][frame_idx]

    # Add desync frame
    # 20th bit is desync flag
    bitstream += bytes.fromhex("00100000")
    return bitstream


def genBitstream(fasm_file: str, spec_file: str, bitstream_file: str) -> None:
    """Generate the bitstream from the FASM file using the bitstream specification.

    Parameters
    ----------
    fasm_file : str
        Path to FASM file containing configuration features
    spec_file : str
        Path to pickle file containing bitstream specification
    bitstream_file : str
        Output path for generated bitstream file
    """
    canon_list = _parse_fasm_to_canon_list(fasm_file)

    with Path(spec_file).open("rb") as f:
        spec_dict = pickle.load(f)

    tile_bits, tile_bits_no_mask = _init_tile_bits(spec_dict)
    _apply_fasm_features(canon_list, spec_dict, tile_bits, tile_bits_no_mask)

    num_columns, num_rows = _compute_grid_size(tile_bits)
    verilog_str, vhdl_str = _build_hdl_strings(tile_bits_no_mask, spec_dict)
    csv_str, bit_array = _build_csv_and_frame_data(tile_bits, spec_dict, num_rows, num_columns)
    bitstream_bytes = _build_binary_bitstream(bit_array, num_columns)

    # Note - format in output file is line by line:
    # Tile Loc, Tile Type, X, Y, bits...... \n
    # Each line is one tile
    output_path = Path(bitstream_file)
    # Write out bitstream CSV representation
    with output_path.with_suffix(".csv").open("w+") as f:
        f.write(csv_str)
    # Write out HDL representations
    with output_path.with_suffix(".vh").open("w+") as f:
        f.write(verilog_str)
    with output_path.with_suffix(".vhd").open("w+") as f:
        f.write(vhdl_str)
    # Write out binary representation
    with output_path.open("bw+") as f:
        f.write(bitstream_bytes)


#####################################################################################
# Main
#####################################################################################
def bit_gen() -> None:
    """Command-line entry point for bitstream generation."""
    parser = argparse.ArgumentParser(
        prog="bit_gen",
        description="FABulous bitstream generation tool",
    )
    subparsers = parser.add_subparsers(dest="command")

    gen_parser = subparsers.add_parser(
        "genBitstream",
        help="Generate a bitstream from a FASM file and bitstream spec",
    )
    gen_parser.add_argument("fasm_file", help="Path to the FASM file")
    gen_parser.add_argument("spec_file", help="Path to the bitstream spec file")
    gen_parser.add_argument("output_file", help="Path to write the output bitstream")

    args = parser.parse_args()

    if args.command == "genBitstream":
        genBitstream(args.fasm_file, args.spec_file, args.output_file)
    else:
        parser.print_help()


if __name__ == "__main__":
    bit_gen()
