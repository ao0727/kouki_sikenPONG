"""どの予想方式が一番当たるかを過去データで比べる（バックテスト）。

日付の古い順に並べ、前半で学習 → 後半（未来のレース）で成績を測る。
未来のデータで学習してしまう「カンニング」を防ぐため、必ず時系列で分ける。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .model import KeibaModel
from .scoring import fit_temperature, score


def split_by_date(history: pd.DataFrame, test_ratio: float = 0.2):
    order = (history.groupby("レースID")["日付"].min()
             .sort_values(kind="stable").index.tolist())
    n_test = max(1, int(len(order) * test_ratio))
    test_ids = set(order[-n_test:])
    is_test = history["レースID"].isin(test_ids)
    return history[~is_test].copy(), history[is_test].copy()


def popularity(df: pd.DataFrame) -> pd.DataFrame:
    """比較用: 単勝オッズだけで予想（1 番人気を本命にする）。"""
    out = df.copy()
    inv = 1.0 / out["単勝オッズ"].where(out["単勝オッズ"] > 0, 999.0)
    out["勝率"] = inv / inv.groupby(out["レースID"]).transform("sum")
    return out


def metrics(pred: pd.DataFrame, ev_threshold: float = 1.2) -> dict[str, float]:
    """予想（勝率つき）と実際の着順から成績を出す。"""
    p = pred.copy()
    top = p.loc[p.groupby("レースID")["勝率"].idxmax()]
    n_races = len(top)
    win_hit = (top["着順"] == 1)
    payout = np.where(win_hit, top["単勝オッズ"].fillna(0), 0.0)

    # 期待値（勝率 × オッズ）が高い馬だけ単勝を買う作戦
    p["期待値"] = p["勝率"] * p["単勝オッズ"]
    bets = p[p["期待値"] >= ev_threshold]
    ev_payout = np.where(bets["着順"] == 1, bets["単勝オッズ"], 0.0).sum()

    # 対数損失（確率の当たり具合。小さいほど良い）
    winners = p[p["着順"] == 1]
    logloss = float(-np.log(winners["勝率"].clip(1e-6)).mean()) if len(winners) else float("nan")

    return {
        "レース数": n_races,
        "本命の単勝的中率": float(win_hit.mean()),
        "本命の複勝率": float((top["着順"] <= 3).mean()),
        "本命単勝の回収率": float(payout.sum() / n_races) if n_races else 0.0,
        "期待値買いの点数": int(len(bets)),
        "期待値買いの回収率": float(ev_payout / len(bets)) if len(bets) else float("nan"),
        "対数損失": logloss,
    }


def compare_methods(history: pd.DataFrame, weights=None, test_ratio: float = 0.2) -> pd.DataFrame:
    train, test = split_by_date(history, test_ratio)
    results = {}
    if test["単勝オッズ"].notna().any():
        results["人気順（オッズのみ）"] = metrics(popularity(test))
    for use_odds, name in [(False, "点数式（オッズなし）"), (True, "点数式（オッズあり）")]:
        temp = fit_temperature(train, weights, use_odds)   # 学習期間だけで温度を決める
        results[name] = metrics(score(test, weights, use_odds, temperature=temp))
    if train["レースID"].nunique() >= 30:
        results["機械学習（オッズなし）"] = metrics(KeibaModel(use_odds=False).fit(train).predict(test))
        results["機械学習（オッズあり）"] = metrics(KeibaModel(use_odds=True).fit(train).predict(test))
    table = pd.DataFrame(results).T
    table.attrs["学習レース数"] = train["レースID"].nunique()
    table.attrs["テストレース数"] = test["レースID"].nunique()
    return table


def best_method(table: pd.DataFrame) -> str:
    """対数損失が一番小さい（確率が一番正確な）方式を返す。人気順は除く。"""
    candidates = table.drop(index=[i for i in table.index if i.startswith("人気順")])
    return str(candidates["対数損失"].astype(float).idxmin())
