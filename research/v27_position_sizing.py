"""V27 reproducible PAPER-ONLY A$50 vs A$100 risk-budget experiment.

Both stakes use identical official Kraken 4h bars, frozen strategies, chronological
splits and next-open hypothetical fills. Earlier 2025-26 data was inspected in
V25/V26: these folds are exploratory diagnostics, NOT untouched validation.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from research.forward_gap_experiment import (
    CANDIDATES, load_archive_all, run_experiment,
)


def compare_stakes(bars, provenance):
    old = run_experiment(bars, provenance, position_cap_aud=50.)
    new = run_experiment(bars, provenance, position_cap_aud=100.)
    if old["training_segment"] != new["training_segment"] or old["later_segment"] != new["later_segment"]:
        raise AssertionError("Research intervals changed between position sizes")
    if len(old["folds"]) != len(new["folds"]):
        raise AssertionError("Fold count mismatch")
    comparisons = {}
    for name in CANDIDATES:
        by_cap = {}
        for cap, report in ((50, old), (100, new)):
            folds = [f["strategies"][name] for f in report["folds"]]
            by_cap[str(cap)] = {
                "trades": sum(f["trades"] for f in folds),
                "gross_aud": round(sum(f["gross_aud"] for f in folds), 6),
                "fees_aud": round(sum(f["fees_aud"] for f in folds), 6),
                "spread_aud": round(sum(f["spread_aud"] for f in folds), 6),
                "slippage_aud": round(sum(f["slippage_aud"] for f in folds), 6),
                "net_aud": round(sum(f["net_aud"] for f in folds), 6),
                "max_fold_drawdown_pct": round(min(f["max_drawdown_pct"] for f in folds), 6),
                "net_return_pct_sum_of_reset_wallets": round(sum(f["net_return_pct"] for f in folds), 6),
                "fold_nets_aud": [f["net_aud"] for f in folds],
                "fold_half_cost_nets_aud": [f["fee_sensitivity"][name]["half_cost_net_aud"] for f in report["folds"]],
                "fold_double_cost_nets_aud": [f["fee_sensitivity"][name]["double_cost_net_aud"] for f in report["folds"]],
                "training_net_aud": report["train"][name]["net_aud"],
                "validation_net_aud": report["validation"][name]["net_aud"],
            }
            x = by_cap[str(cap)]
            if abs(x["gross_aud"] - x["fees_aud"] - x["spread_aud"] -
                   x["slippage_aud"] - x["net_aud"]) > 0.00001:
                raise AssertionError("Unreconciled gross/cost/net ledger")
        comparisons[name] = by_cap
    benchmarks = {}
    for cap, report in ((50, old), (100, new)):
        rows = [f[f"same_AUD{cap}_buy_hold"] for f in report["folds"]]
        benchmarks[str(cap)] = {
            "gross_aud": round(sum(f["gross_aud"] for f in rows), 6),
            "fees_aud": round(sum(f["fees_aud"] for f in rows), 6),
            "spread_aud": round(sum(f["spread_aud"] for f in rows), 6),
            "slippage_aud": round(sum(f["slippage_aud"] for f in rows), 6),
            "net_aud": round(sum(f["net_aud"] for f in rows), 6),
        }
    return {
        "mode": "PAPER_ONLY_V27_POSITION_SIZE_SENSITIVITY",
        "source": provenance,
        "tested_caps_aud": [50, 100],
        "initial_balance_per_fold_aud": 1000,
        "same_bars_same_folds": True,
        "market_history": {"training": old["training_segment"], "later": old["later_segment"]},
        "candidate_selection": {"A$50": old["selected_policy"], "A$100": new["selected_policy"]},
        "comparison": comparisons,
        "same_stake_buy_hold": benchmarks,
        "news_predictive_effect": "NOT TESTED: no matured future returns after first-observed Nov 1 2026 news",
        "data_integrity": "V25/V26 already inspected later-period market data; NOT UNTOUCHED",
        "promotion": "REJECTED: historical diagnostics and size change do not establish prospective NET edge",
        "app_risk_budget": "PAPER ONLY min(10% available cash, A$100) including entry friction",
        "limitations": "No exchange fills, intra-bar order book, queue position, future unseen validation or news causal effect. Separate reset A$1000 accounts, no compounded totals.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="audit/v27-position-sizing.json")
    args = parser.parse_args()
    bars, provenance = load_archive_all()
    result = compare_stakes(bars, provenance)
    result["run_utc"] = datetime.now(timezone.utc).isoformat()
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({
        "report": str(path),
        "source_sha256": provenance["member_sha256"],
        "bars": provenance["observed_bars"],
        "selected": result["candidate_selection"],
        "net_by_strategy": {k: {cap: v[cap]["net_aud"] for cap in ("50", "100")}
                            for k, v in result["comparison"].items()},
        "buy_hold": result["same_stake_buy_hold"],
        "promotion": result["promotion"],
    }, indent=2))


if __name__ == "__main__":
    main()
