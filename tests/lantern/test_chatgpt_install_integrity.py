from __future__ import annotations
import hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "projects/lantern/native_chatgpt_v1"

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def test_sha256sums_match_current_committed_package_bytes():
    entries = {}
    for line in (PKG / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        sha, rel = line.split("  ", 1)
        entries[rel] = sha
    mismatches = {rel: (expected, digest(PKG / rel)) for rel, expected in entries.items() if digest(PKG / rel) != expected}
    assert mismatches == {}

def test_manifest_payload_hashes_match_current_bytes():
    manifest = json.loads((PKG / "MANIFEST.json").read_text(encoding="utf-8"))
    mismatches = {}
    for item in manifest["payload_files"]:
        path = PKG / item["path"]
        actual = (digest(path), path.stat().st_size)
        expected = (item["sha256"], item["size"])
        if actual != expected:
            mismatches[item["path"]] = (expected, actual)
    assert mismatches == {}

def test_source_binding_does_not_claim_unproven_exact_observation_time():
    binding = json.loads((PKG / "SOURCE_BINDING.json").read_text(encoding="utf-8"))
    assert binding["provider"].get("observed_at") is None
    assert binding["provider"].get("observed_at_state") == "UNKNOWN"

def test_install_requires_combined_project_instructions_count_check():
    install = (PKG / "INSTALL.md").read_text(encoding="utf-8")
    assert "8,000" in install
    assert "combined" in install.lower()
    assert "character" in install.lower()

def test_builder_produces_receipt_bound_to_exact_zip():
    import importlib.util
    script = ROOT / "scripts/build_lantern_chatgpt_install.py"
    spec = importlib.util.spec_from_file_location("lantern_pkg_builder", script)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    receipt = mod.build()
    zip_path = PKG / "PROJECT_LANTERN_CHATGPT_INSTALL_V1.zip"
    assert receipt["zip_sha256"] == digest(zip_path)
    assert receipt["zip_size"] == zip_path.stat().st_size
    assert receipt["install_state"] == "PACKAGE_BUILT_NOT_INSTALLED"
    assert receipt["runtime_consumption_state"] == "NOT_ESTABLISHED"

def test_zip_rebuild_is_byte_identical_and_contains_only_install_payload():
    import importlib.util, tempfile
    script = ROOT / "scripts/build_lantern_chatgpt_install.py"
    spec = importlib.util.spec_from_file_location("lantern_pkg_builder2", script)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    first = PKG / "PROJECT_LANTERN_CHATGPT_INSTALL_V1.zip"
    mod.build()
    first_bytes = first.read_bytes()
    with tempfile.TemporaryDirectory() as td:
        second = Path(td) / first.name
        mod._write_zip(second)
        assert second.read_bytes() == first_bytes
