import pytest

from icarus_engine.omnivision.provenance import ProvenanceDAG, ProvenanceEdge, ProvenanceNode


def node(kind, external_id, seed):
    return ProvenanceNode.build(
        kind=kind,
        external_id=external_id,
        as_of=100,
        content_hash=(seed * 64)[:64],
        metadata=(("domain", "macro"),),
    )


def edge(source, target, kind="derived_from", seed="e"):
    return ProvenanceEdge.build(
        kind=kind,
        source_node_id=source.node_id,
        target_node_id=target.node_id,
        run_id="run-1",
        created_at=110,
        transform_id="transform-v1",
        evidence_hashes=((seed * 64)[:64],),
        code_hash="c" * 64,
        config_hash="d" * 64,
    )


def test_node_and_edge_identity_are_deterministic():
    left = node("raw_evidence", "raw-1", "a")
    right = node("raw_evidence", "raw-1", "a")
    assert left == right
    assert len(left.node_id) == 64
    derived = node("normalized_observation", "norm-1", "b")
    assert edge(left, derived) == edge(left, derived)


def test_rejects_unknown_kinds_bad_hashes_self_edges_and_missing_nodes():
    with pytest.raises(ValueError):
        node("mystery", "x", "a")
    with pytest.raises(ValueError):
        ProvenanceNode.build(kind="raw_evidence", external_id="x", as_of=1, content_hash="bad", metadata=())

    graph = ProvenanceDAG()
    raw = node("raw_evidence", "raw", "a")
    graph.add_node(raw)
    with pytest.raises(ValueError):
        edge(raw, raw)
    missing = node("normalized_observation", "missing", "b")
    with pytest.raises(ValueError):
        graph.add_edge(edge(raw, missing))


def test_two_vendors_with_one_upstream_are_not_independent():
    upstream = node("raw_evidence", "official-release", "a")
    vendor_a = node("normalized_observation", "vendor-a", "b")
    vendor_b = node("normalized_observation", "vendor-b", "c")
    graph = ProvenanceDAG()
    for item in (upstream, vendor_a, vendor_b):
        graph.add_node(item)
    graph.add_edge(edge(upstream, vendor_a, "normalized_from", "1"))
    graph.add_edge(edge(upstream, vendor_b, "normalized_from", "2"))
    assert graph.shared_ancestors((vendor_a.node_id, vendor_b.node_id)) == (upstream.node_id,)


def test_recursive_invalidation_finds_all_dependents_without_deleting_history():
    kinds = (
        "raw_evidence", "normalized_observation", "derived_feature",
        "hypothesis", "trial",
    )
    items = [node(kind, f"n-{index}", str(index + 1)) for index, kind in enumerate(kinds)]
    graph = ProvenanceDAG()
    for item in items:
        graph.add_node(item)
    for index in range(len(items) - 1):
        graph.add_edge(edge(items[index], items[index + 1], "depends_on", str(index + 1)))
    closure = graph.invalidation_closure(items[0].node_id)
    assert closure == tuple(item.node_id for item in items)
    assert graph.descendants(items[0].node_id) == tuple(item.node_id for item in items[1:])
    assert graph.ancestors(items[-1].node_id) == tuple(item.node_id for item in items[:-1])


def test_dependency_cycle_is_rejected_but_peer_contradiction_is_allowed():
    a = node("derived_feature", "a", "a")
    b = node("derived_feature", "b", "b")
    graph = ProvenanceDAG()
    graph.add_node(a); graph.add_node(b)
    graph.add_edge(edge(a, b, "derived_from", "1"))
    with pytest.raises(ValueError):
        graph.add_edge(edge(b, a, "depends_on", "2"))

    peer = ProvenanceDAG()
    peer.add_node(a); peer.add_node(b)
    peer.add_edge(edge(a, b, "contradicts", "3"))
    peer.add_edge(edge(b, a, "contradicts", "4"))
    assert len(peer.edges) == 2


def test_duplicate_edge_id_with_different_content_rejects():
    a = node("raw_evidence", "a", "a")
    b = node("normalized_observation", "b", "b")
    graph = ProvenanceDAG(); graph.add_node(a); graph.add_node(b)
    original = edge(a, b, "normalized_from", "1")
    graph.add_edge(original)
    graph.add_edge(original)
    tampered = object.__new__(ProvenanceEdge)
    for name, value in original.__dict__.items():
        object.__setattr__(tampered, name, value)
    object.__setattr__(tampered, "kind", "supports")
    with pytest.raises(ValueError):
        graph.add_edge(tampered)


def test_snapshot_hash_is_order_independent_for_insert_order():
    a = node("raw_evidence", "a", "a")
    b = node("normalized_observation", "b", "b")
    link = edge(a, b, "normalized_from", "1")
    first = ProvenanceDAG(); first.add_node(a); first.add_node(b); first.add_edge(link)
    second = ProvenanceDAG(); second.add_node(b); second.add_node(a); second.add_edge(link)
    assert first.snapshot_hash() == second.snapshot_hash()
