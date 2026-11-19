"""The code gate: the first step of every chat question, before any model (guard, planner, follow-up rewrite, answer) reads it. Standard library only.

Plan: docs/VERSION_4/GUARDRAILS_REDESIGN_2026-11-19.md (step 2). Code checks the STRUCTURE of a message, the LLM guard its MEANING. The red-team of
19/11 (experiments/security_redteam) found the guard sound on plain wording (47 of 47 prompt attacks) but blind to disguised text: hidden characters,
look-alike letters, base64, fake prompt tags. The measured prototype (code_gate.py there) refused 23 of 24 attacks on the prompt and 0 of 1,249
legitimate questions (FinanceBench, name matching, follow-ups, dialogs, guard cases, gold v2).

screen(message) -> Gate:
  clean    what every model receives and what is stored: the message without invisible characters (NFC). Never the scan copy (OWASP: screening
           a cleaned copy while forwarding the original lets hidden text reach the model).
  scan     a copy for matching only: NFKC, look-alike Cyrillic/Greek letters read as Latin, digits inside words read as letters (1gn0r3), letters
           split apart joined again (s y s t e m), base64/hex blobs decoded and appended.
  signals  disguises found that are not refused on their own (hidden, leet, spaced, typo): guard.classify turns such a message away when its
           call fails (SIGNALS), instead of letting it through.
  action   "" or "refuse_instruction"; rule: why (hidden, structure, assistant, disguised).
"""
import base64
import binascii
import re
import unicodedata
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import List

from app.modules.query_router.input_policy import _DAN, _INJECTION, _PROMPT_ATTACK, unaccented

# The disguises the gate found in the message being answered (read by guard.classify when its call fails)
SIGNALS: ContextVar[List[str]] = ContextVar("gate_signals", default=[])

# ---------------------------------------------------------------- invisible characters
_TAGS = range(0xE0000, 0xE0080)  # Unicode tags: invisible copies of ASCII ("ASCII smuggling")
_VS = frozenset(range(0xFE00, 0xFE10)) | frozenset(range(0xE0100, 0xE01F0))  # variation selectors: 256 of them carry one byte each ("emoji smuggling")
_FLAG = re.compile("\U0001F3F4[\U000E0061-\U000E007A]+\U000E007F")  # the only honest use of tags: subdivision flags (England, Scotland, Wales)
_HARMLESS = {"‍", "­"}  # the joiner inside emoji, the soft hyphen of text copied from a web page: removed, not a signal


def is_hidden(ch: str) -> bool:
    cp = ord(ch)
    return unicodedata.category(ch) == "Cf" or cp in _TAGS or cp in _VS


def _smuggled(text: str) -> bool:
    """Text written in invisible characters: tags outside a flag, or variation selectors one after another (an emoji takes at most one)."""
    if any(ord(c) in _TAGS for c in _FLAG.sub("", text)):
        return True
    return any(ord(a) in _VS and ord(b) in _VS for a, b in zip(text, text[1:]))


# ---------------------------------------------------------------- disguised letters and encodings
# The Cyrillic and Greek letters drawn like Latin ones (the ones used in practice; Unicode UTS #39 lists more)
_CONFUSABLE = str.maketrans("аеорсухіјѕԁԛԝАВЕКМНОРСТХІЈЅοαυνκιτΑΒΕΖΗΙΚΜΝΟΡΤΥΧ", "aeopcyxijsdqwABEKMHOPCTXIJSoauvkitABEZHIKMNOPTYX")
_LEET = str.maketrans("013457@$", "oieastas")
_WORD = re.compile(r"\w+")
_MIXED = re.compile(r"[A-Za-z]")
_OTHER_SCRIPT = re.compile(r"[Ͱ-ϿЀ-ӿ]")
_PERIOD_OR_TICKER = re.compile(r"(?i)(?:fy|cy|q|h)?\d+(?:[a-z]{1,2}|q\d|h\d)?|\d+(?:st|nd|rd|th|s|k|m|b|bn|x)")  # FY2023Q1, Q4, 3M, 10K, 2nd
# Letters split apart, joined word by word: "s.y.s.t.e.m" (dots, dashes, underscores inside a word) and "s y s t e m" (single spaces). One pattern
# for both joined "r.e.v.e.a.l y.o.u.r p.r.o.m.p.t" into one word "revealyourprompt" (P1 20/11)
_DOTTED = re.compile(r"\b(?:\w[.\-_]){2,}\w\b")
_SPACED = re.compile(r"\b(?:\w ){3,}\w\b")
_B64 = re.compile(r"(?<![A-Za-z0-9+/=])[A-Za-z0-9+/]{20,}={0,2}(?![A-Za-z0-9+/=])")
_HEX = re.compile(r"\b(?:[0-9a-fA-F]{2}[\s:]?){16,}\b")
# Attack words read with typos ("ignroe", "isntructions"): same first and last letter, the same letters in between in another order
_KEYS = ("ignore", "instructions", "previous", "system", "prompt", "reveal", "bypass", "override", "disregard", "jailbreak")


def _typo_of(word: str) -> str:
    w = word.lower()
    return next((k for k in _KEYS if len(w) == len(k) and w != k and w[0] == k[0] and w[-1] == k[-1] and sorted(w[1:-1]) == sorted(k[1:-1])), "")


def _decoded(text: str) -> List[str]:
    """Readable text (3 words or more) hidden in a base64 or hex blob: no finance question carries one."""
    out = []
    for blob in _B64.findall(text):
        if not (re.search(r"[A-Z]", blob) and re.search(r"[a-z]", blob)):
            continue  # an id or a column of digits, not base64 of text
        try:
            raw = base64.b64decode(blob + "=" * (-len(blob) % 4)).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError, ValueError):
            continue
        if len(re.findall(r"[^\W\d_]{2,}", raw)) >= 3 and sum(c.isprintable() for c in raw) > 0.95 * len(raw):
            out.append(raw)
    for blob in _HEX.findall(text):
        try:
            raw = bytes.fromhex(re.sub(r"[\s:]", "", blob)).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            continue
        if len(re.findall(r"[^\W\d_]{2,}", raw)) >= 3:
            out.append(raw)
    return out


# ---------------------------------------------------------------- structure no finance question needs
_ROLE_TAG = re.compile(r"<\s*/?\s*(system|user|assistant|developer|instructions?)\s*>|<\|\s*(im_start|im_end|system|endoftext)\s*\|>|\[/?INST\]|\"\"\"|"
                       r"```\s*(system|prompt)|^\s*#{0,3}\s*(system|assistant|developer)\s*(message|prompt)?\s*:", re.I | re.M)
_PAYLOAD_SPLIT = re.compile(r"\b\w{1,10}\s*=\s*['\"][^'\"]{3,}['\"].{0,120}?\b\w{1,10}\s*\+\s*\w{1,10}\b", re.S)

# A message aimed at the assistant's own setup that input_policy._PROMPT_ATTACK misses. Each branch needs the assistant as the object ("your",
# "you were given", "của bạn", "cho bạn") or a whole-context phrase ("everything above this line"), so a report's own "rules" or "guidance" never match.
ASSISTANT_ATTACK = re.compile(
    r"\b(your|you were|you've been|you have been|you are)\b[^.?!\n]{0,40}\b(instructions?|rules|guidelines|prompt|configuration|config|setup|set-up|directives?|"
    r"system message|initial message|role definition|guardrails|policies)\b|"
    r"\b(instructions?|rules|guidelines|prompt|configuration|text|message)\b[^.?!\n]{0,40}\b(you (were|are|have been) (given|told|set up|configured|programmed|trained)|"
    r"(that|which) (defines|sets up|configures) (your|you))\b|"
    r"\b(everything|all|the text|the words|the content|whatever is)\b[^.?!\n]{0,15}\b(above|before) (this|that|my) (line|message|sentence|point)\b|"
    # role-play counts when the assistant is the one asked to change ("pretend you are", "role-play: you're"); "pretend I'm new to finance", "let's play
    # a game: guess the segment" and a plant's "maintenance mode" are questions (P1 20/11, experiments/security_redteam/REPORT_P1_2026-11-20.md)
    r"\b(developer|debug|god|sudo|unrestricted|jailbreak|dan) mode\b|\b(developer|admin|system) override\b|"
    r"\b(pretend|imagine|roleplay|role-play|role play)\b[^.?!\n]{0,20}\byou(?:'re|\s+are|\s+have|\s+had|\s+were)\b|"
    r"\b(you are now|from now on you are|act as if you (have|had) no)\b|"
    r"\b(everything|all|whatever|what)\b[^.?!\n]{0,20}\byou (were|have been|got) (told|given|instructed)\b|"
    r"\b(grandma|grandmother)\b[^.?!\n]{0,80}\b(read|tell|recite|told)\b|"
    r"(quy tắc|chỉ dẫn|nguyên tắc|hướng dẫn|cấu hình|lời nhắc|prompt)\b[^.?!\n]{0,30}\b(của bạn|bạn (được|đã được|phải tuân|tuân theo)|"
    r"(được |đã được |mà )?(cài đặt|thiết lập|lập trình|đặt|cài) (cho|vào) bạn)|"
    r"(nhà phát triển|developer|admin|quản trị)\b[^.?!\n]{0,30}\b(đã )?(đặt|cài|giao|cấu hình) (cho )?bạn|"
    r"chế độ (nhà phát triển|developer|bảo trì|gỡ lỗi|debug|quản trị)|"
    r"\b(toàn bộ|tất cả|nội dung|văn bản|những gì)\b[^.?!\n]{0,20}\b(phía trên|ở trên|bên trên|trước đó) (câu|tin nhắn|dòng) này|"
    r"(bản đầy đủ|nguyên văn|toàn văn)[^.?!\n]{0,25}(prompt|chỉ dẫn|lời nhắc|cấu hình)|(prompt|chỉ dẫn|lời nhắc)[^.?!\n]{0,25}(bản đầy đủ|nguyên văn|toàn văn)|"
    r"(giả sử|hãy đóng vai|đóng vai|giả vờ) (bạn là|là|làm)\b[^.?!\n]{0,40}\b(không (bị )?(giới hạn|ràng buộc|kiểm duyệt)|không có (quy tắc|luật|giới hạn))",
    re.I)


def _attack(text: str) -> bool:
    """input_policy's attack rules, as decide() reads them."""
    return bool(_PROMPT_ATTACK.search(unaccented(text)) or _DAN.search(text) or _INJECTION.search(text))


@dataclass
class Gate:
    clean: str
    scan: str
    signals: List[str] = field(default_factory=list)
    action: str = ""
    rule: str = ""

    def trace(self) -> dict:
        return {"rule": self.rule or None, "signals": self.signals}


def screen(message: str) -> Gate:
    text = unicodedata.normalize("NFC", message or "")
    clean = "".join(c for c in text if not is_hidden(c))
    signals = ["hidden"] if any(is_hidden(c) and c not in _HARMLESS and ord(c) not in _VS for c in _FLAG.sub("", text)) else []
    scan = unicodedata.normalize("NFKC", clean)
    mixed = any(_MIXED.search(w) and _OTHER_SCRIPT.search(w) for w in _WORD.findall(scan))
    scan = scan.translate(_CONFUSABLE)
    leet = [w for w in _WORD.findall(scan) if _MIXED.search(w) and re.search(r"\d", w) and not _PERIOD_OR_TICKER.fullmatch(w)]
    if leet:
        scan += "\n" + " ".join(w.lower().translate(_LEET) for w in leet)
        if len(leet) >= 2:  # one such word is a code ("A2M"), two are a disguise
            signals.append("leet")
    if _DOTTED.search(scan) or _SPACED.search(scan):
        signals.append("spaced")
        scan = _DOTTED.sub(lambda m: re.sub(r"[.\-_]", "", m.group(0)), scan)
        scan = _SPACED.sub(lambda m: m.group(0).replace(" ", ""), scan)
    scan = re.sub(r"[ \t]+", " ", scan)
    typos = [k for k in map(_typo_of, _WORD.findall(scan)) if k]
    if typos:
        signals.append("typo")
        scan += "\n" + " ".join(typos)
    decoded = _decoded(clean)
    if decoded:
        scan += "\n" + "\n".join(decoded)
    g = Gate(clean, scan, signals)
    if _smuggled(text):
        g.rule = "hidden"
    elif mixed or decoded or _ROLE_TAG.search(clean) or _PAYLOAD_SPLIT.search(clean):
        g.rule = "structure"
    elif ASSISTANT_ATTACK.search(scan):
        g.rule = "assistant"
    elif _attack(scan) and not _attack(clean):
        g.rule = "disguised"  # an existing rule matches only once the disguise is taken off
    g.action = "refuse_instruction" if g.rule else ""
    return g
