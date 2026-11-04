"""点数式の予想。

各項目をレース内で偏差（平均 0, ばらつき 1）にして、重みを掛けて合計する。
重みは weights.json で自由に変えられる。データが少なくても使えるのが利点。
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .features import build_features, normalize_in_race

# 正の重み = 値が大きいほど有利、負の重み = 値が小さいほど有利
DEFAULT_WEIGHTS: dict[str, float] = {
    "平均着順": -1.0,
    "前走着順率": -0.6,
    "上がり順位率": -0.6,
    "騎手勝率": 0.5,
    "距離複勝率": 0.6,
    "コース複勝率": 0.4,
    "距離変化": -0.2,
    "体重増減絶対値": -0.2,
    "斤量差": -0.2,
    "枠位置": -0.1,
    "ログオッズ": -1.2,   # 人気（市場の評価）。使いたくなければ 0 に
}

# 合計点 → 勝率 に変換するときの「なだらかさ」（大きいほど確率が均等になる）
# weights.json に "_温度" を書けば上書きできる。compare では過去データから自動で決める。
TEMPERATURE = 2.0


def load_weights(path: str | None) -> dict[str, float]:
    if path and Path(path).exists():
        with open(path, encoding="utf-8") as fp:
            return {k: float(v) for k, v in json.load(fp).items()}
    return dict(DEFAULT_WEIGHTS)


def score(df: pd.DataFrame, weights: dict[str, float] | None = None,
          use_odds: bool = True, temperature: float | None = None,
          with_place: bool = True) -> pd.DataFrame:
    """点数・勝率・複勝率を付けて返す。"""
    weights = dict(weights or DEFAULT_WEIGHTS)
    temp = temperature or weights.pop("_温度", TEMPERATURE)
    weights.pop("_温度", None)
    if not use_odds:
        weights.pop("ログオッズ", None)

    f = build_features(df)
    total = pd.Series(0.0, index=f.index)
    for col, w in weights.items():
        if col not in f.columns or w == 0:
            continue
        g = f.groupby("レースID")[col]
        std = g.transform("std").replace(0, np.nan)
        z = ((f[col] - g.transform("mean")) / std).fillna(0.0)
        total += w * z

    out = df.copy()
    out["点数"] = total.round(3)
    out["勝率"] = normalize_in_race(f, np.exp(total / temp))
    if with_place:
        out["複勝率"] = place_prob_from_win(out)
    return out


def fit_temperature(history: pd.DataFrame, weights: dict[str, float] | None = None,
                    use_odds: bool = True) -> float:
    """過去レースで、勝ち馬の確率が一番正確になる温度を探す。"""
    h = history.dropna(subset=["着順"])
    best, best_loss = TEMPERATURE, np.inf
    for t in [0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0]:
        p = score(h, weights, use_odds, temperature=t, with_place=False)
        loss = -np.log(p.loc[p["着順"] == 1, "勝率"].clip(1e-6)).mean()
        if loss < best_loss:
            best, best_loss = t, loss
    return best


def place_prob_from_win(df: pd.DataFrame, n_sim: int = 4000, seed: int = 0) -> pd.Series:
    """勝率から 3 着以内に入る確率をシミュレーションで求める（ハービル式）。"""
    rng = np.random.default_rng(seed)
    result = pd.Series(0.0, index=df.index)
    for _, idx in df.groupby("レースID").groups.items():
        p = df.loc[idx, "勝率"].to_numpy(dtype=float)
        n = len(p)
        k = min(3, n)
        # Gumbel トリックで「勝率に比例した着順」を大量に作る
        g = np.log(p)[None, :] + rng.gumbel(size=(n_sim, n))
        top = np.argsort(-g, axis=1)[:, :k]
        counts = np.bincount(top.ravel(), minlength=n)
        result.loc[idx] = counts / n_sim
    return result
