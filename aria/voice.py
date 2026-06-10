"""ARIA Voice Interface — Talk to ARIA with your voice."""

import os, sys, time, subprocess, logging
import httpx

logger = logging.getLogger(__name__)

OLLAMA_URL = os.environ.get("ARIA_OLLAMA_URL", "http://172.19.16.1:11434")
AUDIO_PATH = "/mnt/c/Users/me/aria_recording.wav"
RECORD_SCRIPT = "C:\\Users\\me\\aria_record.ps1"

C = "\033[96m"; G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; B = "\033[1m"; D = "\033[2m"; X = "\033[0m"

_whisper_model = None

def _get_whisper():
    global _whisper_model
    if _whisper_model is None:
        print(f"{D}Loading Whisper model...{X}")
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel("base.en", device="cpu", compute_type="int8")
        print(f"{G}Whisper ready.{X}")
    return _whisper_model

def record_audio(duration=5):
    try:
        print(f"{Y}Listening ({duration}s)...{X}")
        subprocess.run(
            ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", RECORD_SCRIPT,
             "-Duration", str(duration), "-Output", "C:\\Users\\me\\aria_recording.wav"],
            capture_output=True, timeout=duration + 10
        )
        if os.path.exists(AUDIO_PATH) and os.path.getsize(AUDIO_PATH) > 1000:
            return AUDIO_PATH
    except Exception as e:
        logger.error(f"Recording error: {e}")
    return None

def transcribe(audio_path):
    model = _get_whisper()
    segments, info = model.transcribe(audio_path, beam_size=5)
    return " ".join(s.text for s in segments).strip()

def speak(text):
    clean = text.replace('"', "'").replace("\n", " ").replace("\r", " ")
    if len(clean) > 1500:
        clean = clean[:1500] + "... that is all I will say aloud."
    # Escape for PowerShell
    clean = clean.replace("$", "``$")
    try:
        subprocess.run(
            ["powershell.exe", "-Command",
             f'Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.Rate = 1; $s.Speak("{clean}")'],
            capture_output=True, timeout=120
        )
    except Exception as e:
        logger.error(f"TTS error: {e}")

def query_aria(message):
    try:
        prompt_path = "aria/prompts/general.md"
        system = "You are ARIA, a helpful AI assistant."
        if os.path.exists(prompt_path):
            with open(prompt_path) as f:
                system = f.read().strip()
        system += " Keep responses concise since they will be spoken aloud. 2-3 sentences max unless asked for detail."
        resp = httpx.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": "qwen3:8b",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": message},
                ],
                "stream": False,
                "options": {"temperature": 0.7, "num_predict": 500},
            },
            timeout=120,
        )
        if resp.status_code == 200:
            content = resp.json().get("message", {}).get("content", "").strip()
            # Strip thinking tags
            if "<think>" in content:
                end = content.find("</think>")
                if end > 0:
                    content = content[end + 8:].strip()
            return content
    except Exception as e:
        logger.error(f"Query error: {e}")
    return "Sorry, I could not process that."

def voice_chat(record_seconds=5):
    print(f"""
{C}{B}+========================================+
|         ARIA Voice Interface           |
|   Speak naturally, ARIA listens        |
+========================================+{X}
{D}Press Enter to start recording ({record_seconds}s per turn).
Say 'exit' or 'quit' to stop. Ctrl+C to quit.{X}
""")
    _get_whisper()

    while True:
        try:
            input(f"{G}{B}Press Enter to speak...{X}")
            audio = record_audio(record_seconds)
            if not audio:
                print(f"{R}Recording failed. Try again.{X}")
                continue

            print(f"{D}Transcribing...{X}")
            text = transcribe(audio)
            if not text:
                print(f"{Y}Didn't catch that. Try again.{X}")
                continue

            print(f"{G}You: {text}{X}")

            if text.lower().strip().rstrip(".!") in ("exit", "quit", "stop", "goodbye"):
                speak("Goodbye!")
                print(f"{D}Voice chat ended.{X}")
                break

            print(f"{D}Thinking...{X}")
            response = query_aria(text)
            print(f"{C}{B}ARIA: {response}{X}")
            speak(response)

        except KeyboardInterrupt:
            print(f"\n{D}Voice chat ended.{X}")
            break
        except Exception as e:
            print(f"{R}Error: {e}{X}")
