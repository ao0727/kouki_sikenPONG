"""馬の全戦績を使う予想モデル。

- HorseGBM   : 勾配ブースティング。重賞の出走馬データで学習（戦績特徴量 + レース内比較）
- CareerGBM  : 勾配ブースティング。出走馬の「全キャリアの走」で学習（データ量が数倍になる）
- BenterLogit: 条件付きロジット（いわゆるベンター式）。オッズの確率を土台に、戦績で補正する
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.ensemble import HistGradientBoostingClassifier

from .features import build_features, normalize_in_race
from .horse_features import HORSE_FEATURES, features_from_past, horse_feature_columns


def _gbm(min_leaf: int = 40) -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(
        max_iter=250, learning_rate=0.04, max_leaf_nodes=15, min_samples_leaf=min_leaf,
        l2_regularization=1.0, random_state=0)


def _finish(df: pd.DataFrame, win_raw, place_raw) -> pd.DataFrame:
    out = df.copy()
    f = out.assign(頭数=out.groupby("レースID")["馬番"].transform("count"))
    out["勝率"] = normalize_in_race(f, pd.Series(win_raw, index=out.index))
    out["複勝率"] = normalize_in_race(f, pd.Series(place_raw, index=out.index),
                                   f["頭数"].clip(upper=3)).clip(upper=0.99)
    out["点数"] = (out["勝率"] * 100).round(2)
    return out


# ------------------------------------------------------------------ 重賞データで学習
class HorseGBM:
    def __init__(self, use_odds: bool = True):
        self.cols = horse_feature_columns(use_odds)
        self.win, self.place = _gbm(), _gbm()

    def _X(self, df):
        f = build_features(df)
        return f.reindex(columns=self.cols)

    def fit(self, hist):
        h = hist.dropna(subset=["着順"])
        X = self._X(h)
        self.win.fit(X, (h["着順"] == 1).astype(int))
        self.place.fit(X, (h["着順"] <= 3).astype(int))
        return self

    def predict(self, df):
        X = self._X(df)
        return _finish(df, self.win.predict_proba(X)[:, 1], self.place.predict_proba(X)[:, 1])


# ------------------------------------------------------------------ 全キャリアで学習
CAREER_COLS = HORSE_FEATURES + ["頭数", "ログオッズ", "人気率", "枠位置"]


def build_career_table(runs: pd.DataFrame) -> pd.DataFrame:
    """全走それぞれについて「その走より前の戦績」から特徴量を作る（学習データ）。"""
    rows = []
    for _, g in runs.groupby("馬ID", sort=False):
        g = g.sort_values("日付", ascending=False).reset_index(drop=True)
        for i in range(len(g)):
            r = g.iloc[i]
            if not r["JRA"] or r["芝ダ"] not in ("芝", "ダ") or pd.isna(r["単勝オッズ"]):
                continue
            today = {"日付": r["日付"], "距離": r["距離"], "芝ダ": r["芝ダ"], "競馬場": r["競馬場"],
                     "馬場": r["馬場"], "斤量": r["斤量"], "騎手": r["騎手"], "クラス": r["クラス"]}
            feat = features_from_past(g.iloc[i + 1:], today)
            feat.update({"日付": r["日付"], "着順": r["着順"] if pd.notna(r["着順"]) else 99,
                         "頭数": r["頭数"], "ログオッズ": np.log(r["単勝オッズ"]),
                         "人気率": r["人気"] / r["頭数"] if pd.notna(r["人気"]) else np.nan,
                         "枠位置": r["枠番"] / 8 if pd.notna(r["枠番"]) else np.nan})
            rows.append(feat)
    return pd.DataFrame(rows)


class CareerGBM:
    def __init__(self, career: pd.DataFrame, use_odds: bool = True):
        self.career = career
        self.cols = CAREER_COLS if use_odds else [c for c in CAREER_COLS if c not in ("ログオッズ", "人気率")]
        self.win, self.place = _gbm(100), _gbm(100)

    def fit_until(self, date):
        c = self.career[self.career["日付"] < date]
        X = c.reindex(columns=self.cols)
        self.win.fit(X, (c["着順"] == 1).astype(int))
        self.place.fit(X, (c["着順"] <= 3).astype(int))
        return self

    def predict(self, df):
        f = build_features(df)
        f["人気率"] = df["人気"] / f["頭数"] if "人気" in df else f["人気順位率"]
        X = f.reindex(columns=self.cols)
        return _finish(df, self.win.predict_proba(X)[:, 1], self.place.predict_proba(X)[:, 1])


# ------------------------------------------------------------------ ベンター式
BENTER_COLS = ["近3走着差", "前走着差", "近3走着順率", "近3走人気以上", "前走クラス", "クラス変化",
               "重賞複勝率", "通算複勝率", "同距離帯複勝率", "同芝ダ複勝率", "同競馬場複勝率",
               "同回り複勝率", "同馬場状態複勝率", "得意距離との差", "休み明け", "休み明け複勝率",
               "叩き何戦目", "騎手継続", "騎手との複勝率", "斤量変化", "平均位置取り",
               "騎手勝率", "枠位置", "年齢", "体重増減絶対値", "出走数"]


class BenterLogit:
    """勝率 ∝ exp(a·log(市場の確率) + Σ b_k·特徴量_k) をレースごとに正規化。"""

    def __init__(self, l2: float = 2.0, use_odds: bool = True):
        self.l2, self.use_odds = l2, use_odds

    def _design(self, df, fit=False):
        f = build_features(df)
        X = f.reindex(columns=BENTER_COLS).astype(float)
        if fit:
            self.med = X.median().fillna(0.0)               # 列ごと空なら 0
            self.mu = X.fillna(self.med).mean()
            self.sd = X.fillna(self.med).std().replace(0, 1).fillna(1.0)
        miss = X["出走数"].isna() | (X["出走数"] == 0)
        Z = ((X.fillna(self.med) - self.mu) / self.sd).clip(-4, 4)
        Z["初出走"] = miss.astype(float)
        inv = 1 / f["単勝オッズ"].where(f["単勝オッズ"] > 0)
        mkt = (inv / inv.groupby(f["レースID"]).transform("sum")).fillna(0.01)
        if self.use_odds:
            Z.insert(0, "市場", np.log(mkt.clip(1e-4)))
        return Z.to_numpy(), f["レースID"].to_numpy()

    @staticmethod
    def _logprob(X, races, w):
        s = X @ w
        df = pd.DataFrame({"r": races, "s": s})
        m = df.groupby("r")["s"].transform("max")
        lse = np.log(np.exp(df["s"] - m).groupby(df["r"]).transform("sum")) + m
        return (df["s"] - lse).to_numpy()

    def fit(self, hist):
        h = hist.dropna(subset=["着順"])
        h = h[h.groupby("レースID")["着順"].transform(lambda s: (s == 1).sum()) == 1]
        X, races = self._design(h, fit=True)
        y = (h["着順"] == 1).to_numpy()
        codes = pd.factorize(races)[0]
        n_r = codes.max() + 1

        def loss(w):
            s = X @ w
            m = np.full(n_r, -np.inf)
            np.maximum.at(m, codes, s)
            e = np.exp(s - m[codes])
            tot = np.bincount(codes, e, n_r)
            ll = s[y] - (np.log(tot) + m)[codes[y]]
            p = e / tot[codes]
            grad_s = y.astype(float) - p
            reg = self.l2 * np.r_[0.0, w[1:]] if self.use_odds else self.l2 * w
            return -ll.sum() + 0.5 * (reg * w).sum(), -(X.T @ grad_s) + reg

        w0 = np.zeros(X.shape[1])
        if self.use_odds:
            w0[0] = 1.0
        self.w = minimize(loss, w0, jac=True, method="L-BFGS-B").x
        return self

    def predict(self, df):
        X, races = self._design(df)
        win = np.exp(self._logprob(X, races, self.w))
        out = df.copy()
        out["勝率"] = win
        from .scoring import place_prob_from_win
        out["複勝率"] = place_prob_from_win(out, n_sim=2000)
        out["点数"] = (out["勝率"] * 100).round(2)
        return out

    def weights(self) -> pd.Series:
        names = (["市場"] if self.use_odds else []) + BENTER_COLS + ["初出走"]
        return pd.Series(self.w, index=names)
