from sqlalchemy import (
    Column, Text, String, Integer, Numeric, TIMESTAMP,
    ForeignKey, CheckConstraint, Boolean
)
from sqlalchemy.dialects.postgresql import JSONB
from db import Base

class Pad(Base):
    __tablename__ = "pads"
    pad_id = Column(String, primary_key=True)
    name   = Column(Text)

class Component(Base):
    __tablename__ = "components"
    component_id = Column(String, primary_key=True)
    pad_id       = Column(String, ForeignKey("pads.pad_id"))
    type         = Column(String)  # engine/transmission/lockup/power_end/fluid_end

class Email(Base):
    __tablename__ = "emails"
    email_id       = Column(Integer, primary_key=True, autoincrement=True)
    message_id     = Column(Text, unique=True)
    sent_at        = Column(TIMESTAMP(timezone=True))
    from_addr      = Column(Text)
    to_addr        = Column(Text)
    subject        = Column(Text)
    pad_id         = Column(String, ForeignKey("pads.pad_id"))
    component_id   = Column(String, ForeignKey("components.component_id"))
    component_type = Column(String)
    raw_text       = Column(Text)
    headers        = Column(JSONB)

class KGFact(Base):
    __tablename__ = "kg_facts"
    id            = Column(Integer, primary_key=True, autoincrement=True)
    email_id      = Column(Integer, ForeignKey("emails.email_id"))   # provenance
    # Triple (subject, predicate, object)
    subj_text     = Column(Text)     # e.g., "ENG-12"
    subj_type     = Column(String)   # e.g., "component" | "pad" | "metric" | "symptom"
    predicate     = Column(String)   # e.g., "has_symptom", "located_at", "has_metric"
    obj_text      = Column(Text)     # e.g., "Overheating" or "PAD-A" or "engine_oil_temp_c"
    obj_type      = Column(String)   # e.g., "symptom" | "pad" | "value" | "metric"
    # Optional helpful fields
    pad_id        = Column(String)   # if Gemini detects it (e.g., "PAD-A")
    component_id  = Column(String)   # if Gemini detects it (e.g., "ENG-12")
    metric        = Column(String)   # e.g., "engine_oil_temp_c"
    value         = Column(Numeric)  # if the email states a numeric value
    unit          = Column(String)   # "°C","psi","mm/s","%","bool"
    severity      = Column(String)   # if LLM infers 'LOW/MED/HIGH' text-wise
    confidence    = Column(Numeric)  # 0..1 from LLM scoring (optional)
    attrs         = Column(JSONB)    # any extra JSON (spans, notes)
    extracted_at  = Column(TIMESTAMP(timezone=True))  # set in code (now)

# 📏 One simple thresholds table
class Threshold(Base):
    __tablename__ = "thresholds"
    id               = Column(Integer, primary_key=True, autoincrement=True)
    metric           = Column(String)    # e.g., "engine_oil_temp_c"
    applies_type     = Column(String)    # optional: "engine"/"transmission"/...
    applies_component= Column(String)    # optional: exact component override (e.g., "ENG-12")
    unit             = Column(String)    # "°C","psi","mm/s","%","bool"
    warn_low         = Column(Numeric)   # nullable
    warn_high        = Column(Numeric)   # nullable
    alarm_low        = Column(Numeric)   # nullable
    alarm_high       = Column(Numeric)   # nullable
    active           = Column(Boolean, default=True)


