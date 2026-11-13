import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from keiba_app.columns import prepare  # noqa: E402
from keiba_app.horse_features import add_horse_features  # noqa: E402
from keiba_app.horse_model import BenterLogit, build_career_table  # noqa: E402


def make_runs():
    # 馬 A: 2024-01 に 1 着、2024-03 に 10 着、2024-05（予想対象の日）に 1 着、2024-07 に 1 着
    rows = []
    for d, fin, dist in [("2024-01-01", 1, 1600), ("2024-03-01", 10, 2400),
                         ("2024-05-01", 1, 1600), ("2024-07-01", 1, 1600)]:
        rows.append({"馬ID": "A", "日付": d, "レースID": "202405010111", "競馬場": "東京", "JRA": True,
                     "レース名": "テストS(OP)", "クラス": "OP", "頭数": 10, "枠番": 1, "馬番": 1,
                     "単勝オッズ": 3.0, "人気": 1, "着順": fin, "騎手": "騎手X", "斤量": 56,
                     "芝ダ": "芝", "距離": dist, "馬場": "良", "着差": 0.0 if fin == 1 else 1.0,
                     "最初の通過順": 2, "上がり3F": 34.0, "馬体重": 480})
    runs = pd.DataFrame(rows)
    runs["日付"] = pd.to_datetime(runs["日付"])
    return runs.sort_values("日付", ascending=False)


def test_only_past_runs_are_used():
    entry = prepare(pd.DataFrame([{"レースID": "R1", "日付": "2024-05-01", "馬番": 1, "馬名": "A",
                                   "馬ID": "A", "距離": 1600, "芝ダ": "芝", "競馬場": "東京",
                                   "馬場": "良", "騎手": "騎手X", "斤量": 56}]))
    f = add_horse_features(entry, make_runs()).iloc[0]
    assert f["出走数"] == 2                    # 当日・それ以降の走は数えない
    assert f["前走着差"] == 1.0                # 前走は 2024-03 の 10 着
    assert f["通算勝率"] == 0.5
    assert f["休養日数"] == 61


def test_first_time_starter_has_no_history():
    entry = prepare(pd.DataFrame([{"レースID": "R1", "日付": "2023-01-01", "馬番": 1, "馬名": "A",
                                   "馬ID": "A"}]))
    f = add_horse_features(entry, make_runs()).iloc[0]
    assert f["出走数"] == 0
    assert np.isnan(f["近3走着差"])


def test_career_table_uses_only_earlier_runs():
    car = build_career_table(make_runs()).sort_values("日付")
    assert list(car["出走数"]) == [0, 1, 2, 3]


def test_benter_probabilities_sum_to_one():
    rng = np.random.default_rng(0)
    rows = []
    for r in range(40):
        for i in range(8):
            rows.append({"レースID": f"R{r}", "日付": "2024-01-01", "馬番": i + 1, "馬名": f"H{i}",
                         "単勝オッズ": float(rng.uniform(2, 50)), "着順": i + 1,
                         "前走着順": int(rng.integers(1, 15))})
    h = prepare(pd.DataFrame(rows), need_result=True)
    pred = BenterLogit().fit(h).predict(h)
    assert np.allclose(pred.groupby("レースID")["勝率"].sum(), 1.0)
