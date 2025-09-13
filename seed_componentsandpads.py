# seed_ref.py
from db import SessionLocal
from tables import Pad, Component

pads = [
    {"pad_id": "PAD-A", "name": "North Pad A"},
    {"pad_id": "PAD-B", "name": "West Pad B"},
    {"pad_id": "PAD-C", "name": "South Pad C"},
]

components = [
    {"component_id": "ENG-12", "pad_id": "PAD-A", "type": "engine"},
    {"component_id": "TRANS-12", "pad_id": "PAD-A", "type": "transmission"},
    {"component_id": "FLUEND-12", "pad_id": "PAD-A", "type": "fluid_end"},
    {"component_id": "ENG-27", "pad_id": "PAD-B", "type": "engine"},
    {"component_id": "ENG-34", "pad_id": "PAD-C", "type": "engine"},
]

def main():
    db = SessionLocal()
    try:
        # insert pads first
        for p in pads:
            if not db.get(Pad, p["pad_id"]):
                db.add(Pad(**p))
        db.commit()  # ✅ commit pads so they exist in DB

        # then insert components
        for c in components:
            if not db.get(Component, c["component_id"]):
                db.add(Component(**c))
        db.commit()
        print("Pads and components seeded.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
