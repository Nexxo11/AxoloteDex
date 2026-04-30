from __future__ import annotations

import dearpygui.dearpygui as dpg


TAGS = {
    "project_input": "project_input",
    "project_status": "project_status",
    "species_count": "species_count",
    "search_input": "search_input",
    "species_list": "species_list",
    "apply_btn": "apply_btn",
    "plan_text": "plan_text",
    "message_text": "message_text",
    "confirm_modal": "confirm_modal",
    "build_status": "build_status",
    "build_output": "build_output",
    "preview_warning": "preview_warning",
    "preview_front_path": "preview_front_path",
    "preview_back_path": "preview_back_path",
    "preview_icon_path": "preview_icon_path",
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
}


def build_layout(actions) -> None:
    with dpg.window(label="Species Editor GUI", width=1450, height=900, tag="main_window"):
        with dpg.group(horizontal=True):
            dpg.add_text("Proyecto:")
            dpg.add_input_text(tag=TAGS["project_input"], width=480)
            dpg.add_button(label="Cargar", callback=actions.load_project)
            dpg.add_button(label="Analizar", callback=actions.analyze_project)
            dpg.add_button(label="Validar especie", callback=actions.validate_species)
            dpg.add_button(label="Compilar proyecto", callback=actions.show_build_modal)
            dpg.add_text("Sin cargar", tag=TAGS["project_status"])
            dpg.add_text("Especies: 0", tag=TAGS["species_count"])

        dpg.add_separator()
        with dpg.group(horizontal=True):
            _build_species_panel(actions)
            _build_editor_panel(actions)
            _build_plan_panel(actions)

        dpg.add_separator()
        _build_bottom_status(actions)

        with dpg.window(
            modal=True,
            show=False,
            tag=TAGS["confirm_modal"],
            width=440,
            height=160,
            label="Confirmar cambios",
        ):
            dpg.add_text("Esto modificara archivos del proyecto. ¿Continuar?")
            with dpg.group(horizontal=True):
                dpg.add_button(label="Cancelar", callback=actions.hide_confirm_modal)
                dpg.add_button(label="Si, aplicar", callback=actions.confirm_apply)

        with dpg.window(
            modal=True,
            show=False,
            tag=TAGS["build_modal"],
            width=420,
            height=140,
            label="Compilar proyecto",
        ):
            dpg.add_text("Se ejecutará make -jN. ¿Continuar?")
            with dpg.group(horizontal=True):
                dpg.add_button(label="Cancelar", callback=actions.hide_build_modal)
                dpg.add_button(label="Compilar", callback=actions.run_build_check)

        with dpg.window(
            modal=True,
            show=False,
            tag=TAGS["delete_modal"],
            width=460,
            height=170,
            label="Confirmar eliminación",
        ):
            dpg.add_text("Se eliminará completamente la especie seleccionada y sus assets.")
            dpg.add_text("Esta acción modifica archivos del proyecto.")
            with dpg.group(horizontal=True):
                dpg.add_button(label="Cancelar", callback=actions.hide_delete_modal)
                dpg.add_button(label="Sí, eliminar", callback=actions.confirm_delete_selected)


def _build_species_panel(actions) -> None:
    with dpg.child_window(label="Especies", width=320, height=700, border=True):
        dpg.add_input_text(hint="Buscar", tag=TAGS["search_input"], callback=actions.filter_species, width=300)
        dpg.add_listbox([], tag=TAGS["species_list"], width=300, num_items=33, callback=actions.select_species)


def _build_editor_panel(actions) -> None:
    with dpg.child_window(label="Editor", width=580, height=700, border=True):
        dpg.add_combo(["add", "edit"], label="Mode", tag="edit_mode", default_value="add", callback=actions.mark_dirty, width=120)
        dpg.add_input_text(label="Constant", tag="constant_name", callback=actions.mark_dirty, width=250)
        dpg.add_input_text(label="Nombre visible", tag="species_name", callback=actions.mark_dirty, width=250)
        dpg.add_input_text(label="Folder", tag="folder_name", callback=actions.mark_dirty, width=250)
        dpg.add_input_text(label="Assets folder", tag="assets_folder", callback=actions.mark_dirty, width=420)

        with dpg.collapsing_header(label="Stats", default_open=True):
            with dpg.group(horizontal=True):
                for tag, label in [("hp", "HP"), ("attack", "Atk"), ("defense", "Def")]:
                    dpg.add_input_int(label=label, tag=tag, min_value=1, max_value=255, width=90, callback=actions.mark_dirty)
            with dpg.group(horizontal=True):
                for tag, label in [("speed", "Spd"), ("sp_attack", "SpA"), ("sp_defense", "SpD")]:
                    dpg.add_input_int(label=label, tag=tag, min_value=1, max_value=255, width=90, callback=actions.mark_dirty)

        with dpg.collapsing_header(label="Tipos y habilidades", default_open=True):
            dpg.add_combo(["TYPE_NORMAL"], label="Type 1", tag="type1", callback=actions.mark_dirty, width=240)
            dpg.add_combo([""], label="Type 2", tag="type2", callback=actions.mark_dirty, width=240)
            dpg.add_combo(["ABILITY_NONE"], label="Ability 1", tag="ability1", callback=actions.mark_dirty, width=240)
            dpg.add_combo(["ABILITY_NONE"], label="Ability 2", tag="ability2", callback=actions.mark_dirty, width=240)
            dpg.add_combo(["ABILITY_NONE"], label="Hidden", tag="ability_hidden", callback=actions.mark_dirty, width=240)

        with dpg.collapsing_header(label="Datos básicos", default_open=False):
            dpg.add_input_int(label="Height", tag="height", callback=actions.mark_dirty, width=120)
            dpg.add_input_int(label="Weight", tag="weight", callback=actions.mark_dirty, width=120)
            dpg.add_input_text(label="Gender ratio", tag="gender_ratio", callback=actions.mark_dirty, width=240)
            dpg.add_input_int(label="Catch rate", tag="catch_rate", callback=actions.mark_dirty, width=120)
            dpg.add_input_int(label="Exp yield", tag="exp_yield", callback=actions.mark_dirty, width=120)

        with dpg.collapsing_header(label="Evoluciones", default_open=False):
            with dpg.group(horizontal=True):
                dpg.add_combo(["EVO_LEVEL", "EVO_ITEM", "EVO_TRADE", "EVO_FRIENDSHIP"], label="Método", tag="evo_method", width=160, callback=actions.on_evolution_method_change)
                dpg.add_input_text(label="Param", tag="evo_param", width=100)
                dpg.add_combo(["ITEM_NONE"], label="Item", tag="evo_item_param", width=220, show=False, callback=actions.on_evolution_item_change)
            dpg.add_input_text(label="Target species", tag="evo_target", width=240)
            with dpg.group(horizontal=True):
                dpg.add_button(label="Agregar evolución", callback=actions.add_evolution_row)
                dpg.add_button(label="Actualizar seleccionada", callback=actions.update_evolution_row)
                dpg.add_button(label="Eliminar seleccionada", callback=actions.remove_evolution_row)
                dpg.add_button(label="Limpiar evoluciones", callback=actions.clear_evolutions)
            dpg.add_listbox([], tag=TAGS["evo_rows"], width=520, num_items=6, callback=actions.select_evolution_row)

        with dpg.collapsing_header(label="Movimientos por nivel", default_open=False):
            with dpg.group(horizontal=True):
                dpg.add_input_int(label="Nivel", tag="move_level", default_value=1, min_value=1, max_value=100, width=100)
                dpg.add_combo(["MOVE_TACKLE"], label="Movimiento", tag="move_name", width=260)
            with dpg.group(horizontal=True):
                dpg.add_button(label="Agregar", callback=actions.add_levelup_move)
                dpg.add_button(label="Quitar", callback=actions.remove_levelup_move)
                dpg.add_button(label="↑", callback=actions.move_levelup_up)
                dpg.add_button(label="↓", callback=actions.move_levelup_down)
            dpg.add_listbox([], tag=TAGS["levelup_rows"], width=520, num_items=8, callback=actions.select_levelup_row)

        with dpg.collapsing_header(label="TM/HM", default_open=False):
            with dpg.group(horizontal=True):
                dpg.add_combo(["MOVE_TACKLE"], label="TM/HM Move", tag="tmhm_move", width=280)
                dpg.add_button(label="Agregar TM/HM", callback=actions.add_teachable_move)
                dpg.add_button(label="Quitar TM/HM", callback=actions.remove_teachable_move)
            dpg.add_listbox([], tag=TAGS["teachable_rows"], width=520, num_items=8, callback=actions.select_teachable_row)

        with dpg.collapsing_header(label="Preview", default_open=True):
            with dpg.group(horizontal=True):
                dpg.add_radio_button(["Frame 1", "Frame 2"], tag="preview_frame", default_value="Frame 1", callback=actions.on_preview_mode_change)
                dpg.add_radio_button(["Normal", "Shiny"], tag="preview_palette", default_value="Normal", callback=actions.on_preview_mode_change)
            dpg.add_text("", tag=TAGS["preview_warning"], wrap=550)
            with dpg.group(horizontal=True):
                dpg.add_image("tex_front", width=128, height=128, tag=TAGS["preview_front_img"])
                dpg.add_image("tex_back", width=128, height=128, tag=TAGS["preview_back_img"])
                dpg.add_image("tex_icon", width=128, height=128, tag=TAGS["preview_icon_img"])

        with dpg.group(horizontal=True):
            dpg.add_button(label="Nuevo Pokemon", callback=actions.new_species)
            dpg.add_button(label="Eliminar especie seleccionada", tag=TAGS["delete_btn"], show=False, callback=actions.show_delete_modal)
            dpg.add_button(label="Auto usar ejemplo", callback=actions.auto_use_example)
            dpg.add_button(label="Generar DRY-RUN", callback=actions.generate_dry_run)
            dpg.add_button(label="Aplicar cambios", tag=TAGS["apply_btn"], enabled=False, callback=actions.show_confirm_modal)

        dpg.add_text("Lint: idle", tag=TAGS["lint_status"])
        dpg.add_input_text(tag=TAGS["lint_output"], multiline=True, readonly=True, width=550, height=70)


def _build_plan_panel(actions) -> None:
    with dpg.child_window(label="Change Plan", width=510, height=700, border=True):
        dpg.add_input_text(tag=TAGS["plan_text"], multiline=True, readonly=True, width=490, height=690)


def _build_bottom_status(actions) -> None:
    with dpg.child_window(label="Build Status", width=1420, height=145, border=True):
        dpg.add_text("Estado: idle", tag=TAGS["build_status"])
        dpg.add_progress_bar(default_value=0.0, tag=TAGS["build_progress"], width=500, overlay="Idle")
        with dpg.group(horizontal=True):
            dpg.add_button(label="Compilar proyecto", callback=actions.show_build_modal)
            dpg.add_button(label="Abrir build_summary.md", callback=actions.open_build_summary)
        dpg.add_input_text(tag=TAGS["build_output"], multiline=True, readonly=True, width=1400, height=85)
        dpg.add_input_text(tag=TAGS["message_text"], multiline=True, readonly=True, width=1400, height=40)
