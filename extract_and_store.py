# extract_and_store.py
# LLM-in-the-loop ETL: Email -> Gemini JSON -> DB (emails + kg_facts w/ severity)
# Requires: pip install google-generativeai

import os, re, json
from datetime import datetime, timezone
from typing import Optional, Tuple, Dict, Any, List

import google.generativeai as genai
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import SessionLocal
from tables import Pad, Component, Email, KGFact, Threshold

from dotenv import load_dotenv
load_dotenv()

# -------------------------
# 0) Configuration
# -------------------------
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("Please set GEMINI_API_KEY in the environment.")
genai.configure(api_key=GEMINI_API_KEY)

# Canonical metric dictionary aligned to your seed_thresholds.py
CANONICAL_METRICS = {
    # Engine
    "engine_oil_temp_c": {"unit": "°C"},
    "engine_water_temp_c": {"unit": "°C"},
    "engine_oil_pressure_psi": {"unit": "psi"},
    "engine_load_pct": {"unit": "%"},
    # Transmission
    "trans_oil_temp_c": {"unit": "°C"},
    "trans_oil_pressure_psi": {"unit": "psi"},
    # Power end
    "power_end_oil_temp_c": {"unit": "°C"},
    "power_end_oil_pressure_psi": {"unit": "psi"},
    # Fluid end
    "fluid_end_vibration_mms": {"unit": "mm/s"},
}
# Optional synonyms safety net if the LLM slips (we still force canonical in the prompt)
METRIC_SYNONYMS = {
    "engine_load_percent": "engine_load_pct",
    "engine_oil_pressure": "engine_oil_pressure_psi",
    "engine_oil_temp": "engine_oil_temp_c",
    "engine_water_temp": "engine_water_temp_c",
    "transmission_oil_temp_c": "trans_oil_temp_c",
    "transmission_oil_pressure_psi": "trans_oil_pressure_psi",
    "vibration_mms": "fluid_end_vibration_mms",
}

# -------------------------
# 1) Subject parsing helpers
# -------------------------
PAD_RE = re.compile(r"\bPAD-[A-Z0-9]+\b", re.I)
COMP_RE = re.compile(
    r"\b(ENG(?:INE)?|TRANS(?:MISSION)?|LOCKUP|POWER[_\- ]?END|FLUID[_\- ]?END)-\d+\b",
    re.I,
)

def parse_subject(subject: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    if not subject:
        return None, None
    pad = None
    comp = None
    m = PAD_RE.search(subject)
    if m:
        pad = m.group(0).upper()
    c = COMP_RE.search(subject)
    if c:
        comp_raw = c.group(0).upper().replace("ENGINE-", "ENG-").replace("TRANSMISSION-", "TRANS-")
        comp_raw = comp_raw.replace("POWER END-", "POWER_END-").replace("FLUID END-", "FLUID_END-")
        comp = comp_raw
    return pad, comp

def infer_component_type(component_id: Optional[str]) -> Optional[str]:
    if not component_id:
        return None
    if component_id.startswith("ENG"):
        return "engine"
    if component_id.startswith("TRANS"):
        return "transmission"
    if component_id.startswith("LOCKUP"):
        return "lockup"
    if component_id.startswith("POWER_END"):
        return "power_end"
    if component_id.startswith("FLUID_END"):
        return "fluid_end"
    return None

# -------------------------
# 2) Gemini extraction
# -------------------------
EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "metrics": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "metric": {"type": "string"},  # must be in CANONICAL_METRICS
                    "value": {"type": "number"},
                    "unit": {"type": "string"}
                },
                "required": ["metric", "value", "unit"]
            }
        },
        "qualitative_status": {
            "type": "string"  # normal | warning | exceeded | issue_flagged | unknown
        },
        "notes": {"type": "string"}
    },
    "required": ["metrics"]
}

GEMINI_INSTRUCTIONS = f"""\
You extract structured metrics from oilfield operations email bodies.

Return ONLY valid JSON following this schema:
- metrics: array of objects {{ metric, value, unit }}
- qualitative_status: one of [normal, warning, exceeded, issue_flagged, unknown]
- notes: short free text if needed

Use these canonical metric names EXACTLY (no others):
{chr(10).join('- ' + k + f" ({v['unit']})" for k, v in CANONICAL_METRICS.items())}

Rules:
- Convert values into the units shown in parentheses above.
- If a metric is not mentioned, omit it.
- Be literal: only extract what's stated or numerically implied in the body.
- For percentages, output the numeric value (e.g., 70% -> value: 70, unit: "%").
"""

GEMINI = genai.GenerativeModel(
    model_name=GEMINI_MODEL,
    generation_config={
        "response_mime_type": "application/json",
        "response_schema": EXTRACTION_SCHEMA,
        "temperature": 0.1,
    },
)

def normalize_metric_name(name: str) -> Optional[str]:
    name = name.strip()
    if name in CANONICAL_METRICS:
        return name
    if name in METRIC_SYNONYMS:
        return METRIC_SYNONYMS[name]
    return None

def gemini_extract_metrics(email_body: str) -> Dict[str, Any]:
    resp = GEMINI.generate_content([GEMINI_INSTRUCTIONS, "\nEMAIL BODY:\n" + email_body.strip()])
    data = json.loads(resp.text)

    out = {
        "metrics": [],
        "qualitative_status": data.get("qualitative_status", "unknown"),
        "notes": data.get("notes", "")
    }
    for m in data.get("metrics", []):
        metric_raw = m.get("metric")
        metric = normalize_metric_name(metric_raw) if metric_raw else None
        if not metric:
            # Skip unknown metric names
            continue
        unit_expected = CANONICAL_METRICS[metric]["unit"]
        val = float(m["value"])
        unit = m.get("unit", unit_expected)
        # If unit mismatches, keep value but annotate (you can add conversion here if needed)
        if unit != unit_expected:
            out["notes"] = (out["notes"] + f" unit_mismatch:{metric}({unit}!={unit_expected})").strip()
        out["metrics"].append({"metric": metric, "value": val, "unit": unit_expected})
    return out

# -------------------------
# 3) Threshold-based severity
# -------------------------
def pick_best_threshold(rows: List[Threshold], component_type: Optional[str], component_id: Optional[str]) -> Optional[Threshold]:
    """
    Preference order: applies_component > applies_type > global (neither set).
    """
    best = None
    best_score = -1
    for t in rows:
        score = 0
        if t.applies_component and component_id and t.applies_component == component_id:
            score = 3
        elif t.applies_type and component_type and t.applies_type == component_type:
            score = 2
        elif not t.applies_component and not t.applies_type:
            score = 1
        if score > best_score:
            best_score = score
            best = t
    return best

def severity_from_threshold(t: Threshold, value: float) -> str:
    """
    Map warn/alarm to severities:
      - HIGH if crosses any alarm_* bound
      - MED     if crosses any warn_* bound
      - LOW      otherwise
    """
    # Handle both sides if provided
    if t.alarm_high is not None and value >= float(t.alarm_high):
        return "HIGH"
    if t.alarm_low  is not None and value <= float(t.alarm_low):
        return "HIGH"
    if t.warn_high  is not None and value >= float(t.warn_high):
        return "MED"
    if t.warn_low   is not None and value <= float(t.warn_low):
        return "MED"
    return "LOW"

def compute_severity(session: Session, component_type: Optional[str], component_id: Optional[str], metric: str, value: float) -> Optional[str]:
    rows = session.execute(
        select(Threshold).where(Threshold.metric == metric, Threshold.active == True)
    ).scalars().all()
    if not rows:
        return None
    t = pick_best_threshold(rows, component_type, component_id)
    if not t:
        return None
    return severity_from_threshold(t, value)

# -------------------------
# 4) DB helpers
# -------------------------
def get_or_create_pad(session: Session, pad_id: Optional[str]) -> Optional[Pad]:
    if not pad_id:
        return None
    row = session.get(Pad, pad_id)
    if row:
        return row
    row = Pad(pad_id=pad_id, name=pad_id)
    session.add(row)
    session.flush()
    return row

def get_or_create_component(session: Session, component_id: Optional[str], pad_id: Optional[str], component_type: Optional[str]) -> Optional[Component]:
    if not component_id:
        return None
    row = session.get(Component, component_id)
    if row:
        return row
    row = Component(component_id=component_id, pad_id=pad_id, type=component_type)
    session.add(row)
    session.flush()
    return row

# -------------------------
# 5) Main entry: email -> facts
# -------------------------
def insert_email_and_facts(session: Session, envelope: Dict[str, Any], body: str) -> int:
    """
    envelope: {
      "message_id": "<R001@...>",
      "from": "pad-a-lead@patterson-uti.com",
      "to": "ops@patterson-uti.com",
      "date": datetime(..., tzinfo=timezone.utc),
      "subject": "PAD-B | ENG-27 | Auto-generated event"
    }
    Returns: inserted Email.email_id
    """
    # Parse subject to lock in pad/component deterministically
    pad_id, component_id = parse_subject(envelope.get("subject", ""))
    component_type = infer_component_type(component_id)

    # Ensure dims
    get_or_create_pad(session, pad_id)
    get_or_create_component(session, component_id, pad_id, component_type)

    # Upsert Email (idempotent by message_id)
    existing = session.execute(select(Email).where(Email.message_id == envelope["message_id"])).scalar_one_or_none()
    if existing:
        email = existing
        # Optionally update fields if you want
        email.raw_text = body
    else:
        email = Email(
            message_id=envelope["message_id"],
            from_addr=envelope.get("from"),
            to_addr=envelope.get("to"),
            subject=envelope.get("subject"),
            received_at=envelope.get("date"),
            sent_at=envelope.get("date"),
            pad_id=pad_id,
            component_id=component_id,
            raw_text=body,
            headers={},  # fill with provider headers if available
        )
        session.add(email)
        session.flush()

    # LLM extraction
    ext = gemini_extract_metrics(body)

    # 1) located_at (if we have both)
    if pad_id and component_id:
        session.add(KGFact(
            email_id=email.email_id,
            subj_text=component_id,
            subj_type="component",
            predicate="located_at",
            obj_text=pad_id,
            obj_type="pad",
            pad_id=pad_id,
            component_id=component_id
        ))

    # 2) has_metric (+ severity per thresholds)
    for m in ext["metrics"]:
        metric = m["metric"]
        value = float(m["value"])
        unit = m["unit"]

        # severity from thresholds (aligned to applies_type/component)
        sev = compute_severity(session, component_type, component_id, metric, value)

        session.add(KGFact(
            email_id=email.email_id,
            subj_text=component_id or (pad_id or "UNKNOWN"),
            subj_type="component" if component_id else "pad",
            predicate="has_metric",
            obj_text=metric,
            obj_type="metric",
            pad_id=pad_id,
            component_id=component_id,
            metric=metric,
            value=value,
            unit=unit,
            severity=sev or "LOW",  # default LOW if no threshold
        ))

        # If severity is MED/HIGH, emit a symptom fact (exceeded_limits)
        if sev in ("MED", "HIGH"):
            session.add(KGFact(
                email_id=email.email_id,
                subj_text=component_id or (pad_id or "UNKNOWN"),
                subj_type="component" if component_id else "pad",
                predicate="has_symptom",
                obj_text="exceeded_limits",
                obj_type="symptom",
                pad_id=pad_id,
                component_id=component_id,
                severity=sev
            ))

    # 3) Qualitative status (optional)
    qstat = ext.get("qualitative_status")
    if qstat in ("exceeded", "issue_flagged", "warning", "normal"):
        session.add(KGFact(
            email_id=email.email_id,
            subj_text=component_id or (pad_id or "UNKNOWN"),
            subj_type="component" if component_id else "pad",
            predicate="has_status",
            obj_text=qstat,
            obj_type="status",
            pad_id=pad_id,
            component_id=component_id
        ))

    session.commit()
    return email.email_id

# -------------------------
# 6) Example usage with your three emails
# -------------------------
def _dt(s: str) -> datetime:
    # Parse a RFC-2822-ish time string; for demo accept "Fri, 12 Sep 2025 08:15:00 +0000"
    # In production use email.utils.parsedate_to_datetime
    return datetime.strptime(s, "%a, %d %b %Y %H:%M:%S %z")

def demo():
    examples = [
        {
            "envelope": {
                "from": "pad-a-lead@patterson-uti.com",
                "to": "ops@patterson-uti.com",
                "date": _dt("Fri, 12 Sep 2025 08:15:00 +0000"),
                "subject": "PAD-B | ENG-27 | Auto-generated event",
                "message_id": "<R001@patterson-uti.com>",
            },
            "body": "OBSERVATION: Routine report: engine within range. Oil 62 psi, temp 112°C, water 82°C, load 70%."
        },
        {
            "envelope": {
                "from": "pad-b-supervisor@patterson-uti.com",
                "to": "ops@patterson-uti.com",
                "date": _dt("Fri, 12 Sep 2025 12:30:00 +0000"),
                "subject": "PAD-C | ENG-34 | Auto-generated event",
                "message_id": "<R018@patterson-uti.com>",
            },
            "body": "OBSERVATION: Engine reported oil pressure 71 psi, oil temp 129°C, water temp 87°C, load 95%. Condition: exceeded safe operating limits."
        },
        {
            "envelope": {
                "from": "pad-b-supervisor@patterson-uti.com",
                "to": "engineering@patterson-uti.com",
                "date": _dt("Fri, 12 Sep 2025 13:00:00 +0000"),
                "subject": "PAD-A | TRANS-12 | Auto-generated event",
                "message_id": "<R020@patterson-uti.com>",
            },
            "body": "OBSERVATION: Transmission metrics recorded: oil pressure 165 psi and oil temp 87°C. Issue flagged for follow-up inspection."
        },
    ]

    db = SessionLocal()
    try:
        for ex in examples:
            insert_email_and_facts(db, ex["envelope"], ex["body"])
        print("Inserted demo emails & facts.")
    finally:
        db.close()

if __name__ == "__main__":
    demo()
