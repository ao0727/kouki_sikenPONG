"""買い方（券種・期待値の基準・点数）を研究期間で探し、最終テスト期間で 1 回だけ確かめる。

  python research/strategy_search.py

研究期間   : 2023-11-12 〜 2025-11-11（ここだけを見て作戦を選ぶ）
最終テスト : 2025-11-12 〜 2026-11-11（選んだ作戦をここで 1 回だけ評価する）
すべて 1 点 100 円、実際の払戻金で計算する。
"""
from __future__ import annotations

import sys
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from keiba_app.betting import race_tickets  # noqa: E402

SPLIT = pd.Timestamp("2025-11-12")
MODELS = ["p_twostage", "p_benter300", "p_benter30", "p_career"]
TYPES = ["単勝", "複勝", "馬連", "ワイド", "馬単", "三連複", "三連単"]
MIN_PROB = {"単勝": 0.0, "複勝": 0.0, "馬連": 0.0, "ワイド": 0.0, "馬単": 0.0, "三連複": 0.0, "三連単": 0.0}


def all_tickets(pred: pd.DataFrame, pay: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for rid, g in pred.groupby("レースID"):
        for m in MODELS:
            t = race_tickets(g.assign(勝率=g[m]))
            t["モデル"], t["レースID"], t["日付"] = m, rid, g["日付"].iloc[0]
            rows.append(t)
    T = pd.concat(rows, ignore_index=True)
    T = T.merge(pay, on=["レースID", "券種", "組番"], how="left")
    T["払戻"] = T["払戻"].fillna(0)
    return T


def evaluate(bets: pd.DataFrame, n_races: int, seed: int = 0) -> dict:
    if len(bets) == 0:
        return {"点数": 0}
    per_race = bets.groupby("レースID").agg(投資=("払戻", "size"), 回収=("払戻", "sum"))
    per_race["投資"] *= 100
    roi = per_race["回収"].sum() / per_race["投資"].sum()
    # レース単位のブートストラップで回収率のブレ幅（90% 区間）を出す
    rng = np.random.default_rng(seed)
    inv, ret = per_race["投資"].to_numpy(), per_race["回収"].to_numpy()
    idx = rng.integers(0, len(per_race), size=(2000, len(per_race)))
    boot = ret[idx].sum(1) / inv[idx].sum(1)
    return {"点数": int(len(bets)), "購入レース": len(per_race), "的中": int((bets["払戻"] > 0).sum()),
            "回収率": roi, "下限90": np.quantile(boot, 0.05), "上限90": np.quantile(boot, 0.95),
            "収支": int(per_race["回収"].sum() - per_race["投資"].sum())}


def model_rules():
    for m, kind, ev, k in product(MODELS, TYPES, [1.0, 1.1, 1.2, 1.35, 1.5, 2.0], [1, 3, 5]):
        yield {"モデル": m, "券種": kind, "期待値下限": ev, "最大点数": k}


def pick_model_bets(T: pd.DataFrame, rule: dict) -> pd.DataFrame:
    t = T[(T["モデル"] == rule["モデル"]) & (T["券種"] == rule["券種"]) & (T["期待値"] >= rule["期待値下限"])]
    t = t.sort_values("期待値", ascending=False)
    return t.groupby("レースID").head(rule["最大点数"])


# ------------------------------------------------------------- 人気順だけで買う単純な作戦
def popularity_rules():
    return {
        "単勝 1番人気": ("単勝", [[1]]),
        "複勝 1番人気": ("複勝", [[1]]),
        "複勝 2番人気": ("複勝", [[2]]),
        "ワイド 1-2番人気": ("ワイド", [[1, 2]]),
        "ワイド 1-2,1-3番人気": ("ワイド", [[1, 2], [1, 3]]),
        "馬連 1-2番人気": ("馬連", [[1, 2]]),
        "馬連 1番人気-2〜5番人気": ("馬連", [[1, 2], [1, 3], [1, 4], [1, 5]]),
        "馬単 1→2番人気": ("馬単", [[1, 2]]),
        "三連複 1-2-3番人気": ("三連複", [[1, 2, 3]]),
        "三連複 1番人気軸-2〜6番人気": ("三連複", [[1, a, b] for a in range(2, 7) for b in range(a + 1, 7)]),
        "三連単 1→2→3番人気": ("三連単", [[1, 2, 3]]),
    }


def pick_popularity(pred, pay, kind, combos_by_rank):
    rows = []
    for rid, g in pred.groupby("レースID"):
        rank = g.sort_values("単勝オッズ").reset_index(drop=True)
        num = {i + 1: int(rank.loc[i, "馬番"]) for i in range(len(rank))}
        for c in combos_by_rank:
            if any(r not in num for r in c):
                continue
            nums = [num[r] for r in c]
            key = "-".join(map(str, nums if kind in ("単勝", "複勝", "馬単", "三連単") else sorted(nums)))
            rows.append({"レースID": rid, "券種": kind, "組番": key})
    b = pd.DataFrame(rows).merge(pay, on=["レースID", "券種", "組番"], how="left")
    b["払戻"] = b["払戻"].fillna(0)
    return b


def main():
    pred = pd.read_csv(BASE / "data/oos_predictions.csv", dtype={"レースID": str})
    pred["日付"] = pd.to_datetime(pred["日付"])
    pay = pd.read_csv(BASE / "data/payouts.csv", dtype={"レースID": str, "組番": str})
    dev_ids = set(pred.loc[pred["日付"] < SPLIT, "レースID"])
    hold_ids = set(pred.loc[pred["日付"] >= SPLIT, "レースID"])
    first_half = set(sorted(dev_ids, key=lambda r: pred.loc[pred["レースID"] == r, "日付"].iloc[0])[:len(dev_ids) // 2])

    print("買い目を計算中...", flush=True)
    T = all_tickets(pred, pay)

    # ---------------- 研究期間で探す
    res = []
    for rule in model_rules():
        b = pick_model_bets(T[T["レースID"].isin(dev_ids)], rule)
        e = evaluate(b, len(dev_ids))
        if e["点数"] < 40:
            continue
        h1 = evaluate(b[b["レースID"].isin(first_half)], 0)
        h2 = evaluate(b[~b["レースID"].isin(first_half)], 0)
        res.append({**rule, **e, "前半": h1.get("回収率", np.nan), "後半": h2.get("回収率", np.nan)})
    for name, (kind, combos) in popularity_rules().items():
        b = pick_popularity(pred[pred["レースID"].isin(dev_ids)], pay, kind, combos)
        e = evaluate(b, len(dev_ids))
        h1 = evaluate(b[b["レースID"].isin(first_half)], 0)
        h2 = evaluate(b[~b["レースID"].isin(first_half)], 0)
        res.append({"モデル": "人気順", "券種": name, **e, "前半": h1["回収率"], "後半": h2["回収率"]})
    R = pd.DataFrame(res)
    R.to_csv(BASE / "data/strategy_dev.csv", index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 250)
    pd.set_option("display.unicode.east_asian_width", True)
    fmt = lambda d: d.assign(**{c: d[c].map(lambda v: f"{v*100:.0f}%") for c in ["回収率", "下限90", "上限90", "前半", "後半"]})  # noqa: E731
    print("\n=== 研究期間：人気順の単純作戦 ===")
    print(fmt(R[R["モデル"] == "人気順"]).drop(columns=["期待値下限", "最大点数"]).to_string(index=False))
    print("\n=== 研究期間：モデル作戦 上位（前半・後半とも 95% 以上、点数 40 以上）===")
    stable = R[(R["モデル"] != "人気順") & (R["前半"] >= 0.95) & (R["後半"] >= 0.95)]
    print(fmt(stable.sort_values("下限90", ascending=False).head(25)).to_string(index=False))
    print("\n=== 研究期間：券種ごとの最高（参考・選び過ぎに注意）===")
    best = R[R["モデル"] != "人気順"].sort_values("回収率", ascending=False).groupby("券種").head(1)
    print(fmt(best).to_string(index=False))


if __name__ == "__main__":
    main()
