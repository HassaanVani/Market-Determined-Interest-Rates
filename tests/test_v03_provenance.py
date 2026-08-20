from v03.provenance import tree_fingerprint


def test_tree_fingerprint_ignores_python_cache_files(tmp_path):
    source = tmp_path / "v03"
    source.mkdir()
    (source / "model.py").write_text("value = 1\n")
    first = tree_fingerprint(tmp_path, paths=("v03",))
    cache = source / "__pycache__"
    cache.mkdir()
    (cache / "model.cpython-313.pyc").write_bytes(b"volatile")
    assert tree_fingerprint(tmp_path, paths=("v03",)) == first
