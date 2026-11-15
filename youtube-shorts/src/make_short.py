"""台本(YAML)から YouTube ショート(1080x1920 mp4)を作る。

使い方:
    python src/make_short.py scripts/001_flamingo.yaml
    python src/make_short.py scripts/001_flamingo.yaml --dummy-tts   # VOICEVOX無しで動作確認

必要なもの:
    - VOICEVOX を起動しておく（http://127.0.0.1:50021）
    - pip install -r requirements.txt
"""
from __future__ import annotations

import argparse
import io
import math
import shutil
import struct
import subprocess
import sys
import textwrap
import wave
from pathlib import Path

import requests
import yaml
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
W, H = 1080, 1920
PAUSE_SEC = 0.25  # セリフ間の間

# キャラ設定（style_id は VOICEVOX の「ノーマル」）
CHARACTERS = {
    "zundamon": {
        "name": "ずんだもん", "credit": "VOICEVOX:ずんだもん", "style_id": 3,
        "color": (120, 200, 80), "image": "zundamon.png", "side": "left",
    },
    "metan": {
        "name": "四国めたん", "credit": "VOICEVOX:四国めたん", "style_id": 2,
        "color": (230, 90, 160), "image": "metan.png", "side": "right",
    },
}

FONT_CANDIDATES = [
    ROOT / "assets/fonts/font.ttf",
    ROOT / "assets/fonts/font.otf",
    Path("C:/Windows/Fonts/meiryob.ttc"),
    Path("C:/Windows/Fonts/YuGothB.ttc"),
    Path("/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"),
    Path("/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf"),
]


def find_font() -> str:
    for p in FONT_CANDIDATES:
        if p.exists():
            return str(p)
    sys.exit("日本語フォントが見つかりません。assets/fonts/font.ttf を置いてください。")


def find_ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        sys.exit("ffmpeg が見つかりません。pip install imageio-ffmpeg を実行してください。")


# ---------------- 音声 ----------------
def tts_voicevox(text: str, style_id: int, host: str, speed: float) -> bytes:
    q = requests.post(f"{host}/audio_query", params={"text": text, "speaker": style_id}, timeout=60)
    q.raise_for_status()
    query = q.json()
    query["speedScale"] = speed
    query["prePhonemeLength"] = 0.05
    query["postPhonemeLength"] = 0.05
    r = requests.post(f"{host}/synthesis", params={"speaker": style_id}, json=query, timeout=120)
    r.raise_for_status()
    return r.content


def tts_dummy(text: str, style_id: int, *_args) -> bytes:
    """動作確認用：文字数に応じた長さのビープ音"""
    rate, dur = 24000, 0.13 * len(text) + 0.3
    freq = 440 if style_id == 3 else 330
    frames = b"".join(
        struct.pack("<h", int(3000 * math.sin(2 * math.pi * freq * i / rate)))
        for i in range(int(rate * dur))
    )
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(frames)
    return buf.getvalue()


def concat_wavs(paths: list[Path], out: Path, pause: float) -> list[float]:
    """wav を連結し、各セリフの表示秒数を返す"""
    durations = []
    params = None
    with wave.open(str(out), "wb") as dst:
        for p in paths:
            with wave.open(str(p), "rb") as src:
                if params is None:
                    params = src.getparams()
                    dst.setparams(params)
                frames = src.readframes(src.getnframes())
                dst.writeframes(frames)
                silence = b"\x00" * int(params.framerate * pause) * params.sampwidth * params.nchannels
                dst.writeframes(silence)
                durations.append(src.getnframes() / params.framerate + pause)
    return durations


# ---------------- 画像 ----------------
def load_char_image(key: str, height: int) -> Image.Image | None:
    p = ROOT / "assets/characters" / CHARACTERS[key]["image"]
    if not p.exists():
        return None
    img = Image.open(p).convert("RGBA")
    return img.resize((int(img.width * height / img.height), height))


def draw_placeholder_char(draw: ImageDraw.ImageDraw, key: str, cx: int, cy: int, active: bool, font_path: str):
    c = CHARACTERS[key]
    r = 170
    col = c["color"] if active else tuple(int(v * 0.45 + 60) for v in c["color"])
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=col, outline=(255, 255, 255), width=10)
    f = ImageFont.truetype(font_path, 48)
    draw.text((cx, cy), c["name"], font=f, fill=(255, 255, 255), anchor="mm",
              stroke_width=4, stroke_fill=(40, 40, 40))


def wrap_jp(text: str, width: int) -> list[str]:
    return textwrap.wrap(text, width=width) or [""]


def render_frame(script: dict, line: dict, font_path: str, bg: Image.Image | None) -> Image.Image:
    img = bg.copy() if bg else Image.new("RGB", (W, H), (30, 36, 60))
    if not bg:  # グラデーション背景
        d = ImageDraw.Draw(img)
        for y in range(H):
            t = y / H
            d.line([(0, y), (W, y)], fill=(int(30 + 40 * t), int(40 + 20 * t), int(80 + 40 * t)))
    d = ImageDraw.Draw(img, "RGBA")

    # タイトル帯
    title_font = ImageFont.truetype(font_path, 66)
    d.rectangle((0, 140, W, 420), fill=(0, 0, 0, 170))
    title_lines = [t for part in script["title"].split("\n") for t in wrap_jp(part, 15)][:2]
    for i, t in enumerate(title_lines):
        d.text((W // 2, 220 + i * 100), t, font=title_font, fill=(255, 230, 60), anchor="mm",
               stroke_width=6, stroke_fill=(0, 0, 0))

    # キャラ
    for key, c in CHARACTERS.items():
        active = key == line["speaker"]
        cx = 270 if c["side"] == "left" else W - 270
        char_img = load_char_image(key, 700 if active else 640)
        if char_img:
            if not active:  # 話していない方は半透明
                char_img.putalpha(char_img.getchannel("A").point(lambda a: int(a * 0.6)))
            img.paste(char_img, (cx - char_img.width // 2, 1700 - char_img.height), char_img)
        else:
            draw_placeholder_char(d, key, cx, 1450, active, font_path)

    # 字幕
    c = CHARACTERS[line["speaker"]]
    sub_font = ImageFont.truetype(font_path, 62)
    lines = wrap_jp(line["text"], 14)
    box_h = 70 + 90 * len(lines)
    top = 640
    d.rounded_rectangle((50, top, W - 50, top + box_h), radius=40,
                        fill=(255, 255, 255, 235), outline=c["color"] + (255,), width=12)
    name_font = ImageFont.truetype(font_path, 44)
    tag_w = int(d.textlength(c["name"], font=name_font)) + 50
    d.rounded_rectangle((80, top - 45, 80 + tag_w, top + 25), radius=20, fill=c["color"])
    d.text((100, top - 10), c["name"], font=name_font, fill=(255, 255, 255), anchor="lm")
    for i, t in enumerate(lines):
        d.text((W // 2, top + 80 + i * 90), t, font=sub_font, fill=(30, 30, 30), anchor="mm")

    # クレジット
    cred_font = ImageFont.truetype(font_path, 32)
    d.text((W // 2, H - 90), " / ".join(ch["credit"] for ch in CHARACTERS.values()),
           font=cred_font, fill=(255, 255, 255, 200), anchor="mm")
    return img.convert("RGB")


# ---------------- メイン ----------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script", type=Path)
    ap.add_argument("--host", default="http://127.0.0.1:50021")
    ap.add_argument("--speed", type=float, default=1.15)
    ap.add_argument("--dummy-tts", action="store_true", help="VOICEVOX を使わずビープ音で確認")
    args = ap.parse_args()

    script = yaml.safe_load(args.script.read_text(encoding="utf-8"))
    name = args.script.stem
    work = ROOT / "build" / name
    (work / "audio").mkdir(parents=True, exist_ok=True)
    (work / "frames").mkdir(parents=True, exist_ok=True)
    (ROOT / "output").mkdir(exist_ok=True)

    font_path = find_font()
    ffmpeg = find_ffmpeg()
    tts = tts_dummy if args.dummy_tts else tts_voicevox

    bg_files = sorted((ROOT / "assets/backgrounds").glob("*.[pj][np]g"))
    bg = Image.open(bg_files[0]).convert("RGB").resize((W, H)) if bg_files else None

    wavs, frames = [], []
    for i, line in enumerate(script["lines"]):
        c = CHARACTERS[line["speaker"]]
        print(f"[{i + 1}/{len(script['lines'])}] {c['name']}: {line['text']}")
        wav = work / "audio" / f"{i:03d}.wav"
        wav.write_bytes(tts(line["text"], c["style_id"], args.host, args.speed))
        wavs.append(wav)
        png = work / "frames" / f"{i:03d}.png"
        render_frame(script, line, font_path, bg).save(png)
        frames.append(png)

    voice = work / "voice.wav"
    durations = concat_wavs(wavs, voice, PAUSE_SEC)
    total = sum(durations)
    print(f"合計 {total:.1f} 秒")
    if total > 60:
        print("⚠ 60秒を超えています。台本を短くしてください。")

    # 画像の表示時間リスト（ffmpeg concat demuxer）
    lst = work / "frames.txt"
    with lst.open("w", encoding="utf-8") as f:
        for png, dur in zip(frames, durations):
            f.write(f"file '{png.as_posix()}'\nduration {dur:.3f}\n")
        f.write(f"file '{frames[-1].as_posix()}'\n")

    out = ROOT / "output" / f"{name}.mp4"
    bgm_files = sorted((ROOT / "assets/bgm").glob("*.mp3")) + sorted((ROOT / "assets/bgm").glob("*.wav"))
    cmd = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-i", str(voice)]
    if bgm_files:
        cmd += ["-stream_loop", "-1", "-i", str(bgm_files[0]),
                "-filter_complex", "[2:a]volume=0.12[b];[1:a][b]amix=inputs=2:duration=first[a]",
                "-map", "0:v", "-map", "[a]"]
    else:
        cmd += ["-map", "0:v", "-map", "1:a"]
    cmd += ["-r", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
            "-t", f"{total:.3f}", str(out)]
    subprocess.run(cmd, check=True, capture_output=True)

    # 投稿用テキスト
    meta = ROOT / "output" / f"{name}_投稿用.txt"
    credits = "\n".join(c["credit"] for c in CHARACTERS.values())
    meta.write_text(
        f"【タイトル】\n{script['title']} {' '.join(script.get('hashtags', [])[:3])}\n\n"
        f"【説明欄】\n{script.get('description', '').strip()}\n\n{' '.join(script.get('hashtags', []))}\n\n"
        f"音声:\n{credits}\n",
        encoding="utf-8",
    )
    print(f"完成: {out}\n投稿用テキスト: {meta}")


if __name__ == "__main__":
    main()
