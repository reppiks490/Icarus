"""Shared paper selection for CC1–CC4, using canonical contract economics.

Original identities come from the shipped start-yahoo.ps1 launcher. The added
ten-family selection is the already reviewed corpus/dashboard expansion; it
does not declare ten newly listed exchange products or a free licensed feed.
"""
from .assets import REGISTRY
from .futures_catalog import FUTURES_PRODUCTS

ORIGINAL_ASSETS = (
    'NQ', 'BTC', 'MNQ', 'MES', 'ES', 'YM', 'MYM', 'RTY', 'M2K',
    'GC', 'MGC', 'SI', 'SIL', 'PL', 'PA', 'MBT',
)
ADDED_FAMILIES = ('CL', 'NG', 'HG', '6E', '6J', '6B', '6A', 'ZN', 'ZB', 'BTCF')


def dashboard_assets():
    """Return stable, unique original + added family/micro paper identities."""
    micros = [p.root for p in FUTURES_PRODUCTS.values()
              if p.full_root in ADDED_FAMILIES and p.root != p.full_root]
    return list(dict.fromkeys((*ORIGINAL_ASSETS, 'ETH', 'SOL', *ADDED_FAMILIES, *micros)))


def universe():
    """Project catalog facts without upgrading data rights or order authority."""
    families = []
    for root in ADDED_FAMILIES:
        product = FUTURES_PRODUCTS[root]
        families.append({
            'root': root, 'name': product.name, 'exchange': product.exchange,
            'micros': [p.root for p in FUTURES_PRODUCTS.values()
                       if p.full_root == root and p.root != root],
            'tick_size': product.tick_size, 'tick_value': product.tick_value,
            'point_value': product.point_value, 'provider_symbol': product.provider_symbol,
            'data_status': 'REQUIRES_FEED_OBSERVATION', 'execution_authorized': False,
        })
    return {'schema_version': 'icarus.workspace-universe.v1',
            'original_assets': list(ORIGINAL_ASSETS), 'original_asset_count': len(ORIGINAL_ASSETS),
            'default_assets': dashboard_assets(), 'families': families,
            'catalog_asset_count': len(REGISTRY), 'fresh_feed_access_verified': False,
            'profitability_verified': False, 'execution_authorized': False}
