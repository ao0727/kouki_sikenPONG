import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from keiba_app.columns import prepare  # noqa: E402
from keiba_app.evaluate import compare_methods, split_by_date  # noqa: E402
from keiba_app.model import KeibaModel  # noqa: E402
from keiba_app.report import format_all  # noqa: E402
from keiba_app.scoring import score  # noqa: E402


def make_history(n_races=60, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for r in range(n_races):
        n = 10
        ability = rng.normal(size=n)
        finish = np.argsort(np.argsort(-(ability + rng.normal(0, 0.5, n)))) + 1
        for i in range(n):
            rows.append({"レースID": f"R{r:03d}", "日付": f"2024-01-{1 + r % 28:02d}",
                         "馬番": i + 1, "馬名": f"H{r}-{i}", "枠番": 1 + i * 8 // n,
                         "前走着順": int(np.clip(6 - 2 * ability[i], 1, 18)),
                         "単勝オッズ": round(float(np.exp(2 - ability[i])), 1),
                         "着順": int(finish[i])})
    return prepare(pd.DataFrame(rows), need_result=True)


def test_win_probs_sum_to_one_per_race():
    h = make_history(5)
    for pred in (score(h), KeibaModel().fit(make_history(60)).predict(h)):
        sums = pred.groupby("レースID")["勝率"].sum()
        assert np.allclose(sums, 1.0)
        assert (pred["複勝率"].between(0, 1)).all()


def test_missing_optional_columns_are_ok():
    df = prepare(pd.DataFrame({"レースID": ["A"] * 3, "馬番": [1, 2, 3], "馬名": list("xyz")}))
    pred = score(df)
    assert len(pred) == 3
    assert "◎" in format_all(pred)


def test_split_is_chronological():
    h = make_history(50)
    train, test = split_by_date(h)
    assert train["日付"].max() <= test["日付"].min()


def test_compare_runs():
    table = compare_methods(make_history(80))
    assert "機械学習（オッズあり）" in table.index
    assert table["本命の単勝的中率"].between(0, 1).all()
