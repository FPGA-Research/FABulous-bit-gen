"""Custom exception classes for the FABulous bit_gen module.

This module defines custom exceptions used during bitstream generation.
"""


class SpecMissMatch(Exception):
    """Exception raised when a FASM feature is not found in the bitstream spec."""
