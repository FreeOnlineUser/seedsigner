import sys

from base import BaseTest

from seedsigner.models.settings_definition import SettingsConstants
from seedsigner.views import psbt_views, seed_views, tools_views


def capture_button_data(view):
    captured = {}

    def fake_run_screen(screen_cls, **kwargs):
        captured["button_data"] = kwargs["button_data"]
        from seedsigner.gui.screens.screen import RET_CODE__BACK_BUTTON
        return RET_CODE__BACK_BUTTON

    view.run_screen = fake_run_screen
    view.run()
    return captured["button_data"]


class TestSmartcardDormancy(BaseTest):
    """
    With the master smartcard gate at its default (DISABLED), no smartcard menu
    entry may appear anywhere and no smartcard/pysatochip code may be loaded.
    """

    def test_master_gate_defaults_disabled(self):
        assert (
            self.settings.get_value(SettingsConstants.SETTING__SMARTCARD_SUPPORT)
            == SettingsConstants.OPTION__DISABLED
        )

    def test_tools_menu_has_no_smartcard_entry_by_default(self):
        button_data = capture_button_data(tools_views.ToolsMenuView())
        assert tools_views.ToolsMenuView.SMARTCARD not in button_data

    def test_load_seed_has_no_seedkeeper_entry_by_default(self):
        button_data = capture_button_data(seed_views.LoadSeedView())
        assert seed_views.LoadSeedView.IMPORT_SEEDKEEPER not in button_data

    def test_psbt_select_seed_has_no_card_entries_by_default(self):
        from embit.psbt import PSBT

        self.controller.psbt = PSBT()
        self.controller.psbt_seed = None
        self.controller.storage.seeds = []

        button_data = capture_button_data(psbt_views.PSBTSelectSeedView())
        assert psbt_views.PSBTSelectSeedView.SATOCHIP not in button_data
        assert psbt_views.PSBTSelectSeedView.KEYCARD not in button_data

    def test_no_smartcard_modules_loaded(self):
        # Rendering every gated menu above must not have pulled in pysatochip:
        # everything that touches it is lazy-imported only behind the gate.
        # (Other test files legitimately import the smartcard view module with
        # mocked backends, so only the pysatochip absence is asserted here.)
        assert "pysatochip" not in sys.modules

    def test_tools_menu_shows_smartcard_when_enabled(self):
        self.settings.set_value(
            SettingsConstants.SETTING__SMARTCARD_SUPPORT,
            SettingsConstants.OPTION__ENABLED,
        )
        button_data = capture_button_data(tools_views.ToolsMenuView())
        assert tools_views.ToolsMenuView.SMARTCARD in button_data

    def test_load_seed_shows_seedkeeper_when_enabled(self):
        self.settings.set_value(
            SettingsConstants.SETTING__SMARTCARD_SUPPORT,
            SettingsConstants.OPTION__ENABLED,
        )
        button_data = capture_button_data(seed_views.LoadSeedView())
        assert seed_views.LoadSeedView.IMPORT_SEEDKEEPER in button_data

    def test_smartcard_sub_settings_hidden_until_master_enabled(self):
        from seedsigner.models.settings_definition import SettingsDefinition

        # Master gate defaults to disabled: every smartcard sub-setting must be
        # hidden from all settings menus.
        for attr_name in SettingsDefinition.SMARTCARD_SUB_ENTRY_VISIBILITY:
            assert (
                SettingsDefinition.get_settings_entry(attr_name).visibility
                == SettingsConstants.VISIBILITY__HIDDEN
            ), f"{attr_name} visible while smartcard support disabled"

        # Enabling the master gate restores each sub-setting's own visibility
        self.settings.set_value(
            SettingsConstants.SETTING__SMARTCARD_SUPPORT,
            SettingsConstants.OPTION__ENABLED,
        )
        for attr_name, shown in SettingsDefinition.SMARTCARD_SUB_ENTRY_VISIBILITY.items():
            assert SettingsDefinition.get_settings_entry(attr_name).visibility == shown

        # And disabling hides them again
        self.settings.set_value(
            SettingsConstants.SETTING__SMARTCARD_SUPPORT,
            SettingsConstants.OPTION__DISABLED,
        )
        for attr_name in SettingsDefinition.SMARTCARD_SUB_ENTRY_VISIBILITY:
            assert (
                SettingsDefinition.get_settings_entry(attr_name).visibility
                == SettingsConstants.VISIBILITY__HIDDEN
            )
