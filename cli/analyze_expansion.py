from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Iterable


PROJECT_HINTS = (
    "pokeemerald-expansion",
    "pokeemerald_expansion",
    "expansion",
)

REQUIRED_MARKERS = (
    Path("Makefile"),
    Path("include/constants/species.h"),
    Path("src/data/pokemon/species_info.h"),
)


@dataclass
class Finding:
    title: str
    details: list[str] = field(default_factory=list)

    def add(self, text: str) -> None:
        if text not in self.details:
            self.details.append(text)

    def ensure_not_found(self) -> None:
        if not self.details:
            self.details.append("NO ENCONTRADO")


@dataclass
class ExpansionProject:
    root: Path
    score: int
    reasons: list[str]


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def candidate_dirs(base: Path) -> Iterable[Path]:
    for child in base.iterdir():
        if child.is_dir() and not child.name.startswith("."):
            yield child


def score_candidate(path: Path) -> ExpansionProject:
    score = 0
    reasons: list[str] = []

    name_lower = path.name.lower()
    if any(hint in name_lower for hint in PROJECT_HINTS):
        score += 3
        reasons.append(f"nombre parecido: {path.name}")

    for marker in REQUIRED_MARKERS:
        if (path / marker).exists():
            score += 3
            reasons.append(f"encontrado {marker}")

    if (path / "graphics/pokemon").exists():
        score += 2
        reasons.append("encontrado graphics/pokemon")

    if (path / "tools/gbagfx").exists():
        score += 1
        reasons.append("encontrado tools/gbagfx")

    return ExpansionProject(root=path, score=score, reasons=reasons)


def detect_project(base: Path) -> ExpansionProject:
    candidates = [score_candidate(d) for d in candidate_dirs(base)]
    if not candidates:
        raise FileNotFoundError("No hay subdirectorios para analizar")

    best = max(candidates, key=lambda c: c.score)
    if best.score < 8:
        debug_lines = "\n".join(f"- {c.root.name}: {c.score}" for c in candidates)
        raise FileNotFoundError(
            "No se detecto una carpeta que parezca pokeemerald-expansion.\n" + debug_lines
        )
    return best


def find_paths(root: Path, patterns: list[str]) -> list[Path]:
    out: list[Path] = []
    for pattern in patterns:
        out.extend(root.glob(pattern))
    return sorted(set(out))


def file_contains(path: Path, pattern: str) -> bool:
    if not path.exists() or not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="ignore")
    return re.search(pattern, text, flags=re.MULTILINE) is not None


def gather_findings(root: Path) -> dict[str, Finding]:
    findings: dict[str, Finding] = {
        "1": Finding("Donde se definen las especies"),
        "2": Finding("Donde se definen los nombres visibles"),
        "3": Finding("Donde estan los base stats"),
        "4": Finding("Donde estan los tipos"),
        "5": Finding("Donde estan las habilidades"),
        "6": Finding("Peso, altura, genero, catch ratio y experiencia base"),
        "7": Finding("Sprites front/back"),
        "8": Finding("Icons"),
        "9": Finding("Footprints"),
        "10": Finding("Palettes"),
        "11": Finding("Evoluciones"),
        "12": Finding("Learnsets"),
        "13": Finding("Compatibilidad TM/HM/TR"),
        "14": Finding("Cries"),
        "15": Finding("Archivos obligatorios para compilar nueva especie"),
        "16": Finding("Tools/scripts que convierten assets"),
        "17": Finding("Formatos de imagen esperados"),
        "18": Finding("Convenciones de nombres"),
        "19": Finding("Partes autogeneradas vs manuales"),
        "20": Finding("Riesgos al editar"),
    }

    species_h = root / "include/constants/species.h"
    species_info_h = root / "src/data/pokemon/species_info.h"
    families = find_paths(root, ["src/data/pokemon/species_info/gen_*_families.h"])
    graphics_h = root / "src/data/graphics/pokemon.h"
    pokemon_c = root / "src/pokemon.c"

    if species_h.exists():
        findings["1"].add(rel(species_h, root))
        findings["18"].add(
            "SPECIES_* en include/constants/species.h (alineado a convenciones Showdown)"
        )
    if species_info_h.exists():
        findings["1"].add(rel(species_info_h, root))
        findings["2"].add("gSpeciesInfo[].speciesName en " + rel(species_info_h, root))

    if families:
        sample = rel(families[0], root)
        findings["3"].add(f"Campos .baseHP/.baseAttack/... en {sample} y resto de gen_*_families.h")
        findings["4"].add("Campo .types = MON_TYPES(...) en gen_*_families.h")
        findings["5"].add("Campo .abilities = { ... } en gen_*_families.h")
        findings["6"].add(
            "Campos .height, .weight, .genderRatio, .catchRate, .expYield en gen_*_families.h"
        )
        findings["11"].add("Campo .evolutions = EVOLUTION(...) en gen_*_families.h")
        findings["2"].add("Nombres por forma/especie en gen_*_families.h")

    if graphics_h.exists():
        findings["7"].add("gMonFrontPic_* y gMonBackPic_* en " + rel(graphics_h, root))
        findings["8"].add("gMonIcon_* en " + rel(graphics_h, root))
        findings["9"].add("gMonFootprint_* en " + rel(graphics_h, root))
        findings["10"].add("gMonPalette_* y gMonShinyPalette_* en " + rel(graphics_h, root))
        findings["18"].add("Simbolos graficos tipo gMonFrontPic_<Species>, gMonIcon_<Species>")

    pokemon_graphics_dir = root / "graphics/pokemon"
    if pokemon_graphics_dir.exists():
        findings["7"].add("Assets en graphics/pokemon/<species>/(front|anim_front|back).png")
        findings["8"].add("Assets en graphics/pokemon/<species>/icon.png")
        findings["9"].add("Assets en graphics/pokemon/<species>/footprint.png")
        findings["10"].add("Assets en graphics/pokemon/<species>/(normal|shiny).pal")
        findings["18"].add("Carpetas de especie en snake_case: graphics/pokemon/<species>")

    level_sets = find_paths(root, ["src/data/pokemon/level_up_learnsets/gen_*.h"])
    if level_sets:
        findings["12"].add("Learnsets por nivel en src/data/pokemon/level_up_learnsets/gen_*.h")
    egg_moves = root / "src/data/pokemon/egg_moves.h"
    if egg_moves.exists():
        findings["12"].add("Egg moves en " + rel(egg_moves, root))
    teachables = root / "src/data/pokemon/teachable_learnsets.h"
    if teachables.exists():
        findings["12"].add("Teachable learnsets en " + rel(teachables, root))
        if file_contains(teachables, r"DO NOT MODIFY THIS FILE"):
            findings["19"].add(
                "src/data/pokemon/teachable_learnsets.h es autogenerado (DO NOT MODIFY)"
            )
    if pokemon_c.exists() and file_contains(pokemon_c, r"data/pokemon/teachable_learnsets\.h"):
        findings["13"].add("TM/HM via teachable learnsets cargados desde src/pokemon.c")

    tmhm_constants = root / "include/constants/tms_hms.h"
    if tmhm_constants.exists():
        findings["13"].add(rel(tmhm_constants, root))
    findings["13"].add("TR separado: NO ENCONTRADO")

    cries_h = root / "include/constants/cries.h"
    cry_tables = root / "sound/cry_tables.inc"
    direct_sound_data = root / "sound/direct_sound_data.inc"
    cries_dir = root / "sound/direct_sound_samples/cries"
    if cries_h.exists():
        findings["14"].add("IDs CRY_* en " + rel(cries_h, root))
    if cry_tables.exists():
        findings["14"].add("Tabla de cries en " + rel(cry_tables, root))
    if direct_sound_data.exists():
        findings["14"].add(".incbin de cries en " + rel(direct_sound_data, root))
    if cries_dir.exists():
        findings["14"].add("Audios fuente en " + rel(cries_dir, root))

    mandatory = [
        species_h,
        species_info_h,
        graphics_h,
        root / "src/pokemon.c",
    ]
    for m in mandatory:
        if m.exists():
            findings["15"].add(rel(m, root))
    findings["15"].add(
        "Tambien suelen intervenir assets en graphics/pokemon/<species>/ y constantes de cry en include/constants/cries.h"
    )

    tool_candidates = [
        root / "tools/gbagfx/gbagfx",
        root / "tools/compresSmol/compresSmol",
        root / "tools/wav2agb/wav2agb",
        root / "tools/learnset_helpers/make_teachables.py",
    ]
    for tool in tool_candidates:
        if tool.exists():
            findings["16"].add(rel(tool, root))

    makefile = root / "Makefile"
    if makefile.exists():
        findings["17"].add("Reglas %.1bpp/%.4bpp/%.8bpp desde %.png en Makefile")
        findings["17"].add("Reglas %.gbapal desde %.pal o %.png en Makefile")
    findings["17"].add("Formatos observados: .png, .pal, .4bpp, .1bpp, .gbapal, .smol")

    findings["19"].add("species_info y species constants se editan manualmente")
    findings["19"].add("assets graficos se editan manualmente y se convierten al compilar")

    findings["20"].add("Cambiar IDs en include/constants/species.h puede romper saves")
    findings["20"].add("Referencias gMon* sin assets convertidos provocan errores de build/link")
    findings["20"].add("Editar archivos autogenerados se pierde al regenerar")
    findings["20"].add("Desalinear CRY_* con tablas/archivos de audio rompe compilacion o runtime")

    for finding in findings.values():
        finding.ensure_not_found()

    return findings


def render_notes(project: ExpansionProject, findings: dict[str, Finding]) -> str:
    lines: list[str] = []
    lines.append("# RESEARCH_NOTES")
    lines.append("")
    lines.append("## Proyecto detectado")
    lines.append(f"- Ruta: `{project.root}`")
    lines.append(f"- Score de deteccion: `{project.score}`")
    lines.append("- Evidencias:")
    for reason in project.reasons:
        lines.append(f"  - {reason}")
    lines.append("")
    lines.append("## Hallazgos")

    for key in [str(i) for i in range(1, 21)]:
        finding = findings[key]
        lines.append(f"### {key}. {finding.title}")
        for detail in finding.details:
            lines.append(f"- {detail}")
        lines.append("")

    lines.append("## Notas")
    lines.append("- Este documento fue generado automaticamente por `analyze_expansion.py`.")
    lines.append("- Si algun punto no se detecta con evidencia directa se marca como `NO ENCONTRADO`.")
    return "\n".join(lines) + "\n"


def print_console_summary(project: ExpansionProject, findings: dict[str, Finding]) -> None:
    print("[OK] Proyecto detectado:", project.root)
    print("[OK] Score:", project.score)
    print("[OK] Evidencias:")
    for reason in project.reasons:
        print("  -", reason)

    print("\n[RESUMEN]")
    for key in [str(i) for i in range(1, 21)]:
        first = findings[key].details[0] if findings[key].details else "NO ENCONTRADO"
        print(f"{key:>2}. {findings[key].title}: {first}")


def main() -> None:
    base = Path.cwd()
    project = detect_project(base)
    findings = gather_findings(project.root)

    notes = render_notes(project, findings)
    notes_path = base / "RESEARCH_NOTES.md"
    notes_path.write_text(notes, encoding="utf-8")

    print_console_summary(project, findings)
    print(f"\n[OK] Archivo generado/actualizado: {notes_path}")


if __name__ == "__main__":
    main()
