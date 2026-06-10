import re, sys, time, logging, subprocess, httpx

logger = logging.getLogger(__name__)
OLLAMA_URL = "http://172.19.16.1:11434"

def _query_llm(prompt, model="qwen3:8b"):
    try:
        resp = httpx.post(f"{OLLAMA_URL}/api/chat", json={"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False, "options": {"temperature": 0.3, "num_predict": 1000, "think": False}}, timeout=60)
        if resp.status_code == 200:
            return resp.json().get("message", {}).get("content", "").strip()
    except: pass
    return ""

def _get_clipboard():
    try:
        result = subprocess.run(["powershell.exe", "-Command", "Get-Clipboard"], capture_output=True, text=True, timeout=5)
        return result.stdout.strip()
    except: return ""

def _detect_type(text):
    if not text: return "empty", None
    cve = re.search(r"CVE-\d{4}-\d{4,}", text, re.IGNORECASE)
    if cve: return "cve", cve.group(0)
    if any(kw in text for kw in ["Traceback", "Error:", "Exception:", "FAILED", "panic:", "fatal:"]): return "error", text
    url = re.search(r"https?://[^\s]+", text)
    if url: return "url", url.group(0)
    if any(ind in text for ind in ["def ", "class ", "function ", "import ", "const ", "let ", "var ", "if (", "#!/", "SELECT "]): return "code", text
    ip = re.search(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", text)
    if ip: return "ip", ip.group(0)
    return "text", text

C = "\033[96m"; G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; B = "\033[1m"; D = "\033[2m"; X = "\033[0m"

def monitor(interval=2):
    print(f"{C}{B}ARIA Clipboard Monitor{X}")
    print(f"{D}Watching clipboard... Copy something to analyze. Ctrl+C to stop.{X}")
    last = ""
    while True:
        try:
            cur = _get_clipboard()
            if cur and cur != last:
                last = cur
                t, data = _detect_type(cur)
                if t == "cve":
                    print(f"\n{Y}{B}CVE Detected: {data}{X}")
                    r = _query_llm(f"Explain {data} briefly: what it affects, severity, and how to mitigate it.")
                    if r: print(f"{C}{r}{X}")
                elif t == "error":
                    print(f"\n{R}{B}Error Detected{X}")
                    print(f"{D}{data[:200]}{X}")
                    r = _query_llm(f"Explain this error and suggest a fix:\n\n{data[:1500]}", model="qwen2.5-coder:7b")
                    if r: print(f"\n{G}{r}{X}")
                elif t == "code":
                    lines = data.split("\n")
                    print(f"\n{C}{B}Code Detected ({len(lines)} lines){X}")
                    r = _query_llm(f"Briefly review this code for bugs and security issues:\n\n{data[:2000]}", model="qwen2.5-coder:7b")
                    if r: print(f"\n{G}{r}{X}")
                elif t == "url":
                    print(f"\n{C}{B}URL Detected: {data}{X}")
                    r = _query_llm(f"What can you tell me about this URL? Any security concerns? URL: {data}")
                    if r: print(f"{G}{r}{X}")
                elif t == "ip":
                    print(f"\n{Y}{B}IP Address Detected: {data}{X}")
                    r = _query_llm(f"What can you tell me about IP address {data}? Private or public? What range?")
                    if r: print(f"{G}{r}{X}")
            time.sleep(interval)
        except KeyboardInterrupt:
            print(f"\n{D}Clipboard monitor stopped.{X}")
            break
        except Exception as e:
            logger.error(f"Monitor error: {e}")
            time.sleep(interval)
