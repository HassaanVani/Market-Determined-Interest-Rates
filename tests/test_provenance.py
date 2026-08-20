from engine.provenance import source_fingerprint


def test_source_fingerprint_is_stable_sha256():
    first = source_fingerprint()
    second = source_fingerprint()

    assert first == second
    assert len(first) == 64
    assert set(first) <= set("0123456789abcdef")
