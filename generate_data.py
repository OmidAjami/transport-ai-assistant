import pandas as pd
import numpy as np
import sqlite3
import random
from datetime import datetime, timedelta

np.random.seed(42)
random.seed(42)

START_DATE = datetime(2024, 1, 1)
END_DATE   = datetime(2024, 12, 31)
NUM_SHIPMENTS = 1200

carriers = [
    {"carrier_id": "C001", "name": "Atlas Freight",     "type": "Full Truckload", "region": "National"},
    {"carrier_id": "C002", "name": "Maple Express",     "type": "LTL",            "region": "Eastern"},
    {"carrier_id": "C003", "name": "Northern Logistics","type": "Full Truckload", "region": "National"},
    {"carrier_id": "C004", "name": "Swift Carriers",    "type": "LTL",            "region": "Western"},
    {"carrier_id": "C005", "name": "Coastal Transport", "type": "Intermodal",     "region": "Atlantic"},
]

routes = [
    {"route_id": "R001", "origin": "Toronto, ON",   "destination": "Montreal, QC",      "distance_km": 541,  "region": "Eastern"},
    {"route_id": "R002", "origin": "Vancouver, BC", "destination": "Calgary, AB",        "distance_km": 970,  "region": "Western"},
    {"route_id": "R003", "origin": "Montreal, QC",  "destination": "Halifax, NS",        "distance_km": 1139, "region": "Atlantic"},
    {"route_id": "R004", "origin": "Toronto, ON",   "destination": "Winnipeg, MB",       "distance_km": 2093, "region": "Central"},
    {"route_id": "R005", "origin": "Calgary, AB",   "destination": "Edmonton, AB",       "distance_km": 300,  "region": "Western"},
    {"route_id": "R006", "origin": "Halifax, NS",   "destination": "Charlottetown, PEI", "distance_km": 277,  "region": "Atlantic"},
    {"route_id": "R007", "origin": "Ottawa, ON",    "destination": "Toronto, ON",        "distance_km": 448,  "region": "Eastern"},
    {"route_id": "R008", "origin": "Winnipeg, MB",  "destination": "Regina, SK",         "distance_km": 573,  "region": "Central"},
]

product_categories = ["Grocery", "Electronics", "Apparel", "Home & Garden", "Pharmacy", "Frozen Foods"]

carrier_profiles = {
    "C001": {"otd_base": 0.92, "cost_base": 2.10, "delay_hours_mean": 3},
    "C002": {"otd_base": 0.85, "cost_base": 1.75, "delay_hours_mean": 6},
    "C003": {"otd_base": 0.95, "cost_base": 2.40, "delay_hours_mean": 2},
    "C004": {"otd_base": 0.88, "cost_base": 1.90, "delay_hours_mean": 5},
    "C005": {"otd_base": 0.78, "cost_base": 1.60, "delay_hours_mean": 9},
}

def random_date(start, end):
    return start + timedelta(days=random.randint(0, (end - start).days))

shipments = []
for i in range(1, NUM_SHIPMENTS + 1):
    carrier  = random.choice(carriers)
    route    = random.choice(routes)
    profile  = carrier_profiles[carrier["carrier_id"]]
    ship_date = random_date(START_DATE, END_DATE)

    transit_days   = max(1, int(route["distance_km"] / 600))
    sched_delivery = ship_date + timedelta(days=transit_days)

    anomaly_period = datetime(2024, 3, 4) <= ship_date <= datetime(2024, 3, 17)
    is_anomaly     = anomaly_period and carrier["carrier_id"] == "C005" and route["region"] == "Atlantic"

    otd_rate  = 0.45 if is_anomaly else profile["otd_base"]
    on_time   = np.random.rand() < otd_rate

    delay_hours = 0
    if not on_time:
        delay_multiplier = 3.5 if is_anomaly else 1.0
        delay_hours = max(1, int(np.random.exponential(profile["delay_hours_mean"] * delay_multiplier)))

    actual_delivery = sched_delivery + timedelta(hours=delay_hours)

    base_cost   = route["distance_km"] * profile["cost_base"]
    weight_kg   = random.randint(100, 5000)
    cost_noise  = np.random.normal(1.0, 0.08)
    total_cost  = round(base_cost * cost_noise * (1 + weight_kg / 20000), 2)
    cost_per_km = round(total_cost / route["distance_km"], 4)
    dwell_hours = round(max(0.5, np.random.exponential(4) + (8 if is_anomaly else 0)), 1)

    shipments.append({
        "shipment_id":        f"SHP{i:04d}",
        "carrier_id":         carrier["carrier_id"],
        "route_id":           route["route_id"],
        "product_category":   random.choice(product_categories),
        "ship_date":          ship_date.strftime("%Y-%m-%d"),
        "ship_month":         ship_date.strftime("%Y-%m"),
        "scheduled_delivery": sched_delivery.strftime("%Y-%m-%d"),
        "actual_delivery":    actual_delivery.strftime("%Y-%m-%d"),
        "on_time":            int(on_time),
        "delay_hours":        delay_hours,
        "weight_kg":          weight_kg,
        "total_cost_cad":     total_cost,
        "cost_per_km":        cost_per_km,
        "dwell_hours":        dwell_hours,
        "is_anomaly_period":  int(is_anomaly),
        "status":             "Delivered",
    })

df_shipments = pd.DataFrame(shipments)

scorecards = []
for (carrier_id, month), grp in df_shipments.groupby(["carrier_id", "ship_month"]):
    scorecards.append({
        "carrier_id":      carrier_id,
        "month":           month,
        "total_shipments": len(grp),
        "otd_rate":        round(grp["on_time"].mean(), 4),
        "avg_delay_hours": round(grp["delay_hours"].mean(), 2),
        "avg_cost_per_km": round(grp["cost_per_km"].mean(), 4),
        "avg_dwell_hours": round(grp["dwell_hours"].mean(), 2),
        "total_cost_cad":  round(grp["total_cost_cad"].sum(), 2),
    })

db_path = "transportation.db"
conn = sqlite3.connect(db_path)
pd.DataFrame(carriers).to_sql("carriers",             conn, if_exists="replace", index=False)
pd.DataFrame(routes).to_sql("routes",                 conn, if_exists="replace", index=False)
df_shipments.to_sql("shipments",                      conn, if_exists="replace", index=False)
pd.DataFrame(scorecards).to_sql("carrier_scorecards", conn, if_exists="replace", index=False)
conn.close()

print("✓ Database created:", db_path)
print(f"  {len(shipments)} shipments | {len(carriers)} carriers | {len(routes)} routes | {len(scorecards)} scorecard rows")

conn = sqlite3.connect(db_path)
print("\nOTD by carrier:")
print(pd.read_sql("""
    SELECT c.name, ROUND(AVG(s.on_time)*100,1) as otd_pct, COUNT(*) as shipments
    FROM shipments s JOIN carriers c ON s.carrier_id = c.carrier_id
    GROUP BY c.name ORDER BY otd_pct DESC
""", conn).to_string(index=False))
conn.close()
