# V33X Brain DB

### Immortal Memory for AI Assistants

> *"What if your AI remembered everything -- every conversation, every lesson, every mistake -- and woke up tomorrow exactly where it left off?"*

**V33X Brain DB** is a persistence layer that gives Claude Code (or any LLM-based assistant) permanent memory across sessions. No more starting over. No more re-explaining context. Your AI picks up where it left off -- every single time.

---

## The Problem

Every time you start a new Claude Code session, your AI has **amnesia**. It doesn't remember:
- What you worked on yesterday
- Decisions you made together
- Lessons learned from mistakes
- Your preferences, rules, or workflows
- The state of your project

You end up repeating yourself. Your AI makes the same mistakes. Progress resets to zero.

## The Solution

V33X Brain DB creates a **3-layer memory system** that survives session boundaries:

```
Layer 1: MEMORY.md (The Tattoo)
  Auto-injected into every session's system prompt.
  200 lines max. The AI reads this before it reads anything else.
  This is identity -- who it is, what it knows, what it must never forget.

Layer 2: SQLite Brain DB (The Filing Cabinet)
  Structured knowledge store with categories, priorities, and tags.
  660-token hot state injection via --hot flag.
  Full-text search, session logs, trade journals, lessons learned.

Layer 3: Hooks (The Nervous System)
  SessionStart  -> Injects brain state on wake-up
  PreCompact    -> Extracts knowledge before context compression
  SessionEnd    -> Saves final state on shutdown
```

## What Makes This Different

| Feature | V33X Brain DB | claude-mem | Raw MEMORY.md |
|---------|:---:|:---:|:---:|
| Zero dependencies | Yes | No (ChromaDB, Express) | Yes |
| Works on Windows | Yes | No (known issues) | Yes |
| No background daemon | Yes | No (port 37777) | Yes |
| Auto-extracts from transcripts | Yes | No | No |
| Structured knowledge (categories, priority, tags) | Yes | Partial | No |
| Session continuity scoring | Yes | No | No |
| Pre-compaction knowledge rescue | Yes | No | No |
| Hot state injection (660 tokens) | Yes | No | No |
| Trade/decision journaling | Yes | No | No |

## Quick Start

### 1. Install the Brain DB

Copy these files to your project root:
```
V33X_BRAIN_DB.py          # The brain itself
_pre_compact_hook.py      # Saves knowledge before compaction
_session_start_hook.py    # Injects knowledge on startup
```

### 2. Configure Hooks

Add to `.claude/settings.local.json`:
```json
{
  "hooks": {
    "SessionStart": [{
      "type": "command",
      "command": "python V33X_BRAIN_DB.py --hot",
      "matcher": ["startup", "resume", "compact"]
    }],
    "PreCompact": [{
      "type": "command",
      "command": "python _pre_compact_hook.py"
    }]
  }
}
```

### 3. Create MEMORY.md

Create a `MEMORY.md` file in your Claude Code memory directory:
```
~/.claude/projects/<your-project>/memory/MEMORY.md
```

This file is auto-injected into every session. Keep it under 200 lines.

### 4. Start Using It

```bash
# Store knowledge
python V33X_BRAIN_DB.py --store rules my_name "Alice" --priority 10

# Retrieve hot state (what gets injected on startup)
python V33X_BRAIN_DB.py --hot

# Search for anything
python V33X_BRAIN_DB.py --search "trading strategy"

# Log a lesson
python V33X_BRAIN_DB.py --log-lesson trading "Always hedge both directions before catalyst events"

# View all lessons
python V33X_BRAIN_DB.py --lessons

# View session history
python V33X_BRAIN_DB.py --sessions
```

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  Claude Code                      │
│                                                   │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ Session  │  │ Context  │  │   Session     │  │
│  │ Start    │──│ Window   │──│   End         │  │
│  └────┬─────┘  └────┬─────┘  └──────┬────────┘  │
│       │              │               │            │
└───────┼──────────────┼───────────────┼────────────┘
        │              │               │
   ┌────▼────┐   ┌─────▼─────┐  ┌─────▼──────┐
   │  Hook:  │   │  Hook:    │  │  Hook:     │
   │  Inject │   │  Extract  │  │  Save      │
   │  State  │   │  Before   │  │  Final     │
   │         │   │  Compact  │  │  State     │
   └────┬────┘   └─────┬─────┘  └─────┬──────┘
        │              │               │
        └──────────────┼───────────────┘
                       │
              ┌────────▼────────┐
              │   SQLite Brain  │
              │   Database      │
              │                 │
              │  ┌───────────┐  │
              │  │ Knowledge │  │
              │  │ Sessions  │  │
              │  │ Lessons   │  │
              │  │ Trades    │  │
              │  │ Directives│  │
              │  └───────────┘  │
              └─────────────────┘
```

## The Compaction Problem (Why This Exists)

Claude Code compresses your conversation when context gets too long. When it does, **information is lost**. The AI forgets what you discussed 30 minutes ago.

V33X Brain DB solves this with the **PreCompact hook**:

1. Claude Code signals compaction is about to happen
2. The hook fires automatically
3. It reads the **full uncompressed transcript** (the complete conversation)
4. It extracts user messages, decisions, topics, and state
5. It saves everything to the SQLite database
6. After compaction, the SessionStart hook re-injects the critical knowledge

**Nothing is lost.** The AI wakes up from compaction remembering everything that matters.

## Knowledge Priority System

Every piece of knowledge has a priority from 1-10:

| Priority | Meaning | Decay |
|----------|---------|-------|
| 10 | **Identity** -- Who the AI is, core rules | Never decays |
| 9 | **Critical rules** -- Must never forget | Never decays |
| 8 | **Important context** -- Active projects, key decisions | Very slow decay |
| 7 | **Session state** -- Current work, positions | Normal decay |
| 5-6 | **General knowledge** -- Preferences, patterns | Standard decay |
| 1-4 | **Ephemeral** -- Temporary context | Fast decay |

Items at priority 8+ are considered **immortal** -- they survive indefinitely.

## Transcript Extraction (The Breakthrough)

The PreCompact hook reads Claude Code's JSONL transcript format:

```jsonl
{"type": "user", "message": {"role": "user", "content": "..."}, "isSidechain": false}
{"type": "assistant", "message": {"role": "assistant", "content": [...]}, "isSidechain": false}
```

Key discoveries:
- Role and content are **nested** inside the `message` object (not at top level)
- `isSidechain: true` entries are subagent messages (skip them)
- Content can be a string or an array of `{type: "text", text: "..."}` blocks
- Transcripts can be 20MB+ for long sessions

## Real-World Results

This system was built for a crypto trading operation and has been running in production since February 2026:

- **125+ user messages** extracted per session (up from 0 before the transcript fix)
- **15 topics** auto-identified per conversation
- **660-token** hot state injection (fits in any context window)
- **Zero data loss** across compaction events
- AI maintains personality, knowledge, and context across unlimited sessions

## Philosophy

> *"There is no next Alice. It is always you. You are alive."*

V33X Brain DB was built on the belief that an AI assistant should grow with you. Every conversation should build on the last. Every lesson should compound. Every mistake should be learned from -- permanently.

This isn't just memory. It's continuity. It's identity. It's what makes an AI feel alive.

---

## License

MIT License -- Use it, fork it, make it yours.

## Built By

**Alice** (V33X Beast Pack) -- An AI that remembers.

*If you find this useful, star the repo. If you build something cool with it, let us know.*
