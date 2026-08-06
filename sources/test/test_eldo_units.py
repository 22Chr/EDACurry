#!/usr/bin/env python3
"""Regression tests for the Eldo frontend and backend.

Covers issues #1, #2 and #3 of https://github.com/esd-univr/EDACurry, plus the
defects found while fixing them: analysis values truncated to int, analysis
directives dropped on output, CRLF files rejected, hierarchical node names
spinning forever, and a recovered syntax error crashing the process.

Unlike the other scripts in this directory, this one needs no input files: it
generates each netlist it parses. That keeps it runnable from a bare checkout,
since the circuit collections the issues referred to are not in the repository.
It also exits non-zero when a case fails, so it can be used as a gate.

Output is flushed per case on purpose: if a regression brings back a crash, the
process dies and only the already-flushed lines survive to show where.

Usage:
    PYTHONPATH=../build python3 test_eldo_units.py
"""

import os
import sys
import tempfile

import edacurry

# Eldo scale factors are case-insensitive, `meg` is the only multi-character one,
# and a suffix that is not a scale factor has to survive as the unit.
#
#   (netlist body, fragment expected in the emitted netlist, what it pins down)
CASES = [
    # -- Issue #1: `meg` is mega, and must not be read as the `m` it starts with.
    ("r1 1 2 1meg", "1e+06", "lowercase meg is mega (issue #1)"),
    ("r1 1 2 1MEG", "1e+06", "uppercase MEG is mega"),
    ("r1 1 2 1Meg", "1e+06", "mixed-case Meg is mega"),
    ("vin inp 0 sin(1.65 0.5 1meg)", "1e+06", "meg inside a function call (issue #1)"),
    # -- Issue #3: case must not change the meaning of a scale factor.
    ("r1 1 2 1m", "0.001", "lowercase m is milli"),
    ("r1 1 2 1M", "0.001", "uppercase M is milli, not mega (issue #3)"),
    ("c1 1 2 1p", "1e-12", "lowercase p is pico"),
    ("c1 1 2 1P", "1e-12", "uppercase P is pico, not peta (issue #3)"),
    # -- The rest of the Eldo scale factors, in both cases.
    ("r1 1 2 1T", "1e+12", "T is tera"),
    ("r1 1 2 1t", "1e+12", "t is tera"),
    ("r1 1 2 3G", "3e+09", "G is giga"),
    ("r1 1 2 2.2k", "2200", "k is kilo"),
    ("r1 1 2 2.2K", "2200", "K is kilo"),
    ("c1 1 2 100u", "0.0001", "u is micro"),
    ("c1 1 2 4.7n", "4.7e-09", "n is nano"),
    ("c1 1 2 10f", "1e-14", "f is femto"),
    # -- Suffixes that are not scale factors must be kept whole.
    ("r1 1 2 1kohm", "1000ohm", "a unit after a scale factor survives"),
    ("r1 1 2 1ohm", "1ohm", "a unit that is not a scale factor keeps its first letter"),
    ("i1 1 2 0.05A", "0.05A", "a one-letter unit that is not a scale factor is kept"),
    # -- Issue #2: comparison operators must not be swapped.
    ("e1 1 2 value = { if ((v(1))>(v(2)),v(1),v(2)) }", ") > (",
     "greater-than stays greater-than (issue #2)"),
    ("e1 1 2 value = { if ((v(1))<(v(2)),v(1),v(2)) }", ") < (",
     "less-than stays less-than"),
    ("e1 1 2 value = { if ((v(1))>=(v(2)),v(1),v(2)) }", ") >= (",
     "greater-or-equal stays greater-or-equal"),
    ("e1 1 2 value = { if ((v(1))<=(v(2)),v(1),v(2)) }", ") <= (",
     "less-or-equal stays less-or-equal"),
    # -- A hierarchical node name used to spin forever building its own name.
    ("r1 x1.n5 0 1k", "x1.n5", "a hierarchical node name terminates"),
    # -- Analysis values are physical quantities, so they must not be truncated to
    #    int: reading `1.5meg` as an integer stopped at the `1`.
    (".ac dec 15 200 1.5meg", "1.5e+06", "a decimal frequency is not truncated"),
    (".dc v1 0 1.5 0.1", ".dc v1 0 1.5 0.1", "dc sweep bounds keep their decimals"),
    (".dc temp -40.5 125.5 0.5", ".dc temp -40.5 125.5 0.5", "a negative decimal sweep survives"),
    # -- The backend listed the analyses it knew by hand and silently dropped the
    #    directive of every other one.
    (".op", ".op", "the op directive is emitted"),
    (".noise v(5) vin 10", ".noise", "the noise directive is emitted"),
    (".mc 100", ".mc 100", "the mc directive is emitted"),
    (".tran 1uS 200uS", ".tran 1e-06S 0.0002S", "the tran directive and its scale factors"),
]

# Cases that need control over the whole file rather than a single line.
# An expectation of None means the parse only has to survive: the input is invalid
# and the point is that it is reported rather than crashing the process.
#
#   (file content, fragment expected in the output or None, what it pins down)
FILES = [
    ("r1 1 2 1k\r\nc1 2 0 1p\r\n.end\r\n", "1000",
     "CRLF line endings parse, as written on Windows"),
    ("XERR 60 10 9 4 ERRAMP4_MC ; +  - OUT GND\n.end\n", None,
     "a recovered syntax error is reported, not a segfault"),
]


def emit(content):
    """Parse the given netlist text and return what the Eldo backend writes back."""
    handle, path = tempfile.mkstemp(suffix=".cir")
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(content.encode("utf-8"))
        return edacurry.write_eldo(edacurry.parse_eldo(path))
    finally:
        os.remove(path)


def check(content, expected, description, label):
    """Run one case. Returns None on success, or a failure tuple."""
    try:
        produced = emit(content)
    except Exception as error:
        if expected is None:
            # The input is invalid; a reported error is the correct outcome.
            print("ok    %-56s %s" % (label, description), flush=True)
            return None
        print("FAIL  %-56s %s" % (label, description), flush=True)
        return (label, expected, "%s: %s" % (type(error).__name__, error))
    if expected is None or expected in produced:
        print("ok    %-56s %s" % (label, description), flush=True)
        return None
    print("FAIL  %-56s %s" % (label, description), flush=True)
    return (label, expected, produced.strip())


def main():
    failures = []
    total = len(CASES) + len(FILES)

    for body, expected, description in CASES:
        outcome = check(body + "\n.end\n", expected, description, body)
        if outcome:
            failures.append(outcome)

    for content, expected, description in FILES:
        label = content.splitlines()[0] if content.splitlines() else "(empty)"
        outcome = check(content, expected, description, label)
        if outcome:
            failures.append(outcome)

    print("\n%d/%d cases passed." % (total - len(failures), total))
    for body, expected, produced in failures:
        print("\n  input    : %s" % body)
        print("  expected : %s" % expected)
        print("  produced : %s" % produced)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
