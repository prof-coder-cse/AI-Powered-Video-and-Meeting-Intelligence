import yt_dlp
from pydub import AudioSegment
import os
import shutil
from pathlib import Path
from pydub.utils import mediainfo_json
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



def download_youtube_audio(url : str)-> str:
    output_path = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")
    ydl_opts = {
    'format': 'bestaudio/best',
    'outtmpl': output_path,
    'ffmpeg_location': FFMPEG_PATH,

    'js_runtimes': {
        'deno': {}
    },

    'extractor_args': {
        'youtube': {
            'player_client': ['default,-ios']
        }
    },

    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        filename = str(Path(filename).with_suffix(".mp3"))
    return filename
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
