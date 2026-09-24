from icarus_engine.omnivision import (
    AdmissionRequest,
    ProvenanceDAG,
    ProvenanceEdge,
    ProvenanceNode,
    SourceCapability,
    SourceCapabilityRegistry,
    TrialLedger,
    TrialRecord,
    evaluate_admission,
)


def capability(**changes):
    values = dict(
        source_id="macro", provider="Provider", version=1, domain_classes=("macro",),
        access_class="public", epistemic_role="primary_observation", auth_mode="none",
        entitlement_state="public", health_state="healthy", rate_limit_state="within_limit",
        cost_class="free", reliability_evidence=("official_release",), timing_semantics="published_at",
        revision_semantics="versioned", freshness_policy="until_superseded",
        allowed_entities=("US_CPI",), forbidden_uses=("live_execution",), valid_from=100,
        valid_until=None, review_after=500, upstream_source_ids=(),
    )
    values.update(changes)
    return SourceCapability(**values)


def node(kind, external_id, char, as_of=150):
    return ProvenanceNode.build(
        kind=kind, external_id=external_id, as_of=as_of,
        content_hash=char * 64, metadata=(("domain", "macro"),),
    )


def link(source, target, kind, char):
    return ProvenanceEdge.build(
        kind=kind, source_node_id=source.node_id, target_node_id=target.node_id,
        run_id="stage1-integration", created_at=160, transform_id="v1",
        evidence_hashes=(char * 64,), code_hash="e" * 64, config_hash="f" * 64,
    )


def trial(**changes):
    values = dict(
        hypothesis_id="a" * 64, hypothesis_family_id="b" * 64, parent_trial_ids=(),
        generation_method="gap_forge", feature_config_hash="c" * 64,
        dataset_snapshot_hashes=("d" * 64,), train_start=10, train_end=20,
        validation_start=20, validation_end=30, holdout_start=30, holdout_end=40,
        code_hash="e" * 64, config_hash="f" * 64, decision_at=40,
        metrics=(("correlation", 0.1),), cost_assumptions=(("slippage_bps", 1.0),),
        status="rejected", rejection_reason="weak", family_memberships=("family",),
        execution_authorized=False,
    )
    values.update(changes)
    return TrialRecord.build(**values)


def test_stage1_trust_chain_replays_health_preserves_search_and_invalidates(tmp_path):
    registry = SourceCapabilityRegistry(tmp_path / "capabilities.sqlite3")
    v1 = capability(version=1, valid_from=100, health_state="healthy")
    v2 = capability(version=2, valid_from=200, health_state="quota_exhausted")
    registry.register(v1, recorded_at=100)
    registry.register(v2, recorded_at=200)

    historical = registry.as_of("macro", 150)
    current = registry.as_of("macro", 250)
    assert historical == v1
    assert current == v2
    request = AdmissionRequest(domain="macro", required_roles=("primary_observation",), entity="US_CPI")
    assert evaluate_admission(historical, request, decision_at=150).admitted is True
    assert evaluate_admission(current, request, decision_at=250).reason_code == "health_not_usable"

    graph = ProvenanceDAG()
    capability_node = node("source_capability", v1.capability_id, "1")
    raw = node("raw_evidence", "release-1", "2")
    normalized = node("normalized_observation", "cpi", "3")
    hypothesis = node("hypothesis", "hypothesis-1", "4")
    first_trial = trial()
    trial_node = node("trial", first_trial.trial_id, "5")
    for item in (capability_node, raw, normalized, hypothesis, trial_node):
        graph.add_node(item)
    graph.add_edge(link(capability_node, raw, "produced_by", "6"))
    graph.add_edge(link(raw, normalized, "normalized_from", "7"))
    graph.add_edge(link(normalized, hypothesis, "supports", "8"))
    graph.add_edge(link(hypothesis, trial_node, "tests", "9"))

    trials = TrialLedger(tmp_path / "trials.sqlite3")
    trials.record(first_trial, recorded_at=40)
    second = trial(
        feature_config_hash="1" * 64, decision_at=41, status="passed", rejection_reason=None,
    )
    trials.record(second, recorded_at=41)
    assert trials.search_burden("b" * 64)["correction_required"] is True
    assert trial_node.node_id in graph.invalidation_closure(raw.node_id)
    assert first_trial.execution_authorized is False
    assert second.execution_authorized is False


def test_stage1_common_upstream_is_explicit_not_independent():
    vendor_a = capability(source_id="vendor-a", epistemic_role="aggregator", upstream_source_ids=("official-release",))
    vendor_b = capability(source_id="vendor-b", epistemic_role="aggregator", upstream_source_ids=("official-release",))
    assert vendor_a.upstream_source_ids == vendor_b.upstream_source_ids

    graph = ProvenanceDAG()
    upstream = node("raw_evidence", "official-release", "a")
    left = node("normalized_observation", "vendor-a-normalized", "b")
    right = node("normalized_observation", "vendor-b-normalized", "c")
    for item in (upstream, left, right):
        graph.add_node(item)
    graph.add_edge(link(upstream, left, "normalized_from", "d"))
    graph.add_edge(link(upstream, right, "normalized_from", "e"))
    assert graph.shared_ancestors((left.node_id, right.node_id)) == (upstream.node_id,)


def test_stage1_negative_control_is_registrable_but_not_admissible(tmp_path):
    registry = SourceCapabilityRegistry(tmp_path / "capabilities.sqlite3")
    control = capability(
        source_id="gaming-db", domain_classes=("gaming",), epistemic_role="negative_control",
        allowed_entities=("GAME",), forbidden_uses=("live_execution", "research_evidence"),
    )
    registry.register(control, recorded_at=100)
    replay = registry.as_of("gaming-db", 150)
    decision = evaluate_admission(
        replay,
        AdmissionRequest(domain="gaming", required_roles=("negative_control",), entity="GAME"),
        decision_at=150,
    )
    assert decision.admitted is False
    assert decision.reason_code == "negative_control"
