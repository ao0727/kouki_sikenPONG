"""各馬の「近走」と「得意な条件」を、競馬新聞のような着度数 [1着-2着-3着-着外] で表示する。"""
from __future__ import annotations

import pandas as pd

from .horse_features import BAD_GOING, _turn

MIN_RUNS = 3          # 得意・苦手の判定に必要な最低走数
DIFF = 0.15           # 通算の複勝率とこれだけ差があれば得意/苦手とみなす


def record(sel: pd.DataFrame) -> str:
    fin = sel["着順"]
    c = [(fin == 1).sum(), (fin == 2).sum(), (fin == 3).sum()]
    return f"[{c[0]}-{c[1]}-{c[2]}-{len(sel) - sum(c)}]"


def _top3(sel):
    return float((sel["着順"] <= 3).mean()) if len(sel) else float("nan")


def _run_text(r) -> str:
    """例: 3着 優駿牝馬[G1]"""
    import re
    name = re.sub(r"\((?:G|J|L|OP|重賞|\d勝)[^)]*\)$", "", str(r["レース名"]))[:9]
    fin = f"{int(r['着順'])}着" if pd.notna(r["着順"]) else str(r.get("着順文字", "-"))
    cls = r.get("クラス")
    tag = f"[{cls}]" if cls in ("G1", "G2", "G3", "L", "OP") else ""
    return f"{fin} {name}{tag}"


def horse_profile(past: pd.DataFrame, today: dict) -> dict:
    """past: 今回より前の走（新しい順）。"""
    if len(past) == 0:
        return {"近走": "初出走", "通算": "-", "条件": [], "得意": [], "苦手": []}
    base = _top3(past)
    recent = " ".join(_run_text(r) for _, r in past.head(5).iterrows())
    going_bad = today.get("馬場") in BAD_GOING
    conds = [
        (f"{today['距離']}m前後", past[(past["距離"] - today["距離"]).abs() <= 200]) if today.get("距離") else None,
        (today.get("芝ダ"), past[past["芝ダ"] == today.get("芝ダ")]) if today.get("芝ダ") else None,
        (today.get("競馬場"), past[past["競馬場"] == today.get("競馬場")]) if today.get("競馬場") else None,
        (f"{_turn(today.get('競馬場'))}回り", past[past["競馬場"].map(_turn) == _turn(today.get("競馬場"))])
        if _turn(today.get("競馬場")) else None,
        ("良馬場", past[past["馬場"] == "良"]),
        ("道悪", past[past["馬場"].isin(BAD_GOING)]),
    ]
    gaps = past["日付"].diff(-1).dt.days
    conds.append(("休み明け", past[gaps.fillna(999) >= 70]))
    lines, good, bad = [], [], []
    for item in conds:
        if item is None:
            continue
        name, sel = item
        lines.append(f"{name}{record(sel)}")
        if len(sel) >= MIN_RUNS:
            r = _top3(sel)
            if r >= base + DIFF:
                good.append(name)
            elif r <= base - DIFF:
                bad.append(name)
    days = (today["日付"] - past["日付"].iloc[0]).days
    note = []
    if days >= 70:
        note.append(f"休み明け({days // 7}週)")
    if going_bad and "道悪" in good:
        note.append("道悪◎")
    return {"近走": recent, "通算": record(past), "条件": lines, "得意": good, "苦手": bad, "メモ": note}


def format_profiles(entries: pd.DataFrame, runs: pd.DataFrame, pred: pd.DataFrame | None = None) -> str:
    by_horse = {h: g for h, g in runs.groupby("馬ID", sort=False)}
    order = entries
    if pred is not None:
        order = pred.sort_values("勝率", ascending=False)
    out = []
    marks = ["◎", "○", "▲", "△", "△", "☆"]
    for rank, (_, e) in enumerate(order.iterrows()):
        past = by_horse.get(str(e["馬ID"]), runs.iloc[0:0])
        past = past[past["日付"] < e["日付"]].sort_values("日付", ascending=False)
        today = {k: e.get(k) for k in ["日付", "距離", "芝ダ", "競馬場", "馬場"]}
        p = horse_profile(past, today)
        head = f"{marks[rank] if pred is not None and rank < len(marks) else '  '} {int(e['馬番']):>2} {e['馬名']}"
        if pred is not None:
            head += f"  勝率{e['勝率']*100:4.1f}% 複勝率{e['複勝率']*100:4.1f}%"
        head += f"  騎手:{e.get('騎手', '')}  通算{p['通算']}"
        out.append(head)
        out.append(f"     近走: {p['近走']}")
        if p["条件"]:
            out.append(f"     今回の条件: {' '.join(p['条件'])}")
        tags = [f"得意:{'・'.join(p['得意'])}"] if p["得意"] else []
        tags += [f"苦手:{'・'.join(p['苦手'])}"] if p["苦手"] else []
        tags += p.get("メモ", [])
        if tags:
            out.append(f"     {' / '.join(tags)}")
    return "\n".join(out)
