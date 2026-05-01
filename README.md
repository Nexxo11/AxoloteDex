# AxoloteDex (ASA)

Herramienta para usuarios de `pokeemerald-expansion` que permite **agregar, editar y eliminar especies** con flujo seguro de DRY-RUN, validaciones, lint y rollback.

Esta app esta pensada para trabajo real sobre proyectos de expansion, no solo para exportar datos.

## Que hace la herramienta

- GUI principal para edicion de especies con preview de sprites.
- Flujo seguro obligatorio: `Validar -> Generar DRY-RUN -> Aplicar cambios`.
- Plan de cambios antes de escribir (`output/change_plan.md` y `output/change_plan.json`).
- Backups automaticos antes de aplicar (`backups/YYYYMMDD_HHMMSS/`).
- Lint que bloquea cambios inseguros o inconsistentes.
- Check de compilacion (`make -jN`) desde CLI o GUI.
- Modos de borrado avanzado (safe, replace+delete, force-delete).

## Requisitos

- Python 3.10+ (recomendado 3.11 o 3.12)
- Proyecto `pokeemerald-expansion` funcional
- En Linux/macOS: `make` para build check

## Instalacion rapida

Desde la carpeta del proyecto ASA:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install dearpygui pillow
```

## Uso recomendado (usuario final): GUI

Ejecuta:

```bash
.venv/bin/python gui_app.py
```

Flujo normal:

1. Carga la ruta de tu `pokeemerald-expansion`.
2. Selecciona especie o crea una nueva en el editor.
3. Pulsa `Validar`.
4. Pulsa `Generar DRY-RUN`.
5. Revisa `Change Plan` (errores/warnings/riesgo).
6. Pulsa `Aplicar cambios`.
7. (Opcional recomendado) Pulsa `Compilar proyecto`.

Notas importantes:

- Si cambias datos despues del DRY-RUN, la app puede regenerarlo automaticamente al aplicar.
- Si faltan assets, se usa fallback y se reporta warning.
- Si el lint detecta errores, no se aplica nada.

## Uso por CLI

### 1) Analizar estructura del proyecto

```bash
python3 analyze_expansion.py
```

Genera notas de investigacion y valida estructura base sin modificar el repo objetivo.

### 2) Exportar especies

```bash
python3 export_species.py ./pokeemerald-expansion
```

Salidas:

- `output/species_index.json`
- `output/species_summary.md`
- `output/parse_warnings.md`

### 3) Generar plan de cambio (DRY-RUN)

```bash
python3 apply_species_change.py <ruta_proyecto> <archivo.json>
```

Ejemplo:

```bash
python3 apply_species_change.py ./pokeemerald-expansion examples/new_species.example.json
```

### 4) Aplicar cambios reales

```bash
python3 apply_species_change.py ./pokeemerald-expansion examples/new_species.example.json --apply
```

### 5) Aplicar y compilar

```bash
python3 apply_species_change.py ./pokeemerald-expansion examples/new_species.example.json --apply --build-check
```

Salida de build:

- `output/build_log.txt`
- `output/build_summary.md`

## Borrado de especies (GUI)

La GUI soporta modos de borrado:

- `safe`: bloquea si encuentra referencias externas.
- `replace+delete`: intenta reemplazar referencias y luego borrar.
- `force-delete`: elimina aunque queden referencias (riesgo alto).

Recomendacion: usar siempre `safe` o `replace+delete` y compilar al final.

## Rollback de backup

Ver preview de rollback (sin aplicar):

```bash
python3 rollback_backup.py ./pokeemerald-expansion --latest --remove-path graphics/pokemon/testmon
```

Aplicar rollback real:

```bash
python3 rollback_backup.py ./pokeemerald-expansion --latest --remove-path graphics/pokemon/testmon --apply
```

`--remove-path` ayuda a limpiar carpetas creadas por altas nuevas.

## Comandos de depuracion y soporte

Si algo falla, estos comandos ayudan a diagnosticar rapido:

```bash
# 1) Ejecutar pruebas de seguridad del editor
python3 -m unittest tests.test_species_editor_safety -v

# 2) Ejecutar pruebas de GUI (requiere dearpygui instalado)
python3 -m unittest tests.test_gui_dry_run -v

# 3) Levantar GUI desde venv
.venv/bin/python gui_app.py

# 4) Verificar que la expansion compile
make -j$(nproc)
```

Archivos clave para revisar cuando hay errores:

- `output/change_plan.md`
- `output/change_plan.json`
- `output/lint_report.md`
- `output/build_log.txt`
- `output/build_summary.md`

## Estructura de assets esperada

Para alta/edicion de especie se esperan estos archivos en el folder de assets:

- `front.png`
- `back.png`
- `icon.png`
- `footprint.png`
- `normal.pal`
- `shiny.pal`

Si alguno falta, el sistema intenta fallback con una especie existente y lo deja registrado como warning.

## Seguridad y limites

- Sin `--apply`, nunca se escriben cambios (solo plan).
- Con `--apply`, siempre se genera backup antes de tocar archivos.
- El parser usa enfoque por bloques/regex (no parser C completo).
- Casos de macros muy complejos pueden generar warnings en lugar de abortar.

## Consejos para evitar roturas

- No uses `force-delete` salvo que sepas exactamente el impacto.
- Compila despues de cualquier borrado o cambio grande.
- Si una especie esta muy referenciada, prefiere `replace+delete`.
- Mantene versionados `output/` y backups locales solo para debugging, no para release.

## Version

Interfaz marcada como `AxoloteDex v0.6.0`.
