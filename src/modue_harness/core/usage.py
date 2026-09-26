"""Usage and quota tracking module for ModueHarness.

Tracks token consumption, estimated costs, and call counts across sliding time
windows (e.g., 5-hour rolling limit, weekly rolling limit) for each AI CLI agent.
Detects rate limit and quota exhaustion signals in CLI output to assist proactive
failover and scheduling.
"""

from dataclasses import asdict, dataclass
import datetime
import json
from pathlib import Path
import re
import time
from typing import Any, Dict, List, Optional


# Regex patterns for detecting rate limits, 5-hour limits, weekly limits, and reset times
_RE_5H_LIMIT = re.compile(
    r"(?:5-?hour\s+limit|reached\s+(?:your\s+)?5-?hour\s+limit|5-?hour\s+usage\s+limit)",
    re.IGNORECASE,
)
_RE_WEEKLY_LIMIT = re.compile(
    r"(?:weekly\s+limit|reached\s+(?:your\s+)?weekly\s+limit|weekly\s+usage\s+limit)",
    re.IGNORECASE,
)
_RE_GENERIC_RATE_LIMIT = re.compile(
    r"(?:rate\s*limit\s*reached|exceeded\s*your\s*current\s*quota|insufficient_quota|RESOURCE_?EXHAUSTED|resource\s+(?:has\s+been\s+)?exhausted|429\s+Too\s+Many\s+Requests|Quota\s+exceeded|check\s+quota|usage\s+limit\s+reached)",
    re.IGNORECASE,
)
_RE_RESETS_AT = re.compile(
    r"resets?\s+(?:at|in|on)\s+([0-9]{1,2}(?::[0-9]{2})?\s*(?:AM|PM|am|pm)?|[0-9]+\s*(?:hours?|hrs?|minutes?|mins?)|[A-Za-z]+day|[A-Za-z]+\s+\d{1,2})",
    re.IGNORECASE,
)
_RE_COST = re.compile(r"cost[:\s]+\$?\s*([0-9]+\.[0-9]+)", re.IGNORECASE)
_RE_TOKENS = re.compile(r"(?:tokens?|token\s+count)[:\s]+([0-9,]+)", re.IGNORECASE)


@dataclass
class UsageEntry:
    """A single execution record for an AI agent turn."""

    timestamp: float
    iso_time: str
    agent: str
    job_id: Optional[str] = None
    model: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    duration_sec: float = 0.0
    is_success: bool = True
    is_rate_limited: bool = False
    limit_type: Optional[str] = None  # "5h", "weekly", "quota", "rate_limit"
    resets_at: Optional[str] = None
    is_estimated: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def detect_limit_signal(stdout: str, stderr: str) -> Dict[str, Any]:
    """Inspect CLI process stdout/stderr for 5-hour, weekly, or generic rate limits."""
    combined = f"{stdout}\n{stderr}"
    if not combined.strip():
        return {"is_rate_limited": False, "limit_type": None, "resets_at": None}

    limit_type = None
    is_limited = False

    if _RE_5H_LIMIT.search(combined):
        is_limited = True
        limit_type = "5h"
    elif _RE_WEEKLY_LIMIT.search(combined):
        is_limited = True
        limit_type = "weekly"
    elif _RE_GENERIC_RATE_LIMIT.search(combined):
        is_limited = True
        limit_type = "quota"

    resets_at = None
    if is_limited:
        match_reset = _RE_RESETS_AT.search(combined)
        if match_reset:
            resets_at = match_reset.group(1).strip()

    return {
        "is_rate_limited": is_limited,
        "limit_type": limit_type,
        "resets_at": resets_at,
    }


def extract_or_estimate_usage(
    stdout: str,
    stderr: str,
    prompt_length: int = 0,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """Extract usage metrics from JSON or text output, or estimate based on text length."""
    # 1. Try parsing JSON output (e.g. Claude --output-format json or Codex API response)
    for raw in [stdout, stderr]:
        if not raw:
            continue
        trimmed = raw.strip()
        if (trimmed.startswith("{") and trimmed.endswith("}")) or ("\"usage\"" in trimmed):
            try:
                data = json.loads(trimmed)
                usage_obj = data.get("usage")
                if isinstance(usage_obj, dict):
                    in_tok = int(usage_obj.get("input_tokens") or usage_obj.get("prompt_tokens") or 0)
                    out_tok = int(usage_obj.get("output_tokens") or usage_obj.get("completion_tokens") or 0)
                    cost = float(data.get("cost_usd") or data.get("cost") or 0.0)
                    return {
                        "input_tokens": in_tok,
                        "output_tokens": out_tok,
                        "total_tokens": in_tok + out_tok,
                        "cost_usd": cost,
                        "is_estimated": False,
                    }
            except Exception:
                pass

    # 2. Try parsing text cost and token patterns
    found_cost = 0.0
    c_m = _RE_COST.search(stdout) or _RE_COST.search(stderr)
    if c_m:
        try:
            found_cost = float(c_m.group(1))
        except Exception:
            pass

    found_tokens = 0
    t_m = _RE_TOKENS.search(stdout) or _RE_TOKENS.search(stderr)
    if t_m:
        try:
            found_tokens = int(t_m.group(1).replace(",", ""))
        except Exception:
            pass

    if found_tokens > 0:
        in_tok = max(1, int(found_tokens * 0.4))
        out_tok = max(1, found_tokens - in_tok)
        return {
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "total_tokens": found_tokens,
            "cost_usd": found_cost,
            "is_estimated": False,
        }

    # 3. Fallback: Character length heuristic (~4 characters per token)
    in_tok = max(1, prompt_length // 4)
    out_tok = max(1, len(stdout) // 4) if stdout else 0
    tot_tok = in_tok + out_tok

    # Rough cost heuristic (~$3.00 per 1M tokens)
    estimated_cost = round((tot_tok / 1_000_000.0) * 3.0, 4)

    return {
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "total_tokens": tot_tok,
        "cost_usd": found_cost if found_cost > 0.0 else estimated_cost,
        "is_estimated": True,
    }


class UsageTracker:
    """Manages AI agent usage logs and sliding window metrics."""

    DEFAULT_LIMITS: Dict[str, Dict[str, Any]] = {
        "claude": {
            "five_hour_tokens": 150_000,
            "weekly_tokens": 1_000_000,
            "five_hour_requests": 50,
            "weekly_requests": 300,
        },
        "codex": {
            "five_hour_tokens": 200_000,
            "weekly_tokens": 1_500_000,
            "five_hour_requests": 60,
            "weekly_requests": 400,
        },
        "gemini": {
            "five_hour_tokens": 300_000,
            "weekly_tokens": 2_000_000,
            "five_hour_requests": 100,
            "weekly_requests": 600,
        },
        "default": {
            "five_hour_tokens": 200_000,
            "weekly_tokens": 1_000_000,
            "five_hour_requests": 60,
            "weekly_requests": 300,
        },
    }

    def __init__(self, root_dir: Path, custom_limits: Optional[Dict[str, Any]] = None) -> None:
        self.root_dir = root_dir
        self.usage_dir = root_dir / "usage"
        self.history_file = self.usage_dir / "history.jsonl"
        self.custom_limits = custom_limits or {}

    def _ensure_dir(self) -> None:
        self.usage_dir.mkdir(parents=True, exist_ok=True)

    def record_entry(self, entry: UsageEntry) -> None:
        """Append an execution entry to history.jsonl."""
        self._ensure_dir()
        line = json.dumps(entry.to_dict(), ensure_ascii=False)
        with open(self.history_file, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def record_turn(
        self,
        agent: str,
        stdout: str,
        stderr: str,
        duration_sec: float,
        job_id: Optional[str] = None,
        model: Optional[str] = None,
        prompt_length: int = 0,
        is_success: bool = True,
        override_usage: Optional[Dict[str, Any]] = None,
    ) -> UsageEntry:
        """Analyze a turn execution, detect limits, and record usage."""
        limit_info = detect_limit_signal(stdout, stderr)
        usage_info = override_usage or extract_or_estimate_usage(stdout, stderr, prompt_length=prompt_length, model=model)

        now = time.time()
        iso_str = datetime.datetime.now().isoformat()

        entry = UsageEntry(
            timestamp=now,
            iso_time=iso_str,
            agent=agent,
            job_id=job_id,
            model=model,
            input_tokens=usage_info.get("input_tokens", 0),
            output_tokens=usage_info.get("output_tokens", 0),
            total_tokens=usage_info.get("total_tokens", 0),
            cost_usd=usage_info.get("cost_usd", 0.0),
            duration_sec=duration_sec,
            is_success=is_success,
            is_rate_limited=limit_info["is_rate_limited"],
            limit_type=limit_info["limit_type"],
            resets_at=limit_info["resets_at"],
            is_estimated=usage_info.get("is_estimated", False),
        )
        self.record_entry(entry)
        return entry

    def load_all_entries(self) -> List[UsageEntry]:
        """Read all historical entries from file."""
        if not self.history_file.exists():
            return []
        entries: List[UsageEntry] = []
        try:
            with open(self.history_file, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                        entries.append(UsageEntry(**d))
                    except Exception:
                        continue
        except Exception:
            return []
        return entries

    def get_agent_limits(self, agent: str) -> Dict[str, Any]:
        """Return limit configuration for a specific agent."""
        agent_lower = agent.lower()
        for k in self.custom_limits:
            if k.lower() in agent_lower:
                return self.custom_limits[k]
        for k in self.DEFAULT_LIMITS:
            if k in agent_lower:
                return self.DEFAULT_LIMITS[k]
        return self.DEFAULT_LIMITS["default"]

    def get_window_stats(
        self,
        agent: str,
        window_seconds: float,
        entries: Optional[List[UsageEntry]] = None,
    ) -> Dict[str, Any]:
        """Aggregate stats for an agent within the given window (e.g. 5h, 7d)."""
        all_e = entries if entries is not None else self.load_all_entries()
        cutoff = time.time() - window_seconds

        matching = [e for e in all_e if e.agent == agent and e.timestamp >= cutoff]

        tot_tokens = sum(e.total_tokens for e in matching)
        in_tokens = sum(e.input_tokens for e in matching)
        out_tokens = sum(e.output_tokens for e in matching)
        cost = sum(e.cost_usd for e in matching)
        calls = len(matching)
        failures = sum(1 for e in matching if not e.is_success)

        # Rate limit checks
        rate_limits = [e for e in matching if e.is_rate_limited]
        last_rl = rate_limits[-1] if rate_limits else None

        return {
            "calls": calls,
            "failures": failures,
            "input_tokens": in_tokens,
            "output_tokens": out_tokens,
            "total_tokens": tot_tokens,
            "cost_usd": round(cost, 4),
            "rate_limit_hits": len(rate_limits),
            "last_rate_limit": last_rl.to_dict() if last_rl else None,
        }

    def get_agent_status(
        self,
        agent: str,
        entries: Optional[List[UsageEntry]] = None,
    ) -> Dict[str, Any]:
        """Compute 5-hour, weekly, and lifetime metrics for an agent."""
        all_e = entries if entries is not None else self.load_all_entries()

        five_hours_sec = 5 * 3600.0
        weekly_sec = 7 * 24 * 3600.0

        five_h = self.get_window_stats(agent, five_hours_sec, entries=all_e)
        weekly = self.get_window_stats(agent, weekly_sec, entries=all_e)
        lifetime = self.get_window_stats(agent, 365 * 24 * 3600.0, entries=all_e)

        limits = self.get_agent_limits(agent)
        five_h_max = limits.get("five_hour_tokens", 150_000)
        weekly_max = limits.get("weekly_tokens", 1_000_000)

        five_h_ratio = min(1.0, five_h["total_tokens"] / float(five_h_max)) if five_h_max > 0 else 0.0
        weekly_ratio = min(1.0, weekly["total_tokens"] / float(weekly_max)) if weekly_max > 0 else 0.0

        # Status determination: rate_limited > warning (>80%) > normal
        status = "normal"
        status_label = "정상"
        resets_at = None

        recent_rl = five_h["last_rate_limit"] or weekly["last_rate_limit"]
        if recent_rl:
            status = "rate_limited"
            status_label = "한도 초과"
            resets_at = recent_rl.get("resets_at")
        elif five_h_ratio >= 1.0 or weekly_ratio >= 1.0:
            status = "rate_limited"
            status_label = "한도 소진"
        elif five_h_ratio >= 0.8 or weekly_ratio >= 0.8:
            status = "warning"
            status_label = "주의 (80%+)"

        return {
            "agent": agent,
            "status": status,
            "status_label": status_label,
            "resets_at": resets_at,
            "five_hour": {
                **five_h,
                "limit_tokens": five_h_max,
                "usage_ratio": round(five_h_ratio, 3),
                "percent_str": f"{five_h_ratio * 100:.1f}%",
            },
            "weekly": {
                **weekly,
                "limit_tokens": weekly_max,
                "usage_ratio": round(weekly_ratio, 3),
                "percent_str": f"{weekly_ratio * 100:.1f}%",
            },
            "lifetime": lifetime,
        }

    def get_all_agents_summary(self, agent_names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Return usage status for all requested or known agents, preserving agent_names order."""
        all_e = self.load_all_entries()
        known = set(e.agent for e in all_e)

        ordered_names: List[str] = []
        if agent_names:
            for name in agent_names:
                if name not in ordered_names:
                    ordered_names.append(name)
            # Add any remaining agents from history not explicitly in agent_names
            for name in sorted(known):
                if name not in ordered_names:
                    ordered_names.append(name)
        else:
            ordered_names = sorted(known)

        summaries = []
        for name in ordered_names:
            summaries.append(self.get_agent_status(name, entries=all_e))
        return summaries
