from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ChangeStep:
    target_file: str
    action: str
    reason: str
    new_text: str
    old_text: str | None = None
    insert_after: str | None = None
    insert_before: str | None = None
    risk_level: str = "medium"
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ChangePlan:
    mode: str
    constant_name: str
    project_root: str
    steps: list[ChangeStep] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    strategy_notes: list[str] = field(default_factory=list)

    @property
    def is_blocked(self) -> bool:
        return len(self.errors) > 0

    def add_step(self, step: ChangeStep) -> None:
        self.steps.append(step)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "constant_name": self.constant_name,
            "project_root": self.project_root,
            "steps": [step.to_dict() for step in self.steps],
            "warnings": self.warnings,
            "errors": self.errors,
            "strategy_notes": self.strategy_notes,
            "is_blocked": self.is_blocked,
        }

    def to_markdown(self) -> str:
        lines: list[str] = []
        lines.append("# Change Plan")
        lines.append("")
        lines.append(f"- mode: `{self.mode}`")
        lines.append(f"- constant_name: `{self.constant_name}`")
        lines.append(f"- project_root: `{self.project_root}`")
        lines.append(f"- blocked: `{self.is_blocked}`")
        lines.append("")

        if self.strategy_notes:
            lines.append("## Strategy")
            for note in self.strategy_notes:
                lines.append(f"- {note}")
            lines.append("")

        if self.errors:
            lines.append("## Errors")
            for err in self.errors:
                lines.append(f"- {err}")
            lines.append("")

        if self.warnings:
            lines.append("## Warnings")
            for warn in self.warnings:
                lines.append(f"- {warn}")
            lines.append("")

        lines.append("## Steps")
        for idx, step in enumerate(self.steps, start=1):
            lines.append(f"### {idx}. {step.action} - `{step.target_file}`")
            lines.append(f"- reason: {step.reason}")
            lines.append(f"- risk: {step.risk_level}")
            if step.insert_after:
                lines.append(f"- insert_after: `{step.insert_after}`")
            if step.insert_before:
                lines.append(f"- insert_before: `{step.insert_before}`")
            if step.warnings:
                for warn in step.warnings:
                    lines.append(f"- warning: {warn}")
            if step.old_text:
                lines.append("- old_text:")
                lines.append("```c")
                lines.append(step.old_text)
                lines.append("```")
            lines.append("- new_text:")
            lines.append("```c")
            lines.append(step.new_text)
            lines.append("```")
            lines.append("")

        return "\n".join(lines) + "\n"


def relpath(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
