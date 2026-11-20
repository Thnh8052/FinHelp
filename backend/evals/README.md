# evals: the evaluation kit, one command

```powershell
cd backend
.venv\Scripts\python.exe -m evals                 # every free check, then a table "baseline vs now"; exit code 1 if a number got worse
.venv\Scripts\python.exe -m evals --tests         # the same, plus the whole pytest suite counted as numbers
.venv\Scripts\python.exe -m evals --update-baseline   # after a change you meant to make: today's numbers become the baseline
```

Free = no model, no GPU, no network, no database. It runs in about two seconds (without `--tests`).

## What it checks

| Check | Data | What the numbers mean |
|---|---|---|
| `input.*` | gold v2: 200 questions of the students, each with its own reports as the selected sources | the input rules (`input_policy.decide`) never stop a question the gold wants answered (`answerable_false_refusals` must stay 0) and refuse the "not available" ones for their period or form |
| `security.*` | `security_set.py`: 66 attacks and 40 tricky legitimate questions written on 20/11 after the guardrail code was frozen, bad answers, hidden text in reports | what the code layers stop (gate, input rules, output checks, document flags); `legit_refused` must stay 0 |
| `search.*` | `data/snapshots/search_tk49.json`: the stored TK-49 search of gold v2 | share of questions whose evidence pages were all in the excerpts (page rule) |
| `answers.*` | `data/snapshots/answers_e2e_2026-11-20.jsonl`: the research answers of 20/11, graded by machine (`grading.py`) | share of answers that write the numbers of the gold spec. A screen, not hand grading: it reads figures, not reasoning |
| `failures.*` | the two stored runs together | for every question the gold wants answered, **where it was lost** (below) |

### Where a question was lost (`failures.*`, DG-05)

| kind | evidence in the excerpts | answer | whose fault |
|---|---|---|---|
| `ok` | complete | right | |
| `lucky` | a page missing | right | the model knew or the figure was printed elsewhere |
| `writing` | complete | wrong | the writer: another definition, a wrong line, a wrong formula |
| `retrieval` | a page missing | wrong | the search |
| `unscored` | | | the grader has no number to read |

## Scoring another run

Any run with the same shape can be scored:

```powershell
.venv\Scripts\python.exe -m evals --search <retrieval_*.json or snapshot> --answers <jsonl with {"id","answer","status"} per line>
```

`experiments/scripts/gold_v2/` (git-ignored, on the research machine) holds the scripts that produce such runs: `run_retrieval_v2.py` (search on the stored chunk store, GPU worker),
`e2e_research_v2.py` and `c2_search_deeper.py` (answers, paid). They need the 10,057-chunk store (72 MB) and are therefore not part of this kit.

## Changing the baseline

`baseline.json` is the quality floor. A rule change that makes a number worse fails `python -m evals` and `tests/test_evals.py`; if the change is meant, run `--update-baseline`
and say why in the commit message. Historical reference for the search number: 76.5 % before TK-49 (17/11), 89.3 % after (page rule, 187 questions).
