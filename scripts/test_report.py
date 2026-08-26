#!/usr/bin/env python3
"""Turn a pytest JUnit XML file into Markdown and/or HTML test reports.

Usage::

    python -m pytest tests --junitxml=reports/junit.xml
    python scripts/test_report.py reports/junit.xml \
        --markdown reports/test-results.md \
        --html reports/test-results.html

Only the standard library is used so the script runs anywhere pytest does.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import html
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

STATUS_ICON = {
    "passed": "✅",
    "failed": "❌",
    "error": "💥",
    "skipped": "⏭️",
}


@dataclass
class Case:
    """One ``<testcase>`` entry."""

    classname: str
    name: str
    time: float
    status: str
    message: str = ""
    detail: str = ""

    @property
    def full_name(self) -> str:
        return f"{self.classname}.{self.name}" if self.classname else self.name


@dataclass
class Suite:
    """One ``<testsuite>`` entry and the cases inside it."""

    name: str
    time: float = 0.0
    cases: list[Case] = field(default_factory=list)

    def count(self, status: str) -> int:
        return sum(1 for case in self.cases if case.status == status)

    @property
    def total(self) -> int:
        return len(self.cases)

    @property
    def ok(self) -> bool:
        return self.count("failed") == 0 and self.count("error") == 0


def parse(xml_path: Path) -> list[Suite]:
    """Read ``xml_path`` and return the suites it describes."""
    root = ET.parse(xml_path).getroot()
    elements = [root] if root.tag == "testsuite" else root.findall("testsuite")

    suites: list[Suite] = []
    for element in elements:
        suite = Suite(
            name=element.get("name") or "pytest",
            time=float(element.get("time") or 0.0),
        )
        for case_element in element.findall("testcase"):
            suite.cases.append(_parse_case(case_element))
        suites.append(suite)
    return suites


def _parse_case(element: ET.Element) -> Case:
    status, message, detail = "passed", "", ""
    for tag, name in (("failure", "failed"), ("error", "error"), ("skipped", "skipped")):
        found = element.find(tag)
        if found is not None:
            status = name
            message = found.get("message") or ""
            detail = (found.text or "").strip()
            break

    return Case(
        classname=element.get("classname") or "",
        name=element.get("name") or "<unnamed>",
        time=float(element.get("time") or 0.0),
        status=status,
        message=message,
        detail=detail,
    )


def totals(suites: list[Suite]) -> dict[str, int]:
    """Aggregate counts across every suite."""
    counts = {status: 0 for status in ("passed", "failed", "error", "skipped")}
    for suite in suites:
        for case in suite.cases:
            counts[case.status] += 1
    counts["total"] = sum(counts[status] for status in ("passed", "failed", "error", "skipped"))
    return counts


def _duration(suites: list[Suite]) -> float:
    return sum(suite.time for suite in suites)


def _generated_at() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def render_markdown(suites: list[Suite]) -> str:
    """Render the suites as a GitHub-flavoured Markdown report."""
    counts = totals(suites)
    passing = counts["failed"] == 0 and counts["error"] == 0
    lines = [
        "# Unit Test Results",
        "",
        f"**Status:** {'✅ PASSED' if passing else '❌ FAILED'}  ",
        f"**Generated:** {_generated_at()}  ",
        f"**Duration:** {_duration(suites):.2f}s",
        "",
        "| Total | Passed | Failed | Errors | Skipped |",
        "| ----: | -----: | -----: | -----: | ------: |",
        "| {total} | {passed} | {failed} | {error} | {skipped} |".format(**counts),
        "",
    ]

    if len(suites) > 1:
        lines += [
            "## Suites",
            "",
            "| Suite | Tests | Passed | Failed | Errors | Skipped | Time |",
            "| ----- | ----: | -----: | -----: | -----: | ------: | ---: |",
        ]
        for suite in suites:
            lines.append(
                f"| {'✅' if suite.ok else '❌'} {suite.name} | {suite.total} "
                f"| {suite.count('passed')} | {suite.count('failed')} "
                f"| {suite.count('error')} | {suite.count('skipped')} | {suite.time:.2f}s |"
            )
        lines.append("")

    lines += ["## Tests", "", "| Result | Test | Time |", "| ------ | ---- | ---: |"]
    for suite in suites:
        for case in suite.cases:
            icon = STATUS_ICON.get(case.status, case.status)
            lines.append(f"| {icon} | `{case.full_name}` | {case.time:.3f}s |")
    lines.append("")

    failures = [
        case
        for suite in suites
        for case in suite.cases
        if case.status in ("failed", "error")
    ]
    if failures:
        lines += ["## Failures", ""]
        for case in failures:
            lines += [
                f"### {STATUS_ICON.get(case.status, '')} `{case.full_name}`",
                "",
                f"{case.message}" if case.message else "",
                "",
                "```text",
                case.detail or "(no traceback captured)",
                "```",
                "",
            ]

    return "\n".join(lines).rstrip() + "\n"


_CSS = """
:root { color-scheme: light dark; --fg: #1c1c1c; --bg: #ffffff; --muted: #5b6470;
        --line: #d7dce3; --row: #f6f8fa; --pass: #1a7f37; --fail: #cf222e;
        --skip: #9a6700; }
@media (prefers-color-scheme: dark) {
  :root { --fg: #e6edf3; --bg: #0d1117; --muted: #9198a1; --line: #30363d;
          --row: #161b22; --pass: #3fb950; --fail: #f85149; --skip: #d29922; }
}
* { box-sizing: border-box; }
body { margin: 0; padding: 2rem 1.25rem; background: var(--bg); color: var(--fg);
       font: 16px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }
main { max-width: 60rem; margin: 0 auto; }
h1 { font-size: 1.6rem; margin: 0 0 .35rem; }
h2 { font-size: 1.15rem; margin: 2rem 0 .6rem; }
h3 { font-size: 1rem; margin: 1.4rem 0 .4rem; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.meta { color: var(--muted); font-size: .9rem; margin-bottom: 1.25rem; }
.badge { display: inline-block; padding: .15rem .6rem; border-radius: 999px;
         font-size: .8rem; font-weight: 600; color: #fff; }
.badge.pass { background: var(--pass); }
.badge.fail { background: var(--fail); }
.cards { display: flex; flex-wrap: wrap; gap: .75rem; margin: 1rem 0 1.5rem; }
.card { flex: 1 1 7rem; border: 1px solid var(--line); border-radius: .5rem; padding: .7rem .9rem; }
.card .n { font-size: 1.5rem; font-weight: 600; }
.card .k { color: var(--muted); font-size: .78rem; text-transform: uppercase; letter-spacing: .04em; }
.card.p .n { color: var(--pass); } .card.f .n { color: var(--fail); } .card.s .n { color: var(--skip); }
.scroll { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: .92rem; }
th, td { text-align: left; padding: .45rem .6rem; border-bottom: 1px solid var(--line); }
th { font-size: .78rem; text-transform: uppercase; letter-spacing: .04em; color: var(--muted); }
tbody tr:nth-child(even) { background: var(--row); }
td.num, th.num { text-align: right; white-space: nowrap; }
code, pre { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
pre { background: var(--row); border: 1px solid var(--line); border-radius: .5rem;
      padding: .8rem; overflow-x: auto; font-size: .85rem; }
.st-passed { color: var(--pass); } .st-failed, .st-error { color: var(--fail); }
.st-skipped { color: var(--skip); }
"""


def render_html(suites: list[Suite]) -> str:
    """Render the suites as a standalone, theme-aware HTML report."""
    counts = totals(suites)
    passing = counts["failed"] == 0 and counts["error"] == 0
    esc = html.escape

    cards = "".join(
        f'<div class="card {cls}"><div class="n">{counts[key]}</div>'
        f'<div class="k">{key}</div></div>'
        for key, cls in (
            ("total", ""),
            ("passed", "p"),
            ("failed", "f"),
            ("error", "f"),
            ("skipped", "s"),
        )
    )

    suite_rows = "".join(
        f"<tr><td>{'✅' if suite.ok else '❌'} {esc(suite.name)}</td>"
        f'<td class="num">{suite.total}</td><td class="num">{suite.count("passed")}</td>'
        f'<td class="num">{suite.count("failed")}</td><td class="num">{suite.count("error")}</td>'
        f'<td class="num">{suite.count("skipped")}</td>'
        f'<td class="num">{suite.time:.2f}s</td></tr>'
        for suite in suites
    )
    suite_section = (
        "<h2>Suites</h2><div class=\"scroll\"><table><thead><tr><th>Suite</th>"
        '<th class="num">Tests</th><th class="num">Passed</th><th class="num">Failed</th>'
        '<th class="num">Errors</th><th class="num">Skipped</th><th class="num">Time</th>'
        f"</tr></thead><tbody>{suite_rows}</tbody></table></div>"
        if len(suites) > 1
        else ""
    )

    case_rows = "".join(
        f'<tr><td class="st-{case.status}">{STATUS_ICON.get(case.status, "")} {case.status}</td>'
        f"<td><code>{esc(case.full_name)}</code></td>"
        f'<td class="num">{case.time:.3f}s</td></tr>'
        for suite in suites
        for case in suite.cases
    )

    failures = [
        case
        for suite in suites
        for case in suite.cases
        if case.status in ("failed", "error")
    ]
    failure_section = ""
    if failures:
        blocks = "".join(
            f"<h3>{STATUS_ICON.get(case.status, '')} {esc(case.full_name)}</h3>"
            + (f"<p>{esc(case.message)}</p>" if case.message else "")
            + f"<pre>{esc(case.detail or '(no traceback captured)')}</pre>"
            for case in failures
        )
        failure_section = f"<h2>Failures</h2>{blocks}"

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Unit Test Results</title>
<style>{_CSS}</style>
</head>
<body>
<main>
<h1>Unit Test Results</h1>
<p class="meta">
  <span class="badge {'pass' if passing else 'fail'}">{'PASSED' if passing else 'FAILED'}</span>
  &nbsp;Generated {_generated_at()} &middot; Duration {_duration(suites):.2f}s
</p>
<div class="cards">{cards}</div>
{suite_section}
<h2>Tests</h2>
<div class="scroll"><table>
<thead><tr><th>Result</th><th>Test</th><th class="num">Time</th></tr></thead>
<tbody>{case_rows}</tbody>
</table></div>
{failure_section}
</main>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("junit_xml", type=Path, help="pytest --junitxml output file")
    parser.add_argument("--markdown", type=Path, help="path to write the Markdown report")
    parser.add_argument("--html", type=Path, help="path to write the HTML report")
    parser.add_argument(
        "--fail-on-error",
        action="store_true",
        help="exit non-zero when the report contains failures or errors",
    )
    args = parser.parse_args(argv)

    if not args.markdown and not args.html:
        parser.error("pass --markdown and/or --html")
    if not args.junit_xml.is_file():
        parser.error(f"no such file: {args.junit_xml}")

    suites = parse(args.junit_xml)

    for path, render in ((args.markdown, render_markdown), (args.html, render_html)):
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(render(suites), encoding="utf-8")
            print(f"wrote {path}")

    counts = totals(suites)
    print(
        "total={total} passed={passed} failed={failed} "
        "errors={error} skipped={skipped}".format(**counts)
    )

    if args.fail_on_error and (counts["failed"] or counts["error"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
