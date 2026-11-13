"""The calculations an answer writes out ("1,185 + 454 = 1,639", "16,830 ÷ 2,694 = 6.25x", "(a + b) ÷ c = d ÷ c = e"), read and
evaluated by code (plan v2, H1). Only numbers, + − × ÷, brackets and percents are evaluated, through Python's own parser: nothing the
model writes is ever executed.

fix()             corrects a printed result that is wrong when every number of its expression is trusted (printed in the excerpts,
                  a standard constant, or the result of another correct step), everywhere the wrong value appears in the answer.
written_results() the numbers that the answer's correct written calculations establish from trusted numbers (rule B of numbers.py).

Measured in experiments/ before this module (plan v2 sections 8.6 and 8.10, t1_calc.py and numcheck_v2.py): on about 340 stored answers
no correct figure was changed; 224 of 226 planted wrong results were restored; rule B lets no planted wrong result through.
"""
import ast
import operator
import re
from typing import Dict, List, Optional, Set, Tuple

# a number as answers print it, bold included ("**6.91x**", "0.6836…"): Markdown bold is not multiplication
NUM = r"(?:\*\*)?\(*[-−]?\$?\d[\d,]*(?:\.\d+)?%?\)*…?(?:\*\*)?"
EXPR = rf"{NUM}(?:\s*[-+−–×x*/÷]\s*{NUM})*"
SEP = r"(?:=|≈|→)"  # "1.0150 → 101.0%" states a result as "=" does
# a chain joined by "=", "≈" or "→": "(1,185 + 454) ÷ 1,513 = 1,639 ÷ 1,513 = 1.08"; never inside a date (4/6/2019) or a number
CHAIN = re.compile(rf"(?<![\w/.,])({EXPR}(?:\s*{SEP}\s*{EXPR})+)(?![\d/])")
TOKEN = r"\d(?:[\d,]*\d)?(?:\.\d+)?"  # a trailing comma is punctuation, not part of the number
NUMTOK = re.compile(TOKEN)
SINGLE = re.compile(r"(?:\*\*)?\(*[-−]?\$?\d[\d,]*(?:\.(\d+))?%?\)*…?(?:\*\*)?")
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


def evaluate(expression: str) -> Optional[Tuple[float, bool]]:
    """(value, whether the expression used percent inputs) or None. Thousands commas dropped; "12.5%" read as 12.5; "(33)" is −33."""
    expr = expression.replace("**", "").replace("…", "").replace("$", "").replace(",", "")
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


def value_of(token: str) -> float:
    return float(token.replace(",", ""))


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


def is_calc(left: str, right: str = "") -> bool:
    """A written calculation, or a ratio turned into a percent ("1.0150 → 101.5%": the result must be 100 x the ratio)."""
    if len(NUMTOK.findall(left)) >= 2 and re.search(r"\d\s*[-+−–×x*/÷]\s*\(*[-−]?\$?\d", left.replace("**", "")):
        return True
    plain = left.replace("**", "").rstrip("…").strip()
    return (bool(right) and bool(re.fullmatch(r"[-−]?\d+\.\d+", plain)) and abs(float(plain.replace("−", "-"))) < 10
            and right.replace("**", "").rstrip("…").endswith("%"))


def target(left: str, right: str):
    """"ok" when the printed result is right, (value it should have, decimals) when it is wrong, None when the step cannot be read."""
    a, b = evaluate(left), evaluate(right)
    if a is None or b is None:
        return None
    value, printed = a[0], b[0]
    single = SINGLE.fullmatch(right)
    if not single:  # "a + b ÷ c = d ÷ c": an equal step checks out (its numbers become trusted); a wrong one is never rewritten here
        return "ok" if abs(value - printed) <= 0.002 * abs(printed) + 1e-9 else None
    decimals = len(single.group(1) or "")
    tol = max(0.5 * 10 ** -decimals + 1e-9, 0.002 * abs(printed))
    # "**5.1%**": the bold markers are not part of the unit; "× 100" already makes a percent
    pct = right.replace("**", "").rstrip("…").endswith("%") and "%" not in left and not re.search(r"(?:[×x]|(?<!\*)\*(?!\*))\s*100\b", left)
    candidates = [value] + ([value * 100] if pct else [])
    if any(abs(abs(c) - abs(printed)) <= tol for c in candidates):
        return "ok"
    best = min(candidates, key=lambda c: abs(abs(c) - abs(printed)))  # the reading (ratio or percent) closest to what was printed
    return (abs(best) if printed >= 0 else -abs(best)), decimals


def styled(value: float, like: str, decimals: int) -> str:
    """`value` written as `like` is: same decimals, thousands commas when `like` has them (or the number is long), the same minus sign."""
    number = re.search(TOKEN, like).group(0)
    commas = "," in number or abs(value) >= 10000
    text = f"{abs(value):,.{decimals}f}" if commas else f"{abs(value):.{decimals}f}"
    neg = "−" if "−" in like else "-"
    return (neg if value < 0 and not re.match(r"\(*[-−]", like) else "") + text


def _known(expr: str, trusted: Set[float]) -> bool:
    return all(any(abs(value_of(t) - x) <= 0.5 for x in trusted) or value_of(t) <= SMALL or value_of(t) in CONSTANTS for t in NUMTOK.findall(expr))


def fix(text: str, trusted: Set[float], rounds: int = 5) -> Tuple[str, List[Dict]]:
    """(corrected text, [{"written", "was", "now", "only_here"}]). `trusted`: the excerpt numbers at every scale a printed figure may use."""
    fixes: List[Dict] = []
    for _ in range(rounds):
        found = steps(text)
        known = set(trusted)
        for _ in range(3):  # numbers of correct steps built from trusted numbers become trusted
            for left, right, _ in found:
                if is_calc(left, right) and _known(left, known) and target(left, right) == "ok":
                    known |= {value_of(t) for t in NUMTOK.findall(left + " " + right)}
        change = None
        for left, right, start in found:
            if not is_calc(left, right) or not _known(left, known):
                continue
            t = target(left, right)
            if t is None or t == "ok":
                continue
            value, decimals = t
            token = re.search(TOKEN, right).group(0)
            change = (left, right, start + right.index(token), token, styled(value, right, decimals))
            break
        if not change:
            break
        left, right, at, token, new = change
        # the same figure printed as the result of another correct step: elsewhere it may be that other figure, so only this step changes
        ambiguous = any(r2 != right or s2 != at - right.index(token) for l2, r2, s2 in found
                        if is_calc(l2) and target(l2, r2) == "ok" and re.search(TOKEN, r2) and re.search(TOKEN, r2).group(0) == token)
        if ambiguous:
            text = text[:at] + new + text[at + len(token):]
        else:
            text = re.sub(rf"(?<![\d.,]){re.escape(token)}(?![\d]|[.,]\d)", new, text)
        fixes.append({"written": f"{left} = {right}", "was": token, "now": new, "only_here": ambiguous})
    return text, fixes


def written_results(text: str, ok: Set[float]) -> Set[float]:
    """Rule B: `ok` grown with the numbers the answer's own written calculations establish from numbers in `ok`: the printed result of a step
    that checks ("x ÷ y = z" with z right), and every number of a right side that is itself an expression equal to the left ("(1,185 + 0 + 454
    + 33) ÷ 1,513 = 1,672 ÷ 1,513": 1,672 is the written intermediate). Nothing is searched: only what the answer writes."""
    ok = set(ok)

    def trusted(expr):
        return all(abs(value_of(t)) <= SMALL or any(abs(abs(value_of(t)) - k) <= 0.005 for k in ok) for t in NUMTOK.findall(expr))

    found = steps(text)
    grown = True
    while grown:
        grown = False
        for left, right, _ in found:
            if not is_calc(left) or not trusted(left) or target(left, right) != "ok":
                continue
            new = {abs(value_of(t)) for t in NUMTOK.findall(right)} - ok
            if new:
                ok |= new
                grown = True
    return ok
