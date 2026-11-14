"""複勝転がしの研究。

  python research/fukusho_korogashi.py

1. 複勝の回収率を「単勝オッズ（人気の度合い）」別に調べる（どんな馬の複勝が割安か）
2. 実際の重賞の順番どおりに、ルールに従って複勝を転がすシミュレーション
   - 元手 1,000 円、払戻を全額（100 円単位）次の複勝へ。目標額に届けば成功、100 円未満で失敗
   - すべての開始レースから試して、成功率と平均の戻りを出す
3. 同じ目標倍率の馬券を 1 回だけ買う場合（理論値）と比べる
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from keiba_app.betting import ticket_probs  # noqa: E402

SPLIT = pd.Timestamp("2025-11-12")


def load():
    pred = pd.read_csv(BASE / "data/oos_predictions.csv", dtype={"レースID": str})
    pred["日付"] = pd.to_datetime(pred["日付"])
    pay = pd.read_csv(BASE / "data/payouts.csv", dtype={"レースID": str, "組番": str})
    fuku = pay[pay["券種"] == "複勝"].copy()
    fuku["馬番"] = fuku["組番"].astype(int)
    pred = pred.merge(fuku[["レースID", "馬番", "払戻"]], on=["レースID", "馬番"], how="left")
    pred["複勝払戻"] = pred["払戻"].fillna(0)
    # モデル（ベンター式）の複勝率 = 3 着以内に入る確率
    pred["モデル複勝率"] = np.nan
    for rid, g in pred.groupby("レースID"):
        g = g.sort_values("馬番")
        tp = ticket_probs(g["p_benter300"].to_numpy(float), g["馬番"].astype(int).tolist())["複勝"]
        pred.loc[g.index, "モデル複勝率"] = [tp[str(int(n))] for n in g["馬番"]]
    pred["人気順"] = pred.groupby("レースID")["単勝オッズ"].rank(method="first")
    return pred


def roi_by_odds(pred):
    bins = [1, 1.5, 2, 3, 5, 10, 20, 1000]
    labels = ["〜1.4", "1.5〜1.9", "2.0〜2.9", "3.0〜4.9", "5.0〜9.9", "10〜19.9", "20〜"]
    pred = pred.assign(オッズ帯=pd.cut(pred["単勝オッズ"], bins, right=False, labels=labels),
                       期間=np.where(pred["日付"] < SPLIT, "研究期間", "最終テスト"))
    t = pred.groupby(["オッズ帯", "期間"], observed=True).agg(
        頭数=("複勝払戻", "size"), 的中率=("複勝払戻", lambda s: (s > 0).mean()),
        平均配当=("複勝払戻", lambda s: s[s > 0].mean() / 100), 回収率=("複勝払戻", lambda s: s.mean() / 100))
    return t.unstack("期間")


RULES = {
    "毎レース 1番人気": lambda g: g[g["人気順"] == 1],
    "1番人気（単勝2.0倍未満のときだけ）": lambda g: g[(g["人気順"] == 1) & (g["単勝オッズ"] < 2.0)],
    "1番人気（単勝1.5倍未満のときだけ）": lambda g: g[(g["人気順"] == 1) & (g["単勝オッズ"] < 1.5)],
    "モデル複勝率が最大の馬": lambda g: g.nlargest(1, "モデル複勝率"),
    "モデル複勝率65%以上のときだけ": lambda g: g[g["モデル複勝率"] >= 0.65].nlargest(1, "モデル複勝率"),
    "2番人気（配当高め）": lambda g: g[g["人気順"] == 2],
}


def bet_sequence(pred, rule):
    """レース順に、ルールで選んだ馬の複勝払戻（100円あたり）。見送りレースは含めない。"""
    seq = []
    for rid, g in pred.sort_values(["日付", "レースID"]).groupby("レースID", sort=False):
        pick = rule(g)
        if len(pick):
            seq.append(float(pick["複勝払戻"].iloc[0]))
    return np.array(seq)


def simulate(seq, target, start=1000):
    """すべての開始位置から転がす。戻り値: 成功率・平均の戻り倍率・平均ステップ数・試行数。"""
    results, steps = [], []
    for s in range(len(seq)):
        bank, k = start, 0
        for pay in seq[s:]:
            if bank >= target or bank < 100:
                break
            stake = bank // 100 * 100
            bank = bank - stake + stake // 100 * pay
            k += 1
        if bank < target and bank >= 100:
            continue                       # データの終わりまでに決着しなかった試行は数えない
        results.append(bank / start)
        steps.append(k)
    r = np.array(results)
    if len(r) == 0:
        return {"試行": 0}
    return {"試行": len(r), "成功率": float((r * start >= target).mean()),
            "平均戻り": float(r.mean()), "平均回数": float(np.mean(steps))}


def main():
    pred = load()
    pd.set_option("display.width", 250)
    pd.set_option("display.unicode.east_asian_width", True)

    print("=== 1. 複勝の回収率（単勝オッズ帯別）===")
    t = roi_by_odds(pred)
    print(t.map(lambda v: f"{v:.2f}" if isinstance(v, float) else v).to_string())

    print("\n=== 2. ルール別：1 回ごとの成績（転がさず毎回 100 円）===")
    rows = []
    for name, rule in RULES.items():
        for period, m in [("研究期間", pred["日付"] < SPLIT), ("最終テスト", pred["日付"] >= SPLIT)]:
            seq = bet_sequence(pred[m], rule)
            rows.append({"ルール": name, "期間": period, "回数": len(seq),
                         "的中率": f"{(seq > 0).mean()*100:.0f}%" if len(seq) else "-",
                         "的中時の平均配当": f"{seq[seq > 0].mean()/100:.2f}倍" if (seq > 0).any() else "-",
                         "回収率": f"{seq.mean():.0f}%" if len(seq) else "-"})
    print(pd.DataFrame(rows).to_string(index=False))

    print("\n=== 3. 複勝転がしシミュレーション（全期間・元手 1,000 円）===")
    rows = []
    for name, rule in RULES.items():
        seq = bet_sequence(pred, rule)
        hit, avg = (seq > 0).mean(), seq[seq > 0].mean() / 100
        for mult in [2, 3, 5, 10]:
            sim = simulate(seq, 1000 * mult)
            # 理論値: 1 回の的中率 p・平均配当 o で n = log(M)/log(o) 回連続で当てる確率
            n = np.log(mult) / np.log(avg)
            rows.append({"ルール": name, "目標": f"{mult}倍", "成功率": f"{sim.get('成功率', 0)*100:.1f}%",
                         "理論値": f"{hit ** np.ceil(n) * 100:.1f}%",
                         "必要な連勝": int(np.ceil(n)), "平均戻り": f"{sim.get('平均戻り', 0):.2f}倍",
                         "1回買い(理論)": f"{0.8 / mult * 100:.1f}%", "試行": sim.get("試行", 0)})
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
