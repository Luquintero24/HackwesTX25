# extract_and_store.py
# LLM-in-the-loop ETL: Email -> Gemini JSON -> DB (emails + kg_facts w/ severity)
# Requires: pip install google-generativeai python-dotenv sqlalchemy

import os, re, json, time, random
from datetime import datetime, timezone
from typing import Optional, Tuple, Dict, Any, List

import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import SessionLocal
from tables import Pad, Component, Email, KGFact, Threshold

from dotenv import load_dotenv
load_dotenv()

# -------------------------
# 0) Configuration
# -------------------------
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("Please set GEMINI_API_KEY in the environment.")
genai.configure(api_key=GEMINI_API_KEY)

# Free tier is ~10 req/min; default to 8 to be safe (override with GEMINI_RPM env var)
RATE_LIMIT_RPM = int(os.getenv("GEMINI_RPM", "8"))
_LAST_CALL = [0.0]  # mutable capture for simple rate-limit state

def _respect_rate_limit():
    interval = 60.0 / max(RATE_LIMIT_RPM, 1)
    now = time.time()
    wait = _LAST_CALL[0] + interval - now
    if wait > 0:
        time.sleep(wait)
    _LAST_CALL[0] = time.time()

def _resp_text(resp):
    # Compatible way to get plain text across SDK versions
    if hasattr(resp, "text") and resp.text:
        return resp.text
    try:
        return resp.candidates[0].content.parts[0].text
    except Exception:
        return ""

def _call_gemini_with_retry(contents, generation_config, max_tries=5):
    """
    Rate-limit and auto-retry on 429s and transient errors.
    Respects server-provided retry delay when available.
    """
    delay = 5.0
    for attempt in range(max_tries):
        _respect_rate_limit()
        try:
            return GEMINI.generate_content(contents, generation_config=generation_config)
        except ResourceExhausted as e:
            # Parse server-suggested retry delay from error text (if present)
            msg = str(e)
            m = re.search(r"retry_delay\s*{\s*seconds:\s*(\d+)", msg)
            sleep_s = float(m.group(1)) if m else delay
            time.sleep(sleep_s + random.uniform(0, 1))
            delay = min(delay * 2, 60.0)
        except Exception:
            # Transient: backoff & retry
            time.sleep(delay + random.uniform(0, 1))
            delay = min(delay * 2, 60.0)
    # Final attempt—let exceptions surface
    _respect_rate_limit()
    return GEMINI.generate_content(contents, generation_config=generation_config)

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
# Optional synonyms safety net if the LLM slips
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

# Constructor shape that works across common SDK versions
try:
    GEMINI = genai.GenerativeModel(model_name=GEMINI_MODEL)
except TypeError:
    GEMINI = genai.GenerativeModel(GEMINI_MODEL)

GENERATION_CONFIG = {
    "temperature": 0.1,
    # Newer SDKs accept these; older ones ignore them if passed at call-time
    "response_mime_type": "application/json",
    "response_schema": EXTRACTION_SCHEMA,
}

def normalize_metric_name(name: str) -> Optional[str]:
    name = name.strip()
    if name in CANONICAL_METRICS:
        return name
    if name in METRIC_SYNONYMS:
        return METRIC_SYNONYMS[name]
    return None

def gemini_extract_metrics(email_body: str) -> Dict[str, Any]:
    resp = _call_gemini_with_retry(
        [GEMINI_INSTRUCTIONS, "\nEMAIL BODY:\n" + email_body.strip()],
        generation_config=GENERATION_CONFIG,
    )
    raw = _resp_text(resp).strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"Gemini did not return JSON: {raw[:200]}")
    data = json.loads(raw[start:end+1])

    out = {
        "metrics": [],
        "qualitative_status": data.get("qualitative_status", "unknown"),
        "notes": data.get("notes", "")
    }
    for m in data.get("metrics", []):
        metric_raw = m.get("metric")
        metric = normalize_metric_name(metric_raw) if metric_raw else None
        if not metric:
            continue
        unit_expected = CANONICAL_METRICS[metric]["unit"]
        val = float(m["value"])
        unit = m.get("unit", unit_expected)
        if unit != unit_expected:
            out["notes"] = (out["notes"] + f" unit_mismatch:{metric}({unit}!={unit_expected})").strip()
        out["metrics"].append({"metric": metric, "value": val, "unit": unit_expected})
    return out

# -------------------------
# 3) Threshold-based severity
# -------------------------
def pick_best_threshold(rows: List[Threshold], component_type: Optional[str], component_id: Optional[str]) -> Optional[Threshold]:
    """Preference order: applies_component > applies_type > global (neither set)."""
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
    Your requested semantics:
      - LOW  => value is below the lower bound (warn_low / alarm_low)
      - HIGH => value is above the upper bound (warn_high / alarm_high)
      - MED  => value is within the acceptable band (OK)
    """
    # Too low?
    if t.alarm_low is not None and value <= float(t.alarm_low):
        return "LOW"
    if t.warn_low is not None and value <= float(t.warn_low):
        return "LOW"
    # Too high?
    if t.alarm_high is not None and value >= float(t.alarm_high):
        return "HIGH"
    if t.warn_high is not None and value >= float(t.warn_high):
        return "HIGH"
    # OK range
    return "MED"

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
        email.raw_text = body or email.raw_text
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

    # Timestamp to stamp onto facts
    fact_ts = email.sent_at

    # LLM extraction
    ext = gemini_extract_metrics(body or "")

    # 1) located_at (if both present)
    if pad_id and component_id:
        session.add(KGFact(
            email_id=email.email_id,
            subj_text=component_id,
            subj_type="component",
            predicate="located_at",
            obj_text=pad_id,
            obj_type="pad",
            pad_id=pad_id,
            component_id=component_id,
            extracted_at=fact_ts,
        ))

    # 2) has_metric (+ severity per thresholds)
    any_out_of_range = False
    for m in ext["metrics"]:
        metric = m["metric"]
        value = float(m["value"])
        unit = m["unit"]

        # severity from thresholds (aligned to applies_type/component)
        sev = compute_severity(session, component_type, component_id, metric, value) or "MED"
        if sev != "MED":
            any_out_of_range = True

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
            severity=sev,              # LOW (too low), MED (OK), HIGH (too high)
            extracted_at=fact_ts,
        ))

    # 3) Aggregate symptom if anything is out of range
    if any_out_of_range:
        session.add(KGFact(
            email_id=email.email_id,
            subj_text=component_id or (pad_id or "UNKNOWN"),
            subj_type="component" if component_id else "pad",
            predicate="has_symptom",
            obj_text="exceeded_limits",
            obj_type="symptom",
            pad_id=pad_id,
            component_id=component_id,
            severity="HIGH",  # summary flag; detailed direction lives in metric rows
            extracted_at=fact_ts,
        ))

    # 4) Qualitative status (optional)
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
            component_id=component_id,
            extracted_at=fact_ts,
        ))

    session.commit()
    return email.email_id

# -------------------------
# 6) Batch: process ALL emails in DB
# -------------------------
def process_all_emails(limit: Optional[int] = None, reextract: bool = True, batch: int = 50):
    """
    Iterate all emails in the DB, run Gemini extraction on their bodies,
    and populate kg_facts with extracted_at = sent_at (fallback to received_at -> now()).
    - limit: cap how many to process (None = all)
    - reextract: if True, delete existing facts for that email and reinsert
    - batch: commit every N emails
    """
    db: Session = SessionLocal()
    try:
        q = db.query(Email).order_by(Email.email_id.asc())
        if limit:
            q = q.limit(limit)

        count = 0
        for e in q:
            # body from raw_text or legacy raw_tex
            body = getattr(e, "raw_text", None) or getattr(e, "raw_tex", None) or ""
            if not body:
                continue

            if not reextract:
                # Skip if this email already has any facts
                already = db.query(KGFact.id).filter(KGFact.email_id == e.email_id).first()
                if already:
                    continue
            else:
                # Clean slate for this email
                db.query(KGFact).filter(KGFact.email_id == e.email_id).delete()

            env = {
                "message_id": e.message_id,
                "from": e.from_addr,
                "to": e.to_addr,
                "date": e.sent_at,
                "subject": e.subject,
            }
            insert_email_and_facts(db, env, body)
            count += 1

            if count % batch == 0:
                db.commit()

        db.commit()
        print(f"Processed {count} emails.")
    finally:
        db.close()

# -------------------------
# 7) Entry point
# -------------------------
if __name__ == "__main__":
    # Process ALL emails currently in the DB.
    # Tip: set GEMINI_RPM=8 (or lower) in your .env if you still hit free-tier limits.
    process_all_emails(limit=None, reextract=True, batch=50)
