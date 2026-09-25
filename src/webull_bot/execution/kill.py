"""Kill switch.

Cancels every open order. With ``--flatten``, also exits positions.
Paper state lives in the paper SQLite file, so this works from a second
process. Live mode refuses to run unless the same confirmation phrase
required at startup is present in the environment, so a stray command
cannot flatten a real account.
"""

from __future__ import annotations

import os

from webull_bot.broker.paper import PaperBroker
from webull_bot.broker.webull import WebullBroker
from webull_bot.config import AppConfig, cost_model_from_config
from webull_bot.journal.store import Journal

PHRASE = "I UNDERSTAND LIVE TRADING RISK"


def kill(config: AppConfig, *, mode: str, flatten: bool) -> str:
    journal = Journal(config.get("journal", "path", default="data/journal.sqlite"))
    if mode == "live":
        if os.environ.get("WEBULL_LIVE_CONFIRM") != PHRASE:
            raise SystemExit(
                "Refusing to kill a live account without WEBULL_LIVE_CONFIRM set to "
                f"the exact phrase: {PHRASE}"
            )
        broker = WebullBroker()
        broker.connect()
        canceled = broker.cancel_all()
        fills = broker.flatten() if flatten else []
        journal.event("kill", "live kill switch", {"canceled": canceled, "flatten": flatten, "fills": len(fills)})
        return f"Live kill: canceled {canceled} orders. Flatten submitted: {flatten}."
    broker = PaperBroker(
        config.get("broker", "paper_state_db", default="data/paper_state.sqlite"),
        cost_model_from_config(config),
        starting_equity=float(config.get("account", "starting_equity", default=100_000)),
        account_type=str(config.get("account", "account_type", default="margin")),
    )
    broker.connect()
    canceled = broker.cancel_all()
    fills = broker.flatten() if flatten else []
    journal.event(
        "kill",
        "paper kill switch",
        {"canceled": canceled, "flatten": flatten, "fills": [fill.symbol for fill in fills]},
    )
    return (
        f"Paper kill: canceled {canceled} orders. "
        f"Flattened {len(fills)} positions."
        if flatten
        else f"Paper kill: canceled {canceled} orders. Positions were left open."
    )
