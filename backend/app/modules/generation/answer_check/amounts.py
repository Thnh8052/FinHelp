"""Locale-aware number scanner shared by QC, the profiler and Markdown helpers (no regex).

The backend's only amount scanner: a copy of archive/financial_parser_v1_3/amounts.py (the backend ships on its own and archive/
is frozen), used by answer_check/numbers.py. One addition: a scale suffix glued to the number ("$2,197M", "£5bn", "$40k", as
answers write them) no longer makes it part of a word.

`find_amounts(text, locale)` walks the text once and returns every number with its sign,
currency, percent flag and the separators it was printed with. Separator roles are decided per
number, and the document locale is only consulted when a number is genuinely ambiguous:

    1,234,567.89  -> 1234567.89   (both separators: the last one is the decimal mark)
    1.234.567,89  -> 1234567.89   (VAS)
    1.234.567     -> 1234567      (repeated mark = grouping)
    1,5 / 12.25   -> 1.5 / 12.25  (not followed by exactly three digits = decimal)
    1,234 / 1.234 -> locale: en -> 1234 / 1.234 ; vi -> 1.234 / 1234

Accounting negatives "(1,234)" and "$ (1,234)", a leading "-" or "−", currency symbols before
the number and "%" after it are recognised. Clause markers such as "(1) Includes ..." are not
numbers; a bare "(5)" elsewhere is kept but flagged `is_reference`, because in PDF text a footnote
reference on its own line and a small negative table value look identical. A number glued to letters ("3M", "4G", "10K") is ignored, except the "FY2025" form.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import List, Optional, Tuple

CURRENCY_SYMBOLS = "$₫€£¥"
SCALE_SUFFIXES = ("bn", "mn", "M", "B", "K", "m", "k")
MINUS_SIGNS = "-−"
EN = "en"
VI = "vi"
GROUP_SPACES = "    "  # space, no-break space, thin space, narrow no-break space: how financial statements group thousands ("89 913")


def locale_for_language(language: Optional[str]) -> str:
    """Number locale for a page language code ("vi" -> VAS separators, anything else -> en)."""
    return VI if (language or "").lower() == VI else EN


def _is_digit(ch: str) -> bool:
    return "0" <= ch <= "9"


@dataclass(frozen=True)
class Amount:
    raw: str            # exact span in the text, including sign / parentheses / currency / %
    digits: str         # the number as printed, e.g. "1,234.5"
    normalized: str     # canonical value without currency / %, e.g. "-1234.5"
    start: int
    end: int
    negative: bool = False
    has_grouping: bool = False
    has_decimal: bool = False
    is_percent: bool = False
    currency: str = ""
    is_reference: bool = False  # "(5)": a footnote reference or a tiny negative - cannot be told apart


    @property
    def is_plain_integer(self) -> bool:
        """Printed as bare digits: no separator, sign, currency or percent."""
        return not (self.has_grouping or self.has_decimal or self.negative or self.is_percent or self.currency)

    @property
    def is_year(self) -> bool:
        """'2015' is a year; '2,015', '$2015' and '(2015)' as an amount are not."""
        return self.is_plain_integer and len(self.digits) == 4 and 1900 <= int(self.digits) <= 2099

    @property
    def value(self) -> Optional[Decimal]:
        try:
            return Decimal(self.normalized)
        except InvalidOperation:
            return None


def _interpret(run: str, locale: str) -> Tuple[str, bool, bool]:
    """(unsigned canonical digits, has_grouping, has_decimal) for a run like '1.234.567,89'."""
    marks = [i for i, ch in enumerate(run) if ch in ",."]
    if not marks:
        return run, False, False
    kinds = {run[i] for i in marks}

    def grouped(text: str, mark: str) -> bool:
        parts = text.split(mark)
        return 1 <= len(parts[0]) <= 3 and all(len(part) == 3 for part in parts[1:])

    if len(kinds) == 2:
        decimal_mark = run[marks[-1]]
        group_mark = "," if decimal_mark == "." else "."
        integer, fraction = run[: marks[-1]], run[marks[-1] + 1:]
        if decimal_mark not in integer and grouped(integer, group_mark):
            return integer.replace(group_mark, "") + "." + fraction, True, True
        return run.replace(",", ""), "," in run, "." in run  # malformed: keep the legacy reading

    mark = kinds.pop()
    if len(marks) > 1:
        if grouped(run, mark):
            return run.replace(mark, ""), True, False
        return run.replace(",", ""), mark == ",", mark == "."  # malformed: keep the legacy reading

    integer, fraction = run.split(mark)
    if len(fraction) == 3 and 1 <= len(integer) <= 3 and integer != "0":
        # Ambiguous "1,234" / "1.234": the locale decides which mark groups thousands.
        is_group = (mark == ",") if locale == EN else (mark == ".")
        if is_group:
            return integer + fraction, True, False
    return integer + "." + fraction, False, True


def _skip_space_left(text: str, index: int) -> int:
    """Skip spaces to the left on the same line only: a "$" or "(" on the previous line belongs
    to another cell (PDF text puts the "$" of a table cell and its value on separate lines)."""
    while index >= 0 and text[index] in " 	 ":
        index -= 1
    return index


def _skip_space_right(text: str, index: int) -> int:
    while index < len(text) and text[index] in " \t\n ":
        index += 1
    return index


def _space_groups(text: str, end: int) -> int:
    """End of the thousands groups written with a space after a number of 1-3 digits ("89 913", "1 234 567", "89 913,5"), else `end`.
    A group is a single space and exactly three digits that no digit follows, so "3 650 3 484" stays two numbers and "2025 12" is not touched."""
    length = len(text)
    while end + 4 <= length and text[end] in GROUP_SPACES and text[end + 1:end + 4].isdigit() and not (end + 4 < length and _is_digit(text[end + 4])):
        end += 4
    if end + 1 < length and text[end] in ",." and _is_digit(text[end + 1]) and end >= 4 and text[end - 4] in GROUP_SPACES:
        end += 1
        while end < length and _is_digit(text[end]):
            end += 1
    return end


def find_amounts(text: str, locale: str = EN, space_groups: bool = False) -> List[Amount]:
    """Every number in `text`, left to right. `space_groups`: read "89 913" as one number 89913 (default: two numbers 89 and 913, the
    way the other scanners of the project read it)."""
    amounts: List[Amount] = []
    length = len(text)
    index = 0
    while index < length:
        if not _is_digit(text[index]):
            index += 1
            continue
        start = index
        end = index
        while end < length and (
            _is_digit(text[end])
            or (text[end] in ",." and end + 1 < length and _is_digit(text[end + 1]))
        ):
            end += 1
        if space_groups and end - start <= 3 and text[start:end].isdigit():
            end = _space_groups(text, end)
        index = end

        before = text[start - 1] if start > 0 else ""
        after = text[end] if end < length else ""
        glued_fy = text[max(0, start - 2):start] == "FY" and (start < 3 or not text[start - 3].isalnum())
        scale_suffix = any(text.startswith(s, end) and not (end + len(s) < length and text[end + len(s)].isalnum()) for s in SCALE_SUFFIXES)
        if (before and (before.isalnum() or before in "_.") and not glued_fy) or (after and (after.isalnum() or after == "_") and not scale_suffix):
            while index < length and (text[index].isalnum() or text[index] == "_"):
                index += 1  # part of a word such as "3M", "4G", "A1B2"
            continue

        run = text[start:end]
        spaced = any(ch in GROUP_SPACES for ch in run)
        if spaced:
            run = "".join(ch for ch in run if ch not in GROUP_SPACES)
        canonical, has_grouping, has_decimal = _interpret(run, locale)
        has_grouping = has_grouping or spaced
        span_start, span_end = start, end
        negative = False
        currency = ""
        is_reference = False

        # Left context: "-1,234", "$1,234", "$ (1,234)", "($1,234)", "(1,234)".
        left = start - 1
        # A dash on both sides ("-1-", a page number decoration) is not a sign, nor is one glued to
        # a preceding number or percent ("2020-2022", "0.03%-5.75%": a range).
        if (left >= 0 and text[left] in MINUS_SIGNS
                and (left == 0 or not (text[left - 1].isalnum() or text[left - 1] == "%"))
                and not (after and after in MINUS_SIGNS + "–—")):
            negative, span_start, left = True, left, left - 1
        probe = _skip_space_left(text, left)
        if probe >= 0 and text[probe] in CURRENCY_SYMBOLS:
            currency, span_start = text[probe], probe
            probe = _skip_space_left(text, probe - 1)
        open_paren = probe if probe >= 0 and text[probe] == "(" else -1
        if open_paren >= 0 and not currency:
            outer = _skip_space_left(text, open_paren - 1)
            if outer >= 0 and text[outer] in CURRENCY_SYMBOLS:
                currency = text[outer]

        # Right context: "%" and the closing parenthesis.
        right = _skip_space_right(text, end) if end < length and text[end] in "  " else end
        is_percent = right < length and text[right] == "%"
        if is_percent:
            span_end = right + 1
            right = right + 1
        close_paren = -1
        if open_paren >= 0:
            probe_right = _skip_space_right(text, right)
            if probe_right < length and text[probe_right] == ")":
                close_paren = probe_right

        if open_paren >= 0 and close_paren >= 0:
            integer_digits = canonical.split(".")[0]
            marker_before = open_paren == 0 or text[open_paren - 1] in " \t\n;.,"
            follow = close_paren + 1
            while follow < length and text[follow] in " 	 ":
                follow += 1  # same line only, as in "(1) Includes ..."
            follower = text[follow] if follow < length else ""
            followed_by_text = bool(follower) and (follower.isalpha() or follower in ":;")
            if (not has_grouping and not has_decimal and not currency and not negative and len(run) <= 2
                    and marker_before and followed_by_text):
                index = close_paren + 1
                continue  # clause marker: "(1) Includes ...", "(12): ..."
            # Accounting negative when the digits themselves look like an amount. The currency symbol
            # is deliberately ignored here: whether "$" lands in the same cell as "(26)" depends on the
            # engine, and the canonical value must not. Bare 1-2 digit values such as "(5)" may be
            # footnote references, 4+ digit ones such as "(2020)" years: they keep the plain reading.
            parenthesised = True
            if has_grouping or has_decimal or len(integer_digits) == 3:
                negative = True
            elif len(integer_digits) <= 2 and not currency:
                is_reference = True
            else:
                parenthesised = False  # "(2020)": a plain number that happens to sit in parentheses
            if parenthesised:
                # The span covers the parentheses and a "$" before them: "$ (1,234)" is one token.
                span_start = min(span_start, open_paren)
                outer = _skip_space_left(text, open_paren - 1)
                if currency and outer >= 0 and text[outer] == currency:
                    span_start = min(span_start, outer)
                span_end = max(span_end, close_paren + 1)
                index = max(index, close_paren + 1)

        normalized = ("-" if negative else "") + canonical
        amounts.append(Amount(
            raw=text[span_start:span_end], digits=run, normalized=normalized, start=span_start, end=span_end,
            negative=negative, has_grouping=has_grouping, has_decimal=has_decimal,
            is_percent=is_percent, currency=currency, is_reference=is_reference,
        ))
    return amounts


def parse_amount(token: str, locale: str = EN) -> Optional[Amount]:
    """The single number that makes up the whole of `token` (ignoring outer spaces), else None."""
    text = token.strip()
    found = find_amounts(text, locale)
    if len(found) != 1:
        return None
    amount = found[0]
    return amount if amount.start == 0 and amount.end == len(text) else None
