from __future__ import annotations

from dataclasses import dataclass, asdict
import os
from pathlib import Path
import re
import subprocess
from typing import Any


@dataclass
class BuildIssue:
    file: str
    line: int | None
    message: str


@dataclass
class BuildResult:
    ok: bool
    returncode: int
    stdout: str
    stderr: str
    errors: list[BuildIssue]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "returncode": self.returncode,
            "errors": [asdict(e) for e in self.errors],
            "warnings": self.warnings,
        }


def run_build(project_root: Path) -> BuildResult:
    jobs = max(1, os.cpu_count() or 1)
    proc = subprocess.run(
        ["make", f"-j{jobs}"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    text = proc.stdout + "\n" + proc.stderr
    errors, warnings = parse_build_output(text)
    return BuildResult(
        ok=proc.returncode == 0,
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        errors=errors,
        warnings=warnings,
    )


def parse_build_output(text: str) -> tuple[list[BuildIssue], list[str]]:
    errors: list[BuildIssue] = []
    warnings: list[str] = []

    gcc_error = re.compile(r"^([^:\n]+):(\d+):(?:\d+:)?\s+error:\s+(.+)$", re.MULTILINE)
    undef_ref = re.compile(r"undefined reference to\s+`?([^`\n']+)`?")

    for m in gcc_error.finditer(text):
        errors.append(BuildIssue(file=m.group(1), line=int(m.group(2)), message=m.group(3).strip()))

    for line in text.splitlines():
        low = line.lower()
        if "warning:" in low:
            warnings.append(line.strip())
        if "error:" in low and not gcc_error.search(line):
            errors.append(BuildIssue(file="(unknown)", line=None, message=line.strip()))
        if "undefined reference" in low:
            um = undef_ref.search(line)
            msg = f"undefined reference: {um.group(1)}" if um else line.strip()
            errors.append(BuildIssue(file="(linker)", line=None, message=msg))
        if "gbagfx" in low and ("error" in low or "failed" in low):
            errors.append(BuildIssue(file="tools/gbagfx", line=None, message=line.strip()))

    # Deduplicate while preserving order
    seen = set()
    unique_errors: list[BuildIssue] = []
    for err in errors:
        key = (err.file, err.line, err.message)
        if key in seen:
            continue
        seen.add(key)
        unique_errors.append(err)

    seen_w = set()
    unique_warn = []
    for w in warnings:
        if w in seen_w:
            continue
        seen_w.add(w)
        unique_warn.append(w)

    return unique_errors, unique_warn


def write_build_outputs(output_dir: Path, result: BuildResult) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "build_log.txt"
    summary_path = output_dir / "build_summary.md"
    log_path.write_text(result.stdout + "\n" + result.stderr, encoding="utf-8")

    lines = []
    lines.append("# Build Summary")
    lines.append("")
    lines.append(f"BUILD STATUS: {'OK' if result.ok else 'FAILED'}")
    lines.append(f"Return code: {result.returncode}")
    lines.append("")
    lines.append("## Errores")
    if result.errors:
        for err in result.errors:
            line_text = f"{err.file}:{err.line}" if err.line is not None else err.file
            lines.append(f"- `{line_text}` {err.message}")
    else:
        lines.append("- Ninguno")
    lines.append("")
    lines.append("## Warnings")
    if result.warnings:
        for warn in result.warnings:
            lines.append(f"- {warn}")
    else:
        lines.append("- Ninguno")
    lines.append("")
    lines.append(f"Log completo: `{log_path}`")
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return log_path, summary_path
