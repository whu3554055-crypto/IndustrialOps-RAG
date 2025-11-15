from apps.retrieval.hybrid.rrf import reciprocal_rank_fusion


def test_rrf_merges_two_lists():
    a = ["d1", "d2", "d3"]
    b = ["d2", "d4", "d1"]
    merged = reciprocal_rank_fusion([a, b], k=60, top_n=3)
    ids = [x[0] for x in merged]
    assert "d1" in ids
    assert "d2" in ids
