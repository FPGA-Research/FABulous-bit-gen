"""FABulous Bit Gen - Bitstream generation utilities for FABulous FPGA fabrics.

This package provides functionality for generating bitstreams from FASM (FPGA Assembly)
files for FABulous FPGA fabrics. It handles the conversion of place-and-route results
into configuration bitstreams that can be loaded onto the FPGA fabric.
"""

from fabulous_bit_gen.bit_gen import bitstring_to_bytes, genBitstream

__all__ = ["genBitstream", "bitstring_to_bytes"]
