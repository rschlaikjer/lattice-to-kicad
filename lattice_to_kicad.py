#!/usr/bin/env python3
import sys
import csv
import itertools
import functools

from collections import defaultdict

class LatticePad:

    def __init__(self, csv_header, row):
        # First few columns are common to all parts
        self.pad_number = int(row[0])
        self.pin_ball = row[1]
        self.bank = row[2]
        self.dual_function = row[3] == 'TRUE'
        self.differential = row[4]
        self.high_speed = row[5] == 'TRUE'
        self.dqs = row[6]

        # After that, we have actuall ballout mapping per-part
        self.part_mapping = {}
        for col in range(7, len(row)):
            part_name = csv_header[col]
            self.part_mapping[part_name] = row[col]

    def is_nc(self):
        return self.pin_ball == 'NC'

    def ball_for_package(self, package):
        return self.part_mapping[package]

    def __str__(self):
        return (
            "LatticePad: \n"
            "   pad_number(%s)\n"
            "   pin_ball(%s)\n"
            "   bank(%s)\n"
            "   dual_function(%s)\n"
            "   differential(%s)\n"
            "   high_speed(%s)\n"
            "   dqs(%s)\n"
            "   parts(%s)\n"
        ) % (
            self.pad_number,
            self.pin_ball,
            self.bank,
            self.dual_function,
            self.differential,
            self.high_speed,
            self.dqs,
            ",".join(["%s:%s"% (k, v) for (k, v) in self.part_mapping.items()])
        )


class LatticeCSV:
    def __init__(self, filename):
        self._pads = []

        # Load raw CSV data
        with open(filename) as csvfile:
            reader = csv.reader(csvfile)
            self._raw_rows = [row for row in reader]

        # Preprocess data to get packages, etc
        self._preprocess_rows()

    def _preprocess_rows(self):
        found_header = False
        next_row_is_header = False
        for row in self._raw_rows:
            # All the lattice CSVs seem to use a fully blank line to delimit
            # the end of comments, so scan til we see that
            if not found_header:
                if next_row_is_header:
                    _header = row
                    found_header = True
                if all([v == '' for v in row]):
                    next_row_is_header = True
            else:
                # We know the header, parse this row as data.
                lattice_pad = LatticePad(_header, row)
                self._pads.append(lattice_pad)

    def get_signals_for_part(self, part):
        ret = []
        for pad in self._pads:
            if part in pad.part_mapping.keys():
                if pad.part_mapping[part] != '-':
                    ret.append(pad)
        return ret

    def get_part_names(self):
        names = set()
        for pad in self._pads:
            for part in pad.part_mapping.keys():
                names.add(part)
        return names


class KicadPart:

    def __init__(self, part, package):
        self.part = part
        self.package = package
        self.banks = {}

    def add_bank(self, bank_id, pads):
        self.banks[bank_id] = KicadBank(self.package, bank_id, pads)

    def emit(self):
        # Part header
        part_name = '%s-%s' % (self.part, self.package)
        print('#')
        print('# %s' % part_name)
        print('#')
        print('DEF {partname} U 0 20 Y Y {units} L N'.format(
            partname=part_name,
            units=len(self.banks)
        ))
        print('F0 "U" 0 0 50 H V C CNN')
        print('F1 "{partname}" 0 0 50 H V C CNN'.format(
            partname=part_name
        ))
        print('F2 "" 0 0 50 H I C CNN')
        print('F3 "" 0 0 50 H I C CNN')
        print('DRAW')

        # Generate the IO banks
        for bank in self.banks.values():
            bank.emit()

        # Part footer
        print("ENDDRAW")
        print("ENDDEF")


class KicadBank:

    PIN_Y_SPACING_MILS = 100

    def __init__(self, package, bank_number, pads):
        # Map of signal name to list of physical pads
        self._pads = defaultdict(list)
        self._bank_number = bank_number
        # Stack all the pads with the same net
        for pad in pads:
            self._pads[pad.pin_ball].append(pad.ball_for_package(package))

    def emit(self):
        # Get the total number of unique signals in this bank
        signal_names = self._pads.keys()

        # Split the signals into Vcc, GND, and other
        vcc_signals = [name for name in signal_names if is_vcc_pin(name)]
        gnd_signals = [name for name in signal_names if is_gnd_pin(name)]
        other_signals = [
            name for name in signal_names
            if (name not in vcc_signals) and (name not in gnd_signals)]

        # Sort the names
        vcc_signals.sort()
        gnd_signals.sort()
        other_signals.sort(key=functools.cmp_to_key(KicadBank.pin_compare))

        # Work out the dimensions of this bank using the total signal name count
        total_signal_count = len(signal_names)
        offset_negative_y = int((total_signal_count) / 2)
        start_pin_location_y = offset_negative_y * self.PIN_Y_SPACING_MILS
        pin_location_y = start_pin_location_y

        # Emit all the pin definitions
        combined_ordered_signals = vcc_signals + other_signals + gnd_signals
        for signal in combined_ordered_signals:
            # Pins with the same signal after the first one should be
            # rendered as 'invisible'
            is_first_pin = True
            for ball in self._pads[signal]:
                print(kicad_make_pin(
                    signal, ball, self._bank_number,
                    200, pin_location_y,
                    pin_visible=is_first_pin))
                is_first_pin = False
            pin_location_y -= self.PIN_Y_SPACING_MILS

        # Emit a rectangle around all the names
        max_signal_name_len = max([len(signal) for signal
                                   in combined_ordered_signals])
        print(kicad_make_rect(
            -(max_signal_name_len * 50 + 50), start_pin_location_y + self.PIN_Y_SPACING_MILS,
            0, pin_location_y,
            self._bank_number))

    @staticmethod
    def pin_compare_wrapper(tup1, tup2):
        return KicadBank.pin_compare(tup1[0], tup2[0])

    @staticmethod
    def cmp(x, y):
        return (x > y) - (x < y)

    @staticmethod
    def pin_compare(pin1, pin2):
        # Find the common prefix to both pins
        len1 = len(pin1)
        len2 = len(pin2)
        prefix = ""
        i = 0
        for i in range(min(len1, len2)):
            if pin1[i] == pin2[i]:
                prefix += pin1[i]
            else:
                break

        # Remove the prefix part from both strings
        pin1 = pin1[i:]
        pin2 = pin2[i:]

        # Take the longest int prefix from both strings
        is_numchar = lambda c: c >= '0' and c <= '9'
        intprefix1 = ''.join(c for c in itertools.takewhile(is_numchar, list(pin1)))
        intprefix2 = ''.join(c for c in itertools.takewhile(is_numchar, list(pin2)))

        # If the prefix is missing on one, compare classically
        if not intprefix1 or not intprefix2:
            # Not the sort of pin pattern we're handling,
            # return a normal compare
            return KicadBank.cmp(pin1, pin2)

        intprefix1 = int(intprefix1)
        intprefix2 = int(intprefix2)

        # If the numbers aren't equal, compare on these
        if int(intprefix1) != int(intprefix2):
            return KicadBank.cmp(intprefix1, intprefix2)

        # If the numbers were equal, compare based on the suffix
        intsuffix1 = ''.join(c for c in itertools.dropwhile(is_numchar, pin1))
        intsuffix2 = ''.join(c for c in itertools.dropwhile(is_numchar, pin2))
        return KicadBank.cmp(intsuffix1, intsuffix2)


def split_pads_by_bank(pads):
    pads_per_bank = defaultdict(list)
    for pad in pads:
        pads_per_bank[pad.bank].append(pad)
    return pads_per_bank


def generate_kicad_part(part, csv_data, package):
    # Get all the pads for this part
    sys.stderr.write("Generating part for package '%s'\n" % package)
    pads = csv_data.get_signals_for_part(package)

    # First thing we're going to do is separate all of the pads in to I/O banks.
    # Pins that don't specify a bank (-) in the CSV will be grouped into a final
    # 'Power' bank.
    pads_per_bank = split_pads_by_bank(pads)
    sys.stderr.write("Total IO banks: %s\n" % len(pads_per_bank.keys()))

    # Create a part holder
    kicad_part = KicadPart(part, package)

    # Wrap all the bank pads, renumbering from 0
    bank_ids = list(pads_per_bank.keys())
    bank_ids.sort()
    bank_i = 1
    for bank_id in bank_ids:
        kicad_part.add_bank(bank_i, pads_per_bank[bank_id])
        bank_i += 1

    # Emit the kicad symbol data
    kicad_part.emit()

def kicad_make_rect(start_x, start_y, end_x, end_y, unit):
    # S X1 Y1 X2 Y2 part dmg pen fill
    return "S {x1} {y1} {x2} {y2} {unit} 1 0 N".format(
        x1=start_x,
        y1=start_y,
        x2=end_x,
        y2=end_y,
        unit=unit,
    )

def kicad_make_pin(signal, pad, unit, x, y, orientation='L', pin_visible=True):
    # X name pin X Y length orientation sizenum sizename part dmg type shape
    # I(nput), O(utout), B(idirectional), T(ristate),
    # P(assive), (open) C(ollector), (open) E(mitter), N(on-connected),
    # U(nspecified), or W for power input or w of power output.
    pintype = get_pin_type(signal)
    return "X {signal} {pad} {x} {y} 200 {dir} 50 50 {unit} 1 {pintype}{visible}".format(
        signal=signal,
        pad=pad,
        x=x,
        y=y,
        dir=orientation,
        unit=unit,
        pintype=pintype,
        visible=("" if pin_visible else " N"),
    )

def get_pin_type(pinname):
    if is_power_pin(pinname):
        return 'W'
    if pinname == 'RESERVED':
        return 'U'
    return 'B'

def is_gnd_pin(pinname):
    return pinname == 'GND'

def is_vcc_pin(pinname):
    return pinname.startswith('VCC')

def is_power_pin(pinname):
    if is_gnd_pin(pinname):
        return True
    if is_vcc_pin(pinname):
        return True

def main():
    # Load the CSV data for the part
    part_name = sys.argv[1]
    csv_data = LatticeCSV(sys.argv[2])
    # Get the list of possible packages
    packages = csv_data.get_part_names()
    # Generate KiCad symbols for each package variant
    for package in packages:
        generate_kicad_part(part_name, csv_data, package)


if __name__ == '__main__':
    main()
