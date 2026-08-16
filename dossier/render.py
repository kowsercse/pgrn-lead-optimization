"""The dossier: a static page a scientist reads and decides from.

Self-contained by construction — no network at open, no external stylesheet, no fonts
to fetch. A judge on conference wifi must not be waiting on a CDN.

Six sections, in the order SPEC declares. The gap section renders even when empty,
because an absent gap list reads as "nothing was missing" rather than "nothing was
reported".
"""
from __future__ import annotations

from html import escape
from typing import Mapping, Sequence

from .answers import Answer
from .feasibility import Feasibility
from .loop import Proposal
from .store import Gap, Record

SECTIONS: tuple[str, ...] = (
    "The five answers",
    "Checks",
    "Gaps and demotions",
    "Recommendation",
    "Hand-off",
    "Cost",
)

_GRADE_ORDER = {"measured": 0, "verified": 1, "documented": 2,
                "inferred": 3, "unverified": 4}

_CSS = """
:root{--ground:#F5F6F8;--surface:#fff;--surface-2:#EDEFF3;--ink:#151922;--ink-2:#39414F;
--muted:#5A6472;--rule:#DCE0E6;--accent:#2E3A8C;--warn:#8A6516;--bad:#A33A2E;
--good:#2C6E52;--mono:ui-monospace,"SF Mono",Menlo,monospace}
@media(prefers-color-scheme:dark){:root:not([data-theme=light]){--ground:#101219;
--surface:#171A23;--surface-2:#1D212C;--ink:#E6E9F0;--ink-2:#C3CAD6;--muted:#98A1B0;
--rule:#262B36;--accent:#8E99E8;--warn:#D6AC55;--bad:#E08476;--good:#6FBF95}}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);line-height:1.6;font-size:16px;
font-family:ui-sans-serif,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:960px;margin:0 auto;padding:40px 24px 80px}
h1{font-size:30px;margin:0 0 6px;letter-spacing:-.02em}
h1 small{display:block;font-size:14px;color:var(--muted);font-weight:400;
letter-spacing:0;margin-top:6px}
h2{font-size:20px;margin:44px 0 14px;padding-top:10px;border-top:2px solid var(--ink)}
p{margin:0 0 12px}
.q{background:var(--surface);border:1px solid var(--rule);border-radius:3px;
padding:16px 18px;margin:0 0 12px}
.q .n{font-family:var(--mono);font-size:11px;color:var(--muted);letter-spacing:.1em}
.q .question{font-weight:650;margin:4px 0 8px}
.q .value{color:var(--ink-2)}
details{margin-top:10px;font-size:13.5px;color:var(--muted)}
details td{padding:2px 10px 2px 0;font-family:var(--mono);font-size:12px;
vertical-align:top}
.pill{display:inline-block;font-family:var(--mono);font-size:10.5px;letter-spacing:.06em;
text-transform:uppercase;padding:2px 7px;border:1px solid;border-radius:2px}
.g-measured,.g-verified{color:var(--good);border-color:var(--good)}
.g-documented{color:var(--accent);border-color:var(--accent)}
.g-inferred{color:var(--warn);border-color:var(--warn)}
.g-unverified{color:var(--bad);border-color:var(--bad)}
table.data{border-collapse:collapse;width:100%;font-size:14px;background:var(--surface);
border:1px solid var(--rule);border-radius:3px}
table.data th{text-align:left;font-family:var(--mono);font-size:10.5px;
text-transform:uppercase;letter-spacing:.08em;color:var(--muted);padding:9px 14px;
background:var(--surface-2);border-bottom:1px solid var(--rule)}
table.data td{padding:9px 14px;border-bottom:1px solid var(--rule);color:var(--ink-2)}
table.data tr:last-child td{border-bottom:none}
.pass{color:var(--good)}.fail{color:var(--bad)}
.note{background:var(--surface);border:1px solid var(--rule);border-left:3px solid
var(--accent);border-radius:3px;padding:14px 18px;margin:0 0 14px}
.empty{color:var(--muted);font-style:italic}
.branch{font-family:var(--mono);font-size:12px;color:var(--accent)}
"""


def _pill(grade: str) -> str:
    return f'<span class="pill g-{escape(grade)}">{escape(grade)}</span>'


def _answers(answers: Sequence[Answer]) -> str:
    out = []
    for a in answers:
        agree = ""
        if a.agree_n is not None and a.agree_of:
            agree = f' · <span class="branch">{a.agree_n}/{a.agree_of} agree</span>'
        ident = ""
        if a.source_id:
            ident = f' · <span class="branch">{escape(a.source_id)}</span>'
        out.append(
            f'<div class="q"><div class="n">QUESTION {a.question_no}</div>'
            f'<div class="question">{escape(a.question)}</div>'
            f'<div class="value">{escape(a.value)}</div>'
            f'<p style="margin-top:10px">{_pill(a.grade)}{ident}{agree}</p></div>'
        )
    return "\n".join(out)


def _checks(f: Feasibility) -> str:
    rows = "".join(
        f'<tr><td>{escape(r["kind"])}</td><td>{r["value"]:g}</td>'
        f'<td>{r["threshold"]:g}</td>'
        f'<td class="{"pass" if r["passed"] else "fail"}">'
        f'{"pass" if r["passed"] else "FAIL"}</td></tr>'
        for r in f.as_rows()
    )
    return (f'<table class="data"><tr><th>Check</th><th>Value</th><th>Threshold</th>'
            f'<th>Result</th></tr>{rows}</table>')


def _gaps(gaps: Sequence[Gap], demoted: Sequence[Record]) -> str:
    parts = []
    if gaps:
        items = "".join(
            f'<tr><td>{escape(g.scout or "—")}</td><td>{escape(g.description)}</td>'
            f'<td>{escape(g.reason)}</td></tr>' for g in gaps)
        parts.append(f'<table class="data"><tr><th>Scout</th><th>Gap</th>'
                     f'<th>Reason</th></tr>{items}</table>')
    else:
        parts.append('<p class="empty">No gaps reported — every scout returned.</p>')

    if demoted:
        items = "".join(
            f'<tr><td>{escape(r.source_id or "—")}</td><td>{escape(r.claim)}</td>'
            f'<td>{escape(r.value)}</td></tr>' for r in demoted)
        parts.append(
            f'<p style="margin-top:16px">{len(demoted)} claim(s) demoted by the '
            f'resolver — the cited identifier did not resolve.</p>'
            f'<table class="data"><tr><th>Identifier</th><th>Claim</th>'
            f'<th>Value</th></tr>{items}</table>')
    else:
        parts.append('<p class="empty" style="margin-top:16px">No claims were demoted; '
                     'every cited identifier resolved.</p>')
    return "\n".join(parts)


def render(
    *,
    target: str,
    answers: Sequence[Answer],
    proposal: Proposal,
    feasibility: Feasibility,
    gaps: Sequence[Gap],
    demoted: Sequence[Record],
    cost: Mapping[str, float],
    version: int = 1,
) -> str:
    failed = ", ".join(proposal.failed_checks) or "none"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Target dossier — {escape(target)}</title>
<style>{_CSS}</style></head><body><div class="wrap">
<h1>Target dossier — {escape(target)}
<small>version {version} · is this target tractable for structure-based
small-molecule drug design?</small></h1>

<h2>{SECTIONS[0]}</h2>
{_answers(answers)}

<h2>{SECTIONS[1]}</h2>
<p>Computed after the assessment above was written. These numbers can contradict it.</p>
{_checks(feasibility)}

<h2>{SECTIONS[2]}</h2>
{_gaps(gaps, demoted)}

<h2>{SECTIONS[3]}</h2>
<div class="note"><p class="branch">{escape(proposal.branch)}</p>
<p>{escape(proposal.recommendation)}</p>
<p style="color:var(--muted);font-size:13.5px;margin:0">Failed checks: {escape(failed)}</p>
</div>

<h2>{SECTIONS[4]}</h2>
<p>{escape(proposal.recommendation)}</p>

<h2>{SECTIONS[5]}</h2>
<table class="data"><tr><th>Tokens</th><th>Tool calls</th><th>Wall clock</th></tr>
<tr><td>{cost.get('tokens', 0):,}</td><td>{cost.get('tool_calls', 0):,}</td>
<td>{cost.get('wall_clock_s', 0):.0f} s</td></tr></table>
</div></body></html>"""
