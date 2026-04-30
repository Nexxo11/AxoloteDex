from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from build_check import run_build, write_build_outputs
from species_editor import SpeciesEditor
from species_linter import lint_species_definition, write_lint_report
from validate_species import load_species_json, validate_species_definition


def save_plan(output_dir: Path, plan) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "change_plan.json").write_text(
        json.dumps(plan.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (output_dir / "change_plan.md").write_text(plan.to_markdown(), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Editor de especies con DRY-RUN por defecto")
    parser.add_argument("project_root", type=Path)
    parser.add_argument("species_json", type=Path)
    parser.add_argument("--apply", action="store_true", help="Aplica cambios reales")
    parser.add_argument("--build-check", action="store_true", help="Ejecuta make -j$(nproc)")
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    species_json_path = args.species_json.resolve()

    if not species_json_path.exists():
        print(f"[ERROR] No existe archivo JSON: {species_json_path}")
        sys.exit(1)

    data = load_species_json(species_json_path)
    editor = SpeciesEditor(project_root)
    fallback_folder = editor.pick_fallback_folder()

    validation = validate_species_definition(
        data=data,
        json_path=species_json_path,
        project_root=project_root,
        fallback_folder=fallback_folder,
    )
    lint = lint_species_definition(
        data=data,
        project_root=project_root,
        existing_constants=set(editor.species_by_constant.keys()),
        using_fallback_assets=validation.used_fallback,
    )
    lint_report = write_lint_report(Path.cwd() / "output", lint)
    if lint.errors:
        validation.errors.extend(lint.errors)
    validation.warnings.extend([w for w in lint.warnings if w not in validation.warnings])
    data_for_plan = lint.normalized_data

    plan = editor.build_plan(data_for_plan, validation)

    output_dir = Path.cwd() / "output"
    save_plan(output_dir, plan)

    print("[DRY-RUN] Plan generado")
    print(f"- steps: {len(plan.steps)}")
    print(f"- warnings: {len(plan.warnings)}")
    print(f"- errors: {len(plan.errors)}")
    print(f"- output: {output_dir / 'change_plan.md'}")
    print(f"- output: {output_dir / 'change_plan.json'}")
    print(f"- output: {lint_report}")

    if plan.warnings:
        print("\nWarnings:")
        for w in plan.warnings:
            print(f"- {w}")
    if plan.errors:
        print("\nErrors:")
        for e in plan.errors:
            print(f"- {e}")

    print("\nArchivos afectados:")
    for step in plan.steps:
        print(f"- {step.action}: {step.target_file}")

    if not args.apply:
        if args.build_check:
            build_result = run_build(project_root)
            log_path, summary_path = write_build_outputs(output_dir, build_result)
            status = "OK" if build_result.ok else "FAILED"
            print(f"\n[BUILD] STATUS={status}")
            print(f"- log: {log_path}")
            print(f"- summary: {summary_path}")
        print("\n[INFO] DRY-RUN: no se modifico ningun archivo")
        return

    if plan.is_blocked:
        print("\n[ERROR] No se puede aplicar: hay errores criticos en el plan")
        sys.exit(2)

    result = editor.apply_plan(plan, validation)
    if not result.applied:
        print("\n[ERROR] No se aplicaron cambios")
        for msg in result.messages:
            print(f"- {msg}")
        sys.exit(3)

    print("\n[OK] Cambios aplicados")
    for msg in result.messages:
        print(f"- {msg}")

    if args.build_check:
        build_result = run_build(project_root)
        log_path, summary_path = write_build_outputs(output_dir, build_result)
        status = "OK" if build_result.ok else "FAILED"
        print(f"\n[BUILD] STATUS={status}")
        print(f"- log: {log_path}")
        print(f"- summary: {summary_path}")


if __name__ == "__main__":
    main()
