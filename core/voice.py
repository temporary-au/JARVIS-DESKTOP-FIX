from __future__ import annotations
import threading
import tempfile
import wave
from pathlib import Path
from .paths import DATA_DIR

class VoiceController:
    """Push-to-talk input plus Piper-only offline speech output. No Windows TTS fallback."""
    def __init__(self, app_dir: Path):
        self.app_dir = Path(app_dir)
        self.frames = []
        self.stream = None
        self.last_path = DATA_DIR / "Voice" / "last_recording.wav"
        self._record_lock = threading.Lock()
        self._speech_lock = threading.Lock()
        self._piper_voice = None
        self._piper_model = None
        self._last_error = None

    @property
    def piper_model_path(self) -> Path:
        return self.app_dir / "Voice" / "Piper" / "en_GB-jarvis-high.onnx"

    def piper_status(self) -> str:
        if not self.piper_model_path.is_file():
            return "PIPER MODEL MISSING"
        if self._piper_voice is None:
            return "PIPER MODEL FOUND • NOT LOADED"
        return "PIPER READY"

    def _load_piper(self):
        model = self.piper_model_path
        config = Path(str(model) + ".json")
        if not model.is_file():
            raise RuntimeError(f"Piper voice model not found: {model}\nPlace the .onnx and matching .onnx.json files in Voice\\Piper.")
        if not config.is_file():
            raise RuntimeError(f"Piper configuration not found: {config}\nThe matching .onnx.json file is required.")
        if self._piper_voice is not None and self._piper_model == model:
            return self._piper_voice
        try:
            from piper import PiperVoice
            self._piper_voice = PiperVoice.load(str(model), config_path=str(config))
        except Exception as exc:
            raise RuntimeError(f"Could not load Piper voice: {exc}") from exc
        self._piper_model = model
        return self._piper_voice

    def start_recording(self):
        try:
            import sounddevice as sd
        except Exception as exc:
            raise RuntimeError(f"Microphone library unavailable: {exc}") from exc
        with self._record_lock:
            if self.stream is not None:
                return
            self.frames = []
            def callback(indata, frames, time_info, status):
                if status:
                    self._last_error = str(status)
                with self._record_lock:
                    self.frames.append(indata.copy())
            self.stream = sd.InputStream(samplerate=16000, channels=1, dtype="float32", callback=callback)
            self.stream.start()

    def stop_recording(self):
        with self._record_lock:
            stream = self.stream
            self.stream = None
        if stream is None:
            return
        stream.stop()
        stream.close()
        import numpy as np
        import soundfile as sf
        with self._record_lock:
            frames = list(self.frames)
            self.frames.clear()
        if not frames:
            raise RuntimeError("No audio was captured. Check microphone permissions and try again.")
        audio = np.concatenate(frames, axis=0).reshape(-1)
        self.last_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(self.last_path), audio, 16000)

    def transcribe_last_recording(self) -> str:
        if not self.last_path.is_file():
            raise RuntimeError("There is no recording to transcribe.")
        try:
            from faster_whisper import WhisperModel
        except Exception as exc:
            raise RuntimeError(f"Offline transcription dependency missing: {exc}") from exc
        model_dir = DATA_DIR / "Voice" / "whisper-base"
        model_dir.mkdir(parents=True, exist_ok=True)
        model = WhisperModel("base", device="cpu", compute_type="int8", download_root=str(model_dir))
        segments, _ = model.transcribe(str(self.last_path), vad_filter=True)
        text = " ".join(segment.text.strip() for segment in segments).strip()
        if not text:
            raise RuntimeError("No speech was recognised. Try speaking closer to the microphone.")
        return text

    def speak(self, text: str):
        text = str(text).strip()
        if not text:
            return
        # Fail loudly if Piper is missing; do not switch to the host speech engine.
        with self._speech_lock:
            voice = self._load_piper()
            try:
                import sounddevice as sd
                import soundfile as sf
                (DATA_DIR / "Logs").mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(prefix="jarvis_tts_", suffix=".wav", dir=str(DATA_DIR / "Logs"), delete=False) as tmp:
                    temp_path = Path(tmp.name)
                try:
                    with wave.open(str(temp_path), "wb") as wav_file:
                        voice.synthesize_wav(text, wav_file)
                    audio, sample_rate = sf.read(str(temp_path), dtype="float32", always_2d=False)
                    sd.play(audio, sample_rate)
                    sd.wait()
                finally:
                    try:
                        temp_path.unlink(missing_ok=True)
                    except Exception:
                        pass
            except Exception as exc:
                raise RuntimeError(f"Piper speech generation/playback failed: {exc}") from exc

    def close(self):
        with self._record_lock:
            stream = self.stream
            self.stream = None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
