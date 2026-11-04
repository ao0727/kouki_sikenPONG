"""CSV の列定義と読み込み。"""
from __future__ import annotations

import pandas as pd

# 出馬表 CSV に必要な列（空欄 OK の列もある）
ENTRY_COLUMNS = [
    "レースID", "日付", "競馬場", "芝ダ", "距離", "馬場",
    "枠番", "馬番", "馬名", "年齢", "斤量", "騎手", "騎手勝率",
    "馬体重", "体重増減", "単勝オッズ",
    "前走着順", "2走前着順", "3走前着順", "前走頭数",
    "前走上がり3F", "前走距離", "休養週数",
    "距離複勝率", "コース複勝率", "脚質",
]

# 過去レース CSV は出馬表の列 + 着順
RESULT_COLUMN = "着順"

# 必須の列（これが無いと動かない）
REQUIRED = ["レースID", "馬番", "馬名"]

NUMERIC = [
    "距離", "枠番", "馬番", "年齢", "斤量", "騎手勝率", "馬体重", "体重増減",
    "単勝オッズ", "前走着順", "2走前着順", "3走前着順", "前走頭数",
    "前走上がり3F", "前走距離", "休養週数", "距離複勝率", "コース複勝率",
]

RUNNING_STYLES = ["逃げ", "先行", "差し", "追込"]


def load_csv(path: str, need_result: bool = False) -> pd.DataFrame:
    """CSV を読み込み、列をチェックして型をそろえる。"""
    df = None
    for enc in ("utf-8-sig", "cp932"):
        try:
            df = pd.read_csv(path, encoding=enc)
            break
        except UnicodeDecodeError:
            continue
    if df is None:
        raise ValueError(f"{path} の文字コードを判別できません（UTF-8 か Shift_JIS で保存してください）")
    return prepare(df, need_result=need_result)


def prepare(df: pd.DataFrame, need_result: bool = False) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    missing = [c for c in REQUIRED if c not in df.columns]
    if need_result and RESULT_COLUMN not in df.columns:
        missing.append(RESULT_COLUMN)
    if missing:
        raise ValueError(f"CSV に必要な列がありません: {', '.join(missing)}")

    # 任意の列は無ければ空で作る
    for c in ENTRY_COLUMNS:
        if c not in df.columns:
            df[c] = pd.NA

    for c in NUMERIC + ([RESULT_COLUMN] if RESULT_COLUMN in df.columns else []):
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df["レースID"] = df["レースID"].astype(str)
    df["日付"] = pd.to_datetime(df["日付"], errors="coerce")
    df["脚質"] = df["脚質"].astype("string").str.strip()
    return df.reset_index(drop=True)
