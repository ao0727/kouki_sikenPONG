"""研究期間で選んだ作戦を、最終テスト期間（2025-11-12〜）で 1 回だけ評価する。

  python research/holdout_eval.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "research"))
sys.path.insert(0, str(BASE))

from strategy_search import (SPLIT, all_tickets, evaluate, pick_model_bets,  # noqa: E402
                             pick_popularity, popularity_rules)

# 研究期間の結果を見て決めた作戦（この後は変更しない）
CHOSEN = [
    ("本命作戦A: ベンター式 ワイド 期待値1.0以上 1点", {"モデル": "p_benter300", "券種": "ワイド", "期待値下限": 1.0, "最大点数": 1}),
    ("本命作戦B: ベンター式 馬単 期待値1.0以上 1点", {"モデル": "p_benter300", "券種": "馬単", "期待値下限": 1.0, "最大点数": 1}),
    ("選び過ぎ例: 2段階 三連単 期待値1.1以上 5点", {"モデル": "p_twostage", "券種": "三連単", "期待値下限": 1.1, "最大点数": 5}),
    ("選び過ぎ例: 2段階 三連複 期待値1.0以上 5点", {"モデル": "p_twostage", "券種": "三連複", "期待値下限": 1.0, "最大点数": 5}),
    ("選び過ぎ例: 2段階 馬連 期待値1.0以上 5点", {"モデル": "p_twostage", "券種": "馬連", "期待値下限": 1.0, "最大点数": 5}),
    ("選び過ぎ例: ベンター式(弱) 複勝 期待値1.1以上 1点", {"モデル": "p_benter30", "券種": "複勝", "期待値下限": 1.1, "最大点数": 1}),
]


def main():
    pred = pd.read_csv(BASE / "data/oos_predictions.csv", dtype={"レースID": str})
    pred["日付"] = pd.to_datetime(pred["日付"])
    pay = pd.read_csv(BASE / "data/payouts.csv", dtype={"レースID": str, "組番": str})
    T = all_tickets(pred, pay)
    rows = []
    for name, rule in CHOSEN:
        for period, mask in [("研究期間", T["日付"] < SPLIT), ("最終テスト", T["日付"] >= SPLIT)]:
            e = evaluate(pick_model_bets(T[mask], rule), 0)
            rows.append({"作戦": name, "期間": period, **e})
    for name in ["複勝 1番人気", "ワイド 1-2番人気", "三連複 1番人気軸-2〜6番人気"]:
        kind, combos = popularity_rules()[name]
        for period, m in [("研究期間", pred["日付"] < SPLIT), ("最終テスト", pred["日付"] >= SPLIT)]:
            rows.append({"作戦": f"人気順: {name}", "期間": period,
                         **evaluate(pick_popularity(pred[m], pay, kind, combos), 0)})
    R = pd.DataFrame(rows)
    R.to_csv(BASE / "data/strategy_holdout.csv", index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 250)
    pd.set_option("display.unicode.east_asian_width", True)
    for c in ["回収率", "下限90", "上限90"]:
        R[c] = R[c].map(lambda v: f"{v*100:.0f}%")
    print(R.to_string(index=False))


if __name__ == "__main__":
    main()
