from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import zipfile

PACKAGE_ID = "PROJECT_LANTERN_CHATGPT_INSTALL_V1"
ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/lantern/native_chatgpt_v1"
ZIP_PATH = PKG / f"{PACKAGE_ID}.zip"
PAYLOAD = (
    "INSTALL.md",
    "INSTALL_RECEIPT_TEMPLATE.json",
    "PROJECT_FILES/LANTERN_ACCEPTANCE_V1.md",
    "PROJECT_FILES/LANTERN_OPERATOR_HANDSHAKE_V1.md",
    "PROJECT_FILES/LANTERN_READ_QUERIES_V1.md",
    "PROJECT_FILES/LANTERN_RUNTIME_CONTRACT_V1.md",
    "PROJECT_INSTRUCTIONS_ADDENDUM.md",
    "README.md",
    "ROLLBACK.md",
    "SOURCE_BINDING.json",
)
ZIP_MEMBERS = (*PAYLOAD, "MANIFEST.json", "SHA256SUMS")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_manifest() -> None:
    current = json.loads((PKG / "MANIFEST.json").read_text(encoding="utf-8"))
    current["version"] = "1.0.1"
    current["payload_files"] = [
        {"path": rel, "sha256": sha256(PKG / rel), "size": (PKG / rel).stat().st_size}
        for rel in PAYLOAD
    ]
    (PKG / "MANIFEST.json").write_text(
        json.dumps(current, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _write_checksums() -> None:
    covered = (*PAYLOAD, "MANIFEST.json")
    (PKG / "SHA256SUMS").write_text(
        "".join(f"{sha256(PKG / rel)}  {rel}\n" for rel in covered), encoding="utf-8"
    )


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(f"{PACKAGE_ID}/{name}", date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def _write_zip(destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for rel in sorted(ZIP_MEMBERS):
            zf.writestr(_zip_info(rel), (PKG / rel).read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def _verify_zip(path: Path) -> None:
    with zipfile.ZipFile(path) as zf:
        expected_names = [f"{PACKAGE_ID}/{rel}" for rel in sorted(ZIP_MEMBERS)]
        if zf.namelist() != expected_names:
            raise RuntimeError("ZIP_MEMBER_SET_MISMATCH")
        for rel in sorted(ZIP_MEMBERS):
            if zf.read(f"{PACKAGE_ID}/{rel}") != (PKG / rel).read_bytes():
                raise RuntimeError(f"ZIP_BYTE_MISMATCH:{rel}")


def _verify_manifest_and_checksums() -> None:
    manifest = json.loads((PKG / "MANIFEST.json").read_text(encoding="utf-8"))
    for item in manifest["payload_files"]:
        path = PKG / item["path"]
        if item["sha256"] != sha256(path) or item["size"] != path.stat().st_size:
            raise RuntimeError(f"MANIFEST_MISMATCH:{item['path']}")
    for line in (PKG / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        expected, rel = line.split("  ", 1)
        if expected != sha256(PKG / rel):
            raise RuntimeError(f"CHECKSUM_MISMATCH:{rel}")


def build() -> dict[str, object]:
    _write_manifest()
    _write_checksums()
    _verify_manifest_and_checksums()
    _write_zip(ZIP_PATH)
    _verify_zip(ZIP_PATH)
    # Prove deterministic rebuild against the same source bytes.
    with tempfile.TemporaryDirectory() as td:
        other = Path(td) / ZIP_PATH.name
        _write_zip(other)
        if other.read_bytes() != ZIP_PATH.read_bytes():
            raise RuntimeError("ZIP_NOT_REPRODUCIBLE")
    receipt = {
        "schema": "PROJECT_LANTERN_CHATGPT_PACKAGE_BUILD_RECEIPT_V1",
        "package_id": PACKAGE_ID,
        "zip_sha256": sha256(ZIP_PATH),
        "zip_size": ZIP_PATH.stat().st_size,
        "source_commit": "d0e05365883d8f670030fb1a1ff5fcd847937a77",
        "source_tree": "3b155a88967f2f7a0f4ad6fa7b32ce3cbac73da0",
        "provider_project_id": "agvhmutlrolbaijzlbqk",
        "package_validation": "PASS",
        "zip_extract_byte_equivalence": "PASS",
        "install_state": "PACKAGE_BUILT_NOT_INSTALLED",
        "runtime_consumption_state": "NOT_ESTABLISHED",
        "provider_effect": "NONE",
    }
    (PKG / "PACKAGE_BUILD_RECEIPT.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return receipt


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
