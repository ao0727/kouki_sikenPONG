"""JRA 全レースでの複勝転がしの研究。

  python fetch_all_results.py --start 2025-11-13 --end 2026-11-13
  python research/korogashi_all.py

- 複勝の回収率を、単勝オッズ帯・クラス・頭数別に調べる
- 「1番人気の単勝が X 倍未満のレースだけ」複勝を転がしたときの連勝数・成功率
- 期間を前半・後半に分けて、結果が安定しているかを見る
注意: 馬の選択に使う単勝オッズは確定オッズ。実際には締切前のオッズで選ぶので、少し有利に出る。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]


def load():
    res = pd.read_csv(BASE / "data/all_results.csv", dtype={"レースID": str})
    pay = pd.read_csv(BASE / "data/all_payouts.csv", dtype={"レースID": str, "組番": str})
    res["日付"] = pd.to_datetime(res["日付"])
    fuku = pay[pay["券種"] == "複勝"].copy()
    fuku["馬番"] = fuku["組番"].astype(int)
    res = res.merge(fuku[["レースID", "馬番", "払戻"]], on=["レースID", "馬番"], how="left")
    res["複勝払戻"] = res["払戻"].fillna(0)
    res["人気順"] = res.groupby("レースID")["単勝オッズ"].rank(method="first")
    res["R"] = res["レースID"].str[-2:].astype(int)
    mid = res["日付"].quantile(0.5)
    res["期間"] = np.where(res["日付"] < mid, "前半", "後半")
    return res


def roi_table(df, by):
    g = df.groupby(by, observed=True)["複勝払戻"]
    return pd.DataFrame({"頭数": g.size(), "的中率": g.apply(lambda s: (s > 0).mean()),
                         "平均配当": g.apply(lambda s: s[s > 0].mean() / 100),
                         "回収率": g.mean() / 100})


def favorites(res, max_odds, min_field=8):
    """1番人気の単勝が max_odds 未満、頭数 min_field 以上のレースの 1番人気（レース順）。"""
    fav = res[(res["人気順"] == 1) & (res["単勝オッズ"] < max_odds) & (res["頭数"] >= min_field)]
    return fav.sort_values(["日付", "R", "レースID"])


def streaks(hits):
    out, k = [], 0
    for h in hits:
        if h:
            k += 1
        else:
            out.append(k)
            k = 0
    out.append(k)
    return np.array(out)


def simulate(pays, target, start=1000):
    res = []
    for s in range(len(pays)):
        bank, steps = start, 0
        for p in pays[s:]:
            if bank >= target or bank < 100:
                break
            stake = bank // 100 * 100
            bank = bank - stake + stake // 100 * p
            steps += 1
        if bank >= target or bank < 100:
            res.append((bank >= target, bank / start, steps))
    if not res:
        return {}
    a = np.array(res, dtype=float)
    return {"成功率": a[:, 0].mean(), "平均戻り": a[:, 1].mean(), "平均回数": a[:, 2].mean(), "試行": len(a)}


def main():
    res = load()
    pd.set_option("display.width", 250)
    pd.set_option("display.unicode.east_asian_width", True)
    print(f"{res['レースID'].nunique()} レース / {res['日付'].min().date()}〜{res['日付'].max().date()}\n")

    bins = [1, 1.2, 1.4, 1.6, 1.8, 2.0, 2.5, 3, 5, 10, 1000]
    labels = ["1.0〜1.1", "1.2〜1.3", "1.4〜1.5", "1.6〜1.7", "1.8〜1.9", "2.0〜2.4", "2.5〜2.9",
              "3.0〜4.9", "5.0〜9.9", "10〜"]
    res["オッズ帯"] = pd.cut(res["単勝オッズ"], bins, right=False, labels=labels)
    big = res[res["頭数"] >= 8]
    print("=== 1. 複勝の回収率（8頭以上のレース、単勝オッズ帯別）===")
    t = roi_table(big, ["オッズ帯", "期間"]).unstack("期間")
    print(t.round(2).to_string())
    print("\n=== 1b. 単勝2倍未満の馬：クラス別 / 頭数別 ===")
    strong = res[res["単勝オッズ"] < 2.0]
    print(roi_table(strong, "クラス").round(2).to_string())
    strong = strong.assign(頭数帯=pd.cut(strong["頭数"], [0, 7, 11, 15, 19], labels=["7頭以下", "8〜11", "12〜15", "16〜18"]))
    print(roi_table(strong, "頭数帯").round(2).to_string())

    print("\n=== 2. 1番人気の単勝が X 倍未満のレースだけ複勝を転がす（8頭以上）===")
    rows = []
    for x in [1.3, 1.5, 1.7, 2.0, 2.5]:
        fav = favorites(res, x)
        pays = fav["複勝払戻"].to_numpy()
        hits = pays > 0
        st = streaks(hits)
        row = {"条件": f"単勝{x}倍未満", "回数": len(pays), "的中率": f"{hits.mean()*100:.1f}%",
               "平均配当": f"{pays[hits].mean()/100:.2f}倍", "回収率": f"{pays.mean():.1f}%",
               "前半回収率": f"{fav.loc[fav['期間'] == '前半', '複勝払戻'].mean():.1f}%",
               "後半回収率": f"{fav.loc[fav['期間'] == '後半', '複勝払戻'].mean():.1f}%",
               "最長連勝": int(st.max()), "10連勝以上の回数": int((st >= 10).sum())}
        for m in [2, 5, 10]:
            sim = simulate(pays, 1000 * m)
            row[f"{m}倍到達"] = f"{sim.get('成功率', 0)*100:.1f}%"
        rows.append(row)
    print(pd.DataFrame(rows).to_string(index=False))
    print("\n（参考）同じ倍率の馬券を 1 回だけ買う場合の理論値: 2倍 40% / 5倍 16% / 10倍 8%")


if __name__ == "__main__":
    main()
