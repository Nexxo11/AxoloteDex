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
    "evo_hover_preview": "evo_hover_preview",
    "evo_hover_img": "evo_hover_img",
    "evo_hover_text": "evo_hover_text",
    "levelup_rows": "levelup_rows",
    "teachable_rows": "teachable_rows",
    "tutor_rows": "tutor_rows",
    "learnset_level_panel": "learnset_level_panel",
    "learnset_tmhm_panel": "learnset_tmhm_panel",
    "stats_radar_panel": "stats_radar_panel",
    "stats_radar_drawlist": "stats_radar_drawlist",
    "stats_fields_panel": "stats_fields_panel",
    "type1_icon": "type1_icon",
    "type2_icon": "type2_icon",
    "type1_icon_btn": "type1_icon_btn",
    "type2_icon_btn": "type2_icon_btn",
    "type1_picker": "type1_picker",
    "type2_picker": "type2_picker",
    "type1_modal": "type1_modal",
    "type2_modal": "type2_modal",
    "type1_list": "type1_list",
    "type2_list": "type2_list",
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
    "editor_tabs": "editor_tabs",
    "tab_general": "tab_general",
    "description_counter": "description_counter",
    "settings_fab": "settings_fab",
    "settings_fab_window": "settings_fab_window",
    "settings_modal": "settings_modal",
    "settings_theme": "settings_theme",
    "settings_backup_auto": "settings_backup_auto",
    "settings_backup_keep": "settings_backup_keep",
    "settings_notify_success": "settings_notify_success",
    "settings_notify_warning": "settings_notify_warning",
    "cry_play_btn": "cry_play_btn",
    "settings_custom_colors_group": "settings_custom_colors_group",
    "settings_color_background": "settings_color_background",
    "settings_color_panel": "settings_color_panel",
    "settings_color_input": "settings_color_input",
    "settings_color_border": "settings_color_border",
    "settings_color_primary": "settings_color_primary",
    "settings_color_primary_hover": "settings_color_primary_hover",
    "settings_color_text": "settings_color_text",
    "settings_color_muted_text": "settings_color_muted_text",
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

        with dpg.window(
            tag=TAGS["settings_fab_window"],
            show=True,
            no_title_bar=True,
            no_resize=True,
            no_move=True,
            no_scrollbar=True,
            no_collapse=True,
            no_background=True,
            no_focus_on_appearing=True,
            width=92,
            height=92,
            pos=(1450, 760),
        ):
            dpg.add_button(
                label="⚙",
                tag=TAGS["settings_fab"],
                width=92,
                height=92,
                callback=actions.open_settings_modal,
            )
            with dpg.tooltip(TAGS["settings_fab"]):
                dpg.add_text("Settings")

        with dpg.window(modal=True, show=False, autosize=True, tag=TAGS["settings_modal"], width=560, label="Settings"):
            dpg.add_text("Theme")
            dpg.add_combo(["Dark", "Light", "System", "Custom"], default_value="Dark", width=240, tag=TAGS["settings_theme"], callback=actions.on_settings_theme_change)
            with dpg.group(tag=TAGS["settings_custom_colors_group"], show=False):
                dpg.add_spacer(height=8)
                dpg.add_text("Custom colors")
                dpg.add_color_edit(tag=TAGS["settings_color_background"], label="Background", alpha_bar=False, callback=actions.on_custom_theme_color_change)
                dpg.add_color_edit(tag=TAGS["settings_color_panel"], label="Panel", alpha_bar=False, callback=actions.on_custom_theme_color_change)
                dpg.add_color_edit(tag=TAGS["settings_color_input"], label="Input", alpha_bar=False, callback=actions.on_custom_theme_color_change)
                dpg.add_color_edit(tag=TAGS["settings_color_border"], label="Border", alpha_bar=False, callback=actions.on_custom_theme_color_change)
                dpg.add_color_edit(tag=TAGS["settings_color_primary"], label="Primary button", alpha_bar=False, callback=actions.on_custom_theme_color_change)
                dpg.add_color_edit(tag=TAGS["settings_color_primary_hover"], label="Primary hover", alpha_bar=False, callback=actions.on_custom_theme_color_change)
                dpg.add_color_edit(tag=TAGS["settings_color_text"], label="Text", alpha_bar=False, callback=actions.on_custom_theme_color_change)
                dpg.add_color_edit(tag=TAGS["settings_color_muted_text"], label="Muted text", alpha_bar=False, callback=actions.on_custom_theme_color_change)
            dpg.add_spacer(height=10)

            dpg.add_text("Backup")
            dpg.add_separator()
            dpg.add_checkbox(label="Auto backup before apply", default_value=True, tag=TAGS["settings_backup_auto"])
            dpg.add_input_int(label="Keep last backups", default_value=15, width=140, min_value=1, max_value=200, min_clamped=True, max_clamped=True, tag=TAGS["settings_backup_keep"])
            dpg.add_spacer(height=10)

            dpg.add_text("Notifications")
            dpg.add_separator()
            dpg.add_checkbox(label="Show success messages", default_value=True, tag=TAGS["settings_notify_success"])
            dpg.add_checkbox(label="Show warning messages", default_value=True, tag=TAGS["settings_notify_warning"])
            dpg.add_spacer(height=14)

            dpg.add_text("Tools")
            dpg.add_separator()
            dpg.add_text("My other tools:")
            dpg.add_button(label="- AxoloteOwAdder (GitHub repo)", width=280, callback=actions.open_axolote_ow_adder)
            dpg.add_spacer(height=14)

            dpg.add_text("About Me")
            dpg.add_separator()
            dpg.add_text("AxoloteDex")
            dpg.add_text("Created by Nexxo")
            dpg.add_text("Pokemon species editor for pokeemerald-expansion")
            dpg.add_spacer(height=14)

            with dpg.group(horizontal=True):
                dpg.add_button(label="Close", width=120, callback=actions.close_settings_modal)

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

        with dpg.window(
            tag=TAGS["evo_hover_preview"],
            show=False,
            no_title_bar=True,
            no_resize=True,
            no_move=True,
            no_scrollbar=True,
            no_collapse=True,
            no_focus_on_appearing=True,
            width=170,
            height=170,
        ):
            dpg.add_text("", tag=TAGS["evo_hover_text"])
            dpg.add_image("tex_front", tag=TAGS["evo_hover_img"], width=128, height=128)


def _build_header(actions) -> None:
    with dpg.child_window(tag=TAGS["header_panel"], width=-1, height=124, border=False, no_scrollbar=True):
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
        dpg.add_button(label="New species", tag=TAGS["btn_new"], callback=actions.new_species, width=-1, height=34)
        with dpg.tooltip(TAGS["btn_new"]):
            dpg.add_text("Create a new species entry")
        dpg.add_spacer(height=4)
        dpg.add_button(label="Delete selected", tag=TAGS["delete_btn"], show=False, callback=actions.show_delete_modal, width=-1, height=34)
        with dpg.tooltip(TAGS["delete_btn"]):
            dpg.add_text("Delete the selected species")


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
    with dpg.tab_bar(tag=TAGS["editor_tabs"]):
        with dpg.tab(label="General", tag=TAGS["tab_general"]):
                with dpg.group(horizontal=True):
                    with dpg.child_window(tag=TAGS["general_left"], width=760, height=528, border=False):
                        dpg.add_text("Constant")
                        dpg.add_input_text(tag="constant_name", callback=actions.mark_dirty, width=340)
                        dpg.add_text("Display name")
                        dpg.add_input_text(tag="species_name", callback=actions.mark_dirty, width=340)
                        with dpg.group(horizontal=True):
                            dpg.add_text("Description")
                            dpg.add_spacer(width=12)
                            dpg.add_text("0/180", tag=TAGS["description_counter"], color=(168, 163, 184, 255))
                        dpg.add_input_text(tag="description", multiline=True, height=84, callback=actions.on_description_change, width=420, always_overwrite=True)
                        dpg.add_text("Folder")
                        dpg.add_input_text(tag="folder_name", callback=actions.mark_dirty, width=340)
                        with dpg.group(horizontal=True):
                            with dpg.group():
                                dpg.add_text("Height")
                                dpg.add_input_int(tag="height", callback=actions.mark_dirty, width=120)
                            with dpg.group():
                                dpg.add_text("Weight")
                                dpg.add_input_int(tag="weight", callback=actions.mark_dirty, width=120)
                            with dpg.group():
                                dpg.add_text("Catch rate")
                                dpg.add_input_int(tag="catch_rate", callback=actions.mark_dirty, width=120)
                            with dpg.group():
                                dpg.add_text("Exp yield")
                                dpg.add_input_int(tag="exp_yield", callback=actions.mark_dirty, width=120)
                        with dpg.group(horizontal=True):
                            with dpg.group():
                                dpg.add_text("Female ratio (%)")
                                dpg.add_input_int(tag="gender_ratio", callback=actions.mark_dirty, width=140, min_value=0, max_value=100, min_clamped=True, max_clamped=True)
                            with dpg.group():
                                dpg.add_text("Cry ID")
                                with dpg.group(horizontal=True):
                                    dpg.add_combo(["CRY_NONE"], tag="cry_id", callback=actions.mark_dirty, width=320)
                                    dpg.add_button(label="▶", tag=TAGS["cry_play_btn"], callback=actions.play_selected_cry, width=40)
                                with dpg.tooltip(TAGS["cry_play_btn"]):
                                    dpg.add_text("Play selected cry")
                    with dpg.child_window(tag=TAGS["general_right"], width=360, height=528, border=False):
                        _build_inline_preview_block(actions)
        with dpg.tab(label="Stats"):
                with dpg.group(horizontal=True):
                    with dpg.child_window(tag=TAGS["stats_fields_panel"], border=False, width=500, height=320, no_scrollbar=True):
                        with dpg.group(horizontal=True):
                            with dpg.child_window(border=False, width=240, height=300):
                                dpg.add_text("Base Stats")
                                with dpg.group(horizontal=True):
                                    dpg.add_text("HP ")
                                    dpg.add_input_int(tag="hp", default_value=45, min_value=1, max_value=255, width=110, callback=actions.mark_dirty)
                                with dpg.group(horizontal=True):
                                    dpg.add_text("Atk")
                                    dpg.add_input_int(tag="attack", default_value=49, min_value=1, max_value=255, width=110, callback=actions.mark_dirty)
                                with dpg.group(horizontal=True):
                                    dpg.add_text("Def")
                                    dpg.add_input_int(tag="defense", default_value=49, min_value=1, max_value=255, width=110, callback=actions.mark_dirty)
                                with dpg.group(horizontal=True):
                                    dpg.add_text("Spd")
                                    dpg.add_input_int(tag="speed", default_value=45, min_value=1, max_value=255, width=110, callback=actions.mark_dirty)
                                with dpg.group(horizontal=True):
                                    dpg.add_text("SpA")
                                    dpg.add_input_int(tag="sp_attack", default_value=65, min_value=1, max_value=255, width=110, callback=actions.mark_dirty)
                                with dpg.group(horizontal=True):
                                    dpg.add_text("SpD")
                                    dpg.add_input_int(tag="sp_defense", default_value=65, min_value=1, max_value=255, width=110, callback=actions.mark_dirty)
                            with dpg.child_window(border=False, width=240, height=300):
                                dpg.add_text("EV Yield")
                                with dpg.group(horizontal=True):
                                    dpg.add_text("HP ")
                                    dpg.add_input_int(tag="ev_hp", default_value=0, min_value=0, max_value=3, width=110, callback=actions.mark_dirty)
                                with dpg.group(horizontal=True):
                                    dpg.add_text("Atk")
                                    dpg.add_input_int(tag="ev_attack", default_value=0, min_value=0, max_value=3, width=110, callback=actions.mark_dirty)
                                with dpg.group(horizontal=True):
                                    dpg.add_text("Def")
                                    dpg.add_input_int(tag="ev_defense", default_value=0, min_value=0, max_value=3, width=110, callback=actions.mark_dirty)
                                with dpg.group(horizontal=True):
                                    dpg.add_text("Spd")
                                    dpg.add_input_int(tag="ev_speed", default_value=0, min_value=0, max_value=3, width=110, callback=actions.mark_dirty)
                                with dpg.group(horizontal=True):
                                    dpg.add_text("SpA")
                                    dpg.add_input_int(tag="ev_sp_attack", default_value=0, min_value=0, max_value=3, width=110, callback=actions.mark_dirty)
                                with dpg.group(horizontal=True):
                                    dpg.add_text("SpD")
                                    dpg.add_input_int(tag="ev_sp_defense", default_value=0, min_value=0, max_value=3, width=110, callback=actions.mark_dirty)
                    with dpg.child_window(tag=TAGS["stats_radar_panel"], border=False, width=-1, height=320, no_scrollbar=True):
                        dpg.add_drawlist(tag=TAGS["stats_radar_drawlist"], width=-1, height=-1)
        with dpg.tab(label="Types & Abilities"):
                dpg.add_text("Types:")
                with dpg.group(horizontal=True):
                    dpg.add_image_button("tex_type1", tag=TAGS["type1_icon_btn"], width=64, height=32, callback=actions.open_type1_modal)
                    dpg.add_spacer(width=8)
                    dpg.add_image_button("tex_type2", tag=TAGS["type2_icon_btn"], width=64, height=32, callback=actions.open_type2_modal)
                dpg.add_combo(["TYPE_NORMAL"], tag="type1", callback=actions.on_type_change, width=280, show=False)
                dpg.add_combo([""], tag="type2", callback=actions.on_type_change, width=280, show=False)
                dpg.add_combo(["ABILITY_NONE"], label="Ability 1", tag="ability1", callback=actions.mark_dirty, width=280)
                dpg.add_combo(["ABILITY_NONE"], label="Ability 2", tag="ability2", callback=actions.mark_dirty, width=280)
                dpg.add_combo(["ABILITY_NONE"], label="Hidden", tag="ability_hidden", callback=actions.mark_dirty, width=280)
                with dpg.window(modal=True, show=False, tag=TAGS["type1_modal"], width=360, height=560, label="Select primary type"):
                    with dpg.child_window(tag=TAGS["type1_list"], width=-1, height=470, border=False):
                        pass
                    dpg.add_button(label="Close", callback=actions.close_type_modals, width=120)
                with dpg.window(modal=True, show=False, tag=TAGS["type2_modal"], width=360, height=560, label="Select secondary type"):
                    with dpg.child_window(tag=TAGS["type2_list"], width=-1, height=470, border=False):
                        pass
                    dpg.add_button(label="Close", callback=actions.close_type_modals, width=120)
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
                dpg.add_child_window(tag=TAGS["evo_rows"], width=580, height=210, border=True)

        with dpg.tab(label="Learnsets"):
                with dpg.group(horizontal=True):
                    with dpg.child_window(tag=TAGS["learnset_level_panel"], width=430, height=284, border=False):
                        dpg.add_text("Level-up moves")
                        with dpg.group(horizontal=True):
                            dpg.add_input_int(label="Level", tag="move_level", default_value=1, min_value=1, max_value=100, width=90)
                            dpg.add_combo(["MOVE_TACKLE"], label="Move", tag="move_name", width=260)
                            dpg.add_button(label="Add", callback=actions.add_levelup_move)
                            dpg.add_button(label="Remove", callback=actions.remove_levelup_move)
                            dpg.add_button(label="▲", callback=actions.move_levelup_up)
                            dpg.add_button(label="▼", callback=actions.move_levelup_down)
                        dpg.add_listbox([], tag=TAGS["levelup_rows"], width=-1, num_items=7, callback=actions.select_levelup_row)
                    with dpg.child_window(tag=TAGS["learnset_tmhm_panel"], width=430, height=284, border=False):
                        dpg.add_text("TM/HM")
                        with dpg.group(horizontal=True):
                            dpg.add_combo(["MOVE_TACKLE"], label="TM/HM Move", tag="tmhm_move", width=300)
                            dpg.add_button(label="Add TM/HM", callback=actions.add_teachable_move)
                            dpg.add_button(label="Remove TM/HM", callback=actions.remove_teachable_move)
                        dpg.add_listbox([], tag=TAGS["teachable_rows"], width=-1, num_items=7, callback=actions.select_teachable_row)
                dpg.add_spacer(height=8)
                dpg.add_text("Move Tutor")
                with dpg.group(horizontal=True):
                    dpg.add_combo(["MOVE_TACKLE"], label="Tutor Move", tag="tutor_move", width=300)
                    dpg.add_button(label="Add Tutor", callback=actions.add_tutor_move)
                    dpg.add_button(label="Remove Tutor", callback=actions.remove_tutor_move)
                dpg.add_listbox([], tag=TAGS["tutor_rows"], width=580, num_items=7, callback=actions.select_tutor_row)
        with dpg.tab(label="Lint"):
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
