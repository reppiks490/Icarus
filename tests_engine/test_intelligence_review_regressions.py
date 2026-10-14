from dataclasses import replace
import sqlite3

import pytest

from icarus_engine.intelligence_collaboration import (
    CollaborationIntegrityError, IntelligenceCollaboration, TransitionRequest,
    WorkRequest, build_request_event,
)
from icarus_engine.intelligence_fabric import IntelligenceFabric, IntelligenceEvent
from icarus_engine.intelligence_delivery import IntelligenceDeliveryPlane, SubscriptionSpec

T = '2026-10-14T05:00:00Z'
LATER = '2026-10-14T05:00:00.500000Z'
BEFORE = '2026-10-14T04:59:59Z'


def request(**kwargs):
    return replace(WorkRequest('requester', 'agent', 'principal', 'worker',
                               'research', 'root', 'Review this work'), **kwargs)


def transition(r, head, kind='accepted', actor='worker', op='accept', actor_kind='agent'):
    return TransitionRequest(r.work_id(), kind, actor, actor_kind, op, head)


@pytest.mark.parametrize('later_root', [False, True])
@pytest.mark.parametrize('field,value', [('actor_principal', 'other'), ('actor_kind', 'human')])
def test_root_replay_rejects_actor_requester_mismatch(later_root, field, value):
    with IntelligenceFabric() as f:
        c = IntelligenceCollaboration(f)
        r = request()
        e = build_request_event(r, observed_at=T, received_at=T, actor_kind='agent')
        if later_root:
            f.publish(e)
        payload = dict(e.payload, **{field: value})
        forged = replace(e, payload=payload, **{'source' if field == 'actor_principal' else 'source_kind': value})
        f.publish(forged)
        with pytest.raises(CollaborationIntegrityError, match='requester'):
            c.snapshot(r.work_id())


@pytest.mark.parametrize('parent_transition', ['started', 'completed', 'cancelled'])
def test_child_retry_survives_parent_progress(parent_transition):
    with IntelligenceFabric() as f:
        c = IntelligenceCollaboration(f)
        r = request()
        root = c.create_work(r, observed_at=T, received_at=T)
        accepted = c.append_transition(transition(r, root['event_id']), observed_at=T, received_at=T)
        child = request(requester_principal='worker', target_id='subworker', idempotency_key='child',
                        parent_work_id=r.work_id(), parent_event_id=accepted['event_id'])
        created = c.create_work(child, observed_at=T, received_at=T)
        actor = 'requester' if parent_transition == 'cancelled' else 'worker'
        c.append_transition(transition(r, accepted['event_id'], parent_transition, actor, 'progress'),
                            observed_at=T, received_at=T)
        retry = c.create_work(child, observed_at=T, received_at=T)
        assert retry['conflict_code'] == 'duplicate_root'
        assert retry['original_event_id'] == created['event_id']
        conflict = c.create_work(replace(child, objective='Changed objective'), observed_at=T, received_at=T)
        assert conflict['conflict_code'] == 'conflicting_root'
        assert c.snapshot(child.work_id()).objective == child.objective


@pytest.mark.parametrize('retry_time', [T, LATER])
def test_operation_retry_references_first_applied_occurrence(retry_time):
    with IntelligenceFabric() as f:
        c = IntelligenceCollaboration(f)
        r = request()
        root = c.create_work(r, observed_at=T, received_at=T)
        bad = c.append_transition(transition(r, root['event_id'], actor='other'), observed_at=T, received_at=T)
        good_request = transition(r, root['event_id'])
        good = c.append_transition(good_request, observed_at=T, received_at=T)
        retry = c.append_transition(good_request, observed_at=T, received_at=retry_time)
        assert bad['conflict_code'] == 'actor_not_permitted'
        assert retry['conflict_code'] == 'duplicate_operation'
        assert retry['original_event_id'] == good['event_id']
        assert retry['applied'] is False


def test_exact_rejected_retry_preserves_semantic_failure():
    with IntelligenceFabric() as f:
        c = IntelligenceCollaboration(f)
        r = request()
        root = c.create_work(r, observed_at=T, received_at=T)
        bad = transition(r, root['event_id'], actor='other')
        first = c.append_transition(bad, observed_at=T, received_at=T)
        retry = c.append_transition(bad, observed_at=T, received_at=T)
        assert retry['conflict_code'] == first['conflict_code'] == 'actor_not_permitted'
        assert 'original_event_id' not in retry


def test_fractional_deadline_is_after_whole_second_root():
    with IntelligenceFabric() as f:
        c = IntelligenceCollaboration(f)
        r = request(deadline=LATER)
        assert c.create_work(r, observed_at=T, received_at=T)['applied']
        assert c.snapshot(r.work_id(), as_of=T).deadline_passed is False
        assert c.snapshot(r.work_id(), as_of=LATER).deadline_passed is True


def test_expiry_cannot_precede_fractional_deadline():
    with IntelligenceFabric() as f:
        c = IntelligenceCollaboration(f)
        r = request(deadline=LATER)
        root = c.create_work(r, observed_at=BEFORE, received_at=BEFORE)
        early = c.append_transition(transition(r, root['event_id'], 'expired', 'clock', 'early', 'system'),
                                    observed_at=T, received_at=T)
        assert early['conflict_code'] == 'deadline_violation'
        assert early['state'] == 'OPEN'
        valid = c.append_transition(transition(r, root['event_id'], 'expired', 'clock', 'valid', 'system'),
                                    observed_at=LATER, received_at=LATER)
        assert valid['applied'] and valid['state'] == 'EXPIRED'


def test_transition_receive_time_can_have_fraction_after_whole_observation():
    with IntelligenceFabric() as f:
        c = IntelligenceCollaboration(f)
        r = request()
        root = c.create_work(r, observed_at=T, received_at=T)
        assert c.append_transition(transition(r, root['event_id']), observed_at=T, received_at=LATER)['applied']


def event(received=T, expires=None):
    return IntelligenceEvent('research', 'worker', 'agent', 'research', 'research:test',
                             'Review', 'Test', BEFORE, received, expires_at=expires)


def test_fabric_queries_and_inbox_use_exact_chronological_order():
    with IntelligenceFabric() as f:
        past = f.publish(event(T, LATER))
        future = f.publish(event(LATER))
        assert [x['event_id'] for x in f.query(before=T)] == [past['event_id']]
        assert [x['event_id'] for x in f.query(after=T)] == [future['event_id']]
        assert [x['event_id'] for x in f.inbox(as_of=T)] == [past['event_id']]
        assert past['event_id'] not in [x['event_id'] for x in f.inbox(as_of=LATER)]


def test_delivery_fractional_lease_and_retry_boundaries():
    conn = sqlite3.connect(':memory:')
    try:
        f = IntelligenceFabric(conn)
        d = IntelligenceDeliveryPlane(conn)
        past = f.publish(event())
        future = f.publish(event(LATER))
        d.register_consumer('worker', as_of=BEFORE)
        d.create_subscription(SubscriptionSpec('sub', 1, 'broadcast', consumer_id='worker',
                                               retry_delay_seconds=0), as_of=BEFORE)
        batch = d.claim('sub', 1, 'worker', as_of=T, lease_seconds=1, limit=10)
        assert [x['event_id'] for x in batch] == [past['event_id']]
        d.nack(batch[0]['delivery_id'], 'worker', batch[0]['lease_token'], as_of=LATER)
        assert d.claim('sub', 1, 'worker', as_of=T) == []
        lease = d.claim('sub', 1, 'worker', as_of=LATER, limit=1)[0]
        boundary = '2026-10-14T05:00:30Z'
        assert d.recover_expired(as_of=boundary) == []
        assert d.metrics('sub', 1, as_of=boundary)['active_leases'] == 1
        assert d.ack(lease['delivery_id'], 'worker', lease['lease_token'], as_of=boundary)['state'] == 'ACKED'
    finally:
        conn.close()


def test_reopened_legacy_journal_keeps_ids_and_microsecond_boundaries(tmp_path):
    path = str(tmp_path / 'history.sqlite3')
    micro = '2026-10-14T05:00:00.000001Z'
    with IntelligenceFabric(path) as f:
        old = f.publish(event(T))
        new = f.publish(event(micro))
        material = f.get(old['event_id'])
    with IntelligenceFabric(path) as f:
        assert f.get(old['event_id']) == material
        assert f.publish(event(T))['idempotent'] is True
        assert [x['event_id'] for x in f.query(before=T)] == [old['event_id']]
        assert [x['event_id'] for x in f.query(after=T, before=micro)] == [new['event_id']]


def test_byte_identical_conflicting_operation_preserves_conflict():
    with IntelligenceFabric() as f:
        c = IntelligenceCollaboration(f)
        r = request()
        root = c.create_work(r, observed_at=T, received_at=T)
        c.append_transition(transition(r, root['event_id']), observed_at=T, received_at=T)
        conflict = transition(r, root['event_id'], kind='started')
        first = c.append_transition(conflict, observed_at=T, received_at=T)
        retry = c.append_transition(conflict, observed_at=T, received_at=T)
        assert first['conflict_code'] == retry['conflict_code'] == 'conflicting_operation'


def test_inbox_orders_equal_scores_by_exact_receipt_time():
    with IntelligenceFabric() as f:
        f.publish(event(T))
        later = f.publish(event(LATER))
        assert f.inbox(as_of='2026-10-14T05:00:01Z', limit=1)[0]['event_id'] == later['event_id']


@pytest.mark.parametrize('field', ['assets', 'tags', 'causation_ids', 'evidence_ids'])
def test_mapping_rejects_string_collections(field):
    with IntelligenceFabric() as f:
        material = event().normalized()
        material[field] = 'ES'
        with pytest.raises(ValueError, match='collection'):
            f.publish(material)
        assert f.replay() == []


@pytest.mark.parametrize('sql', [
    "UPDATE fabric_events SET channel='wrong'",
    "UPDATE fabric_events SET source='wrong'",
    "UPDATE fabric_events SET severity=5",
    "UPDATE fabric_events SET received_at='2026-10-14T04:00:00Z'",
    "INSERT INTO fabric_assets SELECT event_id,'FAKE' FROM fabric_events",
    "INSERT INTO fabric_tags SELECT event_id,'FAKE' FROM fabric_events",
])
def test_delivery_rejects_corrupt_routing_projection(sql):
    conn = sqlite3.connect(':memory:')
    try:
        f, d = IntelligenceFabric(conn), IntelligenceDeliveryPlane(conn)
        f.publish(event())
        conn.execute(sql)
        conn.commit()
        d.register_consumer('worker', as_of=T)
        d.create_subscription(SubscriptionSpec('sub', 1, 'broadcast', consumer_id='worker'), as_of=T)
        with pytest.raises(ValueError, match='integrity'):
            d.claim('sub', 1, 'worker', as_of=T)
        assert conn.execute('SELECT COUNT(*) FROM fabric_deliveries').fetchone()[0] == 0
    finally:
        conn.close()


@pytest.mark.parametrize('ending', ['ack', 'nack', 'recover_expired'])
def test_receipts_preserve_lease_audit_after_projection_clears(ending):
    import hashlib
    conn = sqlite3.connect(':memory:')
    try:
        f, d = IntelligenceFabric(conn), IntelligenceDeliveryPlane(conn)
        f.publish(event())
        d.register_consumer('worker', as_of=T)
        d.create_subscription(SubscriptionSpec('sub', 1, 'broadcast', consumer_id='worker'), as_of=T)
        lease = d.claim('sub', 1, 'worker', as_of=T)[0]
        if ending == 'recover_expired':
            d.recover_expired(as_of=lease['lease_expires_at'])
        else:
            getattr(d, ending)(lease['delivery_id'], 'worker', lease['lease_token'], as_of=LATER)
        receipts = d.receipts(delivery_id=lease['delivery_id'])
        names = {'LEASED', {'ack': 'ACKED', 'nack': 'NACKED', 'recover_expired': 'LEASE_EXPIRED'}[ending]}
        state = None
        for receipt in receipts:
            audit = receipt['details']['delivery_audit']
            assert audit['prior_state'] == state
            state = audit['new_state']
            if receipt['transition'] in {'NACKED', 'LEASE_EXPIRED'}:
                assert audit['new_state'] == 'PENDING'
            if receipt['transition'] in names:
                audit = receipt['details']['delivery_audit']
                assert audit['lease_token_sha256'] == hashlib.sha256(lease['lease_token'].encode()).hexdigest()
                assert audit['lease_expires_at'] == lease['lease_expires_at']
                assert audit['leased_at'] == T
                assert audit['journal_sequence'] == lease['journal_sequence']
                assert 'prior_state' in audit and 'new_state' in audit
                assert lease['lease_token'] not in str(receipt)
    finally:
        conn.close()


def test_http_cap_stops_reading_before_entire_upload():
    import asyncio
    from starlette.requests import Request
    from icarus_engine.intelligence_gateway import _strict_json_request, GatewayRequestError
    chunks_read = []
    async def receive():
        chunks_read.append(1)
        return {'type': 'http.request', 'body': b'x' * 100, 'more_body': len(chunks_read) < 3}
    req = Request({'type': 'http', 'method': 'POST', 'path': '/', 'headers': []}, receive)
    with pytest.raises(GatewayRequestError, match='too large'):
        asyncio.run(_strict_json_request(req, max_bytes=32))
    assert len(chunks_read) == 1


def test_unicode_bearer_is_compared_safely():
    from icarus_engine.intelligence_gateway import bearer_matches
    assert bearer_matches('é', 'secret') is False
    assert bearer_matches('é', 'é') is True


def test_exact_conflicting_root_retry_stays_conflicting():
    with IntelligenceFabric() as f:
        c, r = IntelligenceCollaboration(f), request()
        c.create_work(r, observed_at=T, received_at=T)
        changed = replace(r, objective='Different request')
        c.create_work(changed, observed_at=T, received_at=T)
        assert c.create_work(changed, observed_at=T, received_at=T)['conflict_code'] == 'conflicting_root'


def test_child_discovery_ignores_rejected_parent_claim():
    with IntelligenceFabric() as f:
        c, r = IntelligenceCollaboration(f), request()
        c.create_work(r, observed_at=T, received_at=T)
        fake = replace(r, parent_work_id='0' * 64, parent_event_id='missing')
        c.create_work(fake, observed_at=T, received_at=T)
        assert c.children('0' * 64) == []


@pytest.mark.parametrize('kind,data', [('challenge', {'challenge_id': 'q'}),
                                      ('challenge_response', {'challenge_id': 'q'})])
def test_challenge_requires_substantive_material(kind, data):
    with IntelligenceFabric() as f:
        c, r = IntelligenceCollaboration(f), request()
        root = c.create_work(r, observed_at=T, received_at=T)
        accepted = c.append_transition(transition(r, root['event_id']), observed_at=T, received_at=T)
        head = accepted['event_id']
        if kind == 'challenge_response':
            challenged = c.append_transition(TransitionRequest(r.work_id(), 'challenge', 'requester', 'agent',
                'q', head, {'challenge_id': 'q', 'claim': 'Show the evidence'}), observed_at=T, received_at=T)
            head = challenged['event_id']
        actor = 'requester' if kind == 'challenge' else 'worker'
        result = c.append_transition(TransitionRequest(r.work_id(), kind, actor, 'agent', 'empty', head, data),
                                     observed_at=T, received_at=T)
        assert result['applied'] is False
        assert result['conflict_code'] == 'challenge_mismatch'


def test_dead_letter_requeue_audit_states():
    conn = sqlite3.connect(':memory:')
    try:
        f, d = IntelligenceFabric(conn), IntelligenceDeliveryPlane(conn)
        f.publish(event())
        d.register_consumer('worker', as_of=T)
        d.create_subscription(SubscriptionSpec('sub', 1, 'broadcast', consumer_id='worker', max_attempts=1), as_of=T)
        lease = d.claim('sub', 1, 'worker', as_of=T)[0]
        d.nack(lease['delivery_id'], 'worker', lease['lease_token'], as_of=LATER)
        d.requeue_dead_lettered(lease['delivery_id'], as_of=LATER)
        state = None
        for receipt in d.receipts(delivery_id=lease['delivery_id']):
            audit = receipt['details']['delivery_audit']
            assert audit['prior_state'] == state
            state = audit['new_state']
            if receipt['transition'] == 'NACKED':
                assert state == 'DEAD_LETTERED'
            if receipt['transition'] == 'REQUEUED':
                assert state == 'PENDING'
        assert state == 'PENDING'
    finally:
        conn.close()


def test_invalid_unicode_bearer_is_rejected_without_exception():
    from icarus_engine.intelligence_gateway import bearer_matches
    assert bearer_matches('\ud800', 'secret') is False
