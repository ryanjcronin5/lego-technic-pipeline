"""Transform: clean raw frames, tag the focus theme and build tidy inventories."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import pandas as pd


class DataQualityError(ValueError):
    """Raised when transformed data fails a quality gate."""


@dataclass
class Transformed:
    themes: pd.DataFrame
    sets: pd.DataFrame
    part_categories: pd.DataFrame
    parts: pd.DataFrame
    inventory_parts: pd.DataFrame

    def as_tables(self) -> dict[str, pd.DataFrame]:
        return {
            "themes": self.themes,
            "sets": self.sets,
            "part_categories": self.part_categories,
            "parts": self.parts,
            "inventory_parts": self.inventory_parts,
        }


def theme_descendants(themes: pd.DataFrame, root_name: str) -> set[int]:
    """IDs of every top-level theme called ``root_name`` and all of its sub-themes."""
    roots = themes.loc[(themes["name"] == root_name) & themes["parent_id"].isna(), "id"]
    if roots.empty:
        raise DataQualityError(f"no top-level theme named {root_name!r}")

    children: dict[int, list[int]] = {}
    for theme_id, parent in themes.loc[themes["parent_id"].notna(), ["id", "parent_id"]].itertuples(
        index=False
    ):
        children.setdefault(int(parent), []).append(int(theme_id))

    found: set[int] = set()
    queue = deque(int(r) for r in roots)
    while queue:
        current = queue.popleft()
        if current in found:
            continue
        found.add(current)
        queue.extend(children.get(current, []))
    return found


def _parse_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin({"t", "true", "1"})


def transform(raw: dict[str, pd.DataFrame], focus_theme: str = "Technic") -> Transformed:
    themes = raw["themes"].copy()
    themes["id"] = themes["id"].astype(int)
    themes["parent_id"] = themes["parent_id"].astype("Int64")

    focus_ids = theme_descendants(themes, focus_theme)

    sets = raw["sets"].copy()
    sets["set_num"] = sets["set_num"].str.strip()
    sets["year"] = sets["year"].astype(int)
    sets["theme_id"] = sets["theme_id"].astype(int)
    sets["num_parts"] = pd.to_numeric(sets["num_parts"], errors="coerce").fillna(0).astype(int)
    sets["img_url"] = sets["img_url"].where(sets["img_url"].notna(), None)
    sets["is_technic"] = sets["theme_id"].isin(focus_ids)
    sets = sets.drop_duplicates("set_num", keep="last")

    # Only the latest inventory version of each focus-theme set.
    focus_set_nums = set(sets.loc[sets["is_technic"], "set_num"])
    inventories = raw["inventories"]
    latest = (
        inventories[inventories["set_num"].isin(focus_set_nums)]
        .sort_values("version")
        .drop_duplicates("set_num", keep="last")[["id", "set_num"]]
        .rename(columns={"id": "inventory_id"})
    )

    inv = raw["inventory_parts"].merge(latest, on="inventory_id", how="inner")
    inv = inv[~_parse_bool(inv["is_spare"])]
    inv = (
        inv.groupby(["set_num", "part_num", "color_id"], as_index=False)["quantity"]
        .sum()
        .astype({"color_id": int, "quantity": int})
    )

    used_parts = set(inv["part_num"])
    parts = raw["parts"][raw["parts"]["part_num"].isin(used_parts)].copy()
    parts["part_cat_id"] = parts["part_cat_id"].astype("Int64")
    if "part_material" not in parts.columns:
        parts["part_material"] = None
    parts = parts.drop_duplicates("part_num")

    result = Transformed(
        themes=themes,
        sets=sets[["set_num", "name", "year", "theme_id", "num_parts", "img_url", "is_technic"]],
        part_categories=raw["part_categories"].astype({"id": int}),
        parts=parts[["part_num", "name", "part_cat_id", "part_material"]],
        inventory_parts=inv,
    )
    check_quality(result)
    return result


def check_quality(t: Transformed) -> None:
    """Quality gates: fail the run rather than load bad data."""
    problems: list[str] = []
    if t.sets["set_num"].duplicated().any():
        problems.append("duplicate set_num values")
    if not t.sets["is_technic"].any():
        problems.append("no sets tagged with the focus theme")
    if (t.inventory_parts["quantity"] <= 0).any():
        problems.append("non-positive part quantities")
    if t.inventory_parts.duplicated(["set_num", "part_num", "color_id"]).any():
        problems.append("duplicate inventory rows")
    orphans = set(t.inventory_parts["set_num"]) - set(t.sets["set_num"])
    if orphans:
        problems.append(f"{len(orphans)} inventory rows reference unknown sets")
    if problems:
        raise DataQualityError("; ".join(problems))
