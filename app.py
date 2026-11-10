import re
import shutil
import tempfile
from pathlib import Path
from urllib.parse import quote, urlparse

import imageio_ffmpeg
import yt_dlp
from flask import Flask, Response, jsonify, render_template, request
from yt_dlp.utils import DownloadError

ROOT = Path(__file__).resolve().parent
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

app = Flask(__name__)


def valid_url(url: str) -> bool:
    parsed = urlparse(url.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def ydl_opts(**extra):
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "noprogress": True,
        "ffmpeg_location": FFMPEG,
        "socket_timeout": 30,
    }
    opts.update(extra)
    return opts


def clean_error(exc: Exception) -> str:
    text = str(exc).strip()
    text = re.sub(r"^ERROR:\s*", "", text)
    return text or "No se pudo procesar ese enlace."


def extract(url: str):
    with yt_dlp.YoutubeDL(ydl_opts()) as ydl:
        return ydl.extract_info(url, download=False)


VIDEO_EXTS = {"mp4", "webm", "mkv", "mov", "m4v", "avi"}


def is_video(fmt: dict) -> bool:
    vcodec = fmt.get("vcodec")
    if vcodec == "none":
        return False
    if vcodec:
        return True
    return (fmt.get("ext") or "") in VIDEO_EXTS


def video_qualities(info: dict) -> list[dict]:
    by_height: dict[int, dict] = {}
    saw_video = False
    for fmt in info.get("formats") or []:
        if not is_video(fmt):
            continue
        saw_video = True
        height = fmt.get("height")
        if not height:
            continue
        tbr = fmt.get("tbr") or 0
        current = by_height.get(height)
        if current is None or tbr > current["tbr"]:
            by_height[height] = {"height": int(height), "tbr": tbr}

    qualities = [
        {"height": item["height"], "label": f"{item['height']}p"}
        for item in sorted(by_height.values(), key=lambda item: item["height"], reverse=True)
    ]
    if not qualities and saw_video:
        qualities = [{"height": 0, "label": "Mejor disponible"}]
    return qualities


def mp4_format(height: int) -> str:
    if height <= 0:
        return "bestvideo+bestaudio/best"
    return (
        f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/"
        f"bestvideo[height<={height}]+bestaudio/"
        f"best[height<={height}]/best"
    )


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/qualities")
def qualities():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not valid_url(url):
        return jsonify(error="Pega un enlace http o https."), 400
    try:
        info = extract(url)
    except DownloadError as exc:
        return jsonify(error=clean_error(exc)), 400
    except Exception as exc:
        return jsonify(error=clean_error(exc)), 400

    options = video_qualities(info)
    if not options:
        return jsonify(error="Ese enlace no tiene video para guardar en MP4."), 400
    return jsonify(title=info.get("title") or "Video", qualities=options)


@app.post("/api/download")
def download():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    kind = data.get("kind")
    if not valid_url(url):
        return jsonify(error="Pega un enlace http o https."), 400
    if kind not in {"mp3", "mp4"}:
        return jsonify(error="Elige MP3 o MP4."), 400

    height = 0
    if kind == "mp4":
        try:
            height = int(data.get("height") or 0)
        except (TypeError, ValueError):
            return jsonify(error="Elige una calidad."), 400
        if height < 0:
            return jsonify(error="Elige una calidad."), 400

    tmp = Path(tempfile.mkdtemp(prefix="bajar-"))
    outtmpl = str(tmp / "%(title).80B.%(ext)s")
    if kind == "mp3":
        opts = ydl_opts(
            format="bestaudio/best",
            outtmpl=outtmpl,
            postprocessors=[
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
        )
    else:
        opts = ydl_opts(
            format=mp4_format(height),
            outtmpl=outtmpl,
            merge_output_format="mp4",
        )

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        files = [path for path in tmp.iterdir() if path.is_file()]
        if not files:
            raise RuntimeError("La descarga terminó sin archivo.")
    except DownloadError as exc:
        shutil.rmtree(tmp, ignore_errors=True)
        return jsonify(error=clean_error(exc)), 400
    except Exception as exc:
        shutil.rmtree(tmp, ignore_errors=True)
        return jsonify(error=clean_error(exc)), 400

    chosen = max(files, key=lambda path: path.stat().st_size)

    def generate():
        try:
            with chosen.open("rb") as handle:
                while True:
                    chunk = handle.read(512 * 1024)
                    if not chunk:
                        break
                    yield chunk
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    response = Response(generate(), mimetype="application/octet-stream")
    response.headers["Content-Length"] = str(chosen.stat().st_size)
    response.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(chosen.name)}"
    return response


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050, debug=False)
