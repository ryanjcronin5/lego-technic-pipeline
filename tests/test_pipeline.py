from sqlalchemy import text

from technic import analytics
from technic.load import load
from technic.pipeline import main
from technic.transform import transform
from tests.conftest import FIXTURES


def count(engine, table):
    with engine.connect() as conn:
        return conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()


def test_load_counts(loaded):
    assert count(loaded, "sets") == 6
    assert count(loaded, "inventory_parts") == 11
    assert count(loaded, "pipeline_runs") == 1


def test_reload_is_idempotent_and_logs_each_run(loaded, raw):
    load(loaded, transform(raw), source="fixtures")
    assert count(loaded, "sets") == 6
    assert count(loaded, "pipeline_runs") == 2


def test_cli_runs_from_local_source(tmp_path):
    url = f"sqlite:///{(tmp_path / 'cli.db').as_posix()}"
    assert main(["--source", str(FIXTURES), "--database-url", url]) == 0


def test_cli_reports_failure(tmp_path):
    url = f"sqlite:///{(tmp_path / 'cli.db').as_posix()}"
    assert main(["--source", str(tmp_path), "--database-url", url]) == 1


def test_summary(loaded):
    s = analytics.summary(loaded)
    assert s["total_sets"] == 6
    assert s["technic_sets"] == 5
    assert (s["first_technic_year"], s["latest_technic_year"]) == (1980, 2020)
    assert s["distinct_technic_parts"] == 5
    assert s["last_refreshed"].utcoffset().total_seconds() == 0


def test_trends_exclude_empty_sets(loaded):
    by_year = {r["year"]: r for r in analytics.yearly_trends(loaded)}
    assert by_year[2020]["technic_sets"] == 1  # 9999-1 has 0 parts
    assert by_year[2017]["technic_avg_parts"] is None
    assert by_year[2017]["all_avg_parts"] == 7541.0


def test_top_parts(loaded):
    top = analytics.top_parts(loaded, limit=2)
    assert [(p["part_num"], p["total_quantity"], p["set_count"]) for p in top] == [
        ("2780", 120, 3),
        ("32523", 30, 3),
    ]


def test_similar_sets_ranked_by_jaccard(loaded):
    similar = analytics.similar_sets(loaded, "42083-1")
    assert [(s["set_num"], s["similarity"]) for s in similar] == [
        ("8880-1", 0.667),
        ("42115-1", 0.5),
    ]


def test_compare_sets(loaded):
    c = analytics.compare_sets(loaded, "42083-1", "42115-1")
    assert c["shared_parts"] == 2
    assert c["similarity"] == 0.5
    assert c["shared"][0] == {
        "part_num": "2780",
        "name": "Technic Pin with Friction",
        "qty_a": 50,
        "qty_b": 40,
    }
