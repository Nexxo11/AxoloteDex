# Change Plan

- mode: `edit`
- constant_name: `SPECIES_CHARIZARD`
- project_root: `/home/nexxo/Documentos/Programacion/Proyectos/pokeemerald-expansion`
- blocked: `False`

## Steps
### 1. update - `src/data/pokemon/level_up_learnsets/gen_1.h`
- reason: Actualizar level-up learnset
- risk: high
- old_text:
```c
static const struct LevelUpMove sCharizardLevelUpLearnset[] = {
    LEVEL_UP_MOVE(0, MOVE_AIR_SLASH),
    LEVEL_UP_MOVE(1, MOVE_SCRATCH),
    LEVEL_UP_MOVE(1, MOVE_GROWL),
    LEVEL_UP_MOVE(1, MOVE_EMBER),
    LEVEL_UP_MOVE(1, MOVE_SMOKESCREEN),
    LEVEL_UP_MOVE(1, MOVE_HEAT_WAVE),
    LEVEL_UP_MOVE(1, MOVE_DRAGON_CLAW),
    LEVEL_UP_MOVE(12, MOVE_DRAGON_BREATH),
    LEVEL_UP_MOVE(19, MOVE_FIRE_FANG),
    LEVEL_UP_MOVE(24, MOVE_SLASH),
    LEVEL_UP_MOVE(30, MOVE_FLAMETHROWER),
    LEVEL_UP_MOVE(39, MOVE_SCARY_FACE),
    LEVEL_UP_MOVE(46, MOVE_FIRE_SPIN),
    LEVEL_UP_MOVE(54, MOVE_INFERNO),
    LEVEL_UP_MOVE(62, MOVE_FLARE_BLITZ),
    LEVEL_UP_END
};
```
- new_text:
```c
static const struct LevelUpMove sCharizardLevelUpLearnset[] = {
    LEVEL_UP_MOVE(0, MOVE_AIR_SLASH),
    LEVEL_UP_MOVE(1, MOVE_SCRATCH),
    LEVEL_UP_MOVE(1, MOVE_GROWL),
    LEVEL_UP_MOVE(1, MOVE_EMBER),
    LEVEL_UP_MOVE(1, MOVE_SMOKESCREEN),
    LEVEL_UP_MOVE(1, MOVE_HEAT_WAVE),
    LEVEL_UP_MOVE(1, MOVE_DRAGON_CLAW),
    LEVEL_UP_MOVE(12, MOVE_DRAGON_BREATH),
    LEVEL_UP_MOVE(19, MOVE_FIRE_FANG),
    LEVEL_UP_MOVE(24, MOVE_SLASH),
    LEVEL_UP_MOVE(30, MOVE_FLAMETHROWER),
    LEVEL_UP_MOVE(39, MOVE_SCARY_FACE),
    LEVEL_UP_MOVE(46, MOVE_FIRE_SPIN),
    LEVEL_UP_MOVE(54, MOVE_INFERNO),
    LEVEL_UP_MOVE(62, MOVE_FLARE_BLITZ),
    LEVEL_UP_END
};
```

