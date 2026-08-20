from v03.power import required_paired_seeds


def test_required_paired_seeds_increases_as_effect_shrinks():
    assert required_paired_seeds(0.2) > required_paired_seeds(0.5)


def test_required_paired_seeds_handles_unidentified_effect():
    assert required_paired_seeds(0.0) is None
