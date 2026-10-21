"""Selected market diagnostics cannot acquire data or start subscriptions."""
import copy
import threading
from collections import defaultdict, deque
from types import SimpleNamespace

import pytest

from icarus_engine.feeds.databento import Databento, TradeTick
from icarus_engine.feeds.yahoo import Yahoo
from icarus_engine.paper_workspaces import SharedFeed
from icarus_engine.workspace_market_data import snapshot


def trap(*_args, **_kwargs):
    raise AssertionError('diagnostics must not call the provider')


def owner():
    feed=Databento.__new__(Databento)
    feed._lock=threading.RLock()
    feed.dataset='GLBX.MDP3';feed.roll_rule='v'
    feed._meta={'NQ':{'resolved_raw_symbol':'NQZ6','core_session_ok':True},'ES':{'resolved_raw_symbol':'ESZ6'}}
    feed._trades=defaultdict(deque,{'NQ':deque([TradeTick(100,100_000_000_000,101,2),TradeTick(101,101_000_000_000,102,3)]),
                                   'ES':deque([TradeTick(100,100_000_000_000,501,1)])})
    feed._depth=defaultdict(deque,{('NQ','mbp-10'):deque([{'price':99,'levels':[{'bid_px':98}]}]),
                                 ('NQ','mbo'):deque([{'price':97,'action':'A'}]),
                                 ('ES','mbp-10'):deque([{'price':499}])})
    feed._depth_errors={};feed._depth_error_code={};feed._core_error_code=None
    feed._core_broken=False;feed._depth_broken=set()
    feed._live_started={'NQ'};feed._depth_live_symbols={'mbp-10':{'NQ'}}
    for name in ['meta','capabilities','trades','depth_events','start_live','_prepare_depth_live','mbo_snapshot']:
        setattr(feed,name,trap)
    return feed


def runner(feed,ticker='NQ'):
    return SimpleNamespace(feed=feed,symbol='MNQ' if ticker=='NQ' else 'MES',spec=SimpleNamespace(ticker=ticker),lock=threading.RLock())


@pytest.mark.parametrize('wrapped',[False,True])
def test_cached_diagnostics_use_actual_owner_symbol_without_provider_methods(wrapped):
    feed=owner();r=runner(SharedFeed(feed) if wrapped else feed)
    before=(set(feed._trades),set(feed._depth))
    ticks=snapshot(r,'ticks',limit=1,now=105)
    assert ticks['asset']=='MNQ' and ticks['provider_symbol']=='NQ'
    assert [row['price'] for row in ticks['ticks']]==[102]
    assert ticks['cached_only'] is True and ticks['acquisition_requested'] is False
    assert snapshot(r,'depth',schema='mbp-10')['events'][0]['price']==99
    assert snapshot(r,'depth',schema='mbo')['events'][0]['price']==97
    caps=snapshot(r,'capabilities')
    assert caps['metadata']['resolved_raw_symbol']=='NQZ6'
    assert caps['capabilities']['mbo_snapshot'] is False
    assert before==(set(feed._trades),set(feed._depth))
    ticks['ticks'][0]['price']=999
    assert feed._trades['NQ'][-1].price==102


def test_cached_depth_is_detached_and_missing_symbol_does_not_create_buffers():
    feed=owner();r=runner(feed)
    result=snapshot(r,'depth');result['events'][0]['levels'][0]['bid_px']=0
    assert feed._depth[('NQ','mbp-10')][0]['levels'][0]['bid_px']==98
    before=copy.deepcopy(dict(feed._meta)),set(feed._trades),set(feed._depth)
    missing=runner(feed,'6E')
    assert snapshot(missing,'ticks')['ticks']==[]
    assert snapshot(missing,'depth')['events']==[]
    assert snapshot(missing,'capabilities')['metadata'].get('core_session_ok') is None
    assert before==(feed._meta,set(feed._trades),set(feed._depth))


@pytest.mark.parametrize('provider',[SimpleNamespace(meta=trap,capabilities=trap,trades=trap,depth_events=trap),Yahoo.__new__(Yahoo)])
def test_unknown_or_unlocked_provider_is_explicitly_unavailable(provider):
    provider._meta={'NQ':{'regularMarketPrice':888}}
    provider.meta=trap
    result=snapshot(runner(provider),'capabilities')
    assert result['available'] is False and result['metadata']=={}
    assert 'core_session_ok' not in result['metadata']
    assert snapshot(runner(provider),'ticks')['ticks']==[]


@pytest.mark.parametrize('resource,kwargs',[('snapshot',{}),('depth',{'schema':'bad'}),('ticks',{'limit':0}),('ticks',{'limit':10001}),('ticks',{'limit':True})])
def test_invalid_cached_diagnostic_request_rejects_without_provider_access(resource,kwargs):
    with pytest.raises(ValueError):snapshot(runner(owner()),resource,**kwargs)
