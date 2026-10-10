from tl_simulator.catalog import REGISTRATION, build_catalog
from tl_simulator.lab import default_lab


def _catalog():
    return build_catalog(default_lab().bands)


def test_catalog_has_150_tests():
    assert len(_catalog()) == 150


def test_test_names_are_unique():
    names = [test.name for test in _catalog()]
    assert len(names) == len(set(names))


def test_name_contains_family_variant_and_band():
    test = next(t for t in _catalog() if t.family == "HO" and t.band == "n78")
    assert test.name == f"TC_HO_{test.variant}_N78"


def test_every_test_starts_with_registration():
    for test in _catalog():
        assert test.steps[: len(REGISTRATION)] == REGISTRATION


def test_non_registration_tests_add_their_own_steps():
    for test in _catalog():
        if test.family != "REG":
            assert len(test.steps) > len(REGISTRATION)


def test_catalog_order_is_stable():
    assert [t.name for t in _catalog()] == [t.name for t in _catalog()]
