import os
import whisper

WHISPER_MODEL = os.getenv("WHISPER_MODEL" , "small")

_model = None

def load_model():

    global _model

    if _model is None:
        print(f"Loading Whisper model" )
        _model = whisper.load_model(WHISPER_MODEL)

    return _model

def transcribe_chunk(chunk_path: str , translate: bool = False)-> str:
    """Transcribe a single audio chunk using the Whisper model."""
    model = load_model()

    task = "translate" if translate else "transcribe"
    result = model.transcribe(chunk_path , task=task)
    return result["text"]


def transcribe_all(chunks : list , translate : bool = False)-> str:
    """Transcribe all audio chunks and return the combined text."""
    full_transcription = ""
    for i, chunks in enumerate(chunks):
        print(f"Transcribing chunk {i+1}/{len(chunks)}: {chunks}")
        text = transcribe_chunk(chunks, translate)
        full_transcription += text + " "
    print("Transcription complete.")

    return full_transcription
    