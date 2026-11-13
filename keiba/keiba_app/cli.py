"""コマンドラインの入口。

  python main.py predict data/sample_race.csv        予想する
  python main.py train   data/sample_history.csv     機械学習モデルを作る
  python main.py compare data/sample_history.csv     どの方式が当たるか比べる
  python main.py template 出馬表.csv                  入力用の空 CSV を作る
  python main.py gui                                 画面で操作する
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from .columns import ENTRY_COLUMNS, load_csv
from .evaluate import best_method, compare_methods
from .model import KeibaModel
from .report import format_all
from .scoring import load_weights, score

DEFAULT_MODEL = "model.pkl"
DEFAULT_WEIGHTS = "weights.json"


def run_predict(race_csv: str, method: str = "auto", model_path: str = DEFAULT_MODEL,
                weights_path: str = DEFAULT_WEIGHTS, use_odds: bool = True,
                runs_path: str | None = None, history_path: str | None = None) -> tuple[pd.DataFrame, str]:
    df = load_csv(race_csv)
    if method in ("career", "benter"):
        return _predict_with_runs(df, method, runs_path, history_path, use_odds)
    if method == "auto":
        method = "ml" if Path(model_path).exists() else "score"
    if method == "ml":
        if not Path(model_path).exists():
            raise FileNotFoundError(f"モデル {model_path} がありません。先に train を実行してください。")
        model = KeibaModel.load(model_path)
        pred = model.predict(df)
        label = f"機械学習（{'オッズあり' if model.use_odds else 'オッズなし'}）"
    else:
        pred = score(df, load_weights(weights_path), use_odds=use_odds)
        label = f"点数式（{'オッズあり' if use_odds else 'オッズなし'}）"
    return pred, label


def _predict_with_runs(df, method, runs_path, history_path, use_odds):
    """馬の全戦績を使う方式。出馬表に「馬ID」列が必要。"""
    from .horse_features import add_horse_features, load_runs
    from .horse_model import BenterLogit, CareerGBM, build_career_table
    if not runs_path or not Path(runs_path).exists():
        raise FileNotFoundError("--runs に馬の全戦績 CSV（fetch_horses.py で作成）を指定してください")
    if "馬ID" not in df.columns:
        raise ValueError("戦績を使う方式では、出馬表 CSV に「馬ID」列（netkeiba の馬 ID）が必要です")
    runs = load_runs(runs_path)
    entries = add_horse_features(df, runs)
    odds_txt = "オッズあり" if use_odds else "オッズなし"
    if method == "career":
        model = CareerGBM(build_career_table(runs), use_odds).fit_until(df["日付"].min())
        return model.predict(entries), f"全戦績ML（{odds_txt}）"
    if not history_path or not Path(history_path).exists():
        raise FileNotFoundError("ベンター式には --history に過去の重賞 CSV が必要です")
    hist = add_horse_features(load_csv(history_path, need_result=True), runs)
    hist = hist[hist["日付"] < df["日付"].min()]
    return BenterLogit(l2=30, use_odds=use_odds).fit(hist).predict(entries), f"ベンター式（{odds_txt}）"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="keiba", description="競馬予想アプリ")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("predict", help="出馬表 CSV から予想する")
    p.add_argument("csv")
    p.add_argument("--method", choices=["auto", "score", "ml", "career", "benter"], default="auto",
                   help="auto: モデルがあれば機械学習、無ければ点数式")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--weights", default=DEFAULT_WEIGHTS)
    p.add_argument("--no-odds", action="store_true", help="オッズを使わずに予想する")
    p.add_argument("--runs", default="data/horse_runs.csv", help="career / benter で使う馬の全戦績 CSV")
    p.add_argument("--history", default="data/graded_history.csv", help="benter で使う過去の重賞 CSV")
    p.add_argument("--out", help="予想結果を CSV に保存する")

    t = sub.add_parser("train", help="過去レース CSV（着順つき）で機械学習モデルを作る")
    t.add_argument("csv")
    t.add_argument("--model", default=DEFAULT_MODEL)
    t.add_argument("--no-odds", action="store_true")

    c = sub.add_parser("compare", help="過去レースで各方式の的中率・回収率を比べる")
    c.add_argument("csv")
    c.add_argument("--weights", default=DEFAULT_WEIGHTS)
    c.add_argument("--test-ratio", type=float, default=0.2)
    c.add_argument("--walk", action="store_true",
                   help="ウォークフォワード: 過去だけで学習し直しながら、ほぼ全期間をテストする")
    c.add_argument("--min-train", type=int, default=100, help="--walk で最初に学習に使うレース数")
    c.add_argument("--test-from", help="--walk でこの日付(YYYY-MM-DD)以降をテストする。それより前は学習専用")
    c.add_argument("--runs", help="馬の全戦績 CSV（fetch_horses.py で作成）。戦績を使う方式も比べる")
    c.add_argument("--only", nargs="*", help="名前にこの文字を含む方式だけ比べる（例: --only 人気 ベンター）")

    tp = sub.add_parser("template", help="入力用の空 CSV を作る")
    tp.add_argument("csv")
    tp.add_argument("--with-result", action="store_true", help="着順列も付ける（過去レース用）")

    sub.add_parser("gui", help="画面で操作する")

    a = ap.parse_args(argv)
    try:
        if a.cmd == "predict":
            pred, label = run_predict(a.csv, a.method, a.model, a.weights, not a.no_odds,
                                      a.runs, a.history)
            print(f"予想方式: {label}\n")
            print(format_all(pred))
            if a.out:
                pred.to_csv(a.out, index=False, encoding="utf-8-sig")
                print(f"\n結果を {a.out} に保存しました")

        elif a.cmd == "train":
            hist = load_csv(a.csv, need_result=True)
            KeibaModel(use_odds=not a.no_odds).fit(hist).save(a.model)
            print(f"{hist['レースID'].nunique()} レースで学習し、{a.model} に保存しました")

        elif a.cmd == "compare":
            hist = load_csv(a.csv, need_result=True)
            runs = career = None
            if a.runs:
                from .horse_features import load_runs
                from .horse_model import build_career_table
                runs = load_runs(a.runs)
                cache = Path(a.runs).with_suffix(".career.pkl")
                if cache.exists() and cache.stat().st_mtime > Path(a.runs).stat().st_mtime:
                    career = pd.read_pickle(cache)
                else:
                    print("全戦績から学習データを作成中...", flush=True)
                    career = build_career_table(runs)
                    career.to_pickle(cache)
                print(f"全戦績の学習データ: {len(career)} 走")
            table = compare_methods(hist, load_weights(a.weights), a.test_ratio, a.walk, a.min_train,
                                    a.test_from, runs, career, a.only)
            print(f"学習 {table.attrs['学習レース数']} レース → テスト {table.attrs['テストレース数']} レース\n")
            show = table.copy()
            for col in ["本命の単勝的中率", "本命の複勝率", "馬連的中率(3点)", "ワイド的中率(2点)",
                        "3連複的中率(10点)", "本命単勝の回収率", "期待値買いの回収率"]:
                show[col] = show[col].map(lambda v: "-" if pd.isna(v) else f"{v*100:.1f}%")
            show["期待値買いの点数"] = show["期待値買いの点数"].astype(int)
            show["対数損失"] = show["対数損失"].map(lambda v: f"{v:.3f}")
            with pd.option_context("display.unicode.east_asian_width", True, "display.width", 200):
                print(show.drop(columns=["レース数"]).T.to_string())
            print(f"\n→ 確率が一番正確なのは「{best_method(table)}」です（対数損失が最小）")
            print("  ※ 回収率 100% 超え = 利益。テスト期間が短いと運の影響が大きいので注意。")

        elif a.cmd == "template":
            cols = ENTRY_COLUMNS + (["着順"] if a.with_result else [])
            pd.DataFrame(columns=cols).to_csv(a.csv, index=False, encoding="utf-8-sig")
            print(f"{a.csv} を作りました。Excel で開いて 1 行 = 1 頭で入力してください。")

        elif a.cmd == "gui":
            from .gui import run_gui
            run_gui()
    except (FileNotFoundError, ValueError) as e:
        print(f"エラー: {e}", file=sys.stderr)
        return 1
    return 0
