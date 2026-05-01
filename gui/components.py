from __future__ import annotations

import dearpygui.dearpygui as dpg


TAGS = {
    "header_panel": "header_panel",
    "main_row": "main_row",
    "species_panel": "species_panel",
    "workspace_panel": "workspace_panel",
    "general_left": "general_left",
    "general_right": "general_right",
    "preview_frame_toggle": "preview_frame_toggle",
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
    with dpg.window(
        label="AxoloteDex",
        width=1560,
        height=880,
        tag="main_window",
        no_scrollbar=True,
        no_scroll_with_mouse=True,
    ):
        _build_header(actions)
        dpg.add_spacer(height=6)
        with dpg.group(horizontal=True, tag=TAGS["main_row"]):
            _build_species_panel(actions)
            _build_workspace_panel(actions)

        with dpg.window(modal=True, show=False, tag=TAGS["confirm_modal"], width=440, height=160, label="Confirm changes"):
            dpg.add_text("This will modify project files. Continue?")
            with dpg.group(horizontal=True):
                dpg.add_button(label="Cancel", callback=actions.hide_confirm_modal)
                dpg.add_button(label="Yes, apply", callback=actions.confirm_apply)

        with dpg.window(modal=True, show=False, tag=TAGS["build_modal"], width=420, height=140, label="Build project"):
            dpg.add_text("This will run make -jN. Continue?")
            with dpg.group(horizontal=True):
                dpg.add_button(label="Cancel", callback=actions.hide_build_modal)
                dpg.add_button(label="Build", callback=actions.run_build_check)

        with dpg.window(modal=True, show=False, tag=TAGS["delete_modal"], width=560, height=230, label="Confirm deletion"):
            dpg.add_text("The selected species and its assets will be deleted.")
            dpg.add_text("This action modifies project files.")
            with dpg.collapsing_header(label="Advanced / Unsafe", tag=TAGS["delete_advanced_header"], default_open=False):
                dpg.add_radio_button(
                    ["safe", "replace+delete", "force-delete"],
                    tag=TAGS["delete_mode"],
                    default_value="safe",
                )
                dpg.add_checkbox(
                    label="If in use, replace refs with random species",
                    tag=TAGS["delete_replace_trainers_random"],
                    default_value=False,
                )
                dpg.add_text("force-delete may break compilation", color=(255, 92, 108, 255))
            with dpg.group(horizontal=True):
                dpg.add_button(label="Cancel", tag=TAGS["btn_delete_cancel"], callback=actions.hide_delete_modal)
                dpg.add_button(label="Yes, delete", tag=TAGS["btn_delete_confirm"], callback=actions.confirm_delete_selected)

        with dpg.window(modal=True, show=False, no_close=True, no_move=True, no_resize=True, tag=TAGS["delete_work_modal"], width=420, height=130, label="Deleting species"):
            dpg.add_text("Processing deletion. Please wait...", tag=TAGS["delete_work_text"])

        with dpg.file_dialog(directory_selector=True, show=False, callback=actions.on_select_project_path, tag=TAGS["path_dialog"], width=700, height=420):
            dpg.add_file_extension(".*")


def _build_header(actions) -> None:
    with dpg.child_window(tag=TAGS["header_panel"], width=-1, height=112, border=False, no_scrollbar=True):
        with dpg.group(horizontal=True):
            dpg.add_text("AxoloteDex")
            dpg.add_text("by Nexxo", color=(168, 163, 184, 255))
        with dpg.group(horizontal=True):
            dpg.add_input_text(tag=TAGS["project_input"], width=780, hint="Path to pokeemerald-expansion")
            dpg.add_button(label="Select Path", tag=TAGS["btn_project_select"], callback=actions.open_project_path_dialog, width=118)
            dpg.add_button(label="Load", tag=TAGS["btn_load"], callback=actions.load_project, width=92)
        with dpg.group(horizontal=True):
            dpg.add_text("Project: not loaded", tag=TAGS["project_status"])
            dpg.add_spacer(width=18)
            dpg.add_text("Species: 0", tag=TAGS["species_count"])
            dpg.add_spacer(width=24)
            dpg.add_text("Compatibilidad: compatible", tag=TAGS["compat_status"], color=(88, 214, 141, 255))


def _build_species_panel(actions) -> None:
    with dpg.child_window(label="Species", tag=TAGS["species_panel"], width=330, height=710, border=True):
        dpg.add_input_text(hint="Search by name or constant", tag=TAGS["search_input"], callback=actions.filter_species, width=-1)
        dpg.add_spacer(height=4)
        dpg.add_listbox([], tag=TAGS["species_list"], width=-1, num_items=22, callback=actions.select_species)
        dpg.add_spacer(height=8)
        dpg.add_button(label="New species", tag=TAGS["btn_new"], callback=actions.new_species, width=-1, height=36)
        dpg.add_spacer(height=4)
        dpg.add_button(label="Delete selected", tag=TAGS["delete_btn"], show=False, callback=actions.show_delete_modal, width=-1, height=28)


def _build_workspace_panel(actions) -> None:
    with dpg.child_window(label="Workspace", tag=TAGS["workspace_panel"], width=1200, height=710, border=True):
        with dpg.tab_bar():
            with dpg.tab(label="Editor"):
                _build_editor_tab(actions)
            with dpg.tab(label="Change Plan"):
                _build_plan_tab(actions)
            with dpg.tab(label="Build / Logs"):
                _build_build_tab(actions)


def _build_editor_tab(actions) -> None:
    dpg.add_combo(["add", "edit"], label="Mode", tag="edit_mode", default_value="add", callback=actions.mark_dirty, width=120)
    with dpg.tab_bar():
        with dpg.tab(label="General"):
                with dpg.group(horizontal=True):
                    with dpg.child_window(tag=TAGS["general_left"], width=760, height=430, border=False):
                        dpg.add_input_text(label="Constant", tag="constant_name", callback=actions.mark_dirty, width=340)
                        dpg.add_input_text(label="Display name", tag="species_name", callback=actions.mark_dirty, width=340)
                        dpg.add_input_text(label="Description", tag="description", multiline=True, height=72, callback=actions.mark_dirty, width=420)
                        dpg.add_input_text(label="Folder", tag="folder_name", callback=actions.mark_dirty, width=340)
                        dpg.add_input_int(label="Height", tag="height", callback=actions.mark_dirty, width=120)
                        dpg.add_input_int(label="Weight", tag="weight", callback=actions.mark_dirty, width=120)
                        dpg.add_input_text(label="Gender ratio", tag="gender_ratio", callback=actions.mark_dirty, width=260)
                        dpg.add_input_int(label="Catch rate", tag="catch_rate", callback=actions.mark_dirty, width=120)
                        dpg.add_input_int(label="Exp yield", tag="exp_yield", callback=actions.mark_dirty, width=120)
                    with dpg.child_window(tag=TAGS["general_right"], width=360, height=430, border=False):
                        _build_inline_preview_block(actions)
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
        with dpg.tab(label="Evolutions"):
                with dpg.group(horizontal=True):
                    dpg.add_combo(["EVO_LEVEL", "EVO_ITEM", "EVO_TRADE", "EVO_FRIENDSHIP"], label="Method", tag="evo_method", width=170, callback=actions.on_evolution_method_change)
                    dpg.add_input_int(label="Level", tag="evo_level_param", width=100, min_value=1, max_value=100, min_clamped=True, max_clamped=True, default_value=16, show=True, callback=actions.mark_dirty)
                    dpg.add_input_int(label="Friendship", tag="evo_friendship_param", width=120, min_value=1, max_value=255, min_clamped=True, max_clamped=True, default_value=220, show=False, callback=actions.mark_dirty)
                    dpg.add_combo(["ITEM_NONE"], label="Item", tag="evo_item_param", width=260, show=False, callback=actions.on_evolution_item_change)
                    dpg.add_combo(["ITEM_NONE"], label="Trade item", tag="evo_trade_item_param", width=260, show=False, callback=actions.on_evolution_trade_item_change)
                    dpg.add_input_text(label="Param", tag="evo_param", width=120, show=False)
                dpg.add_combo([], label="Target species", tag="evo_target", width=420, callback=actions.mark_dirty)
                with dpg.group(horizontal=True):
                    dpg.add_button(label="Add", callback=actions.add_evolution_row)
                    dpg.add_button(label="Update", callback=actions.update_evolution_row)
                    dpg.add_button(label="Remove", callback=actions.remove_evolution_row)
                dpg.add_button(label="Clear", callback=actions.clear_evolutions)
                dpg.add_listbox([], tag=TAGS["evo_rows"], width=580, num_items=8, callback=actions.select_evolution_row)

        with dpg.tab(label="Learnsets"):
                dpg.add_text("Level-up moves")
                with dpg.group(horizontal=True):
                    dpg.add_input_int(label="Level", tag="move_level", default_value=1, min_value=1, max_value=100, width=90)
                    dpg.add_combo(["MOVE_TACKLE"], label="Move", tag="move_name", width=260)
                    dpg.add_button(label="Add", callback=actions.add_levelup_move)
                    dpg.add_button(label="Remove", callback=actions.remove_levelup_move)
                    dpg.add_button(label="↑", callback=actions.move_levelup_up)
                    dpg.add_button(label="↓", callback=actions.move_levelup_down)
                dpg.add_listbox([], tag=TAGS["levelup_rows"], width=580, num_items=7, callback=actions.select_levelup_row)
                dpg.add_spacer(height=8)
                dpg.add_text("TM/HM")
                with dpg.group(horizontal=True):
                    dpg.add_combo(["MOVE_TACKLE"], label="TM/HM Move", tag="tmhm_move", width=300)
                    dpg.add_button(label="Add TM/HM", callback=actions.add_teachable_move)
                    dpg.add_button(label="Remove TM/HM", callback=actions.remove_teachable_move)
                dpg.add_listbox([], tag=TAGS["teachable_rows"], width=580, num_items=7, callback=actions.select_teachable_row)
        with dpg.tab(label="Assets"):
                dpg.add_input_text(label="Assets folder", tag="assets_folder", callback=actions.mark_dirty, width=420)
                dpg.add_button(label="Use example fallback", callback=actions.auto_use_example)
                dpg.add_text("Lint: idle", tag=TAGS["lint_status"])
                dpg.add_input_text(tag=TAGS["lint_output"], multiline=True, readonly=True, width=580, height=120)
    dpg.add_spacer(height=8)
    with dpg.group(horizontal=True):
        dpg.add_button(label="Validate", tag=TAGS["validate_btn"], callback=actions.validate_species)
        dpg.add_button(label="Generate dry-run", tag=TAGS["dryrun_btn"], callback=actions.generate_dry_run)
        dpg.add_button(label="Apply changes", tag=TAGS["apply_btn"], enabled=False, callback=actions.show_confirm_modal)
    dpg.add_text(
        "Flow: Validate -> Generate dry-run -> Apply changes",
        tag=TAGS["apply_hint"],
        color=(245, 197, 66, 255),
    )


def _build_inline_preview_block(actions) -> None:
    with dpg.group(horizontal=True):
        dpg.add_button(label="Change Frame", tag=TAGS["preview_frame_toggle"], callback=actions.toggle_preview_frame)
    dpg.add_text("", tag=TAGS["preview_warning"], wrap=900)
    with dpg.child_window(width=-1, height=152, border=False, no_scrollbar=True):
        with dpg.group(horizontal=True):
            dpg.add_spacer(width=8)
            dpg.add_image("tex_front", width=112, height=112, tag=TAGS["preview_front_img"])
            dpg.add_spacer(width=12)
            dpg.add_image("tex_back", width=112, height=112, tag=TAGS["preview_back_img"])
            dpg.add_spacer(width=12)
            dpg.add_image("tex_icon", width=112, height=112, tag=TAGS["preview_icon_img"])


def _build_plan_tab(actions) -> None:
    dpg.add_text("No dry-run yet", tag=TAGS["plan_empty"])
    dpg.add_input_text(tag=TAGS["plan_summary"], multiline=True, readonly=True, width=-1, height=88)
    dpg.add_input_text(tag=TAGS["plan_text"], multiline=True, readonly=True, width=-1, height=540)


def _build_build_tab(actions) -> None:
    with dpg.group(horizontal=True):
        dpg.add_button(label="Build", tag=TAGS["compile_btn"], enabled=False, callback=actions.show_build_modal)
        dpg.add_text("Build: idle", tag=TAGS["build_status"])
    dpg.add_progress_bar(default_value=0.0, tag=TAGS["build_progress"], width=520, overlay="Idle")
    dpg.add_input_text(tag=TAGS["build_output"], multiline=True, readonly=True, width=-1, height=560)
    dpg.add_text("Ready", tag=TAGS["message_text"], color=(180, 190, 210, 255))
    with dpg.group(horizontal=True):
        dpg.add_text("AxoloteDex v0.6.0 by Nexxo", tag=TAGS["version_text"], color=(168, 163, 184, 255))
        dpg.add_spacer(width=18)
        dpg.add_text("Project: idle", tag=TAGS["status_project"])
        dpg.add_spacer(width=12)
        dpg.add_text("Validation: idle", tag=TAGS["status_validation"])
        dpg.add_spacer(width=12)
        dpg.add_text("Dry-run: idle", tag=TAGS["status_dryrun"])
        dpg.add_spacer(width=12)
        dpg.add_text("Build: idle", tag=TAGS["status_build"])
