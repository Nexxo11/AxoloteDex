# Change Plan

- mode: `edit`
- constant_name: `SPECIES_WARTORTLE`
- project_root: `/home/nexxo/Documentos/Programacion/Proyectos/pokeemerald-expansion`
- blocked: `False`

## Steps
### 1. update - `src/data/pokemon/level_up_learnsets/gen_1.h`
- reason: Actualizar level-up learnset
- risk: high
- old_text:
```c
static const struct LevelUpMove sWartortleLevelUpLearnset[] = {
    LEVEL_UP_MOVE(1, MOVE_TACKLE),
    LEVEL_UP_MOVE(1, MOVE_TAIL_WHIP),
    LEVEL_UP_MOVE(1, MOVE_WATER_GUN),
    LEVEL_UP_MOVE(1, MOVE_WITHDRAW),
    LEVEL_UP_MOVE(9, MOVE_RAPID_SPIN),
    LEVEL_UP_MOVE(12, MOVE_BITE),
    LEVEL_UP_MOVE(15, MOVE_WATER_PULSE),
    LEVEL_UP_MOVE(20, MOVE_PROTECT),
    LEVEL_UP_MOVE(25, MOVE_RAIN_DANCE),
    LEVEL_UP_MOVE(30, MOVE_AQUA_TAIL),
    LEVEL_UP_MOVE(35, MOVE_SHELL_SMASH),
    LEVEL_UP_MOVE(40, MOVE_IRON_DEFENSE),
    LEVEL_UP_MOVE(45, MOVE_HYDRO_PUMP),
    LEVEL_UP_MOVE(50, MOVE_WAVE_CRASH),
    LEVEL_UP_END
};
```
- new_text:
```c
static const struct LevelUpMove sWartortleLevelUpLearnset[] = {
    LEVEL_UP_MOVE(1, MOVE_TACKLE),
    LEVEL_UP_MOVE(1, MOVE_TAIL_WHIP),
    LEVEL_UP_MOVE(1, MOVE_WATER_GUN),
    LEVEL_UP_MOVE(1, MOVE_WITHDRAW),
    LEVEL_UP_MOVE(9, MOVE_RAPID_SPIN),
    LEVEL_UP_MOVE(12, MOVE_BITE),
    LEVEL_UP_MOVE(15, MOVE_WATER_PULSE),
    LEVEL_UP_MOVE(20, MOVE_PROTECT),
    LEVEL_UP_MOVE(25, MOVE_RAIN_DANCE),
    LEVEL_UP_MOVE(30, MOVE_AQUA_TAIL),
    LEVEL_UP_MOVE(35, MOVE_SHELL_SMASH),
    LEVEL_UP_MOVE(40, MOVE_IRON_DEFENSE),
    LEVEL_UP_MOVE(45, MOVE_HYDRO_PUMP),
    LEVEL_UP_MOVE(50, MOVE_WAVE_CRASH),
    LEVEL_UP_END
};
```

