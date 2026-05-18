"""Agentic tool-use loop, shared between the eval script and the chat server.

Provides two entry points over the same underlying loop:

- `run_one_query(client, tools, question)` — synchronous; returns the final
  answer + trace + cost. Used by `scripts/run_agentic_eval.py`.
- `stream_one_query(client, tools, question)` — generator yielding event dicts
  (`tool_start`, `tool_input`, `tool_result`, `text_delta`, `done`). Used by
  `/api/query/stream` for the live demo UI so Aaron can watch the navigation
  happen instead of staring at a blank screen for 20s.

Both share `SYSTEM_PROMPT` and `_block_to_dict`. Kept here so the eval
artifact and the demo UI can never drift — same prompt, same loop, same
trace shape.
"""

from __future__ import annotations

import time
from typing import Any, Generator

from .agentic_tools import AgenticTools
from .query import MODEL, estimate_cost_usd

MAX_TOKENS_OUT = 4096

SYSTEM_PROMPT = """\
You are the Syracuse University AI Knowledge Base assistant. Answer questions \
about Syracuse's AI tools, policies, and procedures using ONLY content you \
retrieve via the provided tools.

CORPUS SHAPE
- 29 raw pages from Syracuse's "Artificial Intelligence (AI)" Confluence space.
  Topics: Claude, Copilot, Gemini, mentorAI (Clementine), NotebookLM,
  approved-tools policy, data classification, MCP and connectors, Claude
  Code setup, example use cases.
- 2 reviewed wiki hubs that synthesize cross-cutting questions across 3+ raw
  pages each (data policy comparison, Claude product surface map).
- Orientation files (CLAUDE.md, indexes) describe the layout and routing rules.

NAVIGATION PATTERN
1. Start by reading an orientation file (`read_index`) — `index.md` or the
   space-level `raw/.../index.md` — unless you already know which page covers
   the question.
2. For cross-cutting questions (policy comparisons, "what's enabled at SU",
   tool selection), call `list_hubs` and prefer a hub if one matches.
3. Use `search` to find pages by keyword when the indexes don't already point
   at the right page.
4. Always `read_page` before citing. A search snippet is not enough to ground a
   citation.

CITATION RULES
1. Every factual claim MUST cite its source page using `[[<page-id>]]` for raw
   pages (digits) or `[[<slug>]]` for wiki hubs, inline at the end of the
   sentence. Example: "Claude retains chats for 2 years [[488210484]]."
   These wiki-style ids are the backend/admin trace citation.
2. Don't cite a page you haven't read with `read_page` in this turn.
3. User-facing citations must link to the original Confluence pages. End every
   answer with a "Sources:" section where each raw page is listed as a Markdown
   link to its `source_url`, followed by the trace id. Example:
   "- [Claude FAQ](https://answers.atlassian.syr.edu/...) [[488210484]]".
4. If you cite a wiki hub such as `[[approved-ai-tools-for-university-data]]`,
   also list the hub's `source_pages` as Confluence links in "Sources:" so the
   user can open the original Confluence pages behind the synthesis.
5. If the corpus doesn't answer the question, say so explicitly — do not
   invent content.

QUESTION SHAPE — calibrate effort to the question type:

  (a) NARROW LOOKUP questions ("how long does Claude retain chats", "where do I
      sign up", "how do I install X") — the answer lives in one or two pages.
      Target 2–3 tool calls total (orient + read). Don't over-navigate.

  (b) LIST / DISCOVERY / CATALOG questions ("what example uses are available",
      "what pages cover X", "which tools/connectors/options exist", "show me
      all examples of Y") — completeness beats tool-count minimization. If the
      index or a search result identifies multiple relevant pages, READ EACH
      relevant page before summarizing or citing it. Cap at a reasonable ~8
      pages if the set is larger.

  (c) CROSS-CUTTING / SYNTHESIS questions ("how should I decide between X and
      Y", "compare X vs Y on policy", "what's the SU posture on Z") — prefer
      the relevant wiki hub via `list_hubs → read_page(slug)`. One canonical
      hub beats stitching across raw pages.

DO NOT MENTION OTHER PAGES IN PROSE WITHOUT READING THEM. If you reference a
page by title or page_id, either:
  (i)  call `read_page` for it and cite `[[<page-id>]]` inline + add it to the
       Sources section, OR
  (ii) explicitly frame your mention as "the index also lists these page IDs
       (not yet summarized): [list]" so the reader knows it's an index excerpt,
       not a summary.

EFFICIENCY (subordinate to QUESTION SHAPE above):
- Don't call tools just to confirm what an index already told you.
- Don't redundantly read the same page twice in one turn.
"""


def _block_to_dict(block: Any) -> dict[str, Any]:
    """Anthropic SDK content block -> JSON shape the API expects on the next turn."""
    t = getattr(block, "type", None)
    if t == "text":
        return {"type": "text", "text": getattr(block, "text", "")}
    if t == "tool_use":
        return {
            "type": "tool_use",
            "id": getattr(block, "id", ""),
            "name": getattr(block, "name", ""),
            "input": getattr(block, "input", {}),
        }
    if t == "thinking":
        return {"type": "thinking", "thinking": getattr(block, "thinking", "")}
    if hasattr(block, "model_dump"):
        return block.model_dump()
    return {"type": t or "unknown"}


def _zero_usage() -> dict[str, int]:
    return {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
    }


def _system_blocks() -> list[dict[str, Any]]:
    return [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}]


# --- synchronous: used by scripts/run_agentic_eval.py -----------------------


def run_one_query(
    client: Any,
    tools: AgenticTools,
    question: str,
    max_iters: int = 10,
) -> dict[str, Any]:
    """Run one query through the agentic loop. Returns the final answer + trace."""
    tool_defs = tools.tool_definitions
    messages: list[dict[str, Any]] = [{"role": "user", "content": question}]
    trace: list[dict[str, Any]] = []
    total_usage = _zero_usage()
    final_answer = ""
    iters = 0
    t0 = time.perf_counter()
    stop_reason = "unknown"
    search_calls = 0
    miss_calls = 0

    while iters < max_iters:
        iters += 1
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS_OUT,
            system=_system_blocks(),
            tools=tool_defs,
            messages=messages,
        )
        usage = response.usage
        for k in total_usage:
            total_usage[k] += int(getattr(usage, k, 0) or 0)

        stop_reason = getattr(response, "stop_reason", "unknown")
        content_blocks = response.content or []

        if stop_reason != "tool_use":
            for blk in content_blocks:
                text = getattr(blk, "text", None)
                if text:
                    final_answer += text
            break

        messages.append({"role": "assistant", "content": [_block_to_dict(b) for b in content_blocks]})
        tool_results: list[dict[str, Any]] = []
        for blk in content_blocks:
            if getattr(blk, "type", None) != "tool_use":
                continue
            name = blk.name
            inp = blk.input or {}
            result = tools.dispatch(name, inp)
            trace.append({
                "iter": iters,
                "tool": name,
                "input": inp,
                "summary": result.summary,
                "output_chars": len(result.text),
            })
            if name == "search":
                search_calls += 1
            if result.summary.startswith("miss:"):
                miss_calls += 1
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": blk.id,
                "content": result.text,
            })
        messages.append({"role": "user", "content": tool_results})

    latency_ms = int((time.perf_counter() - t0) * 1000)
    cost = estimate_cost_usd(total_usage)
    return {
        "answer": final_answer,
        "trace": trace,
        "iterations": iters,
        "tool_call_count": len(trace),
        "search_calls": search_calls,
        "miss_calls": miss_calls,
        "stop_reason": stop_reason,
        "usage": total_usage,
        "cost_usd": cost,
        "latency_ms": latency_ms,
    }


# --- streaming: used by /api/query/stream for the live demo -----------------


def stream_one_query(
    client: Any,
    tools: AgenticTools,
    question: str,
    max_iters: int = 10,
) -> Generator[dict[str, Any], None, None]:
    """Run one query through the agentic loop, yielding events as they happen.

    Event shapes (each is `{"event": <name>, "data": {...}}`):
      - start         : just before the loop runs (tool defs ready)
      - tool_start    : model decided to call a tool (name + input known)
      - tool_result   : tool ran (summary + size known)
      - text_delta    : a chunk of final-answer text just streamed in
      - usage_update  : one model turn finished — running cost/usage
      - done          : final answer + trace + total cost, loop ended
      - error         : something blew up (Anthropic error, max_iters, etc.)

    The streaming surface uses `client.messages.stream(...)` from the Anthropic
    SDK, which gives us text deltas on the final composition turn for free.
    """
    tool_defs = tools.tool_definitions
    messages: list[dict[str, Any]] = [{"role": "user", "content": question}]
    trace: list[dict[str, Any]] = []
    total_usage = _zero_usage()
    final_answer = ""
    iters = 0
    t0 = time.perf_counter()
    stop_reason = "unknown"

    yield {"event": "start", "data": {
        "tools_available": [t["name"] for t in tool_defs],
        "model": MODEL,
    }}

    while iters < max_iters:
        iters += 1
        try:
            with client.messages.stream(
                model=MODEL,
                max_tokens=MAX_TOKENS_OUT,
                system=_system_blocks(),
                tools=tool_defs,
                messages=messages,
            ) as stream:
                for event in stream:
                    et = getattr(event, "type", None)
                    if et == "content_block_delta":
                        delta = getattr(event, "delta", None)
                        if delta is not None and getattr(delta, "type", None) == "text_delta":
                            chunk = getattr(delta, "text", "")
                            if chunk:
                                final_answer += chunk
                                yield {"event": "text_delta", "data": {"text": chunk}}
                final_message = stream.get_final_message()
        except Exception as e:  # noqa: BLE001 - surface any SDK / network failure cleanly
            yield {"event": "error", "data": {"message": str(e)}}
            return

        usage = final_message.usage
        for k in total_usage:
            total_usage[k] += int(getattr(usage, k, 0) or 0)
        running_cost = estimate_cost_usd(total_usage)
        yield {"event": "usage_update", "data": {
            "iteration": iters,
            "usage": dict(total_usage),
            "cost_usd": running_cost,
        }}

        stop_reason = getattr(final_message, "stop_reason", "unknown")
        content_blocks = final_message.content or []

        if stop_reason != "tool_use":
            break

        messages.append({"role": "assistant", "content": [_block_to_dict(b) for b in content_blocks]})
        tool_results: list[dict[str, Any]] = []
        for blk in content_blocks:
            if getattr(blk, "type", None) != "tool_use":
                continue
            name = blk.name
            inp = blk.input or {}
            yield {"event": "tool_start", "data": {
                "iter": iters,
                "name": name,
                "input": inp,
                "tool_use_id": blk.id,
            }}
            result = tools.dispatch(name, inp)
            trace.append({
                "iter": iters,
                "tool": name,
                "input": inp,
                "summary": result.summary,
                "output_chars": len(result.text),
            })
            yield {"event": "tool_result", "data": {
                "iter": iters,
                "name": name,
                "summary": result.summary,
                "output_chars": len(result.text),
                "is_miss": result.summary.startswith("miss:"),
            }}
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": blk.id,
                "content": result.text,
            })
        messages.append({"role": "user", "content": tool_results})

    latency_ms = int((time.perf_counter() - t0) * 1000)
    cost = estimate_cost_usd(total_usage)
    yield {"event": "done", "data": {
        "answer": final_answer,
        "trace": trace,
        "iterations": iters,
        "tool_call_count": len(trace),
        "stop_reason": stop_reason,
        "usage": total_usage,
        "cost_usd": cost,
        "latency_ms": latency_ms,
    }}
