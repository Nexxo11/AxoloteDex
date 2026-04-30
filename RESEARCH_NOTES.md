# RESEARCH_NOTES

## Proyecto detectado
- Ruta: `/home/nexxo/Documentos/Programacion/Proyectos/ASA/pokeemerald-expansion`
- Score de deteccion: `15`
- Evidencias:
  - nombre parecido: pokeemerald-expansion
  - encontrado Makefile
  - encontrado include/constants/species.h
  - encontrado src/data/pokemon/species_info.h
  - encontrado graphics/pokemon
  - encontrado tools/gbagfx

## Hallazgos
### 1. Donde se definen las especies
- include/constants/species.h
- src/data/pokemon/species_info.h

### 2. Donde se definen los nombres visibles
- gSpeciesInfo[].speciesName en src/data/pokemon/species_info.h
- Nombres por forma/especie en gen_*_families.h

### 3. Donde estan los base stats
- Campos .baseHP/.baseAttack/... en src/data/pokemon/species_info/gen_1_families.h y resto de gen_*_families.h

### 4. Donde estan los tipos
- Campo .types = MON_TYPES(...) en gen_*_families.h

### 5. Donde estan las habilidades
- Campo .abilities = { ... } en gen_*_families.h

### 6. Peso, altura, genero, catch ratio y experiencia base
- Campos .height, .weight, .genderRatio, .catchRate, .expYield en gen_*_families.h

### 7. Sprites front/back
- gMonFrontPic_* y gMonBackPic_* en src/data/graphics/pokemon.h
- Assets en graphics/pokemon/<species>/(front|anim_front|back).png

### 8. Icons
- gMonIcon_* en src/data/graphics/pokemon.h
- Assets en graphics/pokemon/<species>/icon.png

### 9. Footprints
- gMonFootprint_* en src/data/graphics/pokemon.h
- Assets en graphics/pokemon/<species>/footprint.png

### 10. Palettes
- gMonPalette_* y gMonShinyPalette_* en src/data/graphics/pokemon.h
- Assets en graphics/pokemon/<species>/(normal|shiny).pal

### 11. Evoluciones
- Campo .evolutions = EVOLUTION(...) en gen_*_families.h

### 12. Learnsets
- Learnsets por nivel en src/data/pokemon/level_up_learnsets/gen_*.h
- Egg moves en src/data/pokemon/egg_moves.h
- Teachable learnsets en src/data/pokemon/teachable_learnsets.h

### 13. Compatibilidad TM/HM/TR
- TM/HM via teachable learnsets cargados desde src/pokemon.c
- include/constants/tms_hms.h
- TR separado: NO ENCONTRADO

### 14. Cries
- IDs CRY_* en include/constants/cries.h
- Tabla de cries en sound/cry_tables.inc
- .incbin de cries en sound/direct_sound_data.inc
- Audios fuente en sound/direct_sound_samples/cries

### 15. Archivos obligatorios para compilar nueva especie
- include/constants/species.h
- src/data/pokemon/species_info.h
- src/data/graphics/pokemon.h
- src/pokemon.c
- Tambien suelen intervenir assets en graphics/pokemon/<species>/ y constantes de cry en include/constants/cries.h

### 16. Tools/scripts que convierten assets
- tools/gbagfx/gbagfx
- tools/compresSmol/compresSmol
- tools/wav2agb/wav2agb
- tools/learnset_helpers/make_teachables.py

### 17. Formatos de imagen esperados
- Reglas %.1bpp/%.4bpp/%.8bpp desde %.png en Makefile
- Reglas %.gbapal desde %.pal o %.png en Makefile
- Formatos observados: .png, .pal, .4bpp, .1bpp, .gbapal, .smol

### 18. Convenciones de nombres
- SPECIES_* en include/constants/species.h (alineado a convenciones Showdown)
- Simbolos graficos tipo gMonFrontPic_<Species>, gMonIcon_<Species>
- Carpetas de especie en snake_case: graphics/pokemon/<species>

### 19. Partes autogeneradas vs manuales
- src/data/pokemon/teachable_learnsets.h es autogenerado (DO NOT MODIFY)
- species_info y species constants se editan manualmente
- assets graficos se editan manualmente y se convierten al compilar

### 20. Riesgos al editar
- Cambiar IDs en include/constants/species.h puede romper saves
- Referencias gMon* sin assets convertidos provocan errores de build/link
- Editar archivos autogenerados se pierde al regenerar
- Desalinear CRY_* con tablas/archivos de audio rompe compilacion o runtime

## Notas
- Este documento fue generado automaticamente por `analyze_expansion.py`.
- Si algun punto no se detecta con evidencia directa se marca como `NO ENCONTRADO`.
