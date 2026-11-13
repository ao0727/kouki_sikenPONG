"""その馬自身の全戦績から「近走の調子」と「得意な条件」を数値にする。

どの特徴量も、予想するレースの日付より前の走だけから計算する（未来の情報は使わない）。
条件別の成績は走数が少ないとブレるので、その馬の通算成績に寄せて補正する（ベイズ平均）。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

CLASS_LEVEL = {"G1": 7, "G2": 6, "G3": 5, "L": 4, "OP": 4, "3勝": 3, "2勝": 2, "1勝": 1,
               "未勝利": 0, "新馬": 0}
RIGHT_TURN = {"札幌", "函館", "福島", "中山", "京都", "阪神", "小倉"}
LEFT_TURN = {"新潟", "東京", "中京"}
BAD_GOING = {"稍重", "重", "不良"}
LAYOFF_DAYS = 70          # これ以上空いたら「休み明け」
PRIOR_N = 3.0             # 条件別成績の補正の強さ（走数 3 走分だけ通算成績に寄せる）

HORSE_FEATURES = [
    # 経験・通算
    "出走数", "通算勝率", "通算複勝率", "重賞出走数", "重賞複勝率",
    # 近走の調子
    "近3走着順率", "近3走着差", "前走着差", "前走着順率", "近5走最高着順",
    "近3走人気", "近3走人気以上", "着差トレンド", "前走上がり3F",
    # クラス
    "前走クラス", "クラス変化", "勝利最高クラス",
    # 得意な条件（今回と同じ条件での複勝率・補正つき）
    "同距離帯複勝率", "同芝ダ複勝率", "同競馬場複勝率", "同回り複勝率", "同馬場状態複勝率",
    "得意距離との差", "同距離帯経験",
    # 臨戦過程
    "休養日数", "休み明け", "叩き何戦目", "休み明け複勝率", "斤量変化",
    "騎手継続", "騎手との複勝率",
    # 位置取り
    "平均位置取り",
]

# レース内で比べる（偏差にする）特徴量
RELATIVE = ["近3走着差", "近3走着順率", "前走クラス", "近3走人気", "同距離帯複勝率",
            "通算複勝率", "平均位置取り", "重賞複勝率"]


def _turn(venue: str | None) -> str | None:
    if venue in RIGHT_TURN:
        return "右"
    if venue in LEFT_TURN:
        return "左"
    return None


def _rate(sel: pd.DataFrame, base: float) -> float:
    """3 着内率（走数が少ないほど base に寄せる）。"""
    n = len(sel)
    hits = float((sel["着順"] <= 3).sum()) if n else 0.0
    return (hits + PRIOR_N * base) / (n + PRIOR_N)


def features_from_past(past: pd.DataFrame, today: dict) -> dict:
    """past: その馬の、今回より前の走（新しい順）。today: 今回のレース条件。"""
    f: dict[str, float] = {}
    n = len(past)
    f["出走数"] = n
    if n == 0:
        return f   # 初出走: 何も分からない（欠損のまま → モデル側で扱う）

    fin = past["着順"].fillna(past["頭数"])            # 中止などは最下位扱い
    ratio = (fin / past["頭数"]).clip(0, 1)
    margin = past["着差"].clip(lower=0, upper=3.0)      # 勝ったときは 0 秒差
    top3 = (fin <= 3)
    base = float(top3.mean())
    f["通算勝率"] = float((fin == 1).mean())
    f["通算複勝率"] = base

    graded = past[past["クラス"].isin(["G1", "G2", "G3"])]
    f["重賞出走数"] = len(graded)
    f["重賞複勝率"] = _rate(graded, base * 0.5)

    f["近3走着順率"] = float(ratio.head(3).mean())
    f["近3走着差"] = float(margin.head(3).mean())
    f["前走着差"] = float(margin.iloc[0]) if pd.notna(margin.iloc[0]) else np.nan
    f["前走着順率"] = float(ratio.iloc[0])
    f["近5走最高着順"] = float(fin.head(5).min())
    pop = past["人気"].head(3)
    f["近3走人気"] = float(pop.mean()) if pop.notna().any() else np.nan
    f["近3走人気以上"] = float((past["人気"] - fin).head(3).mean()) if pop.notna().any() else np.nan
    f["着差トレンド"] = float(margin.iloc[0] - margin.head(3).iloc[-1]) if n >= 2 else 0.0
    f["前走上がり3F"] = past["上がり3F"].iloc[0]

    lv = past["クラス"].map(CLASS_LEVEL)
    f["前走クラス"] = float(lv.iloc[0]) if pd.notna(lv.iloc[0]) else np.nan
    f["クラス変化"] = CLASS_LEVEL.get(today.get("クラス"), 5) - f["前走クラス"]
    wins = lv[fin == 1]
    f["勝利最高クラス"] = float(wins.max()) if len(wins) else -1.0

    dist, surf, venue, going = today.get("距離"), today.get("芝ダ"), today.get("競馬場"), today.get("馬場")
    if dist:
        same_d = past[(past["距離"] - dist).abs() <= 200]
        f["同距離帯複勝率"] = _rate(same_d, base)
        f["同距離帯経験"] = len(same_d)
        good = past[top3 & past["距離"].notna()]
        f["得意距離との差"] = float(abs(good["距離"].mean() - dist) / 400) if len(good) else np.nan
    f["同芝ダ複勝率"] = _rate(past[past["芝ダ"] == surf], base) if surf else np.nan
    f["同競馬場複勝率"] = _rate(past[past["競馬場"] == venue], base) if venue else np.nan
    t = _turn(venue)
    f["同回り複勝率"] = _rate(past[past["競馬場"].map(_turn) == t], base) if t else np.nan
    if going:
        bad = going in BAD_GOING
        f["同馬場状態複勝率"] = _rate(past[past["馬場"].isin(BAD_GOING) == bad], base)

    days = (today["日付"] - past["日付"]).dt.days
    f["休養日数"] = float(days.iloc[0])
    f["休み明け"] = float(days.iloc[0] >= LAYOFF_DAYS)
    gaps = past["日付"].diff(-1).dt.days                  # 各走とその前走の間隔
    k = 1
    for g in gaps:                                     # 休み明けから数えて今回が何戦目か
        if pd.isna(g) or g >= LAYOFF_DAYS:
            break
        k += 1
    f["叩き何戦目"] = 1.0 if f["休み明け"] else float(k + 1)
    after_layoff = past[gaps.fillna(999) >= LAYOFF_DAYS]
    f["休み明け複勝率"] = _rate(after_layoff, base)
    if today.get("斤量") is not None and pd.notna(past["斤量"].iloc[0]):
        f["斤量変化"] = float(today["斤量"] - past["斤量"].iloc[0])
    jockey = today.get("騎手")
    if jockey:
        f["騎手継続"] = float(past["騎手"].iloc[0] == jockey)
        f["騎手との複勝率"] = _rate(past[past["騎手"] == jockey], base)
    pos = (past["最初の通過順"] / past["頭数"]).head(5)
    f["平均位置取り"] = float(pos.mean()) if pos.notna().any() else np.nan
    return f


def load_runs(path: str) -> pd.DataFrame:
    runs = pd.read_csv(path, dtype={"馬ID": str, "レースID": str})
    runs["日付"] = pd.to_datetime(runs["日付"], errors="coerce")
    return runs.dropna(subset=["日付"]).sort_values(["馬ID", "日付"], ascending=[True, False])


def add_horse_features(entries: pd.DataFrame, runs: pd.DataFrame) -> pd.DataFrame:
    """出馬表（馬ID・日付・距離などを含む）に、戦績から作った特徴量を足す。"""
    by_horse = {h: g for h, g in runs.groupby("馬ID", sort=False)}
    empty = runs.iloc[0:0]
    rows = []
    for _, e in entries.iterrows():
        past = by_horse.get(str(e.get("馬ID")).removesuffix(".0"), empty)
        past = past[past["日付"] < e["日付"]]
        today = {"日付": e["日付"], "距離": e.get("距離"), "芝ダ": e.get("芝ダ"),
                 "競馬場": e.get("競馬場"), "馬場": e.get("馬場"), "斤量": e.get("斤量"),
                 "騎手": e.get("騎手"), "クラス": e.get("グレード", e.get("クラス"))}
        rows.append(features_from_past(past, today))
    feats = pd.DataFrame(rows, index=entries.index).reindex(columns=HORSE_FEATURES)
    out = entries.drop(columns=[c for c in HORSE_FEATURES if c in entries.columns]).join(feats)
    for c in RELATIVE:
        g = out.groupby("レースID")[c]
        std = g.transform("std").replace(0, np.nan)
        out[f"{c}_偏差"] = ((out[c] - g.transform("mean")) / std).fillna(0.0)
    out["レース内先行馬数"] = out.groupby("レースID")["平均位置取り"].transform(lambda s: (s < 0.3).sum())
    return out


def horse_feature_columns(use_odds: bool = True) -> list[str]:
    cols = HORSE_FEATURES + [f"{c}_偏差" for c in RELATIVE] + ["レース内先行馬数", "頭数", "枠位置",
                                                             "年齢", "体重増減絶対値", "斤量差"]
    return cols + (["ログオッズ", "人気順位率"] if use_odds else [])
