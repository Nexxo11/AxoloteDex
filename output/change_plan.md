# Change Plan

- mode: `add`
- constant_name: `SPECIES_GUITEST_1777513085`
- project_root: `/home/nexxo/Documentos/Programacion/Proyectos/ASA/pokeemerald-expansion`
- blocked: `False`

## Strategy
- Constante nueva insertada justo antes de SPECIES_EGG y se actualiza SPECIES_EGG para apuntar a la nueva especie.
- Bloque de especie se inserta al final de src/data/pokemon/species_info/gen_9_families.h antes del bloque __INTELLISENSE__.
- Referencias graficas se insertan en src/data/graphics/pokemon.h antes de la declaracion de Egg.

## Warnings
- assets_folder no provisto; se intentara fallback de assets
- Se usaron assets fallback de graphics/pokemon/bulbasaur para archivos faltantes

## Steps
### 1. insert - `include/constants/species.h`
- reason: Agregar nueva constante de especie
- risk: high
- insert_before: `#define SPECIES_EGG`
- new_text:
```c
#define SPECIES_GUITEST_1777513085                      1575
```

### 2. update - `include/constants/species.h`
- reason: Actualizar SPECIES_EGG para conservar orden
- risk: high
- old_text:
```c
#define SPECIES_EGG                                     (SPECIES_TESTMON2 + 1)
```
- new_text:
```c
#define SPECIES_EGG                                     (SPECIES_GUITEST_1777513085 + 1)
```

### 3. insert - `src/data/pokemon/species_info/gen_9_families.h`
- reason: Agregar bloque de species info
- risk: high
- insert_before: `#ifdef __INTELLISENSE__`
- new_text:
```c

    [SPECIES_GUITEST_1777513085] =
    {
        .baseHP        = 60,
        .baseAttack    = 61,
        .baseDefense   = 62,
        .baseSpeed     = 63,
        .baseSpAttack  = 64,
        .baseSpDefense = 65,
        .types = MON_TYPES(TYPE_GRASS, TYPE_POISON),
        .catchRate = 45,
        .expYield = 64,
        .genderRatio = PERCENT_FEMALE(12.5),
        .eggCycles = 20,
        .friendship = 70,
        .growthRate = GROWTH_MEDIUM_FAST,
        .eggGroups = MON_EGG_GROUPS(EGG_GROUP_MONSTER),
        .abilities = { ABILITY_OVERGROW, ABILITY_NONE, ABILITY_CHLOROPHYLL },
        .bodyColor = BODY_COLOR_GREEN,
        .noFlip = FALSE,
        .speciesName = _("GuiTestmon"),
        .cryId = CRY_NONE,
        .natDexNum = NATIONAL_DEX_NONE,
        .categoryName = _("Custom"),
        .height = 7,
        .weight = 69,
        .description = COMPOUND_STRING(
            "A custom species added by tool.\n"
            "Replace this description later."),
        .pokemonScale = 256,
        .pokemonOffset = 0,
        .trainerScale = 256,
        .trainerOffset = 0,
        .frontPic = gMonFrontPic_Guitest1777513085,
        .frontPicSize = MON_COORDS_SIZE(64, 64),
        .frontPicYOffset = 0,
        .frontAnimFrames = sAnims_SingleFramePlaceHolder,
        .frontAnimId = ANIM_V_SQUISH_AND_BOUNCE,
        .backPic = gMonBackPic_Guitest1777513085,
        .backPicSize = MON_COORDS_SIZE(64, 64),
        .backPicYOffset = 7,
        .backAnimId = BACK_ANIM_NONE,
        .palette = gMonPalette_Guitest1777513085,
        .shinyPalette = gMonShinyPalette_Guitest1777513085,
        .iconSprite = gMonIcon_Guitest1777513085,
        .iconPalIndex = 0,
        FOOTPRINT(Guitest1777513085)
        .levelUpLearnset = sNoneLevelUpLearnset,
        .teachableLearnset = sNoneTeachableLearnset,
        .eggMoveLearnset = sNoneEggMoveLearnset,
    },

```

### 4. insert - `src/data/graphics/pokemon.h`
- reason: Agregar simbolos graficos de especie
- risk: medium
- insert_before: `const u32 gMonFrontPic_Egg[]`
- new_text:
```c

    const u32 gMonFrontPic_Guitest1777513085[] = INCBIN_U32("graphics/pokemon/guitestmon/front.4bpp.smol");
    const u16 gMonPalette_Guitest1777513085[] = INCBIN_U16("graphics/pokemon/guitestmon/normal.gbapal");
    const u32 gMonBackPic_Guitest1777513085[] = INCBIN_U32("graphics/pokemon/guitestmon/back.4bpp.smol");
    const u16 gMonShinyPalette_Guitest1777513085[] = INCBIN_U16("graphics/pokemon/guitestmon/shiny.gbapal");
    const u8 gMonIcon_Guitest1777513085[] = INCBIN_U8("graphics/pokemon/guitestmon/icon.4bpp");
#if P_FOOTPRINTS
    const u8 gMonFootprint_Guitest1777513085[] = INCBIN_U8("graphics/pokemon/guitestmon/footprint.1bpp");
#endif //P_FOOTPRINTS

```

### 5. copy_asset - `graphics/pokemon/guitestmon/front.png`
- reason: Copiar asset requerido (front.png)
- risk: low
- warning: Asset copiado sin conversion; la conversion la maneja el build del proyecto
- new_text:
```c
/home/nexxo/Documentos/Programacion/Proyectos/ASA/pokeemerald-expansion/graphics/pokemon/bulbasaur/anim_front.png
```

### 6. copy_asset - `graphics/pokemon/guitestmon/back.png`
- reason: Copiar asset requerido (back.png)
- risk: low
- warning: Asset copiado sin conversion; la conversion la maneja el build del proyecto
- new_text:
```c
/home/nexxo/Documentos/Programacion/Proyectos/ASA/pokeemerald-expansion/graphics/pokemon/bulbasaur/back.png
```

### 7. copy_asset - `graphics/pokemon/guitestmon/icon.png`
- reason: Copiar asset requerido (icon.png)
- risk: low
- warning: Asset copiado sin conversion; la conversion la maneja el build del proyecto
- new_text:
```c
/home/nexxo/Documentos/Programacion/Proyectos/ASA/pokeemerald-expansion/graphics/pokemon/bulbasaur/icon.png
```

### 8. copy_asset - `graphics/pokemon/guitestmon/footprint.png`
- reason: Copiar asset requerido (footprint.png)
- risk: low
- warning: Asset copiado sin conversion; la conversion la maneja el build del proyecto
- new_text:
```c
/home/nexxo/Documentos/Programacion/Proyectos/ASA/pokeemerald-expansion/graphics/pokemon/bulbasaur/footprint.png
```

### 9. copy_asset - `graphics/pokemon/guitestmon/normal.pal`
- reason: Copiar asset requerido (normal.pal)
- risk: low
- warning: Asset copiado sin conversion; la conversion la maneja el build del proyecto
- new_text:
```c
/home/nexxo/Documentos/Programacion/Proyectos/ASA/pokeemerald-expansion/graphics/pokemon/bulbasaur/normal.pal
```

### 10. copy_asset - `graphics/pokemon/guitestmon/shiny.pal`
- reason: Copiar asset requerido (shiny.pal)
- risk: low
- warning: Asset copiado sin conversion; la conversion la maneja el build del proyecto
- new_text:
```c
/home/nexxo/Documentos/Programacion/Proyectos/ASA/pokeemerald-expansion/graphics/pokemon/bulbasaur/shiny.pal
```

