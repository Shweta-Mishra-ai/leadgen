from __future__ import annotations

from leadgen.models import RawLead, ScoredLead


def make_lead(url: str, score: int = 3) -> ScoredLead:
    raw = RawLead(source="test", title="Need a GenAI freelancer", url=url, snippet="budget ready")
    return ScoredLead.from_raw(raw, score=score)


def test_insert_new_leads(temp_store):
    leads = [make_lead("https://example.com/1"), make_lead("https://example.com/2")]
    inserted = temp_store.insert_new(leads)
    assert inserted == 2
    assert temp_store.count() == 2


def test_dedup_by_url(temp_store):
    lead = make_lead("https://example.com/dup")
    first = temp_store.insert_new([lead])
    second = temp_store.insert_new([lead])  # same URL again
    assert first == 1
    assert second == 0
    assert temp_store.count() == 1


def test_partial_dedup_in_same_batch(temp_store):
    a = make_lead("https://example.com/a")
    b = make_lead("https://example.com/b")
    temp_store.insert_new([a])
    inserted = temp_store.insert_new([a, b])  # a is dup, b is new
    assert inserted == 1
    assert temp_store.count() == 2


def test_top_leads_ordered_by_score_desc(temp_store):
    temp_store.insert_new([
        make_lead("https://example.com/low", score=1),
        make_lead("https://example.com/high", score=9),
        make_lead("https://example.com/mid", score=4),
    ])
    top = temp_store.top_leads(limit=10)
    scores = [row["score"] for row in top]
    assert scores == sorted(scores, reverse=True)
    assert top[0]["url"] == "https://example.com/high"


def test_export_csv_writes_all_rows(temp_store, tmp_path):
    temp_store.insert_new([make_lead("https://example.com/1"), make_lead("https://example.com/2")])
    out = str(tmp_path / "out.csv")
    temp_store.export_csv(out)
    with open(out) as f:
        lines = f.readlines()
    assert len(lines) == 3  # header + 2 rows
