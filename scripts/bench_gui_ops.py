from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.species_editor import SpeciesEditor
from core.species_linter import lint_species_definition
from core.validate_species import validate_species_definition


@dataclass
class BenchResult:
    name: str
    samples_ms: list[float]

    @property
    def avg_ms(self) -> float:
        return statistics.fmean(self.samples_ms) if self.samples_ms else 0.0

    @property
    def p95_ms(self) -> float:
        if not self.samples_ms:
            return 0.0
        if len(self.samples_ms) < 2:
            return self.samples_ms[0]
        return statistics.quantiles(self.samples_ms, n=20)[-1]


def _build_edit_payload(editor: SpeciesEditor) -> dict:
    species = editor.species_by_constant.get("SPECIES_BULBASAUR")
    if species is None:
        species = next(iter(editor.species_by_constant.values()))
    if species is None:
        raise RuntimeError("No species found in project")

    stats = species.base_stats
    types = species.types[:2] if species.types else ["TYPE_NORMAL"]
    abilities = species.abilities[:3] if species.abilities else ["ABILITY_NONE", "ABILITY_NONE", "ABILITY_NONE"]
    if len(abilities) < 3:
        abilities = abilities + ["ABILITY_NONE"] * (3 - len(abilities))

    return {
        "mode": "edit",
        "constant_name": str(species.constant_name or "SPECIES_BULBASAUR"),
        "species_name": str(species.species_name or "Bulbasaur"),
        "description": "Benchmark payload description",
        "folder_name": str(species.folder_name or "bulbasaur"),
        "assets_folder": "",
        "base_stats": {
            "hp": int(stats.hp or 45),
            "attack": int(stats.attack or 49),
            "defense": int(stats.defense or 49),
            "speed": int(stats.speed or 45),
            "sp_attack": int(stats.sp_attack or 65),
            "sp_defense": int(stats.sp_defense or 65),
        },
        "types": [str(t) for t in types],
        "abilities": [str(a) for a in abilities],
        "height": int(species.height or "10"),
        "weight": int(species.weight or "100"),
        "gender_ratio": str(species.gender_ratio or "PERCENT_FEMALE(50)"),
        "catch_rate": int(species.catch_rate or "45"),
        "exp_yield": int(species.exp_yield or "64"),
        "evolutions": [],
        "level_up_learnset": list(species.level_up_moves or [{"level": 1, "move": "MOVE_TACKLE"}]),
        "tmhm_learnset": list(species.teachable_moves_raw or []),
    }


def _time_call(samples: int, name: str, fn) -> BenchResult:
    out: list[float] = []
    for _ in range(samples):
        t0 = time.perf_counter()
        fn()
        out.append((time.perf_counter() - t0) * 1000.0)
    return BenchResult(name=name, samples_ms=out)


def run_benchmark(project_root: Path, iterations: int) -> list[BenchResult]:
    load_result = _time_call(iterations, "load_project", lambda: SpeciesEditor(project_root))
    editor = SpeciesEditor(project_root)
    payload = _build_edit_payload(editor)

    def _validate_only() -> None:
        validate_species_definition(payload, Path.cwd() / "bench_payload.json", project_root, editor.pick_fallback_folder())

    def _lint_only() -> None:
        lint_species_definition(
            data=payload,
            project_root=project_root,
            existing_constants=set(editor.species_by_constant.keys()),
            using_fallback_assets=False,
        )

    def _dry_run_full() -> None:
        validation = validate_species_definition(payload, Path.cwd() / "bench_payload.json", project_root, editor.pick_fallback_folder())
        lint = lint_species_definition(
            data=payload,
            project_root=project_root,
            existing_constants=set(editor.species_by_constant.keys()),
            using_fallback_assets=validation.used_fallback,
        )
        if not lint.ok:
            raise RuntimeError(f"Lint failed during benchmark: {lint.errors}")
        editor.build_plan(lint.normalized_data, validation)

    return [
        load_result,
        _time_call(iterations, "validate_species_definition", _validate_only),
        _time_call(iterations, "lint_species_definition", _lint_only),
        _time_call(iterations, "dry_run_pipeline", _dry_run_full),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark balanced GUI/core operations")
    parser.add_argument("project_root", type=Path, help="Path to pokeemerald-expansion project")
    parser.add_argument("--iterations", type=int, default=5, help="Iterations per operation")
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    results = run_benchmark(project_root, max(1, args.iterations))

    output_dir = Path.cwd() / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "benchmark_results.json"
    md_path = output_dir / "benchmark_results.md"

    payload = {
        "project_root": str(project_root),
        "iterations": args.iterations,
        "results": [
            {
                "name": r.name,
                "avg_ms": round(r.avg_ms, 3),
                "p95_ms": round(r.p95_ms, 3),
                "samples_ms": [round(x, 3) for x in r.samples_ms],
            }
            for r in results
        ],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Benchmark Results",
        "",
        f"Project: `{project_root}`",
        f"Iterations: `{args.iterations}`",
        "",
        "| Operation | Avg (ms) | P95 (ms) |",
        "|---|---:|---:|",
    ]
    for r in results:
        lines.append(f"| {r.name} | {r.avg_ms:.2f} | {r.p95_ms:.2f} |")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Benchmark complete. JSON: {json_path}")
    print(f"Benchmark complete. MD:   {md_path}")
    for r in results:
        print(f"{r.name:28} avg={r.avg_ms:8.2f} ms  p95={r.p95_ms:8.2f} ms")


if __name__ == "__main__":
    main()
