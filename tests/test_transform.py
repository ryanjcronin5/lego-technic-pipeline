import pandas as pd
import pytest

from technic.extract import SchemaError, read_all
from technic.transform import DataQualityError, theme_descendants, transform


def test_theme_descendants_walks_nested_subthemes(raw):
    assert theme_descendants(raw["themes"], "Technic") == {1, 11, 12}


def test_unknown_focus_theme_fails(raw):
    with pytest.raises(DataQualityError, match="no top-level theme"):
        theme_descendants(raw["themes"], "Bionicle")


def test_sets_are_tagged_by_theme_tree(raw):
    sets = transform(raw).sets.set_index("set_num")
    assert sets.loc["42115-1", "is_technic"]  # grandchild theme
    assert not sets.loc["75192-1", "is_technic"]
    assert int(sets["is_technic"].sum()) == 5


def test_uses_latest_inventory_version_and_drops_spares(raw):
    inv = transform(raw).inventory_parts
    bugatti = inv[inv["set_num"] == "42083-1"].set_index("part_num")
    assert "3001" not in bugatti.index  # only in the superseded v1 inventory
    assert bugatti.loc["2780", "quantity"] == 50  # 2 spares excluded


def test_inventories_only_for_focus_theme(raw):
    inv = transform(raw).inventory_parts
    assert "75192-1" not in set(inv["set_num"])


def test_parts_limited_to_those_used(raw):
    parts = transform(raw).parts
    assert set(parts["part_num"]) == {"32523", "2780", "6558", "32062", "3001"}


def test_missing_column_raises_schema_error(tmp_path):
    from tests.conftest import FIXTURES

    for f in FIXTURES.iterdir():
        (tmp_path / f.name).write_text(f.read_text())
    sets = pd.read_csv(tmp_path / "sets.csv").drop(columns=["num_parts"])
    sets.to_csv(tmp_path / "sets.csv", index=False)
    with pytest.raises(SchemaError, match="num_parts"):
        read_all(tmp_path)


def test_quality_gate_rejects_bad_quantities(raw):
    raw["inventory_parts"].loc[1, "quantity"] = -3
    with pytest.raises(DataQualityError, match="non-positive"):
        transform(raw)
