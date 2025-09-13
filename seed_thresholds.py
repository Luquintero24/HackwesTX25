# seed_thresholds.py
from db import SessionLocal
from tables import Threshold

thresholds = [
    # Engine
    {"metric": "engine_oil_temp_c", "applies_type": "engine", "unit": "°C", "warn_high": 110, "alarm_high": 120},
    {"metric": "engine_water_temp_c", "applies_type": "engine", "unit": "°C", "warn_high": 95, "alarm_high": 105},
    {"metric": "engine_oil_pressure_psi", "applies_type": "engine", "unit": "psi", "warn_low": 30, "alarm_low": 25, "warn_high": 90, "alarm_high": 100},
    {"metric": "engine_load_pct", "applies_type": "engine", "unit": "%", "warn_high": 90, "alarm_high": 100},

    # Transmission
    {"metric": "trans_oil_temp_c", "applies_type": "transmission", "unit": "°C", "warn_high": 110, "alarm_high": 120},
    {"metric": "trans_oil_pressure_psi", "applies_type": "transmission", "unit": "psi", "warn_low": 80, "alarm_low": 60, "warn_high": 250, "alarm_high": 300},

    # Power end
    {"metric": "power_end_oil_temp_c", "applies_type": "power_end", "unit": "°C", "warn_high": 110, "alarm_high": 120},
    {"metric": "power_end_oil_pressure_psi", "applies_type": "power_end", "unit": "psi", "warn_low": 30, "alarm_low": 25, "warn_high": 90, "alarm_high": 100},

    # Fluid end
    {"metric": "fluid_end_vibration_mms", "applies_type": "fluid_end", "unit": "mm/s", "warn_high": 5.0, "alarm_high": 7.5},
]

def main():
    db = SessionLocal()
    try:
        for t in thresholds:
            db.add(Threshold(**t))
        db.commit()
        print("Thresholds seeded.")
    finally:
        db.close()

if __name__ == "__main__":
    main()
