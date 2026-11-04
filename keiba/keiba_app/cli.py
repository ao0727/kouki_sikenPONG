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
                weights_path: str = DEFAULT_WEIGHTS, use_odds: bool = True) -> tuple[pd.DataFrame, str]:
    df = load_csv(race_csv)
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="keiba", description="競馬予想アプリ")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("predict", help="出馬表 CSV から予想する")
    p.add_argument("csv")
    p.add_argument("--method", choices=["auto", "score", "ml"], default="auto",
                   help="auto: モデルがあれば機械学習、無ければ点数式")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--weights", default=DEFAULT_WEIGHTS)
    p.add_argument("--no-odds", action="store_true", help="オッズを使わずに予想する（点数式のみ）")
    p.add_argument("--out", help="予想結果を CSV に保存する")

    t = sub.add_parser("train", help="過去レース CSV（着順つき）で機械学習モデルを作る")
    t.add_argument("csv")
    t.add_argument("--model", default=DEFAULT_MODEL)
    t.add_argument("--no-odds", action="store_true")

    c = sub.add_parser("compare", help="過去レースで各方式の的中率・回収率を比べる")
    c.add_argument("csv")
    c.add_argument("--weights", default=DEFAULT_WEIGHTS)
    c.add_argument("--test-ratio", type=float, default=0.2)

    tp = sub.add_parser("template", help="入力用の空 CSV を作る")
    tp.add_argument("csv")
    tp.add_argument("--with-result", action="store_true", help="着順列も付ける（過去レース用）")

    sub.add_parser("gui", help="画面で操作する")

    a = ap.parse_args(argv)
    try:
        if a.cmd == "predict":
            pred, label = run_predict(a.csv, a.method, a.model, a.weights, not a.no_odds)
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
            table = compare_methods(hist, load_weights(a.weights), a.test_ratio)
            print(f"学習 {table.attrs['学習レース数']} レース → テスト {table.attrs['テストレース数']} レース\n")
            show = table.copy()
            for col in ["本命の単勝的中率", "本命の複勝率", "本命単勝の回収率", "期待値買いの回収率"]:
                show[col] = show[col].map(lambda v: "-" if pd.isna(v) else f"{v*100:.1f}%")
            show["期待値買いの点数"] = show["期待値買いの点数"].astype(int)
            show["対数損失"] = show["対数損失"].map(lambda v: f"{v:.3f}")
            with pd.option_context("display.unicode.east_asian_width", True, "display.width", 200):
                print(show.drop(columns=["レース数"]).to_string())
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
