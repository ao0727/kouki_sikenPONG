"""netkeiba から JRA 重賞（G1〜G3）の結果と、各馬の「そのレース時点の過去5走」を取得し、
アプリ用の過去レース CSV を作る。

  python fetch_netkeiba.py --start 2023-11-12 --end 2026-11-11 --out data/graded_history.csv

注意:
  - 個人の研究・検証用です。netkeiba の利用規約を確認し、サーバーに負荷をかけないでください。
    （アクセスは 1.5 秒以上の間隔を空け、取得したページは data/cache/ に保存して再取得しません）
  - 障害レースは除外します。
  - 騎手勝率は「そのレースより前の重賞」だけから計算します（未来の情報は使わない）。
"""
from __future__ import annotations

import argparse
import re
import time
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

BASE = Path(__file__).parent
CACHE = BASE / "data" / "cache"
WAIT_SEC = 1.5
HEADERS = {"User-Agent": "Mozilla/5.0 (keiba-yosou personal research)"}
STYLE = {"逃": "逃げ", "先": "先行", "差": "差し", "追": "追込"}
_last_access = 0.0


def fetch(url: str, cache_name: str) -> str:
    """URL を取得（キャッシュがあればそれを使う）。"""
    global _last_access
    path = CACHE / cache_name
    if path.exists():
        return path.read_text(encoding="utf-8")
    wait = WAIT_SEC - (time.time() - _last_access)
    if wait > 0:
        time.sleep(wait)
    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            _last_access = time.time()
            r.raise_for_status()
            break
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))
    m = re.search(rb'charset="?([\w-]+)', r.content[:3000])
    text = r.content.decode(m.group(1).decode() if m else "utf-8", errors="replace")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text


def _num(s, typ=float):
    m = re.search(r"-?\d+(?:\.\d+)?", str(s or ""))
    return typ(float(m.group())) if m else None


# ---------------------------------------------------------------- 重賞一覧
def graded_races(start: date, end: date) -> list[dict]:
    races = []
    for year in range(start.year, end.year + 1):
        html = fetch(f"https://race.netkeiba.com/top/schedule.html?year={year}", f"schedule_{year}.html")
        soup = BeautifulSoup(html, "lxml")
        for tr in soup.select("table.race_table_01 tr"):
            tds = tr.find_all("td")
            a = tr.find("a")
            md = re.match(r"(\d{2})/(\d{2})", tds[0].get_text(strip=True)) if tds else None
            if len(tds) < 5 or not a or not md:
                continue
            d = date(year, int(md.group(1)), int(md.group(2)))
            grade = tds[2].get_text(strip=True)
            course = tds[4].get_text(strip=True)
            if not (start <= d <= end) or grade not in ("G1", "G2", "G3") or course.startswith("障"):
                continue
            name = a.get_text(strip=True)
            m = re.search(r"/race/(\d{12})", a.get("href", ""))
            # その年の日程ページが特集ページへのリンクのときは、開催日のレース一覧から ID を探す
            rid = m.group(1) if m else find_race_id(d, name, grade, tds[3].get_text(strip=True))
            if rid is None:
                print(f"  レースID が見つかりません: {d} {name}")
                continue
            races.append({"race_id": rid, "date": d, "grade": grade, "name": name})
    return races


GRADE_ICON = {"G1": "Icon_GradeType1", "G2": "Icon_GradeType2", "G3": "Icon_GradeType3"}


def find_race_id(d: date, name: str, grade: str, venue: str) -> str | None:
    ymd = d.strftime("%Y%m%d")
    html = fetch(f"https://race.netkeiba.com/top/race_list_sub.html?kaisai_date={ymd}", f"day_{ymd}.html")
    venue_code = {v: k for k, v in VENUES.items()}.get(venue)
    fallback = None
    for li in BeautifulSoup(html, "lxml").select("li.RaceList_DataItem"):
        a = li.find("a")
        m = re.search(r"race_id=(\d{12})", a["href"]) if a else None
        icon = li.select_one("[class*=Icon_GradeType]")
        if not m or not icon or GRADE_ICON[grade] not in icon.get("class", []):
            continue
        title = li.select_one(".ItemTitle")
        if title and title.get_text(strip=True) == name:
            return m.group(1)
        if m.group(1)[4:6] == venue_code:
            fallback = m.group(1)
    return fallback


# ---------------------------------------------------------------- 結果ページ
def parse_result(html: str) -> tuple[dict, list[dict]]:
    soup = BeautifulSoup(html, "lxml")
    info_txt = soup.select_one(".mainrace_data").get_text(" ", strip=True)
    m = re.search(r"(芝|ダ)[^/]*?(\d{3,4})m", info_txt)
    going = re.search(r"(?:芝|ダート)\s*:\s*(良|稍重|重|不良)", info_txt)
    info = {"芝ダ": m.group(1) if m else None, "距離": int(m.group(2)) if m else None,
            "馬場": going.group(1) if going else None}

    table = soup.select_one("table.race_table_01")
    rows = table.find_all("tr")
    header = [re.sub(r"\s+", "", th.get_text(" ", strip=True)) for th in rows[0].find_all("th")]
    idx = {name: i for i, name in enumerate(header)}
    out = []
    for tr in rows[1:]:
        tds = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        if len(tds) < len(header):
            continue
        weight = tds[idx["馬体重"]]
        sex_age = tds[idx["性齢"]]
        jockey_a = tr.find_all("td")[idx["騎手"]].find("a")
        out.append({
            "着順": _num(tds[idx["着順"]], int) if tds[idx["着順"]].isdigit() else None,
            "枠番": _num(tds[idx["枠番"]], int), "馬番": _num(tds[idx["馬番"]], int),
            "馬名": tds[idx["馬名"]], "性別": sex_age[:1], "年齢": _num(sex_age[1:], int),
            "斤量": _num(tds[idx["斤量"]]), "騎手": tds[idx["騎手"]],
            "騎手ID": re.search(r"(\d{5})", jockey_a["href"]).group(1) if jockey_a else tds[idx["騎手"]],
            "単勝オッズ": _num(tds[idx["単勝"]]), "人気": _num(tds[idx["人気"]], int),
            "馬体重": _num(weight.split("(")[0], int) if "(" in weight else None,
            "体重増減": _num(weight.split("(")[1], int) if "(" in weight else None,
        })
    return info, out


# ---------------------------------------------------------------- 過去5走ページ
def parse_past(html: str, race_date: date, venue: str, dist: int | None, surface: str | None) -> dict[int, dict]:
    soup = BeautifulSoup(html, "lxml")
    result: dict[int, dict] = {}
    for tr in soup.select("tr.HorseList"):
        uma = tr.select_one("td.Waku")
        if not uma or not uma.get_text(strip=True).isdigit():
            continue
        umaban = int(uma.get_text(strip=True))
        style = tr.select_one(".kyakusitu")
        runs = []
        for td in tr.select("td.Past"):
            d01 = td.select_one(".Data01")
            if not d01:
                continue
            spans = d01.find_all("span")
            dm = re.match(r"(\d{4})\.(\d{2})\.(\d{2})\s*(\S+)", spans[0].get_text(" ", strip=True))
            d05 = td.select_one(".Data05").get_text(" ", strip=True) if td.select_one(".Data05") else ""
            d03 = td.select_one(".Data03").get_text(" ", strip=True) if td.select_one(".Data03") else ""
            d06 = td.select_one(".Data06").get_text(" ", strip=True) if td.select_one(".Data06") else ""
            sm = re.match(r"(芝|ダ|障)(\d{3,4})", d05)
            fin = spans[1].get_text(strip=True) if len(spans) > 1 else ""
            agari = re.search(r"\((\d{2}\.\d)\)", d06)
            runs.append({
                "date": date(int(dm.group(1)), int(dm.group(2)), int(dm.group(3))) if dm else None,
                "venue": dm.group(4) if dm else None,
                "finish": int(fin) if fin.isdigit() else None,
                "field": _num(re.search(r"(\d+)頭", d03).group(1), int) if re.search(r"(\d+)頭", d03) else None,
                "surface": sm.group(1) if sm else None, "dist": int(sm.group(2)) if sm else None,
                "agari": float(agari.group(1)) if agari else None,
            })
        runs = [r for r in runs if r["date"] and r["date"] < race_date]   # 念のため未来の走は除く

        def top3_rate(cond):
            sel = [r for r in runs if cond(r) and r["finish"]]
            return round(sum(r["finish"] <= 3 for r in sel) / len(sel), 3) if sel else None

        prev = runs[0] if runs else {}
        result[umaban] = {
            "前走着順": prev.get("finish"),
            "2走前着順": runs[1]["finish"] if len(runs) > 1 else None,
            "3走前着順": runs[2]["finish"] if len(runs) > 2 else None,
            "前走頭数": prev.get("field"), "前走上がり3F": prev.get("agari"),
            "前走距離": prev.get("dist"),
            "休養週数": round((race_date - prev["date"]).days / 7, 1) if prev.get("date") else None,
            "距離複勝率": top3_rate(lambda r: dist and r["dist"] and abs(r["dist"] - dist) <= 200),
            "コース複勝率": top3_rate(lambda r: r["venue"] == venue and r["surface"] == surface),
            "脚質": STYLE.get(style.get_text(strip=True)) if style else None,
        }
    return result


VENUES = {"01": "札幌", "02": "函館", "03": "福島", "04": "新潟", "05": "東京",
          "06": "中山", "07": "中京", "08": "京都", "09": "阪神", "10": "小倉"}


def add_jockey_rate(df: pd.DataFrame, prior_n: float = 20, prior_rate: float = 0.07) -> pd.DataFrame:
    """そのレースより前の重賞成績だけで騎手勝率を出す（少ない騎乗数は平均寄りに補正）。"""
    df = df.sort_values(["日付", "レースID", "馬番"]).reset_index(drop=True)
    wins: dict[str, int] = {}
    rides: dict[str, int] = {}
    rates = []
    for _, g in df.groupby(["日付", "レースID"], sort=True):
        for j in g["騎手ID"]:
            rates.append(round((wins.get(j, 0) + prior_n * prior_rate) / (rides.get(j, 0) + prior_n), 4))
        for j, fin in zip(g["騎手ID"], g["着順"]):
            rides[j] = rides.get(j, 0) + 1
            wins[j] = wins.get(j, 0) + (1 if fin == 1 else 0)
    df["騎手勝率"] = rates
    return df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, help="例 2023-11-12")
    ap.add_argument("--end", required=True, help="例 2026-11-11")
    ap.add_argument("--out", default=str(BASE / "data" / "graded_history.csv"))
    a = ap.parse_args()
    start = datetime.strptime(a.start, "%Y-%m-%d").date()
    end = datetime.strptime(a.end, "%Y-%m-%d").date()

    races = graded_races(start, end)
    print(f"対象の重賞: {len(races)} レース")
    rows = []
    for i, r in enumerate(races, 1):
        rid = r["race_id"]
        try:
            info, horses = parse_result(fetch(f"https://db.netkeiba.com/race/{rid}/", f"result_{rid}.html"))
            venue = VENUES.get(rid[4:6])
            past = parse_past(fetch(f"https://race.netkeiba.com/race/shutuba_past.html?race_id={rid}",
                                    f"past_{rid}.html"), r["date"], venue, info["距離"], info["芝ダ"])
        except Exception as e:  # 1 レースの失敗で全体を止めない
            print(f"  スキップ {rid} {r['name']}: {e}")
            continue
        for h in horses:
            rows.append({"レースID": rid, "日付": r["date"].isoformat(), "レース名": r["name"],
                         "グレード": r["grade"], "競馬場": venue, **info, **h,
                         **past.get(h["馬番"], {})})
        if i % 20 == 0:
            print(f"  {i}/{len(races)} 完了")

    df = pd.DataFrame(rows)
    df = df[df["単勝オッズ"].notna()].copy()        # 出走取消・除外（オッズなし）は除く
    df["着順"] = df["着順"].fillna(99)              # 競走中止・失格は最下位扱い
    df = add_jockey_rate(df)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out, index=False, encoding="utf-8-sig")
    print(f"{df['レースID'].nunique()} レース / {len(df)} 頭分を {a.out} に保存しました")


if __name__ == "__main__":
    main()
