# Analisis y export de especies para pokeemerald-expansion

Este proyecto incluye:

- `analyze_expansion.py` para investigacion de estructura.
- `species_reader.py` como lector interno de especies.
- `export_species.py` para exportar datos estructurados.
- `models.py` con las dataclasses del dominio.

## Requisitos

- Python 3

## Uso (fase 1)

Desde este directorio:

```bash
python3 analyze_expansion.py
```

Si tu sistema tiene alias `python -> python3`, tambien funciona:

```bash
python analyze_expansion.py
```

## Que hace

- Busca automaticamente una carpeta que parezca `pokeemerald-expansion`.
- Verifica indicadores clave de estructura del proyecto.
- Escanea rutas relacionadas con especies, graficos, learnsets, cries y herramientas.
- Muestra un resumen por consola.
- Genera o actualiza `RESEARCH_NOTES.md` con los hallazgos.

## Nota

El script no modifica archivos dentro de la carpeta de `pokeemerald-expansion`; solo lee informacion y escribe resultados en este directorio.

## Uso (fase 2: exportador)

Ejecuta:

```bash
python3 export_species.py ./pokeemerald-expansion
```

Si tu sistema usa alias `python -> python3`, tambien sirve:

```bash
python export_species.py ./pokeemerald-expansion
```

Esto crea:

- `output/species_index.json`
- `output/species_summary.md`
- `output/parse_warnings.md`

## Archivos que lee el exportador

- `include/constants/species.h`
- `src/data/pokemon/species_info.h`
- `src/data/pokemon/species_info/gen_*_families.h`
- `src/data/graphics/pokemon.h`
- `src/data/pokemon/level_up_learnsets/gen_*.h`
- `src/data/pokemon/egg_moves.h`
- `src/data/pokemon/teachable_learnsets.h`

## Limitaciones actuales

- El parser es por regex/bloques, no es un parser C completo.
- Campos muy complejos con macros anidadas pueden quedar en formato raw o vacio.
- Los IDs solo se resuelven cuando el `#define` de `SPECIES_*` es numerico directo.
- En casos raros, se registra warning y se continua sin abortar.

## Ejemplos de datos exportados

- `constant_name`: `SPECIES_BULBASAUR`
- `species_name`: `Bulbasaur`
- `types`: `["TYPE_GRASS", "TYPE_POISON"]`
- `abilities`: `["ABILITY_OVERGROW", "ABILITY_NONE", "ABILITY_CHLOROPHYLL"]`
- `graphics.front_path`: `graphics/pokemon/bulbasaur/anim_front.4bpp.smol`

## Fase 3: editor con DRY-RUN

### Comando

```bash
python3 apply_species_change.py <ruta_proyecto> <archivo.json> [--apply] [--build-check]
```

Ejemplo:

```bash
python3 apply_species_change.py ./pokeemerald-expansion examples/new_species.example.json
```

Por defecto es DRY-RUN y no modifica archivos.

Para aplicar cambios reales:

```bash
python3 apply_species_change.py ./pokeemerald-expansion examples/new_species.example.json --apply
```

### Salidas

- `output/change_plan.md`
- `output/change_plan.json`

### Seguridad

- Sin `--apply`: solo genera plan.
- Con `--apply`: crea backup en `backups/YYYYMMDD_HHMMSS/` antes de escribir.
- Se evita tocar archivos autogenerados.
- Si en modo `add` la constante ya existe, se bloquea.
- Si en modo `edit` la constante no existe, se bloquea.

### Assets y fallback

Assets esperados:

- `front.png`
- `back.png`
- `icon.png`
- `footprint.png`
- `normal.pal`
- `shiny.pal`

Si faltan, se intenta fallback usando una especie existente de `graphics/pokemon/` (por ejemplo `bulbasaur`) y se registra warning en el plan.

## Rollback rapido

Preview (sin cambios):

```bash
python3 rollback_backup.py ./pokeemerald-expansion --latest --remove-path graphics/pokemon/testmon
```

Aplicar rollback real:

```bash
python3 rollback_backup.py ./pokeemerald-expansion --latest --remove-path graphics/pokemon/testmon --apply
```

`--remove-path` es util para borrar carpetas nuevas creadas por un alta (por ejemplo assets de una especie nueva).

## Fase 4: GUI DearPyGui

### Instalacion de dependencias

Recomendado (entorno virtual):

```bash
python3 -m venv .venv
.venv/bin/python -m pip install dearpygui
.venv/bin/python -m pip install pillow
```

### Ejecutar GUI

```bash
.venv/bin/python gui_app.py
```

### Flujo de uso

1. Cargar proyecto en el Panel Proyecto.
2. Elegir/editar datos en Panel Editor.
3. Click en `Generar DRY-RUN`.
4. Revisar `Panel Change Plan`.
5. Click en `Aplicar cambios` y confirmar modal.

La GUI nunca aplica sin preview previo valido.

## Fase 5: Build check + preview sprites

- `apply_species_change.py --build-check` ahora ejecuta `make -j$(nproc)`.
- Se generan:
  - `output/build_log.txt`
  - `output/build_summary.md`
- La GUI incluye sección **Build Status** con botón `Compilar proyecto`.
- El editor muestra preview de `front`, `back` e `icon`.
- Si faltan sprites, usa fallback `graphics/pokemon/bulbasaur/` y muestra warning.

## Fase 6: Lint + autogen + pixel-perfect

- Nuevo módulo: `species_linter.py`.
- Genera `output/lint_report.md`.
- Errores de lint bloquean apply (GUI y CLI).
- Autogeneración simple:
  - hidden ability faltante -> `ABILITY_NONE`
  - learnset vacío -> move básico por tipo (ej. `TYPE_GRASS` -> `MOVE_ABSORB`)
- Preview de sprites pixel-art sin blur:
  - se reescala con `Image.NEAREST`
  - manejo de front/icon con dos frames en un solo PNG (usa frame izquierdo)
