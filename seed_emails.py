# seed_emails.py
import random
from datetime import datetime, timedelta, timezone
from db import SessionLocal
from tables import Email, Component, Pad

senders = [
    "pad-a-lead@patterson-uti.com",
    "pad-b-supervisor@patterson-uti.com",
    "pad-c-lead@patterson-uti.com",
    "maintenance@patterson-uti.com",
]
recipients = [
    "ops@patterson-uti.com",
    "safety@patterson-uti.com",
    "engineering@patterson-uti.com",
]

templates = [
    "Engine reported oil pressure {engine_oil_pressure_psi} psi, oil temp {engine_oil_temp_c}°C, water temp {engine_water_temp_c}°C, load {engine_load_pct}%. Condition: exceeded safe operating limits.",
    "Transmission metrics recorded: oil pressure {trans_oil_pressure_psi} psi and oil temp {trans_oil_temp_c}°C. Issue flagged for follow-up inspection.",
    "Fluid end vibration measured at {fluid_end_vibration_mms} mm/s during operation. Monitoring for potential cavitation risk.",
    "Power end showed oil pressure {power_end_oil_pressure_psi} psi and oil temp {power_end_oil_temp_c}°C. Cooling cycle recommended.",
    "Routine report: engine within range. Oil {engine_oil_pressure_psi} psi, temp {engine_oil_temp_c}°C, water {engine_water_temp_c}°C, load {engine_load_pct}%.",
]

def random_metrics(component_type):
    if component_type == "engine":
        return {
            "engine_oil_pressure_psi": random.randint(55, 95),
            "engine_oil_temp_c": random.randint(90, 130),
            "engine_water_temp_c": random.randint(80, 110),
            "engine_load_pct": random.randint(70, 105),
        }
    elif component_type == "transmission":
        return {
            "trans_oil_pressure_psi": random.randint(50, 320),
            "trans_oil_temp_c": random.randint(80, 125),
        }
    elif component_type == "fluid_end":
        return {
            "fluid_end_vibration_mms": round(random.uniform(2.0, 9.0), 1),
        }
    elif component_type == "power_end":
        return {
            "power_end_oil_pressure_psi": random.randint(20, 110),
            "power_end_oil_temp_c": random.randint(85, 125),
        }
    else:
        return {}

def main(n=100):
    db = SessionLocal()
    try:
        components = db.query(Component).all()
        pads = {p.pad_id: p for p in db.query(Pad).all()}
        base_time = datetime(2025, 9, 12, 8, 0, tzinfo=timezone.utc)

        for i in range(1, n+1):
            comp = random.choice(components)
            pad = pads[comp.pad_id]
            metrics = random_metrics(comp.type)

            from_addr = random.choice(senders)
            to_addr = random.choice(recipients)
            subject = f"{pad.pad_id} | {comp.component_id} | Auto-generated event"
            message_id = f"<R{i:03}@patterson-uti.com>"
            sent_at = base_time + timedelta(minutes=15*i)

            # Pick a template that matches component type
            if comp.type == "engine":
                template = random.choice([templates[0], templates[4]])
            elif comp.type == "transmission":
                template = templates[1]
            elif comp.type == "fluid_end":
                template = templates[2]
            elif comp.type == "power_end":
                template = templates[3]
            else:
                template = "General observation report."

            # Fill in metrics into observation
            observation = template.format(**metrics)

            raw_text = f"""From: {from_addr}
To: {to_addr}
Date: {sent_at.strftime("%a, %d %b %Y %H:%M:%S %z")}
Subject: {subject}
Message-ID: {message_id}

OBSERVATION: {observation}
"""

            email = Email(
                message_id=message_id,
                sent_at=sent_at,
                from_addr=from_addr,
                to_addr=to_addr,
                subject=subject,
                pad_id=pad.pad_id,
                component_id=comp.component_id,
                component_type=comp.type,
                raw_text=raw_text,
                headers={},
            )
            db.add(email)

        db.commit()
        print(f"Seeded {n} emails with metrics embedded in observations.")
    finally:
        db.close()

if __name__ == "__main__":
    main(100)
