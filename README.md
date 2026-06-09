# AI Agents

Experimental AI agent built in Python with support for tool calling, structured reasoning, and persistent conversational memory.

## Overview

I am developing this project into 3 phases to explore how modern AI agents operate under the hood without heavily relying on orchestration frameworks

The agent can:
- Perform mathematical calculations
- Fetch external data through APIs
- Delegate text-processing tasks to another LLM
- Maintain persistent memory across sessions

The project evolved in two phases to improve reliability and orchestration capabilities.

---

# Agentic Flow
<img width="883" height="557" alt="image" src="https://github.com/user-attachments/assets/9a050023-b45a-4024-b835-b52255647be6" />



## Phase 1 — Text-Based Tool Orchestration

The initial version relied on natural language outputs from the LLM to determine:
- which tool to invoke
- the arguments for the tool
- whether the task was completed

Example output:

```text
Use calculator with args: 25 * 12
```

### Limitations
- Difficult to parse reliably
- Inconsistent formatting
- Error-prone orchestration logic
- Harder to scale for multi-step workflows

---

## Phase 2 — Structured Agent Workflow

The orchestration layer was redesigned to use structured JSON outputs from the LLM.

Example response:

```json
{
  "thought": "Need to calculate total price",
  "tool": "calculator",
  "args": {
    "expression": "25 * 12"
  },
  "done": false
}
```

### Improvements
- Deterministic parsing
- Cleaner execution pipeline
- Easier debugging and validation
- Better extensibility for future tools and workflows
- More reliable multi-step reasoning

---

# Tools Implemented

## Calculator Tool
Handles mathematical computations.

Example:
```text
25 * 12
```

---

## Fetcher Tool
Retrieves external information from APIs.

Example use cases:
- weather lookup
- public API queries
- external data enrichment

---

## LLM Text Processing Tool
Delegates text-based transformations to another LLM.

Example tasks:
- rewriting
- summarization
- formatting
- refinement

---

# Persistent Memory Layer

The agent includes a lightweight memory system for maintaining user context across sessions.

At the end of each session:
1. The LLM extracts useful long-term information
2. Relevant preferences/details are stored in a local file
3. Stored memory is injected into future prompts

This enables:
- session continuity
- personalized interactions
- context-aware responses

Example memory:
```json
{
  "preferred_language": "Python",
  "interested_topics": ["cloud", "AI agents"]
}
```

---
# Phase 3 — Expense Tracker Agent

### Capabilities

* Log expenses through natural language ("I spent $12 on coffee today")
* Categorize across five fixed buckets: food, entertainment, bills, shopping, travel
* Resolve relative dates (today, yesterday, N days ago) to ISO format using a UTC reference injected into the system prompt
* Validate inputs at the application layer (amount, category, date sanity, length limits)
* Summarizes user expeneses over a time period with category specific, time interval based along with top-k mininum/maximum expenses 

### Why It Matters

This phase forced engagement with concerns the previous phases didn't surface: data schema design, mutation safety, error semantics that the LLM can actually act on, and how to keep the agent's response shape expressive enough to handle ambiguity (e.g., needing to ask the user a clarifying question rather than guessing).

### Status

The expense tracker currently supports ```logging``` and ```summarization```. Update and budget tools are working in progress.

---

# Tech Stack

- Python
- Ollama
- File-based persistence
- Cursor, Claude (AI tooling)
- MySQL (Persistence)

---

# Goals

This aim of this project is to develop better understanding of concepts that are being involved under the hood:
- agent orchestration
- tool calling workflows
- structured LLM outputs
- memory persistence
- context management
- reliable execution pipelines

instead of treating LLM agents as black-box abstractions.

<h3 align="center"><b>Developed with :heart: by <a href="https://github.com/DEV270201">Devansh Shah</a></b></h3>
