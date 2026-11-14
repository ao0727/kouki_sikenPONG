"""全レースについて「そのレースより前のデータだけで学習した」予想確率を作る（研究用）。

  python research/make_predictions.py   → data/oos_predictions.csv

列:
  p_mkt       : 単勝オッズから出した市場の勝率
  p_fund      : 全戦績ML（オッズなし）= 戦績だけで見た実力
  p_career    : 全戦績ML（オッズあり）
  p_benter30 / p_benter300 : ベンター式（正則化の強さ 30 / 300）
  p_twostage  : 2 段階ベンター式  log p ∝ a·log p_mkt + b·log p_fund（係数は過去レースで学習）
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from keiba_app.columns import load_csv  # noqa: E402
from keiba_app.horse_features import add_horse_features, load_runs  # noqa: E402
from keiba_app.horse_model import BenterLogit, CareerGBM, build_career_table  # noqa: E402

CHUNK = 25


def market(df):
    inv = 1 / df["単勝オッズ"]
    return inv / inv.groupby(df["レースID"]).transform("sum")


def softmax_in_race(score, races):
    s = pd.Series(score)
    m = s.groupby(races).transform("max")
    e = np.exp(s - m)
    return (e / e.groupby(races).transform("sum")).to_numpy()


def fit_clogit(X, races, y, l2=0.1):
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
        return -ll.sum() + 0.5 * l2 * (w @ w), -(X.T @ (y - p)) + l2 * w

    return minimize(loss, np.ones(X.shape[1]) * 0.5, jac=True, method="L-BFGS-B").x


def main():
    hist = load_csv(str(BASE / "data/graded_history.csv"), need_result=True)
    runs = load_runs(str(BASE / "data/horse_runs.csv"))
    cache = BASE / "data/horse_runs.career.pkl"
    career = pd.read_pickle(cache) if cache.exists() else build_career_table(runs)
    hist = add_horse_features(hist, runs)
    hist = hist[hist.groupby("レースID")["着順"].transform(lambda s: (s == 1).sum()) == 1].copy()
    hist["p_mkt"] = market(hist)

    order = hist.groupby("レースID")["日付"].min().sort_values(kind="stable").index.tolist()
    chunks = [order[i:i + CHUNK] for i in range(0, len(order), CHUNK)]
    test_start = int((hist.groupby("レースID")["日付"].min() < pd.Timestamp("2023-11-12")).sum())

    # 1) 戦績だけの実力（全レース分、そのレースより前の走だけで学習）
    hist["p_fund"] = np.nan
    for ch in chunks:
        te = hist["レースID"].isin(ch)
        m = CareerGBM(career, use_odds=False).fit_until(hist.loc[te, "日付"].min())
        hist.loc[te, "p_fund"] = m.predict(hist[te])["勝率"].to_numpy()
        print("fund", len(ch), hist.loc[te, "日付"].min().date(), flush=True)

    # 2) テスト期間（2023-11-12〜）の各方式
    cols = ["p_career", "p_benter30", "p_benter300", "p_twostage"]
    for c in cols:
        hist[c] = np.nan
    for i in range(test_start, len(order), CHUNK):
        tr = hist["レースID"].isin(order[:i])
        te = hist["レースID"].isin(order[i:i + CHUNK])
        train, test = hist[tr], hist[te]
        d0 = test["日付"].min()
        hist.loc[te, "p_career"] = CareerGBM(career, True).fit_until(d0).predict(test)["勝率"].to_numpy()
        hist.loc[te, "p_benter30"] = BenterLogit(l2=30).fit(train).predict(test)["勝率"].to_numpy()
        hist.loc[te, "p_benter300"] = BenterLogit(l2=300).fit(train).predict(test)["勝率"].to_numpy()
        X = np.c_[np.log(train["p_mkt"]), np.log(train["p_fund"].clip(1e-4))]
        w = fit_clogit(X, train["レースID"].to_numpy(), (train["着順"] == 1).to_numpy())
        Xt = np.c_[np.log(test["p_mkt"]), np.log(test["p_fund"].clip(1e-4))]
        hist.loc[te, "p_twostage"] = softmax_in_race(Xt @ w, test["レースID"].to_numpy())
        print("test", d0.date(), "twostage w =", np.round(w, 3), flush=True)

    keep = ["レースID", "日付", "レース名", "グレード", "馬番", "馬名", "人気", "単勝オッズ", "着順",
            "頭数", "p_mkt", "p_fund"] + cols
    out = hist[hist["日付"] >= pd.Timestamp("2023-11-12")].reindex(columns=keep)
    out.to_csv(BASE / "data/oos_predictions.csv", index=False, encoding="utf-8-sig")
    print(f"{out['レースID'].nunique()} レース分を data/oos_predictions.csv に保存")


if __name__ == "__main__":
    main()
