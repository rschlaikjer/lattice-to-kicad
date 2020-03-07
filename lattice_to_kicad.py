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
            ",".join(self.part_mapping.keys())
        )


class LatticeCSV:
    def __init__(self, filename):
        self._pads = {}

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
                self._pads[lattice_pad.pad_number] = lattice_pad

    def get_signals_for_part(self, part):
        ret = []
        for pad in self._pads.values():
            if part in pad.part_mapping.keys():
                if pad.part_mapping[part] != '-':
                    ret.append(pad)
        return ret

    def get_part_names(self):
        names = set()
        for pad in self._pads.values():
            for part in pad.part_mapping.keys():
                names.add(part)
        return names


def csv_to_rows(filename):
    with open(filename) as csvfile:
        reader = csv.reader(csvfile)
        header = next(reader)
        return (header, [row for row in reader])

def pin_compare_wrapper(tup1, tup2):
    return pin_compare(tup1[0], tup2[0])

def cmp(x, y):
    return (x > y) - (x < y)

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
        return cmp(pin1, pin2)

    intprefix1 = int(intprefix1)
    intprefix2 = int(intprefix2)

    # If the numbers aren't equal, compare on these
    if int(intprefix1) != int(intprefix2):
        return cmp(intprefix1, intprefix2)

    # If the numbers were equal, compare based on the suffix
    intsuffix1 = ''.join(c for c in itertools.dropwhile(is_numchar, pin1))
    intsuffix2 = ''.join(c for c in itertools.dropwhile(is_numchar, pin2))
    return cmp(intsuffix1, intsuffix2)

def make_rect(start_x, start_y, end_x, end_y, unit):
    # S X1 Y1 X2 Y2 part dmg pen fill
    return "S {x1} {y1} {x2} {y2} {unit} 1 0 N".format(
        x1=start_x,
        y1=start_y,
        x2=end_x,
        y2=end_y,
        unit=unit,
    )

def make_pin(signal, pad, unit, x, y, orientation='L'):
    # X name pin X Y length orientation sizenum sizename part dmg type shape
    # I(nput), O(utout), B(idirectional), T(ristate),
    # P(assive), (open) C(ollector), (open) E(mitter), N(on-connected),
    # U(nspecified), or W for power input or w of power output.
    pintype = get_pin_type(signal)
    return "X {signal} {pad} {x} {y} 200 {dir} 50 50 {unit} 1 {pintype}".format(
        signal=signal,
        pad=pad,
        x=x,
        y=y,
        dir=orientation,
        unit=unit,
        pintype=pintype,
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
    if len(sys.argv) != 4:
        sys.stderr.write("Usage: %s lattice_csv part package\n" % sys.argv[0])
        return

    # Load csv to list of lists
    header, rows = csv_to_rows(sys.argv[1])

    # Part name / package are next 2 args
    part = sys.argv[2]
    package = sys.argv[3].upper()

    # Find which column has the right package
    ballout_col = header.index(package)

    signals_per_bank = defaultdict(list)

    for row in rows:
        signal = row[1]
        # Ignore NC pins
        if signal == 'NC':
            continue

        # If the pin doesn't exist in this package, ignore
        ballout = row[ballout_col]
        if ballout == '-':
            continue

        # Get the IO bank
        bank = row[2]
        if bank == '-':
            if is_power_pin(signal):
                bank = 'power'
            else:
                bank = 'misc'

        signals_per_bank[bank].append((signal, ballout))

    # Get number of banks
    banks = sorted(signals_per_bank.keys())

    # Part def
    part_name = '%s-%s' % (part, package)
    print('DEF {partname} U 0 20 Y Y {units} L N'.format(
        partname=part_name,
        units=len(banks)
    ))
    print('F0 "U" 0 0 50 H V C CNN')
    print('F1 "{partname}" 0 0 50 H V C CNN'.format(
        partname=part_name
    ))
    print('F2 "" 0 0 50 H I C CNN')
    print('F3 "" 0 0 50 H I C CNN')
    print('DRAW')

    # Now, for each bank, sort and print the pins
    unit_number = 1
    for bank in banks:
        # Get the signals in this bank
        signals = signals_per_bank[bank]
        # Split into VCC / non VCC signals, since we want to put vcc at the top
        vcc_signals = [(signal, ball) for (signal, ball) in signals
                       if signal.startswith('VCC')]
        non_vcc_signals = [(signal, ball) for (signal, ball) in signals
                           if not signal.startswith('VCC')]
        # Make them vaguely in order
        vcc_signals.sort(key=lambda x: x[0])
        non_vcc_signals.sort(key=functools.cmp_to_key(pin_compare_wrapper))
        # Get the start Y value based on the number of pins, and being symmetric
        # about the x axis
        bank_y_start = int((((len(signals)-1) / 2) * 100))
        bank_y_end = -int(((len(signals)-1) / 2) * 100)
        if bank_y_start % 100 != 0:
            delta = bank_y_start % 100
            bank_y_start -= delta
            bank_y_end -= delta
        bank_y_step = -100
        yval = bank_y_start
        pins = []
        for (signal, ballout) in vcc_signals:
            pins.append(make_pin(signal, ballout, unit_number, 200, int(yval)))
            yval += bank_y_step
        for (signal, ballout) in non_vcc_signals:
            pins.append(make_pin(signal, ballout, unit_number, 200, int(yval)))
            yval += bank_y_step
        for pin in pins:
            print(pin)
        print(make_rect(
            -400, bank_y_start - bank_y_step,
            0, bank_y_end + bank_y_step,
            unit_number
        ))

        unit_number += 1

    # End part
    print("ENDDRAW")
    print("ENDDEF")

def test_main():
    csv_data = LatticeCSV(sys.argv[1])
    signals = csv_data.get_signals_for_part("CABGA256")
    for s in signals:
        print(s)


if __name__ == '__main__':
    test_main()
