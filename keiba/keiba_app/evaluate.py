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


def _bet_hits(g: pd.DataFrame) -> dict[str, bool]:
    """1 レース分: 予想順に並べた印どおりに買ったとき、各馬券が当たったか。"""
    g = g.sort_values("勝率", ascending=False)
    fin = g["着順"].to_numpy()
    top2 = set(g.index[fin <= 2])
    top3 = set(g.index[fin <= 3])
    ids = list(g.index)
    hon, aite = ids[0], ids[1:4]
    return {
        "単勝": fin[0] == 1,
        "複勝": fin[0] <= 3,
        # 馬連 ◎ - ○▲△（3 点）: 1・2 着が ◎ と相手のどれか
        "馬連": hon in top2 and len(top2 & set(aite)) >= 1,
        # ワイド ◎ - ○, ◎ - ▲（2 点）
        "ワイド": hon in top3 and len(top3 & set(ids[1:3])) >= 1,
        # 3 連複 ◎ 軸 - ○▲△△☆ 流し（10 点）: ◎ が 3 着内、残り 2 頭が相手 5 頭に入る
        "3連複": hon in top3 and len(top3 & set(ids[1:6])) >= 2,
    }


def metrics(pred: pd.DataFrame, ev_threshold: float = 1.2) -> dict[str, float]:
    """予想（勝率つき）と実際の着順から成績を出す。"""
    p = pred.copy()
    top = p.loc[p.groupby("レースID")["勝率"].idxmax()]
    n_races = len(top)
    payout = np.where(top["着順"] == 1, top["単勝オッズ"].fillna(0), 0.0)

    hits = pd.DataFrame([_bet_hits(g) for _, g in p.groupby("レースID")])

    # 期待値（勝率 × オッズ）が高い馬だけ単勝を買う作戦
    p["期待値"] = p["勝率"] * p["単勝オッズ"]
    bets = p[p["期待値"] >= ev_threshold]
    ev_payout = np.where(bets["着順"] == 1, bets["単勝オッズ"], 0.0).sum()

    # 対数損失（確率の当たり具合。小さいほど良い）
    winners = p[p["着順"] == 1]
    logloss = float(-np.log(winners["勝率"].clip(1e-6)).mean()) if len(winners) else float("nan")

    return {
        "レース数": n_races,
        "本命の単勝的中率": float(hits["単勝"].mean()),
        "本命の複勝率": float(hits["複勝"].mean()),
        "馬連的中率(3点)": float(hits["馬連"].mean()),
        "ワイド的中率(2点)": float(hits["ワイド"].mean()),
        "3連複的中率(10点)": float(hits["3連複"].mean()),
        "本命単勝の回収率": float(payout.sum() / n_races) if n_races else 0.0,
        "期待値買いの点数": int(len(bets)),
        "期待値買いの回収率": float(ev_payout / len(bets)) if len(bets) else float("nan"),
        "対数損失": logloss,
    }


def walk_forward(history: pd.DataFrame, predict_fn, min_train_races: int = 100,
                 step_races: int = 25) -> pd.DataFrame:
    """古い順に、それより前のレースだけで学習 → 次の step_races レースを予想、を繰り返す。"""
    order = (history.groupby("レースID")["日付"].min()
             .sort_values(kind="stable").index.tolist())
    preds = []
    for i in range(min_train_races, len(order), step_races):
        train = history[history["レースID"].isin(order[:i])]
        test = history[history["レースID"].isin(order[i:i + step_races])]
        preds.append(predict_fn(train, test))
    return pd.concat(preds)


def _horse_methods(career: pd.DataFrame | None) -> dict:
    """馬の全戦績を使う方式（history に戦績特徴量が付いているときだけ使える）。"""
    from .horse_model import BenterLogit, CareerGBM, HorseGBM
    m = {
        "戦績ML（オッズなし）": lambda tr, te: HorseGBM(use_odds=False).fit(tr).predict(te),
        "戦績ML（オッズあり）": lambda tr, te: HorseGBM(use_odds=True).fit(tr).predict(te),
        "ベンター式（オッズなし）": lambda tr, te: BenterLogit(use_odds=False).fit(tr).predict(te),
        "ベンター式（オッズあり）": lambda tr, te: BenterLogit(use_odds=True).fit(tr).predict(te),
    }
    if career is not None and len(career):
        m["全戦績ML（オッズなし）"] = lambda tr, te: CareerGBM(career, False).fit_until(te["日付"].min()).predict(te)
        m["全戦績ML（オッズあり）"] = lambda tr, te: CareerGBM(career, True).fit_until(te["日付"].min()).predict(te)
    return m


def _methods(weights):
    """方式名 → (学習データ, テストデータ) から予想を返す関数。"""
    def score_fn(use_odds):
        def f(train, test):
            temp = fit_temperature(train, weights, use_odds)   # 学習期間だけで温度を決める
            return score(test, weights, use_odds, temperature=temp)
        return f

    return {
        "人気順（オッズのみ）": lambda train, test: popularity(test),
        "点数式（オッズなし）": score_fn(False),
        "点数式（オッズあり）": score_fn(True),
        "機械学習（オッズなし）": lambda train, test: KeibaModel(use_odds=False).fit(train).predict(test),
        "機械学習（オッズあり）": lambda train, test: KeibaModel(use_odds=True).fit(train).predict(test),
    }


def compare_methods(history: pd.DataFrame, weights=None, test_ratio: float = 0.2,
                    walk: bool = False, min_train_races: int = 100,
                    test_from: str | None = None, runs: pd.DataFrame | None = None,
                    career: pd.DataFrame | None = None, only: list[str] | None = None) -> pd.DataFrame:
    """各方式の成績表を返す。

    walk=False: 古い (1 - test_ratio) で学習し、残りの新しいレースでテスト
    walk=True : ウォークフォワード（最初の min_train_races レース以降すべてをテスト）
    test_from : walk=True のとき、この日付以降のレースをすべてテストする（それより前は学習専用）
    """
    methods = _methods(weights)
    if runs is not None:
        from .horse_features import add_horse_features
        history = add_horse_features(history, runs)
        methods.update(_horse_methods(career))
    if only:
        methods = {k: v for k, v in methods.items() if any(o in k for o in only)}
    if not history["単勝オッズ"].notna().any():
        methods.pop("人気順（オッズのみ）", None)
    results = {}
    if walk:
        n_races = history["レースID"].nunique()
        if test_from:
            first = history.groupby("レースID")["日付"].min()
            min_train_races = int((first < pd.Timestamp(test_from)).sum())
        elif min_train_races >= n_races - 10:          # データが少ないときは最初の 1/3 で学習
            min_train_races = max(30, n_races // 3)
        for name, fn in methods.items():
            results[name] = metrics(walk_forward(history, fn, min_train_races))
        n_test = n_races - min_train_races
        n_train = f"{min_train_races}〜{n_races - 1}"
    else:
        train, test = split_by_date(history, test_ratio)
        if train["レースID"].nunique() < 30:
            methods = {k: v for k, v in methods.items() if "ML" not in k and not k.startswith("機械学習")}
        for name, fn in methods.items():
            results[name] = metrics(fn(train, test))
        n_train, n_test = train["レースID"].nunique(), test["レースID"].nunique()
    table = pd.DataFrame(results).T
    table.attrs["学習レース数"] = n_train
    table.attrs["テストレース数"] = n_test
    return table


def best_method(table: pd.DataFrame) -> str:
    """対数損失が一番小さい（確率が一番正確な）方式を返す。"""
    return str(table["対数損失"].astype(float).idxmin())
