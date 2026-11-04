"""動作確認用の【ダミー】データを作る。実在のレース・馬ではありません。

  python make_sample_data.py
    → data/sample_history.csv（過去レース・着順つき）
    → data/sample_race.csv   （予想したい出馬表）
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
PLACES = ["東京", "中山", "京都", "阪神", "中京", "新潟", "福島", "小倉", "札幌", "函館"]
JOCKEYS = [f"騎手{c}" for c in "ABCDEFGHIJKLMNOPQRST"]
JOCKEY_SKILL = dict(zip(JOCKEYS, rng.normal(0, 0.35, len(JOCKEYS))))
STYLES = ["逃げ", "先行", "差し", "追込"]


def make_race(race_id: str, date: pd.Timestamp, with_result: bool) -> list[dict]:
    n = int(rng.integers(8, 19))
    dist = int(rng.choice([1200, 1400, 1600, 1800, 2000, 2400, 3000]))
    surface = rng.choice(["芝", "ダ"], p=[0.6, 0.4])
    going = rng.choice(["良", "稍重", "重", "不良"], p=[0.7, 0.15, 0.1, 0.05])
    ability = rng.normal(0, 1, n)                    # 本当の実力（見えない）
    jockeys = rng.choice(JOCKEYS, n, replace=False)
    dist_fit = rng.normal(0, 0.5, n)                 # 距離適性（見えない）

    rows, perf = [], np.zeros(n)
    for i in range(n):
        # 実力が高いほど過去の着順が良い（ノイズ入り）
        past = [int(np.clip(round(8 - 3 * ability[i] + rng.normal(0, 3.5)), 1, 18)) for _ in range(3)]
        prev_dist = int(dist + rng.choice([-400, -200, 0, 0, 200, 400]))
        rest = int(rng.choice([2, 3, 4, 5, 6, 8, 12, 20, 30]))
        delta_w = int(rng.normal(0, 6))
        waku = min(8, 1 + i * 8 // n)
        jskill = JOCKEY_SKILL[jockeys[i]]
        # 当日の走り = 実力 + 距離適性 + 騎手 + 不利要素 + 運
        perf[i] = (ability[i] + dist_fit[i] + jskill
                   - 0.15 * abs(dist - prev_dist) / 400 - 0.02 * abs(delta_w)
                   - 0.03 * waku - (0.2 if rest > 15 else 0) + rng.normal(0, 1.0))
        rows.append({
            "レースID": race_id, "日付": date.date().isoformat(),
            "競馬場": rng.choice(PLACES), "芝ダ": surface, "距離": dist, "馬場": going,
            "枠番": waku, "馬番": i + 1, "馬名": f"ダミーホース{race_id[-4:]}{i + 1:02d}",
            "年齢": int(rng.integers(2, 8)), "斤量": float(rng.choice([54, 55, 56, 57, 58])),
            "騎手": jockeys[i], "騎手勝率": round(float(np.clip(0.08 + 0.06 * jskill + rng.normal(0, 0.01), 0.01, 0.3)), 3),
            "馬体重": int(rng.normal(480, 25)), "体重増減": delta_w,
            "前走着順": past[0], "2走前着順": past[1], "3走前着順": past[2],
            "前走頭数": int(rng.integers(8, 19)),
            "前走上がり3F": round(float(35.5 - 0.5 * ability[i] + rng.normal(0, 0.6)), 1),
            "前走距離": prev_dist, "休養週数": rest,
            "距離複勝率": round(float(np.clip(0.25 + 0.15 * (ability[i] + dist_fit[i]) + rng.normal(0, 0.1), 0, 1)), 2),
            "コース複勝率": round(float(np.clip(0.25 + 0.12 * ability[i] + rng.normal(0, 0.12), 0, 1)), 2),
            "脚質": rng.choice(STYLES),
        })

    # オッズ: 市場は実力をそこそこ見抜く（控除率 20%）
    market = np.exp(1.3 * (ability + 0.5 * dist_fit + rng.normal(0, 0.6, n)))
    market /= market.sum()
    for i, r in enumerate(rows):
        r["単勝オッズ"] = round(float(max(1.1, 0.8 / market[i])), 1)
    if with_result:
        order = np.argsort(-perf)
        for place, i in enumerate(order, start=1):
            rows[i]["着順"] = place
    return rows


def main() -> None:
    out = Path(__file__).parent / "data"
    out.mkdir(exist_ok=True)
    dates = pd.date_range("2023-01-07", "2025-12-28", freq="7D")
    hist = []
    k = 0
    for d in dates:
        for _ in range(6):
            k += 1
            hist += make_race(f"DUMMY{k:05d}", d, with_result=True)
    pd.DataFrame(hist).to_csv(out / "sample_history.csv", index=False, encoding="utf-8-sig")

    race = make_race("DUMMY-TODAY1", pd.Timestamp("2026-11-08"), with_result=False) \
        + make_race("DUMMY-TODAY2", pd.Timestamp("2026-11-08"), with_result=False)
    pd.DataFrame(race).to_csv(out / "sample_race.csv", index=False, encoding="utf-8-sig")
    print(f"過去レース {k} 件・出馬表 2 レースのダミーデータを data/ に作りました")


if __name__ == "__main__":
    main()
