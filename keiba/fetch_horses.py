"""出走馬ごとの全戦績を netkeiba から取得し、1 行 = 1 走の CSV にする。

  python fetch_horses.py --history data/graded_history.csv --out data/horse_runs.csv

- 対象は --history の CSV に出てくる「馬ID」の馬すべて。
- ページは data/cache/horse_<ID>.html に保存し、2 回目以降は再取得しない。
- 個人の研究用。netkeiba の利用規約を確認し、アクセス間隔（1.5 秒）を短くしないこと。
"""
from __future__ import annotations

import argparse
import re

import pandas as pd
from bs4 import BeautifulSoup

from fetch_netkeiba import CACHE, fetch

GRADE_PATTERNS = [("(GI)", "G1"), ("(GII)", "G2"), ("(GIII)", "G3"), ("(G1)", "G1"),
                  ("(G2)", "G2"), ("(G3)", "G3"), ("(重賞)", "G3"), ("(L)", "L"), ("(OP)", "OP")]


def _f(s):
    m = re.search(r"-?\d+(?:\.\d+)?", str(s or ""))
    return float(m.group()) if m else None


def race_class(name: str) -> str:
    for pat, g in GRADE_PATTERNS:
        if pat in name:
            return g
    for key, g in [("3勝", "3勝"), ("1600万", "3勝"), ("2勝", "2勝"), ("1000万", "2勝"),
                   ("1勝", "1勝"), ("500万", "1勝"), ("未勝利", "未勝利"), ("新馬", "新馬")]:
        if key in name:
            return g
    return "OP"   # 特別戦の名前だけのものはオープン扱い


def parse_horse(html: str, horse_id: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    table = soup.select_one("table.db_h_race_results")
    if table is None:
        return []
    rows = table.find_all("tr")
    header = [th.get_text(strip=True) for th in rows[0].find_all("th")]
    idx = {h: i for i, h in enumerate(header)}
    out = []
    for tr in rows[1:]:
        tds = tr.find_all("td")
        if len(tds) < len(header):
            continue
        tx = [td.get_text(" ", strip=True) for td in tds]
        venue_m = re.match(r"\d*(\D+?)\d", tx[idx["開催"]])
        dist_m = re.match(r"(芝|ダ|障)(\d+)", tx[idx["距離"]])
        a = tds[idx["レース名"]].find("a")
        rm = re.search(r"/race/(\w+)", a.get("href", "")) if a else None
        rid = rm.group(1) if rm else None   # 地方・海外は英字まじりの ID
        passing = [int(x) for x in re.findall(r"\d+", tx[idx["通過"]])]
        weight = tx[idx["馬体重"]]
        fin = tx[idx["着順"]]
        out.append({
            "馬ID": horse_id, "日付": tx[idx["日付"]].replace("/", "-"),
            "レースID": rid, "競馬場": venue_m.group(1) if venue_m else tx[idx["開催"]],
            "JRA": bool(rid and rid.isdigit() and len(rid) == 12 and 1 <= int(rid[4:6]) <= 10),
            "レース名": tx[idx["レース名"]], "クラス": race_class(tx[idx["レース名"]]),
            "頭数": _f(tx[idx["頭数"]]), "枠番": _f(tx[idx["枠番"]]), "馬番": _f(tx[idx["馬番"]]),
            "単勝オッズ": _f(tx[idx["オッズ"]]), "人気": _f(tx[idx["人気"]]),
            "着順": int(fin) if fin.isdigit() else None, "着順文字": fin,
            "騎手": tx[idx["騎手"]], "斤量": _f(tx[idx["斤量"]]),
            "芝ダ": dist_m.group(1) if dist_m else None, "距離": int(dist_m.group(2)) if dist_m else None,
            "馬場": tx[idx["馬場"]], "着差": _f(tx[idx["着差"]]),
            "最初の通過順": passing[0] if passing else None,
            "上がり3F": _f(tx[idx["上り"]]),
            "馬体重": _f(weight.split("(")[0]) if "(" in weight else _f(weight),
        })
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--history", default="data/graded_history.csv")
    ap.add_argument("--out", default="data/horse_runs.csv")
    ap.add_argument("--fetch-only", action="store_true", help="ページの取得だけ行う")
    a = ap.parse_args()

    ids = sorted(pd.read_csv(a.history, dtype={"馬ID": str})["馬ID"].dropna().unique())
    todo = [h for h in ids if not (CACHE / f"horse_{h}.html").exists()]
    print(f"対象 {len(ids)} 頭（未取得 {len(todo)} 頭）", flush=True)
    rows = []
    for i, h in enumerate(ids, 1):
        try:
            html = fetch(f"https://db.netkeiba.com/horse/result/{h}/", f"horse_{h}.html")
            if not a.fetch_only:
                rows += parse_horse(html, h)
        except Exception as e:  # 1 頭の失敗で全体を止めない
            print(f"  スキップ {h}: {e}", flush=True)
        if i % 200 == 0:
            print(f"  {i}/{len(ids)} 頭", flush=True)
    if not a.fetch_only:
        df = pd.DataFrame(rows)
        df.to_csv(a.out, index=False, encoding="utf-8-sig")
        print(f"{df['馬ID'].nunique()} 頭 / {len(df)} 走を {a.out} に保存しました")


if __name__ == "__main__":
    main()
