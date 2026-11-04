"""tkinter を使った簡単な画面（Windows の Python なら追加インストール不要）。"""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .cli import DEFAULT_MODEL, run_predict
from .columns import load_csv
from .model import KeibaModel
from .report import rank_race, suggest_bets

COLUMNS = ["印", "馬番", "馬名", "勝率", "複勝率", "単勝オッズ", "期待値", "騎手"]


def run_gui() -> None:
    root = tk.Tk()
    root.title("競馬予想アプリ")
    root.geometry("820x600")

    state = {"pred": None}
    method = tk.StringVar(value="auto")
    use_odds = tk.BooleanVar(value=True)
    race_var = tk.StringVar()
    status = tk.StringVar(value="出馬表 CSV を開いてください")

    # 上部の操作バー
    bar = ttk.Frame(root, padding=8)
    bar.pack(fill="x")
    ttk.Button(bar, text="出馬表を開いて予想", command=lambda: open_race()).pack(side="left")
    ttk.Button(bar, text="過去データで学習", command=lambda: train()).pack(side="left", padx=6)
    ttk.Label(bar, text="方式:").pack(side="left", padx=(12, 2))
    ttk.Combobox(bar, textvariable=method, width=7, state="readonly",
                 values=["auto", "score", "ml"]).pack(side="left")
    ttk.Checkbutton(bar, text="オッズを使う", variable=use_odds).pack(side="left", padx=8)
    ttk.Label(bar, text="レース:").pack(side="left", padx=(12, 2))
    race_box = ttk.Combobox(bar, textvariable=race_var, width=16, state="readonly")
    race_box.pack(side="left")
    race_box.bind("<<ComboboxSelected>>", lambda e: show_race())

    tree = ttk.Treeview(root, columns=COLUMNS, show="headings", height=18)
    for c in COLUMNS:
        tree.heading(c, text=c)
        tree.column(c, width=150 if c in ("馬名", "騎手") else 70, anchor="center")
    tree.pack(fill="both", expand=True, padx=8)

    bets = tk.Text(root, height=7)
    bets.pack(fill="x", padx=8, pady=4)
    ttk.Label(root, textvariable=status, anchor="w").pack(fill="x", padx=8, pady=(0, 6))

    def open_race():
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            pred, label = run_predict(path, method.get(), use_odds=use_odds.get())
        except Exception as e:  # 画面ではすべてのエラーを表示して続行
            messagebox.showerror("エラー", str(e))
            return
        state["pred"] = pred
        ids = list(dict.fromkeys(pred["レースID"]))
        race_box["values"] = ids
        race_var.set(ids[0])
        status.set(f"予想方式: {label}")
        show_race()

    def show_race():
        pred = state["pred"]
        if pred is None:
            return
        r = rank_race(pred[pred["レースID"] == race_var.get()])
        tree.delete(*tree.get_children())
        for _, x in r.iterrows():
            tree.insert("", "end", values=(
                x["印"], int(x["馬番"]), x["馬名"], f"{x['勝率']*100:.1f}%",
                f"{x['複勝率']*100:.1f}%", x["単勝オッズ"], x["期待値"], x["騎手"]))
        bets.delete("1.0", "end")
        bets.insert("end", "【買い目の例】\n" + "\n".join(suggest_bets(r)))

    def train():
        path = filedialog.askopenfilename(title="過去レース CSV（着順つき）", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            hist = load_csv(path, need_result=True)
            KeibaModel(use_odds=use_odds.get()).fit(hist).save(DEFAULT_MODEL)
        except Exception as e:
            messagebox.showerror("エラー", str(e))
            return
        messagebox.showinfo("学習完了", f"{hist['レースID'].nunique()} レースで学習しました")

    root.mainloop()
