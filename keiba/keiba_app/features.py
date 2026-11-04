"""出馬表データから予想に使う特徴量を作る。

どの特徴量も「同じレースの中で比べてどうか」が大事なので、
レース内での順位・偏差もあわせて作る。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# オッズを使わない特徴量
BASE_FEATURES = [
    "平均着順", "前走着順率", "最高着順", "上がり順位率",
    "距離変化", "休養週数", "騎手勝率", "距離複勝率", "コース複勝率",
    "斤量差", "体重増減絶対値", "枠位置", "年齢", "頭数",
    "前に行く馬", "レース内逃げ先行数",
    "平均着順_偏差", "騎手勝率_偏差", "距離複勝率_偏差",
]

# オッズ（市場の評価）を使う特徴量
ODDS_FEATURES = ["ログオッズ", "人気順位率"]


def feature_columns(use_odds: bool = True) -> list[str]:
    return BASE_FEATURES + (ODDS_FEATURES if use_odds else [])


def _within_race_z(df: pd.DataFrame, col: str) -> pd.Series:
    g = df.groupby("レースID")[col]
    std = g.transform("std").replace(0, np.nan)
    return ((df[col] - g.transform("mean")) / std).fillna(0.0)


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """特徴量列を追加した DataFrame を返す（欠損は控えめな値で埋める）。"""
    f = df.copy()
    race = f.groupby("レースID")

    f["頭数"] = race["馬番"].transform("count").astype(float)

    past = f[["前走着順", "2走前着順", "3走前着順"]]
    f["平均着順"] = past.mean(axis=1).fillna(10.0)   # 新馬など実績なしは 10 着相当
    f["最高着順"] = past.min(axis=1).fillna(10.0)
    f["前走着順率"] = (f["前走着順"] / f["前走頭数"].fillna(14)).fillna(0.7).clip(0, 1)

    # 前走の上がり3F（小さいほど速い）をレース内で順位付け → 0(最速)〜1(最遅)
    agari_rank = race["前走上がり3F"].rank(method="average")
    agari_n = race["前走上がり3F"].transform("count").replace(0, np.nan)
    f["上がり順位率"] = ((agari_rank - 1) / (agari_n - 1).replace(0, np.nan)).fillna(0.5)

    f["距離変化"] = ((f["距離"] - f["前走距離"]).abs() / 400.0).fillna(0.0)
    f["休養週数"] = f["休養週数"].fillna(4.0)
    f["騎手勝率"] = f["騎手勝率"].fillna(0.05)
    f["距離複勝率"] = f["距離複勝率"].fillna(0.2)
    f["コース複勝率"] = f["コース複勝率"].fillna(0.2)
    f["斤量差"] = (f["斤量"] - race["斤量"].transform("mean")).fillna(0.0)
    f["体重増減絶対値"] = f["体重増減"].abs().fillna(0.0)
    f["枠位置"] = (f["枠番"] / 8.0).fillna(0.5)
    f["年齢"] = f["年齢"].fillna(4.0)

    f["前に行く馬"] = f["脚質"].isin(["逃げ", "先行"]).astype(float)
    f["レース内逃げ先行数"] = f.groupby("レースID")["前に行く馬"].transform("sum")

    for col in ["平均着順", "騎手勝率", "距離複勝率"]:
        f[f"{col}_偏差"] = _within_race_z(f, col)

    odds = f["単勝オッズ"]
    f["ログオッズ"] = np.log(odds.where(odds > 0)).fillna(np.log(30.0))
    pop_rank = f.groupby("レースID")["ログオッズ"].rank(method="average")
    f["人気順位率"] = ((pop_rank - 1) / (f["頭数"] - 1).replace(0, np.nan)).fillna(0.5)
    return f


def normalize_in_race(df: pd.DataFrame, values: pd.Series, total: float | pd.Series = 1.0) -> pd.Series:
    """レースごとに値の合計が total になるよう正規化する（確率化）。"""
    s = values.clip(lower=1e-9)
    return s / s.groupby(df["レースID"]).transform("sum") * total
