"""各馬の勝率から馬券（単勝〜三連単）の的中確率・期待値を計算し、買い目を選ぶ。

組み合わせの確率はハービル式を使い、2・3 着は Lo & Bacon-Shone の補正
（勝率を γ 乗して人気馬に寄りすぎないようにする）をかける。
"""
from __future__ import annotations

from itertools import combinations, permutations

import numpy as np
import pandas as pd

# JRA の控除率（払戻率 = 1 - 控除率）
TAKEOUT = {"単勝": 0.20, "複勝": 0.20, "馬連": 0.225, "ワイド": 0.225,
           "馬単": 0.25, "三連複": 0.25, "三連単": 0.275}
GAMMA2, GAMMA3 = 0.81, 0.65       # 2 着・3 着の補正（Lo & Bacon-Shone 1994 の推定値）


def _norm(x):
    x = np.asarray(x, dtype=float)
    return x / x.sum()


def order_probs(p: np.ndarray, g2: float = GAMMA2, g3: float = GAMMA3) -> np.ndarray:
    """P[i, j, k] = i が 1 着・j が 2 着・k が 3 着になる確率（n×n×n）。"""
    n = len(p)
    p1 = _norm(p)
    q2 = _norm(p ** g2)
    q3 = _norm(p ** g3)
    P = np.zeros((n, n, n))
    for i in range(n):
        d2 = 1 - q2[i]
        for j in range(n):
            if j == i:
                continue
            d3 = 1 - q3[i] - q3[j]
            if d3 <= 0:
                continue
            P[i, j, :] = p1[i] * q2[j] / d2 * q3 / d3
            P[i, j, i] = P[i, j, j] = 0
    return P


def ticket_probs(p: np.ndarray, numbers: list[int]) -> dict[str, dict[str, float]]:
    """券種 → {組番: 的中確率}。numbers は各馬の馬番（p と同じ並び）。"""
    n = len(p)
    P = order_probs(p)
    first = P.sum(axis=(1, 2))
    in3 = P.sum(axis=(1, 2)) + P.sum(axis=(0, 2)) + P.sum(axis=(0, 1))
    pair_order = P.sum(axis=2)                                       # i 1着・j 2着
    num = numbers
    out: dict[str, dict[str, float]] = {k: {} for k in TAKEOUT}
    for i in range(n):
        out["単勝"][f"{num[i]}"] = first[i]
        out["複勝"][f"{num[i]}"] = in3[i] if n >= 8 else pair_order[i].sum() + pair_order[:, i].sum()
    for i, j in combinations(range(n), 2):
        key = "-".join(map(str, sorted((num[i], num[j]))))
        out["馬連"][key] = pair_order[i, j] + pair_order[j, i]
        # ワイド: i と j がともに 3 着以内（3 頭目は誰でもよい）
        out["ワイド"][key] = (P[i, j, :].sum() + P[j, i, :].sum() + P[i, :, j].sum()
                            + P[j, :, i].sum() + P[:, i, j].sum() + P[:, j, i].sum())
    for i, j in permutations(range(n), 2):
        out["馬単"][f"{num[i]}-{num[j]}"] = pair_order[i, j]
    for i, j, k in combinations(range(n), 3):
        key = "-".join(map(str, sorted((num[i], num[j], num[k]))))
        out["三連複"][key] = sum(P[a, b, c] for a, b, c in permutations((i, j, k)))
    idx = np.argwhere(P > 0)
    for i, j, k in idx:
        out["三連単"][f"{num[i]}-{num[j]}-{num[k]}"] = P[i, j, k]
    return out


def race_tickets(race: pd.DataFrame, prob_col: str = "勝率", odds_col: str = "単勝オッズ") -> pd.DataFrame:
    """1 レース分の全買い目について、モデル確率・市場確率・推定オッズ・推定期待値を返す。"""
    r = race.dropna(subset=[odds_col]).sort_values("馬番")
    nums = r["馬番"].astype(int).tolist()
    model = ticket_probs(r[prob_col].to_numpy(float), nums)
    mkt = ticket_probs(_norm(1 / r[odds_col].to_numpy(float)), nums)
    rows = []
    for kind in TAKEOUT:
        for key, pm in model[kind].items():
            pk = mkt[kind].get(key, 0.0)
            if pk <= 0:
                continue
            est_odds = (1 - TAKEOUT[kind]) / pk
            if kind == "単勝":
                est_odds = float(r.loc[r["馬番"] == int(key), odds_col].iloc[0])   # 単勝は実オッズ
            rows.append({"券種": kind, "組番": key, "確率": pm, "市場確率": pk,
                         "推定オッズ": est_odds, "期待値": pm * est_odds})
    return pd.DataFrame(rows)


def select_bets(tickets: pd.DataFrame, rule: dict) -> pd.DataFrame:
    """rule: {券種, 期待値下限, 確率下限, 最大点数, オッズ上限} に合う買い目を期待値順に選ぶ。"""
    t = tickets[tickets["券種"] == rule["券種"]]
    t = t[(t["期待値"] >= rule.get("期待値下限", 1.0)) & (t["確率"] >= rule.get("確率下限", 0.0))]
    if rule.get("オッズ上限"):
        t = t[t["推定オッズ"] <= rule["オッズ上限"]]
    return t.sort_values("期待値", ascending=False).head(rule.get("最大点数", 5))
