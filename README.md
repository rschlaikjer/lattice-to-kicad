# KiCad Symbol Generator for Lattice FPGA parts

Quick script for converting Lattice's pinout CSV format into KiCad symbols.

- Pins will be grouped into KiCad units based on the 'BANK' value in the pinout CSV
    - This places VCCIO pins with the relevant I/O bank.
    - Pins with no bank (`-`) are grouped into the same bank
- Pins are ordered such that power pins are at the top of the unit, grounds
are at the bottom
- Signals that map to more than one physical pin (VCCs, GNDs) are stacked, and
all pins after the first on the same net are set to invisible. This greatly
reduces the size of some symbols.

## Usage

Included is a `Makefile` that generates a library containing all of the ECP5
series FPGA parts. This can be used as a starting off point for loading other
parts.

Direct usage:

    ./lattice_to_kicad.py part_name csv_file

The script will print symbol data on standard out.
The script does NOT handle updates to existing libraries / generation of
library header. See the makefile for the minimal extra calls necessary to make a
library readable by KiCad.
