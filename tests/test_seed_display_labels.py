from base import BaseTest  # noqa: F401 - must import first; mocks out hardware deps

from seedsigner.models.seed import Seed
from seedsigner.models.settings_definition import SettingsConstants
from seedsigner.views.seed_views import get_seed_display_fingerprint

NETWORK = SettingsConstants.MAINNET

PARENT_A = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about".split()
PARENT_B = "zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo wrong".split()


def make_child(parent: Seed, index: int) -> Seed:
    """Derive a real BIP-85 child and tag it the same way SeedBackupView does."""
    child = Seed(mnemonic=parent.get_bip85_child_mnemonic(index, 12).split())
    child.parent_fingerprint = parent.get_fingerprint(NETWORK)
    child.bip85_child_index = index
    return child


def label(seed, seeds):
    return get_seed_display_fingerprint(seed, seeds, NETWORK)


class TestSeedDisplayLabels(BaseTest):

    def test_single_parent_real_indices(self):
        parent = Seed(mnemonic=PARENT_A)
        c0 = make_child(parent, 0)
        c12 = make_child(parent, 12)
        seeds = [parent, c0, c12]

        # Single parent shows bare fingerprint; children show their real index
        assert label(parent, seeds) == parent.get_fingerprint(NETWORK)
        assert label(c0, seeds) == f"{c0.get_fingerprint(NETWORK)} (c0)"
        assert label(c12, seeds) == f"{c12.get_fingerprint(NETWORK)} (c12)"

    def test_labels_stable_after_sibling_discarded(self):
        # The hazard positional numbering had: discarding c0 must not shift
        # any other child's label
        parent = Seed(mnemonic=PARENT_A)
        c0 = make_child(parent, 0)
        c12 = make_child(parent, 12)

        before = label(c12, [parent, c0, c12])
        after = label(c12, [parent, c12])
        assert before == after == f"{c12.get_fingerprint(NETWORK)} (c12)"

    def test_max_index_elides_middle(self):
        # 2147483647 can't fit any 240px surface; middle-elide with an explicit
        # ".." so partial digits never read as a complete different index
        parent = Seed(mnemonic=PARENT_A)
        huge = make_child(parent, 2**31 - 1)
        assert label(huge, [parent, huge]) == f"{huge.get_fingerprint(NETWORK)} (c21..47)"

    def test_elision_threshold(self):
        parent = Seed(mnemonic=PARENT_A)
        six_digits = make_child(parent, 999999)
        seven_digits = make_child(parent, 1234567)
        seeds = [parent, six_digits, seven_digits]

        # Up to 6 digits fits everywhere and must show in full
        assert label(six_digits, seeds) == f"{six_digits.get_fingerprint(NETWORK)} (c999999)"
        assert label(seven_digits, seeds) == f"{seven_digits.get_fingerprint(NETWORK)} (c12..67)"

    def test_index_zero_is_labeled(self):
        # Index 0 is a real, distinct child - must never render as falsy/absent
        parent = Seed(mnemonic=PARENT_A)
        c0 = make_child(parent, 0)
        assert "(c0)" in label(c0, [parent, c0])

    def test_multi_parent(self):
        pa = Seed(mnemonic=PARENT_A)
        pb = Seed(mnemonic=PARENT_B)
        ca5 = make_child(pa, 5)
        cb0 = make_child(pb, 0)
        seeds = [pa, ca5, pb, cb0]

        assert label(pa, seeds) == f"{pa.get_fingerprint(NETWORK)} (p1)"
        assert label(pb, seeds) == f"{pb.get_fingerprint(NETWORK)} (p2)"
        assert label(ca5, seeds) == f"{ca5.get_fingerprint(NETWORK)} (p1)(c5)"
        assert label(cb0, seeds) == f"{cb0.get_fingerprint(NETWORK)} (p2)(c0)"

    def test_missing_index_never_guesses(self):
        # Unreachable in practice (index is set wherever parent_fingerprint is),
        # but a wrong index is worse than an honest unknown
        parent = Seed(mnemonic=PARENT_A)
        child = make_child(parent, 7)
        child.bip85_child_index = None
        assert label(child, [parent, child]) == f"{child.get_fingerprint(NETWORK)} (c?)"

    def test_orphan_child_shows_bare_fingerprint(self):
        # Parent discarded: no lineage displayable
        parent = Seed(mnemonic=PARENT_A)
        child = make_child(parent, 3)
        assert label(child, [child]) == child.get_fingerprint(NETWORK)

    def test_grandchild_stacks_chain(self):
        # Child-of-a-child shows the full derivation path, and the middle
        # seed is NOT promoted to a second parent
        root = Seed(mnemonic=PARENT_A)
        child = make_child(root, 1)
        grandchild = make_child(child, 21)
        seeds = [root, child, grandchild]

        assert label(root, seeds) == root.get_fingerprint(NETWORK)  # single family: no (pN)
        assert label(child, seeds) == f"{child.get_fingerprint(NETWORK)} (c1)"
        assert label(grandchild, seeds) == f"{grandchild.get_fingerprint(NETWORK)} (c1)(c21)"

    def test_grandchild_multi_family(self):
        # Two independent root families: (pN) prefixes every chain
        root_a = Seed(mnemonic=PARENT_A)
        child_a = make_child(root_a, 1)
        grandchild_a = make_child(child_a, 21)
        root_b = Seed(mnemonic=PARENT_B)
        child_b = make_child(root_b, 0)
        seeds = [root_a, child_a, grandchild_a, root_b, child_b]

        assert label(root_a, seeds) == f"{root_a.get_fingerprint(NETWORK)} (p1)"
        assert label(grandchild_a, seeds) == f"{grandchild_a.get_fingerprint(NETWORK)} (p1)(c1)(c21)"
        assert label(root_b, seeds) == f"{root_b.get_fingerprint(NETWORK)} (p2)"
        assert label(child_b, seeds) == f"{child_b.get_fingerprint(NETWORK)} (p2)(c0)"

    def test_discarded_middle_orphans_grandchild(self):
        # Root and grandchild loaded but the middle seed discarded: the
        # chain is unprovable, so no lineage is guessed
        root = Seed(mnemonic=PARENT_A)
        child = make_child(root, 1)
        grandchild = make_child(child, 21)
        seeds = [root, grandchild]  # child discarded

        assert label(grandchild, seeds) == grandchild.get_fingerprint(NETWORK)
        assert label(root, seeds) == root.get_fingerprint(NETWORK)
