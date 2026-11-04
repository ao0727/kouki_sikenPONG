"""機械学習による予想（勾配ブースティング）。

過去レース（着順つき）から「1着になる確率」「3着以内に入る確率」を学習する。
データが多いほど精度が上がる（目安: 数百レース以上）。
"""
from __future__ import annotations

import pickle

import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

from .features import build_features, feature_columns, normalize_in_race


def _make_clf() -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(
        max_iter=300, learning_rate=0.05, max_leaf_nodes=15,
        min_samples_leaf=40, l2_regularization=1.0, random_state=0,
    )


class KeibaModel:
    def __init__(self, use_odds: bool = True):
        self.use_odds = use_odds
        self.cols = feature_columns(use_odds)
        self.win_clf = _make_clf()
        self.place_clf = _make_clf()

    def fit(self, history: pd.DataFrame) -> "KeibaModel":
        h = history.dropna(subset=["着順"])
        f = build_features(h)
        X = f[self.cols]
        self.win_clf.fit(X, (h["着順"] == 1).astype(int))
        self.place_clf.fit(X, (h["着順"] <= 3).astype(int))
        return self

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        f = build_features(df)
        X = f[self.cols]
        win_raw = pd.Series(self.win_clf.predict_proba(X)[:, 1], index=f.index)
        place_raw = pd.Series(self.place_clf.predict_proba(X)[:, 1], index=f.index)

        out = df.copy()
        out["勝率"] = normalize_in_race(f, win_raw)                   # レース内で合計 1
        place_total = f["頭数"].clip(upper=3)
        out["複勝率"] = normalize_in_race(f, place_raw, place_total).clip(upper=0.99)
        out["点数"] = (out["勝率"] * 100).round(2)
        return out

    def save(self, path: str) -> None:
        with open(path, "wb") as fp:
            pickle.dump(self, fp)

    @staticmethod
    def load(path: str) -> "KeibaModel":
        # 自分で作ったモデルファイル以外は読み込まないこと（pickle の仕様上）
        with open(path, "rb") as fp:
            return pickle.load(fp)
