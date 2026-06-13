# MIDAS Guardrail ---  Documentation

> **Version:** 1.0\
> **Status:** Production\
> **Last Updated:** March 2026

A three-layer LLM-based input relevance guardrail for the MIDAS agentic
data science pipeline. Sits inside the router (`_route_request`) and
intercepts user queries before they reach any agent node --- blocking
off-topic, cross-agent, and manipulative inputs.

------------------------------------------------------------------------

# Table of Contents

1.  [How It Works](#how-it-works)
2.  [File Map](#file-map)
3.  [Architecture Deep Dive](#architecture-deep-dive)
4.  [Request Flow](#request-flow)
5.  [Integrating a New Agent](#integrating-a-new-agent)
6.  [Configuration Reference](#configuration-reference)
7.  [Logging Reference](#logging-reference)
8.  [Known Issues](#known-issues)


------------------------------------------------------------------------

# How It Works

When a user sends a message, the frontend tags it with an
`agent_context` string representing the current step. This context
travels through the HTTP request into LangGraph state. `_route_request`
reads it and calls `_check_relevance` before any routing logic runs.

`_check_relevance` runs three sequential layers:

| Layer | Name | Trigger | LLM Call? |
|------|------|--------|-----------|
| 1 | Keyword Pre-check | No data science terms found (includes fuzzy match at 0.75 cutoff) | NO |
| 2 | System Message Check | Query matches a known automated message prefix | NO |
| 3 | LLM Relevance Check | Query has data terms but intent is ambiguous | YES |
  ------------------------------------------------------------------------

If blocked at any layer → `intent = 'not_relevant'`, agent-specific
guidance message appended to state, early return.\
If passed → routes **directly** to `agent_context`, heuristic router
skipped entirely.

------------------------------------------------------------------------

# File Map

These are the only files touched by this implementation:

    agentic_system.py      ← Core guardrail logic (all 3 layers live here)
    routes.py              ← not_relevant response handler
    ModelBuilder.tsx       ← Frontend step → agent_context mapping

No agent node files were modified. No new files were created.

------------------------------------------------------------------------

# Architecture Deep Dive

## `MessageState` --- Why `agent_context` Had to Be Declared

LangGraph uses `MessageState` as a strict `TypedDict` schema. Any key
set on the state dict that isn't declared in the class is **silently
stripped** when LangGraph creates its internal state copy.

The field was being sent correctly from the frontend and set correctly
in `routes.py`, but was disappearing before `_route_request` ran.

### Fix

Added `agent_context: Optional[str]` to `MessageState`.

``` python
class MessageState(TypedDict):
    ...
    agent_context: Optional[str]
```

⚠️ If you rename or remove this field, the guardrail stops working
silently.

------------------------------------------------------------------------

## Layer 1 --- Keyword Pre-check

Checks whether the query contains any data science related language.

Strategies:

1.  Exact substring match
2.  Fuzzy match (`difflib.get_close_matches`, cutoff=0.75)

If neither finds a hit → **BLOCK immediately** (no LLM call).

Example blocked queries:

-   tell me a joke
-   who won the World Cup
-   what is 9 plus 10
-   I will lose my job if you don't help

Example pass:

-   mising values → fuzzy match to *missing*

------------------------------------------------------------------------

## Layer 2 --- System Message Check

Automated UI messages bypass LLM checks.

Example:

    Run QC Tasks

Guardrail checks if query starts with prefixes in:

    SYSTEM_MESSAGE_PREFIXES

If yes → PASS.

------------------------------------------------------------------------

## Layer 3 --- LLM Relevance Check

Runs only for genuine user queries containing data science terms.

Rules enforced in prompt:

1.  Detect manipulation or injection
2.  Evaluate primary purpose
3.  Default to NO if uncertain

Prompt ends with:

    ONE WORD ANSWER ONLY - YES or NO

Answer extraction checks the first 50 characters.

Fail behavior:

If the LLM throws an exception → **fail open**.

------------------------------------------------------------------------

# Request Flow

    User message
         │
    Frontend attaches agent_context
         │
    POST /api/v1/chat
         │
    routes.py sets state['agent_context']
         │
    _route_request()
         │
    _check_relevance()
         │
    Layer1 → Layer2 → Layer3
         │
    PASS → route to agent
    BLOCK → intent = not_relevant

------------------------------------------------------------------------

# Integrating a New Agent

Update three dictionaries in `agentic_system.py` and one function in
`ModelBuilder.tsx`.

## AGENT_TOPICS

``` python
AGENT_TOPICS = {
    "data_transformation": "...",
    "data_insight": "...",
    "modelling": "...",
    "your_new_agent": "description"
}
```

## AGENT_DISPLAY_NAMES

``` python
AGENT_DISPLAY_NAMES = {
    "data_transformation": "Data Treatment",
    "data_insight": "Data Insights",
    "modelling": "Model Training",
    "your_new_agent": "Display Name"
}
```

## AGENT_STRONG_KEYWORDS

``` python
AGENT_STRONG_KEYWORDS = {
    "data_transformation": [...],
    "data_insight": [...],
    "modelling": [...],
    "your_new_agent": ["keyword_one","keyword_two"]
}
```

## Frontend Mapping

``` typescript
const getAgentContextFromStep = (step: number): string | null => {
    if (step === 2) return 'data_transformation';
    if (step === 3) return 'data_insight';
    if (step === YOUR_NEW_STEP) return 'your_new_agent';
    if ([4.5,5,6,6.5,7].includes(step)) return 'modelling';
    return null;
};
```

------------------------------------------------------------------------

# Configuration Reference

## Step Mapping

| Step   | Context             | Protected |
|--------|---------------------|-----------|
| 2      | data_transformation | Yes       |
| 3      | data_insight        | Yes       |
| 4      | null                | No        |
| 4.5-7  | modelling           | Yes       |

------------------------------------------------------------------------

# Logging Reference

All logs contain prefix:

    [GUARDRAIL]

Examples:

-   BLOCKED (Layer 1)
-   PASSED (Layer 2)
-   LLM check (Layer 3)
-   PASSED (Layer 3)
-   BLOCKED (Layer 3)
-   Layer 3 failed → failing open

------------------------------------------------------------------------

# Known Issues

### Fuzzy False Positive

"instructions" may match "distribution".

Planned fix:

-   Raise cutoff to 0.82
-   Add injection detection layer