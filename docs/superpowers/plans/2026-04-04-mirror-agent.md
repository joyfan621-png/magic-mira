# Mirror Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable Python CLI project for the "镜子虾" skincare bestie agent with Zhipu AI chat, image analysis, Markdown memory, and local skincare knowledge.

**Architecture:** The CLI entrypoint delegates conversation orchestration to `agent.py`. The agent loads prompt and memory context, calls `GLM-4`, executes local tools when requested, and persists diary/profile/insight Markdown files through `memory.py`. Image analysis routes through `GLM-4V`, and all state is stored on disk.

**Tech Stack:** Python 3.10+, `zhipuai`, standard library `pathlib`, `json`, `base64`, `datetime`, `unittest`

---

### Task 1: Scaffold docs, test targets, and project layout

**Files:**
- Create: `mirror-agent/requirements.txt`
- Create: `mirror-agent/tests/test_memory.py`
- Create: `mirror-agent/tests/test_tools.py`
- Create: `mirror-agent/tests/test_agent.py`

- [ ] **Step 1: Write the failing tests for the minimum behaviors**

```python
def test_recent_diaries_only_returns_latest_days(self):
    ...

def test_search_knowledge_returns_matching_section(self):
    ...

def test_should_end_session_detects_bye(self):
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd mirror-agent && python -m unittest discover -s tests -v`
Expected: FAIL with import errors because implementation modules do not exist yet.

- [ ] **Step 3: Add dependency metadata**

```text
zhipuai>=2.1.5
```

- [ ] **Step 4: Run tests again and confirm they still fail for missing code**

Run: `cd mirror-agent && python -m unittest discover -s tests -v`
Expected: FAIL with missing module/function errors only.

### Task 2: Implement Markdown memory layer

**Files:**
- Create: `mirror-agent/memory.py`
- Create: `mirror-agent/memory/profile.md`
- Create: `mirror-agent/memory/insights.md`

- [ ] **Step 1: Write or keep failing tests for memory bootstrap and diary reads**

```python
store = MemoryStore(temp_dir)
store.ensure_structure()
self.assertTrue((temp_dir / "memory" / "profile.md").exists())
```

- [ ] **Step 2: Implement `MemoryStore` with structure bootstrap, diary writes, and recent diary reads**

```python
class MemoryStore:
    def ensure_structure(self) -> None:
        ...
```

- [ ] **Step 3: Run targeted tests**

Run: `cd mirror-agent && python -m unittest tests.test_memory -v`
Expected: PASS

### Task 3: Implement knowledge and tool helpers

**Files:**
- Create: `mirror-agent/tools.py`
- Create: `mirror-agent/knowledge/skincare.md`

- [ ] **Step 1: Keep a failing test for knowledge search**

```python
result = search_knowledge(knowledge_path, "眼霜")
self.assertIn("眼霜", result)
```

- [ ] **Step 2: Implement local knowledge search and tool registry**

```python
def search_knowledge(knowledge_path: Path, query: str, limit: int = 3) -> str:
    ...
```

- [ ] **Step 3: Run targeted tests**

Run: `cd mirror-agent && python -m unittest tests.test_tools -v`
Expected: PASS

### Task 4: Implement configuration and agent orchestration

**Files:**
- Create: `mirror-agent/config.py`
- Create: `mirror-agent/agent.py`
- Create: `mirror-agent/soul.md`

- [ ] **Step 1: Keep a failing test for end-session detection**

```python
self.assertTrue(should_end_session("晚安啦"))
```

- [ ] **Step 2: Implement config loading, system context assembly, and session helpers**

```python
class MirrorAgent:
    def build_memory_context(self) -> str:
        ...
```

- [ ] **Step 3: Run targeted tests**

Run: `cd mirror-agent && python -m unittest tests.test_agent -v`
Expected: PASS

### Task 5: Implement CLI entrypoint and finish runnable setup

**Files:**
- Create: `mirror-agent/main.py`
- Modify: `mirror-agent/agent.py`

- [ ] **Step 1: Add CLI loop and `/image` command handling**

```python
if raw.startswith("/image "):
    ...
```

- [ ] **Step 2: Run the full test suite**

Run: `cd mirror-agent && python -m unittest discover -s tests -v`
Expected: PASS

- [ ] **Step 3: Run a smoke check**

Run: `cd mirror-agent && python main.py`
Expected: Program starts, prints welcome text, and exits cleanly if API key is not configured after showing setup guidance.
