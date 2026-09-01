import re
from pathlib import Path

SQL = Path("projects/lantern/sql/001_material_universe_v1.sql").read_text()
APPEND = SQL.split(
    "CREATE OR REPLACE FUNCTION lantern_material.append_material_v1(", 1
)[1].split("END $$;", 1)[0]


def test_plpgsql_rowtype_variables_do_not_collide_with_recursive_genesis_aliases():
    declaration = APPEND.split("BEGIN", 1)[0]
    rowtype_variables = set(
        re.findall(r"\b([A-Za-z_]\w*)\s+lantern_material\.\w+%ROWTYPE", declaration)
    )
    genesis_aliases = set(
        re.findall(r"\bFROM\s+genesis\s+([A-Za-z_]\w*)\b", APPEND)
    )
    assert rowtype_variables.isdisjoint(genesis_aliases)
