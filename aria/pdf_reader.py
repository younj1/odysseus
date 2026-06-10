"""ARIA PDF Reader — Extract, query, and ingest PDFs."""

import os, json, logging, httpx
from datetime import date

logger = logging.getLogger(__name__)

OLLAMA_URL = os.environ.get("ARIA_OLLAMA_URL", "http://172.19.16.1:11434")

C = "\033[96m"; G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; B = "\033[1m"; D = "\033[2m"; X = "\033[0m"


def _query_llm(prompt, model="qwen3:8b"):
    try:
        resp = httpx.post(f"{OLLAMA_URL}/api/chat", json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 3000},
        }, timeout=180)
        if resp.status_code == 200:
            content = resp.json().get("message", {}).get("content", "").strip()
            if "<think>" in content:
                end = content.find("</think>")
                if end > 0: content = content[end + 8:].strip()
            return content
    except Exception as e:
        logger.error(f"LLM error: {e}")
    return ""


def extract_text(pdf_path):
    """Extract all text from a PDF."""
    try:
        import fitz  # pymupdf
        doc = fitz.open(pdf_path)
        pages = []
        for i, page in enumerate(doc):
            text = page.get_text()
            if text.strip():
                pages.append({"page": i + 1, "text": text.strip()})
        doc.close()
        return pages
    except Exception as e:
        logger.error(f"PDF extraction error: {e}")
        return []


def get_pdf_info(pdf_path):
    """Get PDF metadata and stats."""
    try:
        import fitz
        doc = fitz.open(pdf_path)
        meta = doc.metadata
        info = {
            "filename": os.path.basename(pdf_path),
            "pages": len(doc),
            "title": meta.get("title", "") or "",
            "author": meta.get("author", "") or "",
            "subject": meta.get("subject", "") or "",
            "creator": meta.get("creator", "") or "",
        }
        total_chars = sum(len(page.get_text()) for page in doc)
        info["total_characters"] = total_chars
        info["estimated_words"] = total_chars // 5
        doc.close()
        return info
    except Exception as e:
        logger.error(f"PDF info error: {e}")
        return {}


def ask_pdf(pdf_path, question):
    """Ask a question about a PDF."""
    pages = extract_text(pdf_path)
    if not pages:
        return "Could not extract text from the PDF."

    full_text = "\n\n".join(f"[Page {p['page']}]\n{p['text']}" for p in pages)

    # Truncate if too long
    if len(full_text) > 8000:
        full_text = full_text[:8000] + "\n[Truncated...]"

    prompt = f"""Answer this question based on the PDF content below.

QUESTION: {question}

PDF CONTENT:
{full_text}

Provide a thorough answer based only on the document content. Cite page numbers when possible."""

    return _query_llm(prompt)


def summarize_pdf(pdf_path):
    """Generate a summary of a PDF."""
    pages = extract_text(pdf_path)
    if not pages:
        return "Could not extract text from the PDF."

    full_text = "\n\n".join(f"[Page {p['page']}]\n{p['text']}" for p in pages)
    if len(full_text) > 8000:
        full_text = full_text[:8000] + "\n[Truncated...]"

    prompt = f"""Summarize this document comprehensively.

DOCUMENT:
{full_text}

Provide:
1. A brief executive summary (2-3 sentences)
2. Key points organized by theme
3. Important details, data, or conclusions
4. Any action items or recommendations mentioned"""

    return _query_llm(prompt)


def ingest_to_vault(pdf_path, folder="Knowledge"):
    """Convert a PDF to markdown and save to Obsidian vault."""
    from aria.aria_config import get_config
    from aria.vault.obsidian_client import ObsidianClient

    config = get_config()
    obs = config.get("obsidian", {})
    client = ObsidianClient(
        base_url=obs.get("api_url", "http://172.19.16.1:27123"),
        api_key=obs.get("api_key", ""),
    )

    if not client.health():
        return None, "Obsidian not connected. Open Obsidian first."

    info = get_pdf_info(pdf_path)
    pages = extract_text(pdf_path)
    if not pages:
        return None, "Could not extract text from PDF."

    full_text = "\n\n".join(p["text"] for p in pages)

    # Generate summary and tags
    print(f"  {D}Generating summary...{X}")
    summary = _query_llm(f"Summarize this document in 3-5 sentences:\n\n{full_text[:4000]}")

    print(f"  {D}Generating tags...{X}")
    tags_response = _query_llm(f"Suggest 3-5 tags for this document. Return ONLY a JSON array like [\"tag1\", \"tag2\"].\n\nContent:\n{full_text[:2000]}")
    tags = ["pdf", "imported"]
    try:
        clean = tags_response.replace("\n", " ")
        s = clean.find("[")
        e = clean.rfind("]") + 1
        if s >= 0 and e > s:
            parsed = json.loads(clean[s:e])
            tags = [t.lower().strip() for t in parsed if isinstance(t, str)]
    except: pass

    # Build markdown note
    title = info.get("title") or os.path.basename(pdf_path).replace(".pdf", "").replace("_", " ").replace("-", " ")
    tag_yaml = "\n".join(f"  - {t}" for t in tags)

    markdown = f"""---
tags:
{tag_yaml}
date: {date.today().isoformat()}
source: {os.path.basename(pdf_path)}
pages: {info.get('pages', 0)}
author: {info.get('author', 'Unknown')}
aria_imported: true
type: pdf-import
---

# {title}

## Summary
{summary}

## Content
"""

    for page in pages:
        markdown += f"\n### Page {page['page']}\n{page['text']}\n"

    # Save to vault
    safe_name = title.replace(" ", "-").replace("/", "-")[:60]
    note_path = f"{folder}/{safe_name}.md"
    if client.save_note(note_path, markdown):
        return note_path, f"Saved to vault: {note_path}"
    return None, "Failed to save to vault."


def interactive_pdf(pdf_path):
    """Interactive PDF Q&A session."""
    info = get_pdf_info(pdf_path)
    if not info:
        print(f"{R}Could not open PDF: {pdf_path}{X}")
        return

    print(f"""
{C}{B}ARIA PDF Reader{X}
{D}File: {info['filename']}
Pages: {info['pages']}
Words: ~{info['estimated_words']:,}
Title: {info.get('title', 'N/A')}
Author: {info.get('author', 'N/A')}{X}

{D}Commands: ask, summarize, ingest, info, quit{X}
""")

    while True:
        try:
            cmd = input(f"{G}{B}pdf > {X}").strip().lower()
            if not cmd: continue
            if cmd in ("quit", "exit", "q"): break
            elif cmd == "info":
                for k, v in info.items():
                    print(f"  {k}: {v}")
            elif cmd == "summarize":
                print(f"{D}Summarizing...{X}")
                result = summarize_pdf(pdf_path)
                print(f"\n{C}{result}{X}\n")
            elif cmd == "ingest":
                folder = input(f"  Vault folder (default: Knowledge): ").strip() or "Knowledge"
                print(f"{D}Ingesting to vault...{X}")
                path, msg = ingest_to_vault(pdf_path, folder)
                if path:
                    print(f"{G}{msg}{X}")
                else:
                    print(f"{R}{msg}{X}")
            elif cmd.startswith("ask"):
                question = cmd[3:].strip()
                if not question:
                    question = input(f"  Question: ").strip()
                if question:
                    print(f"{D}Analyzing...{X}")
                    answer = ask_pdf(pdf_path, question)
                    print(f"\n{C}{answer}{X}\n")
            else:
                # Treat as a question
                print(f"{D}Analyzing...{X}")
                answer = ask_pdf(pdf_path, cmd)
                print(f"\n{C}{answer}{X}\n")
        except KeyboardInterrupt:
            print(f"\n{D}PDF session ended.{X}")
            break
