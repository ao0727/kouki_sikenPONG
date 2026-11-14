"""これから行われるレースの出馬表を netkeiba から取得し、予想用の CSV を作る。
出走馬の全戦績もまだ無ければ取得して data/horse_runs.csv に追加する。

  python fetch_entries.py 202608050411            → data/entries_202608050411.csv
  python main.py profile data/entries_202608050411.csv   各馬の近走・得意条件と予想

単勝オッズの列は空のまま作るので、発売後にオッズを入れれば --method benter でも予想できる。
"""
from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

from fetch_horses import parse_horse
from fetch_netkeiba import CACHE, VENUES, fetch

BASE = Path(__file__).parent


def parse_shutuba(html: str, race_id: str) -> pd.DataFrame:
    soup = BeautifulSoup(html, "lxml")
    title = soup.title.get_text() if soup.title else ""
    dm = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", title)
    info = soup.select_one(".RaceData01").get_text(" ", strip=True) if soup.select_one(".RaceData01") else ""
    cm = re.search(r"(芝|ダ)(\d{3,4})m", info)
    gm = re.search(r"馬場\s*[:：]\s*(良|稍重|重|不良)", info)
    name_el = soup.select_one(".RaceName")
    grade = re.search(r"\((G[123])\)", title)
    rows = []
    for tr in soup.select("tr.HorseList"):
        tds = tr.find_all("td")
        horse_a = tr.select_one("a[href*='/horse/']")
        if not horse_a or len(tds) < 8:
            continue
        sex_age = tr.select_one("td.Barei").get_text(strip=True) if tr.select_one("td.Barei") else ""
        weight = tr.select_one("td.Weight").get_text(" ", strip=True) if tr.select_one("td.Weight") else ""
        wm = re.match(r"(\d+)\s*\(([-+]?\d+)\)", weight)
        rows.append({
            "レースID": race_id,
            "日付": date(int(dm.group(1)), int(dm.group(2)), int(dm.group(3))).isoformat() if dm else None,
            "レース名": name_el.get_text(strip=True) if name_el else title.split("出馬表")[0],
            "グレード": grade.group(1) if grade else None,
            "競馬場": VENUES.get(race_id[4:6]), "芝ダ": cm.group(1) if cm else None,
            "距離": int(cm.group(2)) if cm else None, "馬場": gm.group(1) if gm else "良",
            "枠番": int(tds[0].get_text(strip=True)), "馬番": int(tds[1].get_text(strip=True)),
            "馬名": horse_a.get_text(strip=True),
            "馬ID": re.search(r"/horse/(\w+)", horse_a["href"]).group(1),
            "性別": sex_age[:1], "年齢": int(sex_age[1:]) if sex_age[1:].isdigit() else None,
            "斤量": float(tds[5].get_text(strip=True) or "nan"),
            "騎手": tr.select_one("td.Jockey").get_text(strip=True) if tr.select_one("td.Jockey") else None,
            "馬体重": int(wm.group(1)) if wm else None, "体重増減": int(wm.group(2)) if wm else None,
            "単勝オッズ": None,
        })
    return pd.DataFrame(rows)


def update_runs(horse_ids, runs_path: Path) -> None:
    """全戦績 CSV に無い馬だけ取得して追加する。"""
    runs = pd.read_csv(runs_path, dtype={"馬ID": str, "レースID": str}) if runs_path.exists() else pd.DataFrame()
    have = set(runs["馬ID"]) if len(runs) else set()
    new_rows = []
    for h in horse_ids:
        if h in have:
            continue
        html = fetch(f"https://db.netkeiba.com/horse/result/{h}/", f"horse_{h}.html")
        new_rows += parse_horse(html, h)
    if new_rows:
        runs = pd.concat([runs, pd.DataFrame(new_rows)], ignore_index=True)
        runs.to_csv(runs_path, index=False, encoding="utf-8-sig")
        print(f"全戦績に {len({r['馬ID'] for r in new_rows})} 頭を追加しました")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("race_id")
    ap.add_argument("--runs", default=str(BASE / "data/horse_runs.csv"))
    a = ap.parse_args()
    html = fetch(f"https://race.netkeiba.com/race/shutuba.html?race_id={a.race_id}",
                 f"shutuba_{a.race_id}_{date.today():%Y%m%d}.html")
    df = parse_shutuba(html, a.race_id)
    out = BASE / f"data/entries_{a.race_id}.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"{df['レース名'].iloc[0]} {len(df)} 頭の出馬表を {out} に保存しました")
    update_runs(df["馬ID"].tolist(), Path(a.runs))


if __name__ == "__main__":
    main()
