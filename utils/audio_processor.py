import yt_dlp
from pydub import AudioSegment
import os
import shutil
from pathlib import Path
from pydub.utils import mediainfo_json
import requests
import subprocess
import platform

# ── Auto-install Deno if missing (needed on Streamlit Cloud) ──
def _ensure_deno():
    """Install Deno if it's not already available on the system."""
    if shutil.which("deno"):
        return  # already available

    print("Deno not found — installing automatically...")
    deno_dir = Path.home() / ".deno"
    deno_bin = deno_dir / "bin" / "deno"

    if not deno_bin.exists():
        # Official one-liner adapted for non-interactive use
        subprocess.run(
            ["sh", "-c", "curl -fsSL https://deno.land/install.sh | sh"],
            check=True,
            env={**os.environ, "DENO_INSTALL": str(deno_dir)},
        )

    if deno_bin.exists():
        # Make deno discoverable for subprocesses
        os.environ["PATH"] = f"{deno_dir / 'bin'}:{os.environ.get('PATH', '')}"
        print(f"Deno installed at {deno_bin}")
    else:
        raise RuntimeError(
            "Failed to install Deno. YouTube downloads may not work."
        )

_ensure_deno()

# Cross-platform FFmpeg configuration
FFMPEG_PATH = shutil.which("ffmpeg") or os.path.expanduser("~/Downloads/ffmpeg")
FFPROBE_PATH = shutil.which("ffprobe") or os.path.expanduser("~/Downloads/ffprobe")

if not os.path.isfile(FFMPEG_PATH):
    raise RuntimeError("FFmpeg not found. Please install FFmpeg.")

if not os.path.isfile(FFPROBE_PATH):
    raise RuntimeError("FFprobe not found. Please install FFprobe.")

AudioSegment.converter = FFMPEG_PATH
AudioSegment.ffprobe = FFPROBE_PATH


DOWNLOAD_DIR = "downloads" # saari cheezo ko ism save krke rakhenge
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

import importlib.util

def check_pot_provider():
    plugin = importlib.util.find_spec(
        "yt_dlp_plugins.extractor.getpot_bgutil_script"
    )
    print("BgUtils Script Plugin:", "Installed" if plugin else "Not Installed")
# def check_pot_provider():
#     plugin = importlib.util.find_spec(
#         "yt_dlp_plugins.extractor.getpot_bgutil_script"
#     )
#     print("BgUtils Script Plugin:", "Installed" if plugin else "Not Installed")

def get_bgutil_server_home():
    # Local Mac installation
    local_server = Path.home() / "bgutil-ytdlp-pot-provider" / "server"

    if local_server.is_dir():
        server_dir = local_server
    else:
        # Streamlit Cloud installation
        cache_dir = Path.home() / ".cache" / "bgutil-ytdlp-pot-provider"
        repo_dir = cache_dir / "repo"
        server_dir = repo_dir / "server"

        if not server_dir.exists():
            cache_dir.mkdir(parents=True, exist_ok=True)

            subprocess.run(
                [
                    "git", "clone",
                    "--depth", "1",
                    "--branch", "2.0.2",
                    "https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git",
                    str(repo_dir)
                ],
                check=True
            )

        if not (server_dir / "src" / "generate_once.ts").exists():
            raise RuntimeError("BgUtils provider source not found!")

    # Install provider dependencies once
    if not (server_dir / "node_modules").exists():
        subprocess.run(
            ["deno", "install", "--allow-scripts=npm:canvas", "--frozen"],
            cwd=str(server_dir),
            check=True
        )

    return str(server_dir)


def fetch_youtube_transcript(url: str, language_code: str = "en") -> str | None:
    """Fetch transcripts/subtitles directly from YouTube without downloading media streams.
    Bypasses datacenter IP blocks (HTTP 403) and saves processing time & memory.
    """
    import json
    import re
    import urllib.request

    # Strategy 1: youtube_transcript_api
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", url)
        if match:
            video_id = match.group(1)
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript = None
            langs = [language_code, "en", "hi", "en-US", "en-GB"]
            try:
                transcript = transcript_list.find_transcript(langs)
            except Exception:
                try:
                    transcript = transcript_list.find_generated_transcript(langs)
                except Exception:
                    # fallback to any available transcript
                    for t in transcript_list:
                        transcript = t
                        break

            if transcript:
                data = transcript.fetch()
                parts = [entry["text"] for entry in data if entry.get("text")]
                text = " ".join(parts).strip()
                if text:
                    print(f"Direct transcript fetched via YouTubeTranscriptApi: {len(text)} characters")
                    return text
    except Exception as exc:
        print(f"YouTubeTranscriptApi attempt skipped/failed: {exc}")

    # Strategy 2: yt-dlp subtitle metadata extraction (downloads JSON, not video/audio)
    try:
        ydl_opts = {
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "quiet": True,
            "no_warnings": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            subtitles = info.get("subtitles") or {}
            auto_subtitles = info.get("automatic_captions") or {}

            target_subs = None
            langs = [language_code, "en", "en-US", "en-GB", "en-orig", "hi"]
            for lang in langs:
                if lang in subtitles:
                    target_subs = subtitles[lang]
                    break
                elif lang in auto_subtitles:
                    target_subs = auto_subtitles[lang]
                    break

            if not target_subs and auto_subtitles:
                first_lang = list(auto_subtitles.keys())[0]
                target_subs = auto_subtitles[first_lang]

            if target_subs:
                json_fmt = next((fmt for fmt in target_subs if fmt.get("ext") == "json3"), None)
                if json_fmt and json_fmt.get("url"):
                    req = urllib.request.Request(
                        json_fmt["url"],
                        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                    )
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        sub_data = json.loads(resp.read().decode("utf-8"))
                        lines = []
                        for event in sub_data.get("events", []):
                            segs = event.get("segs", [])
                            seg_text = "".join(s.get("utf8", "") for s in segs).strip()
                            if seg_text and seg_text != "\n":
                                lines.append(seg_text)
                        text = " ".join(lines).strip()
                        if text:
                            print(f"Direct transcript fetched via yt-dlp subtitles: {len(text)} characters")
                            return text
    except Exception as exc:
        print(f"yt-dlp subtitle extraction skipped/failed: {exc}")

    return None


def download_youtube_audio(url: str) -> str:
    plugin = importlib.util.find_spec(
        "yt_dlp_plugins.extractor.getpot_bgutil_script"
    )
    print("BgUtils Script Plugin:", "Installed" if plugin else "Not Installed")

    output_path = os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s")

    # Strategy 1: Use PO tokens + cloud-friendly player clients
    ydl_opts = {
        "format": "worstaudio/worst",  # smaller = less likely to be blocked
        "outtmpl": output_path,
        "ffmpeg_location": FFMPEG_PATH,
        "retries": 5,
        "fragment_retries": 5,
        "socket_timeout": 30,
        "geo_bypass": True,
        "js_runtimes": {
            "deno": {}
        },
        "extractor_args": {
            "youtube": {
                "player_client": ["android_vr", "mediaconnect", "mweb", "tv"],
                "player_skip": ["webpage"],
            },
            "youtubepot-bgutilscript": {
                "server_home": [get_bgutil_server_home()]
            }
        },
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "128",
        }],
    }

    strategies = [
        ("PO token + android_vr/mediaconnect", ydl_opts),
        ("Fallback: web client only", {
            **ydl_opts,
            "extractor_args": {
                "youtube": {
                    "player_client": ["web", "mweb"],
                },
                "youtubepot-bgutilscript": {
                    "server_home": [get_bgutil_server_home()]
                }
            },
        }),
    ]

    last_error = None
    for name, opts in strategies:
        try:
            print(f"Trying download strategy: {name}")
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)

                filename = info.get("filepath")
                if not filename:
                    requested = info.get("requested_downloads", [])
                    if requested:
                        filename = requested[0].get("filepath")

                if filename and os.path.isfile(filename):
                    print(f"Download succeeded with strategy: {name}")
                    return filename

                raise FileNotFoundError(
                    f"Downloaded audio file not found. Path: {filename}"
                )
        except Exception as e:
            print(f"Strategy '{name}' failed: {e}")
            last_error = e
            continue

    raise RuntimeError(
        "YouTube blocked the download from this cloud server (HTTP 403). "
        "This is a known limitation — YouTube restricts downloads from "
        "datacenter IPs. Please use the **Upload a file** tab instead: "
        "download the video/audio to your device first, then upload it."
    ) from last_error

# data = (download_youtube_audio("https://youtu.be/v0ynfDPpe4E?si=Zvx0OQTIhOCD4S5U"))


def convert_to_wav(input_path: str) -> str:

    output_path = os.path.splitext(input_path)[0] + "_converted.wav"

    audio = AudioSegment.from_file(input_path)

    audio = audio.set_channels(1).set_frame_rate(16000)

    audio.export(output_path, format="wav")

    return output_path
# data_final = convert_to_wav(data)

# function to convert audio into chunks

def chunk_audio(wav_path : str  , chunk_minutes : int = 10) -> list:
    """Chunk the audio file into smaller segments of specified duration in minutes."""
    audio = AudioSegment.from_wav(wav_path)
    chunk_ms = chunk_minutes * 60 * 1000  # Convert minutes to milliseconds
    chunks = []

    for i, start in enumerate(range(0, len(audio), chunk_ms)):
        # end = min(start + chunk_length_ms, len(audio))
        chunk = audio[start: start + chunk_ms]
        chunk_path = f"{wav_path}_chunk_{i}.wav"
        chunk.export(chunk_path, format="wav")
        chunks.append(chunk_path)

    return chunks
    
# print(chunk_audio(data_final))


def process_audio_from_youtube(source: str) -> list:
    """Download audio from YouTube, convert to WAV, and chunk it."""

    if source.startswith(("http://", "https://")):
        print("Youtube path detected, downloading audio...")
        audio_path = download_youtube_audio(source)

    else:
        print("Local file path detected...")
        audio_path = source

    # Convert downloaded/local audio into WAV
    print("Converting audio to WAV...")
    wave_path = convert_to_wav(audio_path)

    # Chunk only WAV files
    print("Chunking the audio...")
    chunks = chunk_audio(wave_path)

    print(f"Audio processing complete. {len(chunks)} chunks created.")

    return chunks
