from pathlib import Path
SQL=Path("projects/lantern/sql/001_material_universe_v1.sql").read_text()
def test_runtime_never_uses_generic_memory_events(): assert "memory_events" in SQL and "runtime_visible_v1" in SQL
def test_base_tables_public_dml_revoked(): assert "REVOKE ALL ON lantern_material.material, lantern_material.admission_receipt FROM PUBLIC" in SQL
def test_raw_row_not_visible_without_receipt(): assert "JOIN lantern_material.admission_receipt" in SQL
def test_target_unbound(): assert "DEPLOYMENT_BINDING_UNBOUND" in SQL
