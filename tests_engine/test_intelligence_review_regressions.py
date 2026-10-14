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
