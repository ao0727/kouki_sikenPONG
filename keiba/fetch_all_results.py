"""JRA の全レース（重賞以外も）の結果と払戻金を取得する。複勝転がしなどの研究用。

  python fetch_all_results.py --start 2025-11-13 --end 2026-11-13

  → data/all_results.csv（1 行 = 1 頭）, data/all_payouts.csv
個人の研究用。ページは data/cache/ に保存し再取得しない。アクセス間隔は 1.5 秒。
"""
from __future__ import annotations

import argparse
import re
from datetime import date, datetime, timedelta

import pandas as pd
from bs4 import BeautifulSoup

from fetch_netkeiba import BASE, VENUES, fetch, parse_result
from keiba_app.payouts import parse_payouts


def race_ids_on(d: date) -> list[tuple[str, str]]:
    ymd = d.strftime("%Y%m%d")
    try:
        html = fetch(f"https://race.netkeiba.com/top/race_list_sub.html?kaisai_date={ymd}", f"day_{ymd}.html")
    except Exception as e:   # 開催のない日はエラーになることがある
        print(f"  {ymd} の日程を取得できませんでした（開催なしとみなします）: {e}", flush=True)
        return []
    out = []
    for li in BeautifulSoup(html, "lxml").select("li.RaceList_DataItem"):
        a = li.find("a")
        m = re.search(r"race_id=(\d{12})", a["href"]) if a else None
        title = li.select_one(".ItemTitle")
        if m:
            out.append((m.group(1), title.get_text(strip=True) if title else ""))
    return out


def race_class(name: str, title: str) -> str:
    text = name + " " + title
    for key, c in [("(G1)", "G1"), ("(G2)", "G2"), ("(G3)", "G3"), ("新馬", "新馬"), ("未勝利", "未勝利"),
                   ("1勝", "1勝"), ("2勝", "2勝"), ("3勝", "3勝"), ("(L)", "L"), ("オープン", "OP")]:
        if key in text:
            return c
    return "OP"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    a = ap.parse_args()
    d0 = datetime.strptime(a.start, "%Y-%m-%d").date()
    d1 = datetime.strptime(a.end, "%Y-%m-%d").date()

    days = [d0 + timedelta(i) for i in range((d1 - d0).days + 1)]
    days = [d for d in days if d.weekday() in (0, 4, 5, 6)]   # 開催は主に土日（祝日の月・金も）
    rows, pays, n = [], [], 0
    for d in days:
        for rid, name in race_ids_on(d):
            if not (1 <= int(rid[4:6]) <= 10):
                continue
            try:
                html = fetch(f"https://db.netkeiba.com/race/{rid}/", f"result_{rid}.html")
                info, horses = parse_result(html)
            except Exception as e:   # 1 レースの失敗で止めない
                print(f"  スキップ {rid}: {e}", flush=True)
                continue
            soup_title = re.search(r"<title>(.*?)</title>", html)
            cls = race_class(name, soup_title.group(1) if soup_title else "")
            for h in horses:
                rows.append({"レースID": rid, "日付": d.isoformat(), "競馬場": VENUES.get(rid[4:6]),
                             "レース名": name, "クラス": cls, "頭数": len(horses), **info, **h})
            pays += parse_payouts(html, rid)
            n += 1
            if n % 200 == 0:
                print(f"  {n} レース（{d}）", flush=True)
    df = pd.DataFrame(rows)
    df = df[df["単勝オッズ"].notna()]
    df.to_csv(BASE / "data/all_results.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(pays).to_csv(BASE / "data/all_payouts.csv", index=False, encoding="utf-8-sig")
    print(f"{df['レースID'].nunique()} レース / {len(df)} 頭を保存しました")


if __name__ == "__main__":
    main()
