"""v0.2 图谱存储."""

from apps.retrieval.graph.store import expand_doc_ids, load_graph, match_entity_ids


def test_load_graph_has_edges() -> None:
    g = load_graph()
    assert len(g.get("edges", [])) >= 3


def test_match_p101_e01() -> None:
    ids = match_entity_ids("P-101 故障码 E01 怎么处理")
    assert "device:P-101" in ids or "fault:E01" in ids
    docs = expand_doc_ids(ids)
    assert any("pump" in d for d in docs)
