# FABulous bit_gen

Bitstream generation utilities for FABulous FPGA fabrics.

This package provides functionality for generating bitstreams from FASM (FPGA Assembly)
files for FABulous FPGA fabrics. It handles the conversion of place-and-route results
into configuration bitstreams that can be loaded onto the FPGA fabric.

## Features

- Parse FASM files containing FPGA configuration features
- Process configuration bits according to bitstream specifications
- Generate bitstream output in multiple formats:
  - Binary (.bin)
  - CSV (.csv)
  - Verilog header (.vh)
  - VHDL package (.vhd)

## Installation

```bash
pip install FABulous-bit-gen
```

## Usage

### Command Line

```bash
bit_gen -genBitstream input.fasm spec.pkl output.bin
```

### Python API

```python
from FABulous_bit_gen import genBitstream

genBitstream("input.fasm", "spec.pkl", "output.bin")
```

## License

Apache Software License 2.0
