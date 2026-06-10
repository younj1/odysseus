"""Prepare training data from Odysseus conversations and Obsidian vault."""

import json
import os
import sys
import logging
from typing import List, Dict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

logger = logging.getLogger(__name__)


def extract_from_conversations(data_dir: str = "data") -> List[Dict]:
    """Extract instruction/response pairs from Odysseus chat history."""
    pairs = []
    db_path = os.path.join(data_dir, "odysseus.db")
    
    if not os.path.exists(db_path):
        logger.warning(f"Database not found: {db_path}")
        return pairs

    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all chat messages ordered by session and timestamp
        cursor.execute("""
            SELECT session_id, role, content, created_at 
            FROM chat_messages 
            ORDER BY session_id, created_at
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        # Group by session and create pairs
        current_session = None
        user_msg = None
        
        for session_id, role, content, created_at in rows:
            if session_id != current_session:
                current_session = session_id
                user_msg = None
            
            if role == "user":
                user_msg = content
            elif role == "assistant" and user_msg:
                # Only include substantial exchanges
                if len(user_msg.strip()) > 10 and len(content.strip()) > 50:
                    pairs.append({
                        "instruction": user_msg.strip(),
                        "output": content.strip(),
                    })
                user_msg = None
        
        logger.info(f"Extracted {len(pairs)} conversation pairs")
    except Exception as e:
        logger.error(f"Failed to extract conversations: {e}")
    
    return pairs


def extract_from_vault(vault_path: str = None) -> List[Dict]:
    """Extract knowledge from Obsidian vault notes as training data."""
    pairs = []
    
    if not vault_path:
        from aria.aria_config import get_config
        config = get_config()
        vault_path = config.get("obsidian", {}).get("vault_path", "")
    
    if not vault_path or not os.path.isdir(vault_path):
        # Try via API
        try:
            from aria.vault.obsidian_client import ObsidianClient
            from aria.aria_config import get_config
            config = get_config()
            obs = config.get("obsidian", {})
            client = ObsidianClient(
                base_url=obs.get("api_url", "http://172.19.16.1:27123"),
                api_key=obs.get("api_key", ""),
            )
            
            # Get Knowledge folder notes
            knowledge_files = client.list_files("Knowledge")
            for f in knowledge_files:
                if f.endswith(".md"):
                    content = client.get_note(f"Knowledge/{f}")
                    if content and len(content.strip()) > 100:
                        title = f.replace(".md", "").replace("-", " ")
                        pairs.append({
                            "instruction": f"What do you know about {title}?",
                            "output": content.strip()[:3000],
                        })
                        pairs.append({
                            "instruction": f"Summarize the key points about {title}.",
                            "output": content.strip()[:2000],
                        })
            
            logger.info(f"Extracted {len(pairs)} vault pairs")
        except Exception as e:
            logger.error(f"Failed to extract from vault: {e}")
    
    return pairs


def prepare_dataset(
    output_path: str = "data/training_data.jsonl",
    include_conversations: bool = True,
    include_vault: bool = True,
    system_prompt: str = "You are ARIA, a helpful personal AI assistant.",
) -> str:
    """Prepare a complete training dataset in JSONL format.
    
    Format: {"messages": [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
    """
    all_pairs = []
    
    if include_conversations:
        all_pairs.extend(extract_from_conversations())
    
    if include_vault:
        all_pairs.extend(extract_from_vault())
    
    if not all_pairs:
        print("No training data found.")
        return ""
    
    # Convert to chat format
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, "w") as f:
        for pair in all_pairs:
            entry = {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": pair["instruction"]},
                    {"role": "assistant", "content": pair["output"]},
                ]
            }
            f.write(json.dumps(entry) + "\n")
    
    print(f"Prepared {len(all_pairs)} training examples -> {output_path}")
    print(f"  Conversations: {len([p for p in all_pairs if 'What do you know' not in p['instruction']])}")
    print(f"  Vault knowledge: {len([p for p in all_pairs if 'What do you know' in p['instruction'] or 'Summarize' in p['instruction']])}")
    
    return output_path


if __name__ == "__main__":
    prepare_dataset()
