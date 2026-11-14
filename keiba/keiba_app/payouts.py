"""netkeiba の結果ページから払戻金を読み取る。"""
from __future__ import annotations

import re

import pandas as pd
from bs4 import BeautifulSoup

BET_TYPES = ["単勝", "複勝", "枠連", "馬連", "ワイド", "馬単", "三連複", "三連単"]
ORDERED = {"単勝", "複勝", "馬単", "三連単"}      # 着順どおりの並びが意味を持つ券種


def parse_payouts(html: str, race_id: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    rows = []
    for tb in soup.select("table.pay_table_01"):
        for tr in tb.find_all("tr"):
            cells = tr.find_all(["th", "td"])
            if len(cells) < 3:
                continue
            kind = cells[0].get_text(strip=True)
            if kind not in BET_TYPES:
                continue
            combos = cells[1].get_text("|", strip=True).split("|")
            pays = cells[2].get_text("|", strip=True).split("|")
            for combo, pay in zip(combos, pays):
                nums = tuple(int(x) for x in re.findall(r"\d+", combo))
                if kind not in ORDERED:
                    nums = tuple(sorted(nums))
                rows.append({"レースID": race_id, "券種": kind,
                             "組番": "-".join(map(str, nums)),
                             "払戻": int(pay.replace(",", ""))})
    return rows


def load_payouts_from_cache(cache_dir, race_ids) -> pd.DataFrame:
    rows = []
    for rid in race_ids:
        path = cache_dir / f"result_{rid}.html"
        if path.exists():
            rows += parse_payouts(path.read_text(encoding="utf-8"), str(rid))
    return pd.DataFrame(rows)
