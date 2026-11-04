"""予想結果を見やすく整形し、買い目を提案する。"""
from __future__ import annotations

import pandas as pd

MARKS = ["◎", "○", "▲", "△", "△", "☆"]


def rank_race(pred: pd.DataFrame) -> pd.DataFrame:
    """1 レース分の予想を勝率順に並べ、印と期待値を付ける。"""
    r = pred.sort_values("勝率", ascending=False).reset_index(drop=True)
    r["印"] = [MARKS[i] if i < len(MARKS) else "" for i in range(len(r))]
    r["予想順位"] = range(1, len(r) + 1)
    r["期待値"] = (r["勝率"] * r["単勝オッズ"]).round(2)
    return r


def suggest_bets(r: pd.DataFrame, ev_threshold: float = 1.2) -> list[str]:
    def num(i):
        return int(r.loc[i, "馬番"])

    lines = []
    if len(r) >= 1:
        lines.append(f"単勝  {num(0)}（◎{r.loc[0, '馬名']}）")
    if len(r) >= 4:
        aite = "・".join(str(num(i)) for i in range(1, 4))
        lines.append(f"馬連  {num(0)} - {aite}（3点）")
        lines.append(f"ワイド {num(0)} - {num(1)}, {num(0)} - {num(2)}（2点・堅め）")
    if len(r) >= 5:
        himo = "・".join(str(num(i)) for i in range(1, 5))
        lines.append(f"3連複 {num(0)} 軸 - {himo} 流し（6点）")
    value = r[r["期待値"] >= ev_threshold]
    if len(value):
        txt = ", ".join(f"{int(m)}番 {n}（期待値 {e:.2f}）"
                        for m, n, e in zip(value["馬番"], value["馬名"], value["期待値"]))
        lines.append(f"妙味あり（勝率×オッズ ≥ {ev_threshold}）: {txt}")
    return lines


def format_race(pred: pd.DataFrame) -> str:
    r = rank_race(pred)
    head = r.iloc[0]
    title_parts = [str(head["レースID"])]
    for c in ("競馬場", "芝ダ", "距離", "馬場"):
        v = head.get(c)
        if pd.notna(v):
            title_parts.append(f"{int(v)}m" if c == "距離" else str(v))
    lines = ["=" * 64, "  " + " ".join(title_parts), "=" * 64,
             f"{'印':<2} {'馬番':>3}  {'馬名':<12} {'勝率':>6} {'複勝率':>6} {'オッズ':>6} {'期待値':>6}"]
    for _, x in r.iterrows():
        odds = f"{x['単勝オッズ']:.1f}" if pd.notna(x["単勝オッズ"]) else "-"
        ev = f"{x['期待値']:.2f}" if pd.notna(x["期待値"]) else "-"
        lines.append(f"{x['印']:<2} {int(x['馬番']):>4}  {str(x['馬名']):<12} "
                     f"{x['勝率']*100:5.1f}% {x['複勝率']*100:5.1f}% {odds:>6} {ev:>6}")
    lines.append("-" * 64)
    lines.append("【買い目の例】")
    lines += ["  " + s for s in suggest_bets(r)]
    return "\n".join(lines)


def format_all(pred: pd.DataFrame) -> str:
    return "\n\n".join(format_race(g) for _, g in pred.groupby("レースID", sort=False))
