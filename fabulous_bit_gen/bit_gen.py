#!/usr/bin/env python

"""Bitstream generation utilities for FABulous FPGA fabrics.

This module provides functionality for generating bitstreams from FASM (FPGA Assembly)
files for FABulous FPGA fabrics. It handles the conversion of place-and-route results
into configuration bitstreams that can be loaded onto the FPGA fabric.

The module includes functions for parsing FASM files, processing configuration bits, and
generating the final bitstream output in various formats.

Bitstream format
----------------
The binary bitstream has the following structure::

    [ 20-byte sync header           ]
    for each column (x = 0 … num_columns-1):
      for each frame (f = 0 … MaxFramesPerCol-1):
        [ 4-byte frame-select word  ]  — addresses column + frame
        [ frame data bytes          ]  — ceil(FrameBitsPerRow/8) bytes of config bits
    [ 4-byte desync frame           ]  — bit DESYNC_BIT set

Frame-select word (32-bit big-endian):
  - Bits [31:27]: column index (5 bits, normal binary order).
  - Bits [26:21]: unused (always 0).
  - Bit  [20]:    sync/desync flag — set only in the trailing desync frame.
  - Bits [19:0]:  frame strobe — bit ``f`` set selects frame index ``f``
                  (one-hot, supports up to 20 frames, indices 0–19).

Frame data bytes:
  Concatenation of FrameBitsPerRow configuration bits from each emitted row
  of that column (Y descending), bit-reversed per row, packed into bytes.
  Emitted rows are interior-only by default, or all rows when
  ``include_border_rows`` is enabled.
"""

import argparse
import math
import pickle
import re
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from fabulous_bit_gen.custom_exception import SpecMissMatch

try:
    from fasm import (
        FasmLine,
        fasm_tuple_to_string,
        parse_fasm_filename,
        parse_fasm_string,
        set_feature_to_str,
    )
except ImportError:
    logger.critical("Could not import fasm. Bitstream generation not supported.")

# Bitstream format constants defaults
COLUMN_SELECT_BITS: int = 5
"""Default bits used to encode column index inside the frame-select word."""

FRAME_SELECT_BITS: int = 32
"""Default width of each frame-address/control word (bits) prepended to each frame.

This word encodes the destination column and active frame strobe. The top
``COLUMN_SELECT_BITS`` bits carry the column index; usable low bits are
``FRAME_SELECT_BITS - COLUMN_SELECT_BITS``.

Default FABulous Fabric ingress is 32-bit WriteData.
Changing this width needs RTL/protocol changes.
"""

FRAME_BITS_PER_ROW: int = 32
"""Default width of the configuration *data* payload (bits) per frame row.

This is the number of configuration bits carried in each per-row frame data
word written after the frame-select word. In current FABulous Fabric RTL both
address/control and data transfers use 32-bit ``WriteData`` words, so changing
this width requires matching RTL/protocol updates.
"""

MAX_FRAMES_PER_COL: int = 20
"""Default number of one-hot frame strobe bits used per column.

Frame index ``f`` uses low bit ``f`` of the frame-select word (default range
``0..19``).
"""

SYNC_HEADER_HEX: str = "00AAFF01000000010000000000000000FAB0FAB1"
"""Default FABulous sync header that opens every bitstream."""

DESYNC_BIT: int = 20
"""Default bit position of desync flag inside the frame-select word.

With defaults, this is bit 20, above the frame strobe range (bits 0..19).
"""


def _parse_bool(value: bool | str, *, key_name: str) -> bool:
    """Parse a bool field from spec values."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized == "true":
            return True
        if normalized == "false":
            return False
    raise ValueError(
        f"{key_name} must be a bool or 'True'/'False' string; got {value!r}"
    )


@dataclass(frozen=True)
class BitstreamFormat:
    """Typed bitstream wire-format settings resolved from spec/defaults."""

    frame_bits_per_row: int
    max_frames_per_col: int
    sync_header_hex: str
    column_select_bits: int
    frame_select_bits: int
    desync_bit: int
    include_border_rows: bool = False


def _resolve_bitstream_format(spec_dict: dict) -> BitstreamFormat:
    """Resolve bitstream-format settings from spec dict once with fallbacks."""
    search_sections = (
        spec_dict,
        spec_dict.get("BitstreamConstants", {}),
        spec_dict.get("BitstreamFormat", {}),
        spec_dict.get("BitstreamSpecs", {}),
        spec_dict.get("ArchSpecs", {}),
    )

    def pick(key: str, default: int | str) -> int | str:
        for section in search_sections:
            if key in section:
                return section[key]
        logger.debug(f"{key} missing in bitstream spec; using default {default!r}.")
        return default

    fmt = BitstreamFormat(
        frame_bits_per_row=FRAME_BITS_PER_ROW,
        max_frames_per_col=int(pick("MaxFramesPerCol", MAX_FRAMES_PER_COL)),
        sync_header_hex=str(pick("sync_header_hex", SYNC_HEADER_HEX)),
        column_select_bits=int(pick("column_select_bits", COLUMN_SELECT_BITS)),
        frame_select_bits=FRAME_SELECT_BITS,
        desync_bit=int(pick("desync_bit", DESYNC_BIT)),
        include_border_rows=_parse_bool(
            spec_dict.get("include_border_rows", False),
            key_name="include_border_rows",
        ),
    )
    if fmt.column_select_bits >= fmt.frame_select_bits:
        raise ValueError(
            f"COLUMN_SELECT_BITS ({fmt.column_select_bits}) must be less than "
            f"FRAME_SELECT_BITS ({fmt.frame_select_bits})"
        )

    selectable_frame_bits = fmt.frame_select_bits - fmt.column_select_bits
    if fmt.max_frames_per_col > selectable_frame_bits:
        raise ValueError(
            f"MaxFramesPerCol ({fmt.max_frames_per_col}) exceeds "
            "FRAME_SELECT_BITS minus COLUMN_SELECT_BITS "
            f"({selectable_frame_bits}): frame index would overlap the "
            "column index bits"
        )
    if fmt.desync_bit < fmt.max_frames_per_col:
        raise ValueError(
            f"DESYNC_BIT ({fmt.desync_bit}) must be >= MaxFramesPerCol "
            f"({fmt.max_frames_per_col}) so it does not overlap frame strobe bits"
        )
    if fmt.desync_bit >= selectable_frame_bits:
        raise ValueError(
            f"DESYNC_BIT ({fmt.desync_bit}) must be less than "
            f"{selectable_frame_bits} so it does not overlap "
            "the column select bits in the frame-select word"
        )
    return fmt


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
    return int(s, 2).to_bytes(math.ceil(len(s) / 8), byteorder="big")


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
    list
        Canonicalised list of FASM lines parsed from the file.
    """
    fasm_lines = parse_fasm_filename(fasm_file)
    canonical_str = fasm_tuple_to_string(fasm_lines, True)
    return list(parse_fasm_string(canonical_str))


def _init_tile_bits(
    spec_dict: dict,
    bitstream_format: BitstreamFormat,
) -> tuple[dict[str, list[int]], dict[str, list[int]]]:
    """Initialise per-tile bit arrays to all zeros.

    Allocates two flat integer lists of length
    ``MaxFramesPerCol * FrameBitsPerRow`` for every tile in ``TileMap``:
    one for the masked bitstream written to the binary output, and one for
    the unmasked (No_Mask) bitstream used by the HDL emulation constants.

    Parameters
    ----------
    spec_dict : dict
        Bitstream specification dictionary loaded from the pickle spec file.
        Must contain ``TileMap``.
    bitstream_format : BitstreamFormat
        Resolved wire-format settings supplying ``MaxFramesPerCol`` and
        ``FrameBitsPerRow`` for the allocation size.

    Returns
    -------
    tuple[dict[str, list[int]], dict[str, list[int]]]
        A pair ``(tile_bits, tile_bits_no_mask)``, each mapping tile location
        strings (e.g. ``'X1Y2'``) to a zero-filled integer list of length
        ``MaxFramesPerCol * FrameBitsPerRow``.
    """
    total_bits = (
        bitstream_format.max_frames_per_col * bitstream_format.frame_bits_per_row
    )

    tile_bits = {tile: [0] * total_bits for tile in spec_dict["TileMap"]}
    tile_bits_no_mask = {tile: [0] * total_bits for tile in spec_dict["TileMap"]}
    return tile_bits, tile_bits_no_mask


def _apply_fasm_features(
    canon_list: list[FasmLine],
    spec_dict: dict,
    tile_bits: dict[str, list[int]],
    tile_bits_no_mask: dict[str, list[int]],
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
    """
    # Track which bit indices have already been written for each tile so that
    # overwrites are detected regardless of the bit value (a feature can
    # legitimately map a bit to 0, making a value-based sentinel unreliable).
    touched_bits: dict[str, set] = {tile: set() for tile in tile_bits}
    touched_bits_no_mask: dict[str, set] = {tile: set() for tile in tile_bits_no_mask}

    for line in canon_list:
        if not line.set_feature:
            continue
        feature_str = set_feature_to_str(line.set_feature)
        if "CLK" in feature_str:
            continue

        feature_parts = feature_str.split(".")
        if len(feature_parts) < 3:
            raise SpecMissMatch(
                f"Feature '{feature_str}' has fewer than 3 dot-separated parts"
            )
        if len(feature_parts) > 3:
            logger.warning(
                f"Feature '{feature_str}' has {len(feature_parts)} dot-separated "
                "parts; only the first three are used — trailing parts are ignored."
            )
        tile_loc = feature_parts[0]
        feature_name = ".".join((feature_parts[1], feature_parts[2]))

        if tile_loc not in spec_dict["TileMap"]:
            raise SpecMissMatch(
                f"Tile location {tile_loc} not found in the bitstream spec"
            )

        # Set the necessary bits high
        tile_type = spec_dict["TileMap"][tile_loc]
        if tile_loc not in spec_dict["TileSpecs"]:
            raise SpecMissMatch(f"Tile location '{tile_loc}' not found in TileSpecs")
        if feature_name in spec_dict["TileSpecs"][tile_loc]:
            if spec_dict["TileSpecs"][tile_loc][feature_name]:
                for bit_idx, bit_val in spec_dict["TileSpecs"][tile_loc][
                    feature_name
                ].items():
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
                if tile_loc not in spec_dict["TileSpecs_No_Mask"]:
                    raise SpecMissMatch(
                        f"Tile location '{tile_loc}' not found in TileSpecs_No_Mask"
                    )
                if feature_name not in spec_dict["TileSpecs_No_Mask"][tile_loc]:
                    raise SpecMissMatch(
                        f"Feature '{feature_name}' of tile '{tile_loc}' missing "
                        "from TileSpecs_No_Mask"
                    )
                for bit_idx, bit_val in spec_dict["TileSpecs_No_Mask"][tile_loc][
                    feature_name
                ].items():
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


def _compute_grid_size(tile_bits: dict[str, list[int]]) -> tuple[int, int]:
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
    ValueError
        If any tile key does not match the ``XnYm`` coordinate format.
    """
    num_columns = 0
    num_rows = 0
    tile_coord_re: re.Pattern = re.compile(r"X(\d+)Y(\d+)")

    for tile_key in tile_bits:
        coords_match = tile_coord_re.fullmatch(tile_key)
        if coords_match is None:
            raise ValueError(f"Tile key '{tile_key}' does not match XnYm format")
        num_columns = max(int(coords_match.group(1)) + 1, num_columns)
        num_rows = max(int(coords_match.group(2)) + 1, num_rows)
    return num_columns, num_rows


def _build_hdl_strings(
    tile_bits_no_mask: dict[str, list[int]],
    spec_dict: dict,
    bitstream_format: BitstreamFormat,
) -> tuple[str, str]:
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
        Bitstream specification dictionary.  Must contain ``TileMap`` and
        ``FrameMap``.
    bitstream_format : BitstreamFormat
        Resolved wire-format settings supplying frame dimensions and the
        ``include_border_rows`` flag.

    Returns
    -------
    tuple[str, str]
        ``(verilog_str, vhdl_str)`` — the complete Verilog header file content
        and the complete VHDL package file content, respectively.
    """
    total_bits = (
        bitstream_format.max_frames_per_col * bitstream_format.frame_bits_per_row
    )

    verilog_str = ""
    vhdl_str = (
        "library IEEE;\nuse IEEE.STD_LOGIC_1164.ALL;\n\npackage emulate_bitstream is\n"
    )
    for tile_key, bits in tile_bits_no_mask.items():
        tile_type = spec_dict["TileMap"][tile_key]
        frame_map_entry = spec_dict["FrameMap"].get(tile_type, {})
        if tile_type == "NULL" or (
            len(frame_map_entry) == 0 and not bitstream_format.include_border_rows
        ):
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
    tile_bits: dict[str, list[int]],
    spec_dict: dict,
    num_rows: int,
    num_columns: int,
    bitstream_format: BitstreamFormat,
) -> tuple[str, list[list[bytes]]]:
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
    bitstream_format : BitstreamFormat
        Resolved wire-format settings supplying frame dimensions and the
        ``include_border_rows`` flag.

    Returns
    -------
    tuple[str, list[list[bytes]]]
        ``(csv_str, bit_array)`` where ``csv_str`` is the full CSV text and
        ``bit_array[col][frame]`` holds the packed bytes for that
        column/frame combination, ready for binary assembly.
    """
    csv_str = ""
    # bit_array[col][frame] accumulates packed bytes from every row in that column.
    bit_array = [
        [b"" for _ in range(bitstream_format.max_frames_per_col)]
        for _ in range(num_columns)
    ]

    if bitstream_format.include_border_rows:
        logger.info("Border rows included in bitstream.")
        start_row = num_rows - 1
        stop_row = -1
    else:
        logger.info("Border rows excluded from bitstream (default).")
        start_row = num_rows - 2
        stop_row = 0

    # Rows are written top-to-bottom in the CSV
    for y in range(start_row, stop_row, -1):
        for x in range(num_columns):
            tile_key = f"X{x}Y{y}"
            tile_type = spec_dict["TileMap"].get(tile_key, "NULL")

            tile_csv = f"{tile_key},{tile_type},{x},{y}\n"

            for frame_idx in range(bitstream_format.max_frames_per_col):
                if tile_type == "NULL":
                    # NULL get an all-zero row
                    frame_bits = "0" * bitstream_format.frame_bits_per_row
                else:
                    if tile_key not in tile_bits:
                        raise SpecMissMatch(
                            "Tile location "
                            f"'{tile_key}' missing from initialized tile bits"
                        )
                    # Slice this frame's bits from the flat per-tile array and
                    # bit-reverse: the spec stores bits in frame-ascending order
                    # but we need them reversed within each row.
                    offset = bitstream_format.frame_bits_per_row * frame_idx
                    raw = tile_bits[tile_key][
                        offset : offset + bitstream_format.frame_bits_per_row
                    ]
                    frame_bits = "".join(map(str, raw))[::-1]

                tile_csv += (
                    f"frame{frame_idx},{frame_idx},"
                    f"{bitstream_format.frame_bits_per_row},{frame_bits}\n"
                )

                # Append this row's contribution; the full column/frame payload
                # is the concatenation of all rows processed in this loop.
                bit_array[x][frame_idx] += bitstring_to_bytes(frame_bits)

            csv_str += tile_csv + "\n"

    return csv_str, bit_array


def _build_binary_bitstream(
    bit_array: list[list[bytes]],
    num_columns: int,
    bitstream_format: BitstreamFormat,
) -> bytes:
    """Assemble the final binary bitstream from per-column frame data.

    Prepends the 20-byte FABulous sync header, then for every column and
    each frame present in ``bit_array[col]`` emits a 32-bit frame-select
    word followed by the frame's data bytes. The frame-select word places
    the column index in the top ``COLUMN_SELECT_BITS`` bits and sets bit
    ``frame_idx`` (one-hot) to identify the active frame.
    Finally appends the desync frame with bit ``DESYNC_BIT`` set.

    Parameters
    ----------
    bit_array : list[list[bytes]]
        ``bit_array[col][frame]`` — packed frame bytes as produced by
        ``_build_csv_and_frame_data``.
    num_columns : int
        Total number of columns in the grid.
    bitstream_format : BitstreamFormat
        Typed wire-format settings resolved from the bitstream specification.

    Returns
    -------
    bytes
        Complete binary bitstream including the sync header, all frame-select
        words and frame data, and the trailing desync frame.
    """
    # Add sync header at the start of the bitstream
    bitstream = bytes.fromhex(bitstream_format.sync_header_hex)

    # Emit one (frame-select word + frame data) pair per frame per column.
    # Columns are written left-to-right; frames top-to-bottom within each column.
    for col in range(num_columns):
        for frame_idx, frame_data in enumerate(bit_array[col]):
            # Frame-select word: column in top bits (address),
            # frame as one-hot bit (select).
            frame_select_word = (
                col
                << (
                    bitstream_format.frame_select_bits
                    - bitstream_format.column_select_bits
                )
            ) | (1 << frame_idx)
            bitstream += frame_select_word.to_bytes(
                math.ceil(bitstream_format.frame_select_bits / 8), byteorder="big"
            )
            # Frame data: packed config bits for this column/frame across all rows
            bitstream += frame_data

    # Desync frame signals end-of-bitstream to the configuration engine.
    desync_frame = (1 << bitstream_format.desync_bit).to_bytes(
        math.ceil(bitstream_format.frame_select_bits / 8), byteorder="big"
    )
    bitstream += desync_frame
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
    ValueError
        If the resolved bitstream format is invalid (e.g. ``MaxFramesPerCol``
        exceeds ``FRAME_SELECT_BITS``, or the grid is wider than
        ``COLUMN_SELECT_BITS`` can address).
    """
    canon_list = _parse_fasm_to_canon_list(fasm_file)
    if not canon_list:
        logger.warning(
            "FASM file contains no features; the generated bitstream will be all zeros."
        )

    with Path(spec_file).open("rb") as f:
        spec_dict = pickle.load(f)

    bitstream_format = _resolve_bitstream_format(spec_dict)
    tile_bits, tile_bits_no_mask = _init_tile_bits(spec_dict, bitstream_format)
    _apply_fasm_features(canon_list, spec_dict, tile_bits, tile_bits_no_mask)

    num_columns, num_rows = _compute_grid_size(tile_bits)
    max_addressable_columns = 2**bitstream_format.column_select_bits
    if num_columns > max_addressable_columns:
        raise ValueError(
            f"Grid has {num_columns} columns but COLUMN_SELECT_BITS "
            f"({bitstream_format.column_select_bits}) can only address "
            f"{max_addressable_columns}: column index would overflow "
            "the frame-select word"
        )
    verilog_str, vhdl_str = _build_hdl_strings(
        tile_bits_no_mask,
        spec_dict,
        bitstream_format,
    )
    csv_str, bit_array = _build_csv_and_frame_data(
        tile_bits,
        spec_dict,
        num_rows,
        num_columns,
        bitstream_format,
    )
    bitstream_bytes = _build_binary_bitstream(
        bit_array,
        num_columns,
        bitstream_format,
    )

    output_path = Path(bitstream_file)
    # Write out bitstream CSV representation
    with output_path.with_suffix(".csv").open("w") as f:
        f.write(csv_str)
    # Write out HDL representations
    with output_path.with_suffix(".vh").open("w") as f:
        f.write(verilog_str)
    with output_path.with_suffix(".vhd").open("w") as f:
        f.write(vhdl_str)
    # Write out binary representation
    with output_path.with_suffix(".bin").open("wb") as f:
        f.write(bitstream_bytes)


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
