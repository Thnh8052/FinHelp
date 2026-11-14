"""The calculations an answer writes out ("1,185 + 454 = 1,639", "16,830 ÷ 2,694 = 6.25x", "(a + b) ÷ c = d ÷ c = e"), read and
evaluated by code (plan v2, H1). Only numbers, + − × ÷, brackets and percents are evaluated, through Python's own parser: nothing the
model writes is ever executed.

written_results() the numbers that the answer's correct written calculations establish from trusted numbers (rule B of numbers.py).

It only reads and verifies; it never rewrites a result. A rewrite (calculations.fix) existed until 14/11: measured on 317 stored answers it acted 0 times
in 247 answers written with the model's thinking on (325 written steps), 7 times in 70 answers written with thinking off, and it changed right figures into wrong
ones on 2 of 27 new answers (a percent closed by a bracket, "EPS = 2.09 vs 2.55 = -18.0%"). A wrong written result is now reported by the number check
("unverified") and goes to the one repair. experiments/scripts/rag_improvement/_calculations_with_rewrite_14_11.py is the module as it was, for the measurement.
Rule B lets no planted wrong result through, and without it 11 more answers of 317 are flagged (10 of 247 with thinking on).
"""
import ast
import operator
import re
from collections import Counter
from typing import List, Optional, Set, Tuple

from app.modules.generation.answer_check.amounts import EN, GROUP_SPACES, _interpret

# Numbers as answers print them. English: "1,185", "0.8937". A Vietnamese answer may write "11 100,6" (a space groups thousands, a comma is the
# decimal mark) or "11.100,6"; amounts._interpret tells the marks apart, and only "1,185" / "1.185" (one mark, three digits) need the answer's own
# habit (locale_of). A mark at the end ("1,185, then") is punctuation, not part of the number.
VI = "vi"
GROUP = f"[{GROUP_SPACES}]"
TOKEN = rf"(?:\d{{1,3}}(?:{GROUP}\d{{3}})+(?!\d)(?:[.,]\d+)?|\d(?:[.,]?\d)*)"
NUMTOK = re.compile(TOKEN)
NUM = rf"(?:\*\*)?\(*[-−]?\$?{TOKEN}%?\)*…?(?:\*\*)?"  # bold included ("**6.91x**", "0.6836…"): Markdown bold is not multiplication
EXPR = rf"{NUM}(?:\s*[-+−–×x*/÷]\s*{NUM})*"
SEP = r"(?:=|≈|→)"  # "1.0150 → 101.0%" states a result as "=" does
# a chain joined by "=", "≈" or "→": "(1,185 + 454) ÷ 1,513 = 1,639 ÷ 1,513 = 1.08"; never inside a date (4/6/2019) or a number
CHAIN = re.compile(rf"(?<![\w/.,])({EXPR}(?:\s*{SEP}\s*{EXPR})+)(?![\d/])")
SINGLE = re.compile(rf"(?:\*\*)?\(*[-−]?\$?({TOKEN})%?\)*…?(?:\*\*)?")
CITATION = re.compile(r"\[\d+(?:\s*[,;]\s*\d+)*\]")  # "[1,2]" is not a number with a decimal comma
# words before a "calculation" that is really a reference ("excerpt 4/6)", "page 3-4") and an exponent "^(1/2)"
REFERENCE = re.compile(r"(?:excerpts?|pages?|notes?|items?|\^)\s*$", re.I)
CONSTANTS = {365.0, 360.0, 100.0, 52.0, 53.0}  # days, weeks, percent: standard inputs no excerpt prints (numbers up to 12 are always allowed)
SMALL = 12
OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.USub: operator.neg}


def _eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return float(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in OPS:
        return OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in OPS:
        return OPS[type(node.op)](_eval(node.operand))
    raise ValueError("not arithmetic")


def canon(token: str, locale: str = EN) -> Optional[str]:
    """The number a printed token stands for, as Python writes it ("11 100,6" -> "11100.6"), or None when it is not a number ("31.12.2018")."""
    text = _interpret("".join(ch for ch in token if ch not in GROUP_SPACES), locale)[0]
    try:
        float(text)
    except ValueError:
        return None
    return text


def locale_of(text: str) -> str:
    """"vi" when the answer writes its decimals with a comma ("10,63", "0,8937", "11 100,6") more often than with a point, else "en".
    Only numbers that can be read one way vote: "1,185" and "1.185" say nothing."""
    votes: Counter = Counter()
    for token in NUMTOK.findall(CITATION.sub(" ", text.split("<answer_meta>")[0])):
        run = "".join(ch for ch in token if ch not in GROUP_SPACES)
        reading = _interpret(run, EN)
        if reading[2] and reading == _interpret(run, VI) and canon(token) is not None:
            votes[run[max(run.rfind(","), run.rfind("."))]] += 1
    return VI if votes[","] > votes["."] else EN


def readings_of(text: str) -> Tuple[str, ...]:
    """The ways to read the numbers of an answer's calculations. An English-style answer has one. An answer with decimal commas has two: its own,
    and the report's ("12,421" copied as printed next to a result "11 100,6"); a step counts as right when one of them makes it right."""
    return (EN,) if locale_of(text) == EN else (VI, EN)


def evaluate(expression: str, locale: str = EN) -> Optional[Tuple[float, bool]]:
    """(value, whether the expression used percent inputs) or None. Thousands marks dropped; "12.5%" read as 12.5; "(33)" is −33."""
    expr = expression.replace("**", "").replace("…", "").replace("$", "")
    expr = NUMTOK.sub(lambda m: canon(m.group(0), locale) or m.group(0), expr)
    expr = expr.replace("−", "-").replace("–", "-").replace("×", "*").replace("÷", "/")
    expr = re.sub(r"\((\d+(?:\.\d+)?)\)", r"(-\1)", expr)  # accounting notation: "337 − (33) = 370"
    expr = re.sub(r"(?<=\d)\s*x\s*(?=[\d(])", "*", expr)
    has_pct = "%" in expr
    expr = expr.replace("%", "")
    if expr.count("(") != expr.count(")"):
        expr = expr.strip("()")
    try:
        return _eval(ast.parse(expr, mode="eval").body), has_pct
    except (SyntaxError, ValueError, ZeroDivisionError, OverflowError):
        return None


def value_of(token: str, locale: str = EN) -> float:
    """NaN for a token that is not a number: it equals nothing, so its step is never trusted."""
    return float(canon(token, locale) or "nan")


def steps(text: str) -> List[Tuple[str, str, int]]:
    """[(left, right, start of right in text)] of every written step; the machine block (answer_meta) is not read."""
    body = text.split("<answer_meta>")[0]
    out = []
    for m in CHAIN.finditer(body):
        if REFERENCE.search(body[max(0, m.start() - 12):m.start()]):
            continue
        chain, base = m.group(1), m.start(1)
        pos, pieces = 0, []
        for part in re.split(r"(\s*(?:=|≈|→)\s*)", chain):
            pieces.append((part, base + pos))
            pos += len(part)
        exprs = pieces[::2]
        for (left, _), (right, rstart) in zip(exprs, exprs[1:]):
            out.append((left.strip(), right.strip(), rstart + (len(right) - len(right.lstrip()))))
    return out


def is_calc(left: str) -> bool:
    """A written calculation: two or more numbers joined by an operator ("554 ÷ 10,800"). A lone number is not one: "2.09 vs 2.55 = −18.0%" is a comparison."""
    return len(NUMTOK.findall(left)) >= 2 and bool(re.search(r"\d\s*[-+−–×x*/÷]\s*\(*[-−]?\$?\d", left.replace("**", "")))


def holds(left: str, right: str, locale: str = EN) -> bool:
    """Whether the printed result is right for its expression: within the rounding of the digits printed, a percent also as 100 x the ratio. False when it is wrong
    or when either side cannot be read."""
    a, b = evaluate(left, locale), evaluate(right, locale)
    if a is None or b is None:
        return False
    value, printed = a[0], b[0]
    single = SINGLE.fullmatch(right)
    if not single:  # "a + b ÷ c = d ÷ c": an equal step (its numbers become trusted)
        return abs(value - printed) <= 0.002 * abs(printed) + 1e-9
    decimals = len((canon(single.group(1), locale) or "").partition(".")[2])
    tol = max(0.5 * 10 ** -decimals + 1e-9, 0.002 * abs(printed))
    # "**5.1%**": the bold markers are not part of the unit; "(… = 77.8%)": nor is a closing bracket; "× 100" already makes a percent
    pct = right.replace("**", "").rstrip("…").rstrip(") ").endswith("%") and "%" not in left and not re.search(r"(?:[×x]|(?<!\*)\*(?!\*))\s*100\b", left)
    return any(abs(abs(c) - abs(printed)) <= tol for c in [value] + ([value * 100] if pct else []))


def written_results(text: str, ok: Set[float]) -> Set[float]:
    """Rule B: `ok` grown with the numbers the answer's own written calculations establish from numbers in `ok`: the printed result of a step
    that checks ("x ÷ y = z" with z right), and every number of a right side that is itself an expression equal to the left ("(1,185 + 0 + 454
    + 33) ÷ 1,513 = 1,672 ÷ 1,513": 1,672 is the written intermediate). Nothing is searched: only what the answer writes."""
    ok = set(ok)

    def trusted(expr, loc):
        return all(abs(v) <= SMALL or any(abs(abs(v) - k) <= 0.005 for k in ok) for v in (value_of(t, loc) for t in NUMTOK.findall(expr)))

    found = steps(text)
    readings = readings_of(text)
    grown = True
    while grown:
        grown = False
        for left, right, _ in found:
            for loc in readings:
                if not is_calc(left) or not trusted(left, loc) or not holds(left, right, loc):
                    continue
                new = {abs(value_of(t, loc)) for t in NUMTOK.findall(right)} - ok
                if new:
                    ok |= new
                    grown = True
    return ok
