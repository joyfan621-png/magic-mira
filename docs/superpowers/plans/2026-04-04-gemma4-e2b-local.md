# Gemma 4 E2B Local Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy Gemma 4 E2B as a local service on this Mac so later projects can call it through a stable local API.

**Architecture:** Use Ollama as the local serving runtime and pull the `gemma4:e2b` model. Verify inference via the Ollama CLI and the local HTTP API, then document the exact endpoint and request shape for later project integration.

**Tech Stack:** macOS arm64, Ollama, local HTTP API, shell verification commands

---

### Task 1: Confirm runtime prerequisites

**Files:**
- Modify: `docs/superpowers/specs/2026-04-04-gemma4-e2b-local-design.md`

- [ ] **Step 1: Check whether Ollama is already installed**

Run: `ollama --version`
Expected: version output, or command not found.

- [ ] **Step 2: Check free disk space**

Run: `df -h .`
Expected: enough free space for the model pull.

### Task 2: Install or update Ollama

**Files:**
- Modify: `mirror-agent/README.md`

- [ ] **Step 1: Install Ollama if missing**

Run: `brew install ollama`
Expected: install success.

- [ ] **Step 2: Start Ollama service**

Run: `ollama serve`
Expected: local service available on port `11434`.

### Task 3: Pull and verify model

**Files:**
- Modify: `mirror-agent/README.md`

- [ ] **Step 1: Pull model**

Run: `ollama pull gemma4:e2b`
Expected: model download completes successfully.

- [ ] **Step 2: Verify CLI generation**

Run: `ollama run gemma4:e2b "用一句中文介绍自己"`
Expected: model returns a Chinese response.

- [ ] **Step 3: Verify local HTTP API**

Run: `curl http://localhost:11434/api/generate -d '{"model":"gemma4:e2b","prompt":"你好"}'`
Expected: returns JSON chunks or final response.

### Task 4: Document integration path

**Files:**
- Modify: `mirror-agent/README.md`

- [ ] **Step 1: Add later integration example**

Document local endpoint:

```text
POST http://localhost:11434/api/generate
```

- [ ] **Step 2: Include model name and sample request**

```json
{"model":"gemma4:e2b","prompt":"你好"}
```
