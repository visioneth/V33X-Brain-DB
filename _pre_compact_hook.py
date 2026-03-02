import sys
import json
import sqlite3
import os
from collections import Counter
from datetime import datetime
import re

STOPWORDS = {
    'the', 'and', 'a', 'to', 'in', 'is', 'you', 'that', 'it', 'of', 'for',
    'on', 'with', 'as', 'by', 'this', 'an', 'i', 'we', 'are', 'be', 'at', 'do'
}

# Update this path to match your install location
DB_PATH = r"C:\Users\King Geo\OneDrive\Desktop\V33X_Beast_Pack\V33X_BEAST_PACK\memory\brain_db.sqlite"

# Windows file path detection
PATH_PATTERN = re.compile(r'[A-Za-z]:\\(?:[^\s,\'"<>\n\\]+\\)*[^\s,\'"<>\n\\]+')

# Keywords that signal completed work — scanned in assistant messages
COMPLETION_KEYWORDS = [
    'fixed', 'built', 'created', 'wrote', 'deployed', 'pushed', 'updated',
    'added', 'tested', 'shipped', 'committed', 'solved', 'working', 'done',
    'complete', 'installed', 'configured', 'enabled', 'disabled', 'saved',
    'written', 'finished', 'launched', 'running', 'live'
]

# Decision/instruction signals from user messages
DECISION_PATTERN = re.compile(
    r"(?:let's|we're going to|i want to|we need to|going to|we decided|"
    r"we're building|build|make|create|fix|update|add|remove|delete|"
    r"push|post|send|run|deploy|write|test|launch)\s+(.{10,120})",
    re.IGNORECASE
)


def extract_facts(transcript_lines):
    """
    Extract meaningful facts from both user and assistant messages.
    Returns list of (category, key, value, priority) tuples.

    Reads the FULL transcript — not just user messages — so assistant
    completion statements ("Fixed. The hook now works.") are captured too.
    """
    facts = []
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    counter = [0]

    def next_key(prefix):
        counter[0] += 1
        return f"{prefix}_{ts}_{counter[0]}"

    for msg_role, msg_text in transcript_lines:
        if not msg_text or len(msg_text.strip()) < 15:
            continue

        # --- File paths (any message) ---
        paths = PATH_PATTERN.findall(msg_text)
        for path in set(paths):
            if len(path) > 15:
                facts.append(('file_path', next_key('path'), path[:200], 7))

        # --- Completion statements (assistant only) ---
        if msg_role == 'assistant':
            sentences = re.split(r'(?<=[.!?\n])\s+', msg_text)
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) < 25:
                    continue
                lower = sentence.lower()
                for kw in COMPLETION_KEYWORDS:
                    if kw in lower:
                        facts.append(('completed', next_key(kw), sentence[:250], 7))
                        break  # one fact per sentence max

        # --- Decisions and instructions (user only) ---
        if msg_role == 'user':
            matches = DECISION_PATTERN.findall(msg_text)
            for target in matches:
                target = target.strip().rstrip('.,!?')
                if len(target) > 10:
                    facts.append(('instruction', next_key('instr'), target[:200], 6))

    # Deduplicate by first 60 chars of value
    seen = set()
    unique = []
    for category, key, value, priority in facts:
        sig = value[:60].lower().strip()
        if sig not in seen:
            seen.add(sig)
            unique.append((category, key, value, priority))

    return unique


def main():
    try:
        raw = sys.stdin.read()
        input_json = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, Exception) as e:
        sys.stderr.write(f"Failed to parse input JSON: {e}\n")
        input_json = {}

    transcript_path = input_json.get('transcript_path', '')

    user_messages = []
    transcript_lines = []  # (role, text) pairs — both user and assistant

    if not transcript_path or not os.path.exists(transcript_path):
        sys.stderr.write("No transcript path — saving empty session\n")
    else:
        try:
            with open(transcript_path, 'r', encoding='utf-8') as file:
                for line in file:
                    try:
                        message = json.loads(line)
                        if message.get('isSidechain') is True:
                            continue
                        role = message['message']['role']
                        content = message['message']['content']
                        if isinstance(content, list):
                            content = ' '.join(
                                b.get('text', '') for b in content
                                if isinstance(b, dict) and b.get('type') == 'text'
                            )
                        if isinstance(content, str) and content.strip():
                            transcript_lines.append((role, content))
                            if role == 'user':
                                user_messages.append(content)
                    except (json.JSONDecodeError, KeyError, TypeError, Exception) as e:
                        sys.stderr.write(f"Failed to parse message: {e}\n")
        except OSError as e:
            sys.stderr.write(f"Error reading transcript file: {e}\n")

    transcript_string = ' '.join(user_messages)

    # Word frequency — filter words shorter than 4 chars to eliminate code noise
    try:
        words = [w for w in transcript_string.lower().split()
                 if w.isalpha() and len(w) > 3]
        word_counts = Counter(words)
        filtered = {w: c for w, c in word_counts.items() if w not in STOPWORDS}
        top_topics = dict(Counter(filtered).most_common(10))
    except Exception as e:
        sys.stderr.write(f"Error processing words: {e}\n")
        top_topics = {}

    # spaCy NER — optional, graceful fallback if not installed
    try:
        import spacy
        nlp = spacy.load('en_core_web_sm')
        doc = nlp(transcript_string[:50000])  # cap to avoid memory blow-up
        entities = list({ent.text for ent in doc.ents})[:50]
    except (OSError, AttributeError, ImportError, Exception) as e:
        sys.stderr.write(f"spaCy unavailable: {e}\n")
        entities = []

    # Extract structured facts from full conversation
    facts = extract_facts(transcript_lines)

    # --- Database ---
    conn = None  # initialized here so finally block never hits NameError
    try:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id        INTEGER PRIMARY KEY,
                timestamp TEXT,
                summary   TEXT,
                topics    TEXT,
                entities  TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS knowledge (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                category   TEXT,
                key        TEXT UNIQUE,
                value      TEXT,
                priority   INTEGER DEFAULT 5,
                created_at TEXT
            )
        ''')

        timestamp = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO sessions (timestamp, summary, topics, entities)
            VALUES (?, ?, ?, ?)
        ''', (timestamp, transcript_string[:500], json.dumps(top_topics), json.dumps(entities)))

        now = datetime.now().isoformat()
        for category, key, value, priority in facts:
            cursor.execute('''
                INSERT OR REPLACE INTO knowledge (category, key, value, priority, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (category, key, value, priority, now))

        conn.commit()

    except sqlite3.Error as e:
        sys.stderr.write(f"Database error: {e}\n")
    finally:
        if conn:
            conn.close()

    sys.stderr.write(
        f"Processed {len(user_messages)} user messages, "
        f"{len(transcript_lines)} total lines. "
        f"Topics: {top_topics}. "
        f"Facts extracted: {len(facts)}.\n"
    )


if __name__ == "__main__":
    main()
