"""Shared "official classroom roll-call" ordering ("Extending the
attendance system" spec, Part 11 — Student Ordering).

Every place students are displayed — panel rosters, Student Management,
live attendance monitoring, session review, attendance reports, and Excel
exports — sorts by this same key, so faculty always see the exact order
they'd expect from a physical attendance register.

Roll numbers are stored as free text (`Student.roll_number`, nullable —
not every student necessarily has one on file), so a plain string sort
would put "10" before "2". This key treats a roll number as numeric
whenever it parses as one ("2" < "10"), falls back to a case-insensitive
string comparison for anything that doesn't parse (e.g. "A12"), and always
sorts a missing roll number last — never first, never silently dropped.
"""
from __future__ import annotations


def roll_number_sort_key(roll_number: str | None) -> tuple[int, float | str]:
    """Sort key for a single roll number. Use as `key=` in `sorted()`.

    Returns a `(tier, value)` tuple: tier 0 (numeric) sorts before tier 1
    (non-numeric text) sorts before tier 2 (missing) — so numeric roll
    numbers are ordered correctly among themselves (2 before 10), any
    non-numeric roll numbers come after them in alphabetical order, and
    students with no roll number on file are always listed last rather
    than interleaved or erroring.
    """
    if roll_number is None:
        return (2, "")

    stripped = roll_number.strip()
    if not stripped:
        return (2, "")

    try:
        return (0, float(stripped))
    except ValueError:
        return (1, stripped.lower())


def sort_by_roll_number(items, roll_number_getter):
    """Convenience wrapper: `sorted(items, key=lambda x: roll_number_sort_key(roll_number_getter(x)))`."""
    return sorted(items, key=lambda item: roll_number_sort_key(roll_number_getter(item)))
