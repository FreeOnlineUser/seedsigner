# Must import test base before the Controller
from base import FlowTest, FlowStep

from seedsigner.gui.screens.screen import RET_CODE__BACK_BUTTON
from seedsigner.models.settings import SettingsConstants
from seedsigner.models.seed import Seed
from seedsigner.views import seed_views


class TestBIP85BackupTestFlows(FlowTest):
    """
    The BIP-85 words flow ends with the child seed being auto-imported into
    SeedStorage carrying its lineage metadata (parent fingerprint + child index),
    whether the user verifies the backup or skips the test.
    """

    CHILD_INDEX = 7
    NUM_WORDS = 12

    def load_parent_seed(self) -> Seed:
        seed = Seed(mnemonic=["abandon"] * 11 + ["about"])
        self.controller.storage.set_pending_seed(seed)
        self.controller.storage.finalize_pending_seed()
        return seed


    def bip85_data(self) -> dict:
        return dict(child_index=self.CHILD_INDEX, num_words=self.NUM_WORDS)


    def assert_child_imported(self, parent: Seed):
        network = self.settings.get_value(SettingsConstants.SETTING__NETWORK)
        assert len(self.controller.storage.seeds) == 2
        child = self.controller.storage.seeds[1]
        expected_mnemonic = parent.get_bip85_child_mnemonic(self.CHILD_INDEX, self.NUM_WORDS).split()
        assert child.mnemonic_list == expected_mnemonic
        assert child.parent_fingerprint == parent.get_fingerprint(network)
        assert child.bip85_child_index == self.CHILD_INDEX
        assert self.controller.storage.get_pending_seed() is None


    def test_skip_backup_test_auto_imports_child(self):
        """
        Skipping the backup test in the BIP-85 flow should still auto-import the
        child seed and land on its SeedOptionsView.
        """
        parent = self.load_parent_seed()
        self.run_sequence(
            [
                FlowStep(seed_views.SeedWordsBackupTestPromptView, button_data_selection=seed_views.SeedWordsBackupTestPromptView.SKIP),
                FlowStep(seed_views.SeedOptionsView),
            ],
            initial_destination_view_args=dict(seed=parent, bip85_data=self.bip85_data()),
        )
        self.assert_child_imported(parent)


    def test_verified_backup_test_auto_imports_child(self):
        """
        Completing the backup test in the BIP-85 flow should auto-import the child
        seed and land on its SeedOptionsView.
        """
        parent = self.load_parent_seed()
        self.run_sequence(
            [
                FlowStep(seed_views.SeedWordsBackupTestSuccessView, screen_return_value=0),
                FlowStep(seed_views.SeedOptionsView),
            ],
            initial_destination_view_args=dict(seed=parent, bip85_data=self.bip85_data()),
        )
        self.assert_child_imported(parent)


    def test_backup_test_back_button_returns_to_prompt(self):
        """
        Backing out of the word quiz should return to the Verify/Skip prompt with
        the bip85 context intact and without importing anything.
        """
        parent = self.load_parent_seed()
        self.run_sequence(
            [
                FlowStep(seed_views.SeedWordsBackupTestView, screen_return_value=RET_CODE__BACK_BUTTON),
                FlowStep(seed_views.SeedWordsBackupTestPromptView),
            ],
            initial_destination_view_args=dict(seed=parent, bip85_data=self.bip85_data()),
        )
        assert len(self.controller.storage.seeds) == 1


    def test_skip_without_bip85_returns_to_seed_options(self):
        """
        The plain (non-BIP-85) backup test skip should return to the seed's own
        SeedOptionsView without touching storage.
        """
        parent = self.load_parent_seed()
        self.run_sequence(
            [
                FlowStep(seed_views.SeedWordsBackupTestPromptView, button_data_selection=seed_views.SeedWordsBackupTestPromptView.SKIP),
                FlowStep(seed_views.SeedOptionsView),
            ],
            initial_destination_view_args=dict(seed=parent),
        )
        assert len(self.controller.storage.seeds) == 1
