import pytest

from icarus_bridge.brokers.shadow import ShadowBroker


@pytest.mark.parametrize(
    "side,take_profit,stop_loss,exit_price,winning_leg",
    [
        ("buy", 110, 90, 111, 0),   # long take profit
        ("buy", 110, 90, 89, 1),    # long stop
        ("sell", 90, 110, 89, 0),   # short take profit
        ("sell", 90, 110, 111, 1),  # short stop
    ],
)
def test_bracket_exits_fill_once_and_cancel_oco_sibling(
    side, take_profit, stop_loss, exit_price, winning_leg,
):
    broker = ShadowBroker(prices={"ES": 100})

    parent = broker.submit_bracket("ES", side, 2, take_profit, stop_loss)
    assert parent.status == "filled"
    assert broker.position("ES") == (2 if side == "buy" else -2)
    take_profit_leg, stop_leg = parent.legs
    assert {leg.status for leg in parent.legs} == {"accepted"}

    broker.set_price("ES", exit_price)

    winner = parent.legs[winning_leg]
    sibling = parent.legs[1 - winning_leg]
    assert winner.status == "filled"
    assert winner.fill_price == (take_profit if winning_leg == 0 else exit_price)
    assert sibling.status == "canceled"
    assert broker.position("ES") == 0
    assert broker.open_orders("ES") == []
    assert len(broker.recent_fills()) == 2
    assert [fill["id"] for fill in broker.recent_fills()] == [parent.id, winner.id]


def test_bracket_children_wait_until_parent_fills():
    broker = ShadowBroker()
    parent = broker.submit_bracket("ES", "buy", 1, 110, 90)
    take_profit_leg, stop_leg = parent.legs

    assert parent.status == "accepted"
    assert broker.position("ES") == 0
    assert [order.id for order in broker.open_orders("ES")] == [parent.id]
    assert take_profit_leg.status == stop_leg.status == "held"

    broker.set_price("ES", 100)
    assert parent.status == "filled"
    assert broker.position("ES") == 1
    assert take_profit_leg.status == stop_leg.status == "accepted"

    broker.set_price("ES", 111)
    assert take_profit_leg.status == "filled"
    assert stop_leg.status == "canceled"
    assert broker.position("ES") == 0
    assert broker.open_orders("ES") == []


def test_canceling_bracket_parent_cancels_held_legs_and_retires_oco_links():
    broker = ShadowBroker()
    parent = broker.submit_bracket("ES", "buy", 1, 110, 90)
    take_profit_leg, stop_leg = parent.legs

    assert broker.cancel_order(parent.id)
    assert parent.status == "canceled"
    assert take_profit_leg.status == stop_leg.status == "canceled"
    assert broker.open_orders() == []
    assert broker._oco_siblings == {}


def test_canceling_one_oco_exit_cancels_its_sibling():
    broker = ShadowBroker(prices={"ES": 100})
    parent = broker.submit_bracket("ES", "buy", 1, 110, 90)
    take_profit_leg, stop_leg = parent.legs

    assert broker.cancel_order(take_profit_leg.id)
    assert take_profit_leg.status == stop_leg.status == "canceled"
    assert broker._oco_siblings == {}
