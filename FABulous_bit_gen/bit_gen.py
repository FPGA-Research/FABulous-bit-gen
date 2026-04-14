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

# ---------------------------------------------------------------------------
# Bitstream format constants
# ---------------------------------------------------------------------------

BITS_PER_BYTE: int = 8
"""Number of bits in one byte; used for byte-aligned packing."""

BORDER_ROWS: int = 2
"""Number of border rows (top + bottom) that carry no bitstream content."""

COLUMN_INDEX_BITS: int = 5
"""Bits used to encode the column index inside the frame-select word."""

FRAME_SELECT_BITS: int = 32
"""Width in bits of the frame-select word prepended to each frame."""

MAX_FRAMES_PER_COL: int = 20
"""Maximum number of frames per column in the FABulous bitstream format."""

SYNC_HEADER_HEX: str = "00AAFF01000000010000000000000000FAB0FAB1"
"""FABulous 20-byte sync header that opens every bitstream."""

DESYNC_BIT: int = 20
"""Bit position of the desync flag inside the 32-bit frame-select word."""

DESYNC_FRAME: bytes = (1 << DESYNC_BIT).to_bytes(
    FRAME_SELECT_BITS // BITS_PER_BYTE, byteorder="big"
)
"""FABulous 4-byte desync frame: bit ``DESYNC_BIT`` set in a big-endian 32-bit word."""

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
    return int(s, 2).to_bytes((len(s) + BITS_PER_BYTE - 1) // BITS_PER_BYTE, byteorder="big")


def _parse_fasm_to_canon_list(fasm_file: str) -> list:
    """Parse a FASM file and return its canonicalised feature list.

    Reads the raw FASM file, converts it to canonical form (which resolves
    any shorthand and normalises feature values), then parses that canonical
    string back into a list of FasmLine objects ready for processing.

    Parameters
    ----------
    fasm_file : str
        Path to the FASM file to parse.

    Returns
    -------
    list[FasmLine]
        Canonicalised list of FASM lines parsed from the file.

    Raises
    ------
    FileNotFoundError
        If ``fasm_file`` does not exist.
    """
    fasm_lines = parse_fasm_filename(fasm_file)
    canonical_str = fasm_tuple_to_string(fasm_lines, True)
    return list(parse_fasm_string(canonical_str))


def _init_tile_bits(spec_dict: dict) -> tuple:
    """Initialise per-tile bit arrays to all zeros.

    Allocates two flat integer lists of length
    ``MaxFramesPerCol * FrameBitsPerRow`` for every tile in ``TileMap``:
    one for the masked bitstream written to the binary output, and one for
    the unmasked (No_Mask) bitstream used by the HDL emulation constants.

    Parameters
    ----------
    spec_dict : dict
        Bitstream specification dictionary loaded from the pickle spec file.
        Must contain ``ArchSpecs`` (with ``FrameBitsPerRow`` and
        ``MaxFramesPerCol``) and ``TileMap``.

    Returns
    -------
    tuple[dict[str, list[int]], dict[str, list[int]]]
        A pair ``(tile_bits, tile_bits_no_mask)``, each mapping tile location
        strings (e.g. ``'X1Y2'``) to a zero-filled integer list of length
        ``MaxFramesPerCol * FrameBitsPerRow``.
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
    """Apply FASM feature lines to the tile bit arrays in place.

    Iterates over every canonicalised FASM line, skipping comment/annotation
    lines (``set_feature is None``) and any feature whose name contains
    ``'CLK'``.  For each remaining feature the tile location and feature name
    are resolved against ``TileSpecs`` and the corresponding bit indices are
    written into both ``tile_bits`` (masked) and ``tile_bits_no_mask``
    (unmasked) using the values stored in the spec.

    A warning is emitted via ``logger.warning`` whenever a bit that was
    already written is overwritten, both for ``tile_bits`` (masked) and
    ``tile_bits_no_mask`` (unmasked), indicating that two FASM features
    compete for the same configuration bit.

    Parameters
    ----------
    canon_list : list[FasmLine]
        Canonicalised FASM lines as returned by ``_parse_fasm_to_canon_list``.
    spec_dict : dict
        Bitstream specification dictionary.  Must contain ``TileMap``,
        ``TileSpecs``, and ``TileSpecs_No_Mask``.
    tile_bits : dict[str, list[int]]
        Per-tile bit array for the masked bitstream, mutated in place.
    tile_bits_no_mask : dict[str, list[int]]
        Per-tile bit array for the unmasked HDL bitstream, mutated in place.

    Raises
    ------
    SpecMissMatch
        If a feature's tile location is not present in ``TileMap``, or if
        the feature name is not found in ``TileSpecs`` for that tile.
    IndexError
        If a feature string contains fewer than three dot-separated parts
        (i.e. does not follow the ``TileLoc.Part1.Part2`` convention).
    KeyError
        If a feature is present in ``TileSpecs`` for a tile but absent from
        the corresponding ``TileSpecs_No_Mask`` entry.
    """
    # NOTE: SOME OF THE FOLLOWING METHODS HAVE BEEN CHANGED DUE TO A MODIFIED BITSTREAM
    # SPEC FORMAT
    # Please bear in mind that the tilespecs are now mapped by
    # tile loc and not by cell type

    # Track which bit indices have already been written for each tile so that
    # overwrites are detected regardless of the bit value (a feature can
    # legitimately map a bit to 0, making a value-based sentinel unreliable).
    touched_bits: dict[str, set] = {tile: set() for tile in tile_bits}
    touched_bits_no_mask: dict[str, set] = {tile: set() for tile in tile_bits_no_mask}

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
                    new_val = int(bit_val)
                    if bit_idx in touched_bits[tile_loc]:
                        logger.warning(
                            f"Bit {bit_idx} of tile {tile_loc} is being overwritten "
                            f"by feature {feature_name} "
                            f"(old value: {tile_bits[tile_loc][bit_idx]}, "
                            f"new value: {new_val})"
                        )
                    touched_bits[tile_loc].add(bit_idx)
                    tile_bits[tile_loc][bit_idx] = new_val
                for bit_idx, bit_val in spec_dict["TileSpecs_No_Mask"][tile_loc][feature_name].items():
                    new_val = int(bit_val)
                    if bit_idx in touched_bits_no_mask[tile_loc]:
                        logger.warning(
                            f"Bit {bit_idx} of tile {tile_loc} is being overwritten "
                            f"in the unmasked bitstream by feature {feature_name} "
                            f"(old value: {tile_bits_no_mask[tile_loc][bit_idx]}, "
                            f"new value: {new_val})"
                        )
                    touched_bits_no_mask[tile_loc].add(bit_idx)
                    tile_bits_no_mask[tile_loc][bit_idx] = new_val
        else:
            raise SpecMissMatch(
                f"Tile type: {tile_type}\n"
                f"with location {tile_loc} and \n"
                f"Feature: {feature_name}\n"
                "found in fasm file was not found in the bitstream spec"
            )


def _compute_grid_size(tile_bits: dict) -> tuple:
    """Compute grid dimensions from tile coordinate keys.

    Scans all keys in ``tile_bits`` (expected to follow the ``XnYm`` naming
    convention) and returns the number of distinct columns and rows in the
    grid.  The counts are one-based, so a tile at ``X3Y2`` contributes to a
    grid of at least 4 columns and 3 rows.

    Parameters
    ----------
    tile_bits : dict[str, list[int]]
        Per-tile bit arrays whose keys are tile location strings (e.g.
        ``'X0Y1'``, ``'X2Y3'``).

    Returns
    -------
    tuple[int, int]
        ``(num_columns, num_rows)`` — the total width and height of the grid.

    Raises
    ------
    AttributeError
        If any tile key does not match the ``X<digits>Y<digits>`` pattern,
        causing the regex match to return ``None``.
    """
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
    """Build Verilog (.vh) and VHDL (.vhd) emulation bitstream constant strings.

    Produces one `` `define`` macro per non-NULL tile for Verilog and one
    ``constant`` declaration per non-NULL tile for VHDL.  Tiles whose type is
    ``'NULL'`` or whose ``FrameMap`` entry is empty are skipped.  The bit
    vector is written in descending index order (MSB first) as required by
    both HDL formats.

    Parameters
    ----------
    tile_bits_no_mask : dict[str, list[int]]
        Unmasked per-tile bit arrays (as produced by ``_apply_fasm_features``
        into the ``tile_bits_no_mask`` structure).
    spec_dict : dict
        Bitstream specification dictionary.  Must contain ``ArchSpecs``
        (``FrameBitsPerRow``, ``MaxFramesPerCol``), ``TileMap``, and
        ``FrameMap``.

    Returns
    -------
    tuple[str, str]
        ``(verilog_str, vhdl_str)`` — the complete Verilog header file content
        and the complete VHDL package file content, respectively.
    """
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

    Iterates over interior rows only (rows 1 through ``num_rows - 2``
    inclusive, in descending order) because the top and bottom rows carry no
    bitstream content (hardcoded convention throughout FABulous).  For each
    tile it appends a header line followed by one line per frame, and packs
    the frame bits into the ``bit_array`` used later to assemble the binary
    bitstream.

    Parameters
    ----------
    tile_bits : dict[str, list[int]]
        Masked per-tile bit arrays (after feature application).
    spec_dict : dict
        Bitstream specification dictionary.  Must contain ``ArchSpecs``
        (``FrameBitsPerRow``, ``MaxFramesPerCol``) and ``TileMap``.
    num_rows : int
        Total number of rows in the grid (from ``_compute_grid_size``).
    num_columns : int
        Total number of columns in the grid (from ``_compute_grid_size``).

    Returns
    -------
    tuple[str, list[list[bytes]]]
        ``(csv_str, bit_array)`` where ``csv_str`` is the full CSV text and
        ``bit_array[col][frame]`` holds the packed bytes for that
        column/frame combination, ready for binary assembly.
    """
    frame_bits_per_row = spec_dict["ArchSpecs"]["FrameBitsPerRow"]
    max_frames_per_col = spec_dict["ArchSpecs"]["MaxFramesPerCol"]

    csv_str = ""
    bit_array = [[b"" for _ in range(max_frames_per_col)] for _ in range(num_columns)]

    # Top/bottom rows have no bitstream content (hardcoded throughout FABulous)
    # reversed row order
    for y in range(num_rows - BORDER_ROWS, 0, -1):
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

    Prepends the 20-byte FABulous sync header, then for every column and
    frame emits a 32-bit frame-select word followed by the frame's data
    bytes.  The frame-select word encodes the column index in the five
    least-significant bits (in reversed bit order) and sets the bit
    corresponding to the active frame index.  Finally appends the 4-byte
    desync frame (bit 20 is the desync flag).

    Parameters
    ----------
    bit_array : list[list[bytes]]
        ``bit_array[col][frame]`` — packed frame bytes as produced by
        ``_build_csv_and_frame_data``.
    num_columns : int
        Total number of columns in the grid.

    Returns
    -------
    bytes
        Complete binary bitstream including the sync header, all frame-select
        words and frame data, and the trailing desync frame.
    """
    bitstream = bytes.fromhex(SYNC_HEADER_HEX)

    for col in range(num_columns):
        for frame_idx in range(MAX_FRAMES_PER_COL):
            col_idx_reversed = f"{col:0{COLUMN_INDEX_BITS}b}"[::-1]
            frame_select = ["0"] * FRAME_SELECT_BITS

            for k in range(-COLUMN_INDEX_BITS, 0, 1):
                frame_select[k] = col_idx_reversed[k]
            frame_select[frame_idx] = "1"
            frame_select_str = ("".join(frame_select))[::-1]

            bitstream += bitstring_to_bytes(frame_select_str)
            bitstream += bit_array[col][frame_idx]

    # Add desync frame (bit DESYNC_BIT is the desync flag)
    bitstream += DESYNC_FRAME
    return bitstream


def genBitstream(fasm_file: str, spec_file: str, bitstream_file: str) -> None:
    """Generate the bitstream from the FASM file using the bitstream specification.

    Orchestrates the full bitstream generation pipeline:

    1. Parse the FASM file into a canonicalised feature list.
    2. Load the bitstream specification from the pickle file.
    3. Initialise per-tile bit arrays and apply FASM features to them.
    4. Derive grid dimensions from the tile map.
    5. Build HDL emulation strings (Verilog and VHDL).
    6. Build the CSV representation and pack frame data.
    7. Assemble the binary bitstream.
    8. Write all four output files (.csv, .vh, .vhd, .bin).

    Parameters
    ----------
    fasm_file : str
        Path to the FASM file containing the configuration features to apply.
    spec_file : str
        Path to the pickle file containing the bitstream specification
        (``TileMap``, ``TileSpecs``, ``FrameMap``, ``ArchSpecs``, etc.).
    bitstream_file : str
        Base output path.  The extension is replaced to produce the four
        output files: ``<base>.csv``, ``<base>.vh``, ``<base>.vhd``, and
        ``<base>.bin`` (the binary bitstream).

    Raises
    ------
    FileNotFoundError
        If ``fasm_file`` or ``spec_file`` does not exist.
    pickle.UnpicklingError
        If ``spec_file`` cannot be deserialised as a valid pickle.
    SpecMissMatch
        If a FASM feature references a tile location or feature name not
        present in the bitstream specification.
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
