#!/usr/bin/env python3
"""Format-drift guard for the listening log (long-play issue #23).

The Weekly-log section of listening-log.md must use the canonical feedback
schema (reference/feedback-schema.md): one row per reaction, first cell the
week number. An older in-file comment documented a different column layout,
and rows written to that layout silently match zero parser rows across the
grower / streak / predictions / wild-card loops. This module lets each
parser detect that condition and warn on stderr instead of returning empty.

Usage in a parser::

    from log_drift import drift_watch
    watch, warn = drift_watch(ROW_RE)
    with open(LOG) as f:
        for line in f:
            m = watch(line)      # ROW_RE match, or None
            if not m:
                continue
            ...
    warn()

The watcher is deliberately conservative: it only counts rows inside the
Weekly-log section, ignores markdown separator rows, and only flags rows
that contain reaction text (played/skipped/loved/bounced off) — so a log
with no feedback rows yet, or with only the pre-course canon table, stays
silent.
"""
import re
import sys

SECTION_RE = re.compile(r"^#+\s*weekly log\b", re.IGNORECASE)
END_SECTION_RE = re.compile(r"^#{1,2}(?:\s|$)")  # a ##/# heading ends it; ### stays
SEPARATOR_RE = re.compile(r"^\|[\s:\-|]+\|$")
REACTION_WORD_RE = re.compile(r"\b(played|skipped|loved|bounced off)\b",
                              re.IGNORECASE)

SCHEMA_REF = "reference/feedback-schema.md"


def drift_watch(row_re):
    """Watch lines for the feedback-schema drift condition.

    row_re: compiled regex matching canonical rows (week number first).
    Returns (watch, warn): watch(line) returns the row_re match or None;
    warn() prints a format-drift warning to stderr when table rows in the
    Weekly-log section look like reaction records but none matched.
    """
    state = {"in_section": False, "matched": 0, "suspicious": 0}

    def watch(line):
        if SECTION_RE.match(line):
            state["in_section"] = True
            return None
        if state["in_section"] and END_SECTION_RE.match(line):
            state["in_section"] = False
            return None
        if not state["in_section"] or not line.lstrip().startswith("|"):
            return None
        if SEPARATOR_RE.match(line.strip()):
            return None
        m = row_re.match(line)
        if m:
            state["matched"] += 1
            return m
        if REACTION_WORD_RE.search(line):
            state["suspicious"] += 1
        return None

    def warn():
        if state["suspicious"] and not state["matched"]:
            print("WARNING: listening-log.md: table rows in the Weekly log "
                  "section look like reaction records but match 0 rows of "
                  f"the feedback schema ({SCHEMA_REF}) — format drift?",
                  file=sys.stderr)

    return watch, warn
