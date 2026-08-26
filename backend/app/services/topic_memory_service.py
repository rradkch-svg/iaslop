import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Set
from backend.app.config import BANNED_TOPICS_FILE

def normalize_text(text: str) -> str:
    """Normalizes text for fuzzy deduplication comparison (lowercase, ascii, stripped)"""
    if not text:
        return ""
    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8')
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    return " ".join(text.split())

class TopicMemoryService:
    """
    Topic Memory & Blacklist Service:
    Ensures that once a topic has been suggested or used in Minuto Inexplicável,
    it is permanently recorded in storage/banned_topics.json and NEVER suggested again.
    """
    def __init__(self):
        self.file_path: Path = BANNED_TOPICS_FILE
        self._ensure_file()

    def _ensure_file(self):
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump([], f, indent=2, ensure_ascii=False)

    def _load_raw(self) -> List[Dict[str, Any]]:
        try:
            if self.file_path.exists():
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
        except Exception as e:
            print(f"Error loading banned topics: {e}")
        return []

    def _save_raw(self, data: List[Dict[str, Any]]):
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving banned topics: {e}")

    def get_banned_topics(self) -> List[str]:
        """Returns the list of all banned topic titles."""
        entries = self._load_raw()
        return [e["topic"] for e in entries if isinstance(e, dict) and "topic" in e]

    def get_recent_banned_topics(self, limit: int = 60) -> List[str]:
        """Returns the most recent N banned topic titles for prompt injection."""
        all_topics = self.get_banned_topics()
        return all_topics[-limit:]

    def is_banned(self, topic: str) -> bool:
        """
        Checks whether a candidate topic is identical or substantially similar
        to an already banned topic.
        """
        norm_candidate = normalize_text(topic)
        if not norm_candidate:
            return False

        banned_list = self.get_banned_topics()
        candidate_words = set(norm_candidate.split())

        for b in banned_list:
            norm_b = normalize_text(b)
            if norm_candidate == norm_b:
                return True
            
            # Substring containment
            if len(norm_candidate) > 10 and (norm_candidate in norm_b or norm_b in norm_candidate):
                return True
            
            # Word overlap similarity (Jaccard > 0.70)
            b_words = set(norm_b.split())
            if candidate_words and b_words:
                overlap = len(candidate_words & b_words)
                union = len(candidate_words | b_words)
                if union > 0 and (overlap / union) >= 0.70:
                    return True

        return False

    def ban_topic(self, topic: str, source: str = "suggested") -> bool:
        """Permanently bans a single topic."""
        clean_topic = topic.strip()
        if not clean_topic:
            return False

        entries = self._load_raw()
        # Check if already present
        for e in entries:
            if normalize_text(e.get("topic", "")) == normalize_text(clean_topic):
                return False

        new_entry = {
            "topic": clean_topic,
            "banned_at": datetime.now().isoformat(),
            "source": source
        }
        entries.append(new_entry)
        self._save_raw(entries)
        return True

    def ban_topics(self, topics: List[str], source: str = "suggested") -> int:
        """Permanently bans multiple topics in a single transaction."""
        if not topics:
            return 0

        entries = self._load_raw()
        existing_norms = {normalize_text(e.get("topic", "")) for e in entries}
        
        added_count = 0
        now_str = datetime.now().isoformat()

        for t in topics:
            clean_t = t.strip()
            if not clean_t:
                continue
            norm_t = normalize_text(clean_t)
            if norm_t not in existing_norms:
                entries.append({
                    "topic": clean_t,
                    "banned_at": now_str,
                    "source": source
                })
                existing_norms.add(norm_t)
                added_count += 1

        if added_count > 0:
            self._save_raw(entries)

        return added_count

    def clear_banned_topics(self) -> bool:
        """Clears the banned topics blacklist."""
        self._save_raw([])
        return True

    def get_stats(self) -> Dict[str, Any]:
        """Returns statistics about banned topics."""
        entries = self._load_raw()
        return {
            "total_banned": len(entries),
            "recent_topics": [e.get("topic") for e in entries[-10:]]
        }

topic_memory = TopicMemoryService()
