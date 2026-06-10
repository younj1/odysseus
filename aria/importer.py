"""ARIA Universal Importer — Import conversations from any source."""

import json, os, re, logging, zipfile, glob
from datetime import datetime, date
from pathlib import Path

logger = logging.getLogger(__name__)

C = "\033[96m"; G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; B = "\033[1m"; D = "\033[2m"; X = "\033[0m"


def _detect_format(filepath):
    """Detect the format of an import file."""
    ext = filepath.lower().split(".")[-1]
    if ext == "zip":
        return "zip"
    elif ext == "md":
        return "markdown"
    elif ext == "txt":
        return "text"
    elif ext == "json":
        try:
            with open(filepath) as f:
                data = json.load(f)
            if isinstance(data, list) and data and "uuid" in data[0]:
                return "claude"
            if isinstance(data, list) and data and "mapping" in data[0]:
                return "chatgpt"
            if isinstance(data, dict) and "conversations" in data:
                return "chatgpt"
            return "json"
        except:
            return "json"
    return "unknown"


def _extract_zip(filepath, temp_dir="/tmp/aria_import"):
    """Extract a zip file and return list of extracted files."""
    os.makedirs(temp_dir, exist_ok=True)
    with zipfile.ZipFile(filepath, "r") as z:
        z.extractall(temp_dir)
    files = []
    for root, dirs, fnames in os.walk(temp_dir):
        for fn in fnames:
            files.append(os.path.join(root, fn))
    return files


def _parse_claude_json(filepath):
    """Parse Claude.ai conversation export."""
    conversations = []
    with open(filepath) as f:
        data = json.load(f)
    if not isinstance(data, list):
        data = [data]
    for conv in data:
        title = conv.get("name", conv.get("title", "Untitled"))
        messages = []
        for msg in conv.get("chat_messages", conv.get("messages", [])):
            role = msg.get("sender", msg.get("role", "user"))
            if role == "human": role = "user"
            elif role == "assistant": role = "assistant"
            content = ""
            if isinstance(msg.get("content"), list):
                for block in msg["content"]:
                    if isinstance(block, dict):
                        content += block.get("text", "")
                    elif isinstance(block, str):
                        content += block
            elif isinstance(msg.get("content"), str):
                content = msg["content"]
            elif isinstance(msg.get("text"), str):
                content = msg["text"]
            if content.strip():
                messages.append({"role": role, "content": content.strip()})
        if messages:
            created = conv.get("created_at", conv.get("create_time", datetime.now().isoformat()))
            conversations.append({"title": title, "messages": messages, "created": str(created)[:19], "source": "claude"})
    return conversations


def _parse_chatgpt_json(filepath):
    """Parse ChatGPT conversation export."""
    conversations = []
    with open(filepath) as f:
        data = json.load(f)
    if isinstance(data, dict) and "conversations" in data:
        data = data["conversations"]
    if not isinstance(data, list):
        return conversations
    for conv in data:
        title = conv.get("title", "Untitled")
        messages = []
        mapping = conv.get("mapping", {})
        if mapping:
            for node_id, node in mapping.items():
                msg = node.get("message")
                if not msg: continue
                role = msg.get("author", {}).get("role", "user")
                if role not in ("user", "assistant"): continue
                parts = msg.get("content", {}).get("parts", [])
                content = " ".join(str(p) for p in parts if isinstance(p, str))
                if content.strip():
                    messages.append({"role": role, "content": content.strip()})
        if messages:
            created = conv.get("create_time", "")
            if isinstance(created, (int, float)):
                created = datetime.fromtimestamp(created).isoformat()
            conversations.append({"title": title, "messages": messages, "created": str(created)[:19], "source": "chatgpt"})
    return conversations


def _parse_markdown(filepath):
    """Parse a markdown file as a single conversation/note."""
    with open(filepath) as f:
        content = f.read()
    title = Path(filepath).stem.replace("-", " ").replace("_", " ")
    # Try to detect Q&A pattern
    messages = []
    blocks = re.split(r"\n(?:#{1,3}\s|\*\*(?:User|Human|Assistant|AI|You|Bot))", content)
    if len(blocks) > 1:
        role = "user"
        for block in blocks:
            if block.strip():
                messages.append({"role": role, "content": block.strip()})
                role = "assistant" if role == "user" else "user"
    if not messages:
        messages = [{"role": "user", "content": f"Tell me about {title}"}, {"role": "assistant", "content": content.strip()}]
    return [{"title": title, "messages": messages, "created": datetime.now().isoformat()[:19], "source": "markdown"}]


def _parse_text(filepath):
    """Parse a plain text file."""
    with open(filepath) as f:
        content = f.read()
    title = Path(filepath).stem.replace("-", " ").replace("_", " ")
    return [{"title": title, "messages": [{"role": "user", "content": f"Tell me about {title}"}, {"role": "assistant", "content": content.strip()}], "created": datetime.now().isoformat()[:19], "source": "text"}]


def parse_file(filepath):
    """Parse any supported file format into conversations."""
    fmt = _detect_format(filepath)
    print(f"  {D}Detected format: {fmt}{X}")
    if fmt == "zip":
        extracted = _extract_zip(filepath)
        all_convos = []
        for f in extracted:
            sub_fmt = _detect_format(f)
            if sub_fmt in ("claude", "chatgpt", "json", "markdown", "text"):
                all_convos.extend(parse_file(f))
        return all_convos
    elif fmt == "claude":
        return _parse_claude_json(filepath)
    elif fmt == "chatgpt":
        return _parse_chatgpt_json(filepath)
    elif fmt == "markdown":
        return _parse_markdown(filepath)
    elif fmt == "text":
        return _parse_text(filepath)
    elif fmt == "json":
        return _parse_claude_json(filepath)
    else:
        print(f"  {R}Unsupported format: {fmt}{X}")
        return []


def import_to_vault(conversations, folder="Conversations"):
    """Save conversations as Obsidian notes."""
    from aria.vault.obsidian_client import ObsidianClient
    from aria.aria_config import get_config
    config = get_config()
    obs = config.get("obsidian", {})
    client = ObsidianClient(base_url=obs.get("api_url", "http://172.19.16.1:27123"), api_key=obs.get("api_key", ""))
    if not client.health():
        print(f"{R}Obsidian not connected.{X}")
        return 0
    saved = 0
    for conv in conversations:
        title = conv["title"][:60].replace("/", "-").replace("\\", "-")
        safe_title = re.sub(r"[^a-zA-Z0-9\s\-]", "", title).strip().replace(" ", "-")
        if not safe_title: safe_title = f"import-{saved}"
        md = f"---\ntags:\n  - import\n  - {conv.get('source', 'unknown')}\ndate: {conv.get('created', date.today().isoformat())[:10]}\nimported: {date.today().isoformat()}\n---\n\n# {title}\n\n"
        for msg in conv["messages"]:
            role = "**You**" if msg["role"] == "user" else "**Assistant**"
            md += f"{role}:\n{msg['content']}\n\n---\n\n"
        path = f"{folder}/{safe_title}.md"
        if client.save_note(path, md):
            saved += 1
    return saved


def import_to_training(conversations, output="data/training_data.jsonl", append=True):
    """Convert conversations to fine-tuning training data."""
    os.makedirs(os.path.dirname(output), exist_ok=True)
    mode = "a" if append else "w"
    count = 0
    with open(output, mode) as f:
        for conv in conversations:
            msgs = conv["messages"]
            for i in range(len(msgs) - 1):
                if msgs[i]["role"] == "user" and msgs[i+1]["role"] == "assistant":
                    user_msg = msgs[i]["content"].strip()
                    asst_msg = msgs[i+1]["content"].strip()
                    if len(user_msg) > 10 and len(asst_msg) > 50:
                        entry = {"messages": [
                            {"role": "system", "content": "You are ARIA, a helpful personal AI assistant."},
                            {"role": "user", "content": user_msg},
                            {"role": "assistant", "content": asst_msg},
                        ]}
                        f.write(json.dumps(entry) + "\n")
                        count += 1
    return count


def import_file(filepath, to_vault=True, to_training=True):
    """Import a file — parse, save to vault, and add to training data."""
    print(f"\n{C}{B}ARIA Importer{X}")
    print(f"{D}File: {filepath}{X}")
    if not os.path.exists(filepath):
        print(f"{R}File not found: {filepath}{X}")
        return
    conversations = parse_file(filepath)
    if not conversations:
        print(f"{R}No conversations found in file.{X}")
        return
    total_msgs = sum(len(c["messages"]) for c in conversations)
    print(f"{G}Parsed {len(conversations)} conversations ({total_msgs} messages){X}")
    sources = set(c.get("source", "unknown") for c in conversations)
    print(f"{D}Sources: {', '.join(sources)}{X}")
    if to_vault:
        print(f"\n{Y}Saving to Obsidian vault...{X}")
        saved = import_to_vault(conversations)
        print(f"{G}  Saved {saved} notes to vault{X}")
    if to_training:
        print(f"\n{Y}Adding to training data...{X}")
        count = import_to_training(conversations)
        print(f"{G}  Added {count} training pairs{X}")
    print(f"\n{G}{B}Import complete!{X}")


def import_folder(folder_path, to_vault=True, to_training=True):
    """Import all supported files from a folder."""
    print(f"\n{C}{B}ARIA Folder Import{X}")
    print(f"{D}Folder: {folder_path}{X}")
    if not os.path.isdir(folder_path):
        print(f"{R}Folder not found: {folder_path}{X}")
        return
    files = []
    for ext in ("*.json", "*.md", "*.txt", "*.zip"):
        files.extend(glob.glob(os.path.join(folder_path, ext)))
        files.extend(glob.glob(os.path.join(folder_path, "**", ext), recursive=True))
    files = list(set(files))
    print(f"Found {len(files)} files to import")
    total_convos = 0
    total_training = 0
    for f in sorted(files):
        print(f"\n{D}Processing: {os.path.basename(f)}{X}")
        conversations = parse_file(f)
        if conversations:
            total_convos += len(conversations)
            if to_vault:
                import_to_vault(conversations)
            if to_training:
                total_training += import_to_training(conversations)
    print(f"\n{G}{B}Folder import complete!{X}")
    print(f"  Conversations: {total_convos}")
    print(f"  Training pairs: {total_training}")
