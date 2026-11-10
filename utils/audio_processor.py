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
