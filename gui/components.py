from __future__ import annotations

import dearpygui.dearpygui as dpg


TAGS = {
    "project_input": "project_input",
    "project_status": "project_status",
    "species_count": "species_count",
    "status_project": "status_project",
    "status_validation": "status_validation",
    "status_dryrun": "status_dryrun",
    "status_build": "status_build",
    "search_input": "search_input",
    "species_list": "species_list",
    "apply_btn": "apply_btn",
    "validate_btn": "validate_btn",
    "dryrun_btn": "dryrun_btn",
    "compile_btn": "compile_btn",
    "plan_text": "plan_text",
    "plan_summary": "plan_summary",
    "plan_empty": "plan_empty",
    "message_text": "message_text",
    "confirm_modal": "confirm_modal",
    "build_status": "build_status",
    "build_output": "build_output",
    "preview_warning": "preview_warning",
    "build_modal": "build_modal",
    "delete_modal": "delete_modal",
    "delete_btn": "delete_btn",
    "build_progress": "build_progress",
    "preview_front_img": "preview_front_img",
    "preview_back_img": "preview_back_img",
    "preview_icon_img": "preview_icon_img",
    "lint_status": "lint_status",
    "lint_output": "lint_output",
    "evo_rows": "evo_rows",
    "levelup_rows": "levelup_rows",
    "teachable_rows": "teachable_rows",
    "path_dialog": "path_dialog",
    "delete_replace_trainers_random": "delete_replace_trainers_random",
    "compat_status": "compat_status",
    "version_text": "version_text",
    "btn_project_select": "btn_project_select",
    "btn_load": "btn_load",
    "btn_new": "btn_new",
    "btn_delete_confirm": "btn_delete_confirm",
    "btn_delete_cancel": "btn_delete_cancel",
    "delete_mode": "delete_mode",
    "delete_advanced_header": "delete_advanced_header",
    "apply_hint": "apply_hint",
    "delete_work_modal": "delete_work_modal",
    "delete_work_text": "delete_work_text",
}


def build_layout(actions) -> None:
    with dpg.window(label="AxoloteDex", width=1560, height=940, tag="main_window"):
        _build_header(actions)
        dpg.add_spacer(height=6)
        with dpg.group(horizontal=True):
            _build_species_panel(actions)
            _build_editor_panel(actions)
            _build_preview_plan_panel(actions)
        dpg.add_spacer(height=6)
        _build_bottom_status(actions)

        with dpg.window(modal=True, show=False, tag=TAGS["confirm_modal"], width=440, height=160, label="Confirmar cambios"):
            dpg.add_text("Esto modificara archivos del proyecto. ¿Continuar?")
            with dpg.group(horizontal=True):
                dpg.add_button(label="Cancelar", callback=actions.hide_confirm_modal)
                dpg.add_button(label="Si, aplicar", callback=actions.confirm_apply)

        with dpg.window(modal=True, show=False, tag=TAGS["build_modal"], width=420, height=140, label="Compilar proyecto"):
            dpg.add_text("Se ejecutará make -jN. ¿Continuar?")
            with dpg.group(horizontal=True):
                dpg.add_button(label="Cancelar", callback=actions.hide_build_modal)
                dpg.add_button(label="Compilar", callback=actions.run_build_check)

        with dpg.window(modal=True, show=False, tag=TAGS["delete_modal"], width=560, height=230, label="Confirmar eliminación"):
            dpg.add_text("Se eliminará completamente la especie seleccionada y sus assets.")
            dpg.add_text("Esta acción modifica archivos del proyecto.")
            with dpg.collapsing_header(label="Advanced / Unsafe", tag=TAGS["delete_advanced_header"], default_open=False):
                dpg.add_radio_button(
                    ["safe", "replace+delete", "force-delete"],
                    tag=TAGS["delete_mode"],
                    default_value="safe",
                )
                dpg.add_checkbox(
                    label="Si está en uso, reemplazar referencias por especies aleatorias",
                    tag=TAGS["delete_replace_trainers_random"],
                    default_value=False,
                )
                dpg.add_text("force-delete puede dejar el proyecto sin compilar", color=(255, 92, 108, 255))
            with dpg.group(horizontal=True):
                dpg.add_button(label="Cancelar", tag=TAGS["btn_delete_cancel"], callback=actions.hide_delete_modal)
                dpg.add_button(label="Sí, eliminar", tag=TAGS["btn_delete_confirm"], callback=actions.confirm_delete_selected)

        with dpg.window(modal=True, show=False, no_close=True, no_move=True, no_resize=True, tag=TAGS["delete_work_modal"], width=420, height=130, label="Eliminando especie"):
            dpg.add_text("Procesando eliminación. Espera por favor...", tag=TAGS["delete_work_text"])

        with dpg.file_dialog(directory_selector=True, show=False, callback=actions.on_select_project_path, tag=TAGS["path_dialog"], width=700, height=420):
            dpg.add_file_extension(".*")


def _build_header(actions) -> None:
    with dpg.child_window(width=1540, height=112, border=False):
        dpg.add_text("AxoloteDex")
        with dpg.group(horizontal=True):
            dpg.add_input_text(tag=TAGS["project_input"], width=780, hint="Ruta a pokeemerald-expansion")
            dpg.add_button(label="Select Path", tag=TAGS["btn_project_select"], callback=actions.open_project_path_dialog)
            dpg.add_button(label="Cargar", tag=TAGS["btn_load"], callback=actions.load_project)
            dpg.add_button(label="Validar", tag=TAGS["validate_btn"], callback=actions.validate_species)
            dpg.add_button(label="Generar Dry-run", tag=TAGS["dryrun_btn"], callback=actions.generate_dry_run)
            dpg.add_button(label="Aplicar cambios", tag=TAGS["apply_btn"], enabled=False, callback=actions.show_confirm_modal)
            dpg.add_button(label="Compilar", tag=TAGS["compile_btn"], enabled=False, callback=actions.show_build_modal)
        dpg.add_text(
            "Flujo: Validar -> Generar Dry-run -> Aplicar cambios",
            tag=TAGS["apply_hint"],
            color=(245, 197, 66, 255),
        )
        with dpg.group(horizontal=True):
            dpg.add_text("Proyecto: sin cargar", tag=TAGS["project_status"])
            dpg.add_spacer(width=18)
            dpg.add_text("Especies: 0", tag=TAGS["species_count"])
        with dpg.group(horizontal=True):
            dpg.add_text("Proyecto: idle", tag=TAGS["status_project"])
            dpg.add_spacer(width=12)
            dpg.add_text("Validación: idle", tag=TAGS["status_validation"])
            dpg.add_spacer(width=12)
            dpg.add_text("Dry-run: idle", tag=TAGS["status_dryrun"])
            dpg.add_spacer(width=12)
            dpg.add_text("Build: idle", tag=TAGS["status_build"])


def _build_species_panel(actions) -> None:
    with dpg.child_window(label="Especies", width=330, height=710, border=True):
        dpg.add_button(label="Nueva especie", tag=TAGS["btn_new"], callback=actions.new_species, width=300)
        dpg.add_spacer(height=6)
        dpg.add_input_text(hint="Buscar por nombre o constante", tag=TAGS["search_input"], callback=actions.filter_species, width=300)
        dpg.add_listbox([], tag=TAGS["species_list"], width=300, num_items=34, callback=actions.select_species)


def _build_editor_panel(actions) -> None:
    with dpg.child_window(label="Editor", width=620, height=710, border=True):
        dpg.add_combo(["add", "edit"], label="Mode", tag="edit_mode", default_value="add", callback=actions.mark_dirty, width=120)
        dpg.add_button(label="Eliminar especie seleccionada", tag=TAGS["delete_btn"], show=False, callback=actions.show_delete_modal)
        with dpg.tab_bar():
            with dpg.tab(label="General"):
                dpg.add_input_text(label="Constant", tag="constant_name", callback=actions.mark_dirty, width=340)
                dpg.add_input_text(label="Nombre visible", tag="species_name", callback=actions.mark_dirty, width=340)
                dpg.add_input_text(label="Folder", tag="folder_name", callback=actions.mark_dirty, width=340)
                dpg.add_input_int(label="Height", tag="height", callback=actions.mark_dirty, width=120)
                dpg.add_input_int(label="Weight", tag="weight", callback=actions.mark_dirty, width=120)
                dpg.add_input_text(label="Gender ratio", tag="gender_ratio", callback=actions.mark_dirty, width=260)
                dpg.add_input_int(label="Catch rate", tag="catch_rate", callback=actions.mark_dirty, width=120)
                dpg.add_input_int(label="Exp yield", tag="exp_yield", callback=actions.mark_dirty, width=120)
            with dpg.tab(label="Stats"):
                with dpg.group(horizontal=True):
                    for tag, label, val in [("hp", "HP", 45), ("attack", "Atk", 49), ("defense", "Def", 49)]:
                        dpg.add_input_int(label=label, tag=tag, default_value=val, min_value=1, max_value=255, width=110, callback=actions.mark_dirty)
                with dpg.group(horizontal=True):
                    for tag, label, val in [("speed", "Spd", 45), ("sp_attack", "SpA", 65), ("sp_defense", "SpD", 65)]:
                        dpg.add_input_int(label=label, tag=tag, default_value=val, min_value=1, max_value=255, width=110, callback=actions.mark_dirty)
            with dpg.tab(label="Tipos/Habilidades"):
                dpg.add_combo(["TYPE_NORMAL"], label="Type 1", tag="type1", callback=actions.mark_dirty, width=280)
                dpg.add_combo([""], label="Type 2", tag="type2", callback=actions.mark_dirty, width=280)
                dpg.add_combo(["ABILITY_NONE"], label="Ability 1", tag="ability1", callback=actions.mark_dirty, width=280)
                dpg.add_combo(["ABILITY_NONE"], label="Ability 2", tag="ability2", callback=actions.mark_dirty, width=280)
                dpg.add_combo(["ABILITY_NONE"], label="Hidden", tag="ability_hidden", callback=actions.mark_dirty, width=280)
            with dpg.tab(label="Evoluciones"):
                with dpg.group(horizontal=True):
                    dpg.add_combo(["EVO_LEVEL", "EVO_ITEM", "EVO_TRADE", "EVO_FRIENDSHIP"], label="Método", tag="evo_method", width=170, callback=actions.on_evolution_method_change)
                    dpg.add_input_text(label="Param", tag="evo_param", width=100)
                    dpg.add_combo(["ITEM_NONE"], label="Item", tag="evo_item_param", width=220, show=False, callback=actions.on_evolution_item_change)
                dpg.add_input_text(label="Target species", tag="evo_target", width=310)
                with dpg.group(horizontal=True):
                    dpg.add_button(label="Agregar", callback=actions.add_evolution_row)
                    dpg.add_button(label="Actualizar", callback=actions.update_evolution_row)
                    dpg.add_button(label="Eliminar", callback=actions.remove_evolution_row)
                    dpg.add_button(label="Limpiar", callback=actions.clear_evolutions)
                dpg.add_listbox([], tag=TAGS["evo_rows"], width=580, num_items=8, callback=actions.select_evolution_row)
            with dpg.tab(label="Learnsets"):
                dpg.add_text("Movimientos por nivel")
                with dpg.group(horizontal=True):
                    dpg.add_input_int(label="Nivel", tag="move_level", default_value=1, min_value=1, max_value=100, width=90)
                    dpg.add_combo(["MOVE_TACKLE"], label="Movimiento", tag="move_name", width=260)
                    dpg.add_button(label="Agregar", callback=actions.add_levelup_move)
                    dpg.add_button(label="Quitar", callback=actions.remove_levelup_move)
                    dpg.add_button(label="↑", callback=actions.move_levelup_up)
                    dpg.add_button(label="↓", callback=actions.move_levelup_down)
                dpg.add_listbox([], tag=TAGS["levelup_rows"], width=580, num_items=7, callback=actions.select_levelup_row)
                dpg.add_spacer(height=8)
                dpg.add_text("TM/HM")
                with dpg.group(horizontal=True):
                    dpg.add_combo(["MOVE_TACKLE"], label="TM/HM Move", tag="tmhm_move", width=300)
                    dpg.add_button(label="Agregar TM/HM", callback=actions.add_teachable_move)
                    dpg.add_button(label="Quitar TM/HM", callback=actions.remove_teachable_move)
                dpg.add_listbox([], tag=TAGS["teachable_rows"], width=580, num_items=7, callback=actions.select_teachable_row)
            with dpg.tab(label="Assets"):
                dpg.add_input_text(label="Assets folder", tag="assets_folder", callback=actions.mark_dirty, width=420)
                dpg.add_button(label="Usar fallback de ejemplo", callback=actions.auto_use_example)
                dpg.add_text("Lint: idle", tag=TAGS["lint_status"])
                dpg.add_input_text(tag=TAGS["lint_output"], multiline=True, readonly=True, width=580, height=120)


def _build_preview_plan_panel(actions) -> None:
    with dpg.child_window(label="Preview / Plan", width=590, height=710, border=True):
        dpg.add_text("Preview")
        with dpg.group(horizontal=True):
            dpg.add_text("Frame")
            dpg.add_radio_button(["Frame 1", "Frame 2"], tag="preview_frame", default_value="Frame 1", callback=actions.on_preview_mode_change)
            dpg.add_text("Palette")
            dpg.add_radio_button(["Normal", "Shiny"], tag="preview_palette", default_value="Normal", callback=actions.on_preview_mode_change)
        dpg.add_text("", tag=TAGS["preview_warning"], wrap=560)
        with dpg.child_window(width=565, height=180, border=False):
            with dpg.group(horizontal=True):
                dpg.add_spacer(width=35)
                dpg.add_image("tex_front", width=128, height=128, tag=TAGS["preview_front_img"])
                dpg.add_spacer(width=20)
                dpg.add_image("tex_back", width=128, height=128, tag=TAGS["preview_back_img"])
                dpg.add_spacer(width=20)
                dpg.add_image("tex_icon", width=128, height=128, tag=TAGS["preview_icon_img"])
        dpg.add_separator()
        dpg.add_text("Change Plan")
        dpg.add_text("Sin DRY-RUN aún", tag=TAGS["plan_empty"])
        dpg.add_input_text(tag=TAGS["plan_summary"], multiline=True, readonly=True, width=565, height=72)
        dpg.add_input_text(tag=TAGS["plan_text"], multiline=True, readonly=True, width=565, height=345)


def _build_bottom_status(actions) -> None:
    with dpg.child_window(label="Consola", width=1540, height=120, border=True):
        dpg.add_text("Build: idle", tag=TAGS["build_status"])
        dpg.add_progress_bar(default_value=0.0, tag=TAGS["build_progress"], width=500, overlay="Idle")
        dpg.add_input_text(tag=TAGS["build_output"], multiline=True, readonly=True, width=1520, height=62)
        dpg.add_text("Listo", tag=TAGS["message_text"], color=(180, 190, 210, 255))
        with dpg.group(horizontal=True):
            dpg.add_text("AxoloteDex v0.6.0", tag=TAGS["version_text"], color=(168, 163, 184, 255))
            dpg.add_spacer(width=18)
            dpg.add_text("Compatibilidad: compatible", tag=TAGS["compat_status"], color=(88, 214, 141, 255))
