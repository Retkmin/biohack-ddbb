import asyncio
import pandas as pd
import uuid
import random
import json
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# Configuration
SAM_DB_URL = "postgresql+asyncpg://postgres:postgres@localhost:5433/sam_db"
EXCEL_PATH = r"D:\Trabajo\app-biohack\repos\biohack-ddbb\docs\Seguimiento Dieta Phase A.xlsx"

def generate_id(prefix: str = "") -> str:
    short = uuid.uuid4().hex[:12]
    return f"{prefix}_{short}" if prefix else short

# 12 Users Base Data (Synchronized with seed_users.py)
USERS = [
    {"id": "usr_dario01", "name": "Dario", "is_real": True},
    {"id": "usr_elena002", "name": "Elena", "is_real": False},
    {"id": "usr_roberto003", "name": "Roberto", "is_real": False},
    {"id": "usr_sofia004", "name": "Sofia", "is_real": False},
    {"id": "usr_carlos005", "name": "Carlos", "is_real": False},
    {"id": "usr_lucia006", "name": "Lucia", "is_real": False},
    {"id": "usr_marc007", "name": "Marc", "is_real": False},
    {"id": "usr_carmen008", "name": "Carmen", "is_real": False},
    {"id": "usr_hugo009", "name": "Hugo", "is_real": False},
    {"id": "usr_julia010", "name": "Julia", "is_real": False},
    {"id": "usr_david011", "name": "David", "is_real": False},
    {"id": "usr_ana012", "name": "Ana", "is_real": False}
]

async def seed_high_fidelity():
    print("[INFO] Starting High-Fidelity Metabolic Seeding...")
    engine = create_async_engine(SAM_DB_URL)
    
    # 0. Cleanup
    async with engine.begin() as conn:
        print("  Cleaning up old logs, sessions and recipes...")
        await conn.execute(text("TRUNCATE daily_logs, meal_slots, food_items, workout_sessions, workout_exercises, workout_sets, recipes, recipe_ingredients CASCADE"))

    # 1. Parse Real Data for Alejandro
    print("  Parsing Alejandro's Excel data...")
    df = pd.read_excel(EXCEL_PATH, header=2)
    # Filter rows with valid dates
    df = df[df['Fecha'].notna()]
    
    async with engine.begin() as conn:
        # A. Recipes Injection (Static Metabolic Recipes)
        print("  Injecting Recipe Book...")
        RECIPES = [
            ("Porridge de Proteína", "desayuno", 45, 10, 50, 480, ["post-workout", "bulking"]),
            ("Pollo Teriyaki Biohack", "comida", 35, 12, 40, 420, ["high-protein", "clinical"]),
            ("Revuelto de Claras y Jamón", "cena", 40, 8, 5, 280, ["low-carb", "cutting"]),
            ("Salmón con Espárragos", "cena", 38, 22, 10, 390, ["omega-3", "clean"]),
            ("Ensalada de Quinoa y Atún", "comida", 30, 9, 45, 380, ["moderate", "fiber"])
        ]
        
        for r_name, r_cat, r_p, r_f, r_c, r_cal, r_tags in RECIPES:
            rec_id = generate_id("rec")
            await conn.execute(
                text("INSERT INTO recipes (recipe_id, user_id, name, category, total_protein, total_fat, total_carbs, total_calories, tags) VALUES (:id, 'usr_dario01', :name, :cat, :p, :f, :c, :cal, :tags)"),
                {"id": rec_id, "name": r_name, "cat": r_cat, "p": r_p, "f": r_f, "c": r_c, "cal": r_cal, "tags": json.dumps(r_tags)}
            )

        # B. Users Loop
        for user in USERS:
            user_id = user["id"]
            print(f"  Generating 30-day history for {user['name']}...")
            
            # Use a separate transaction per user to find the needle
            async with engine.begin() as conn_user:
                if user["is_real"]:
                    for _, row in df.iterrows():
                        try:
                            def get_val(keywords):
                                for k in keywords:
                                    for col in df.columns:
                                        if k.lower() in col.lower():
                                            v = row[col]
                                            return v if pd.notna(v) else None
                                return None

                            day_num = get_val(['D', 'a', 'Day'])
                            log_date = row['Fecha'].strftime("%Y-%m-%d") if isinstance(row['Fecha'], datetime) else str(row['Fecha'])
                            weight = get_val(['Peso'])
                            prot = get_val(['Prote', 'Prot'])
                            fat = get_val(['Grasa', 'Fat'])
                            carb = get_val(['Hidrat', 'HC', 'Carb'])
                            kcal = get_val(['Calor', 'Kcal'])
                            defic = get_val(['ficit', 'Deficit'])
                            phase = get_val(['Estado', 'Phase']) or 'deficit_a'
                            
                            if weight is None: continue

                            log_id = generate_id("log")
                            await conn_user.execute(
                                text("""
                                    INSERT INTO daily_logs (daily_log_id, user_id, date, day_number, phase, weight, body_fat_percent, lbm, bmr, tdee, total_protein, total_fat, total_carbs, total_calories, deficit, exercise_type, rucking_minutes)
                                    VALUES (:id, :u_id, :date, :num, :phase, :w, 22.0, 80.0, 2100.0, 2600.0, :tp, :tf, :tc, :cal, :def, 'Cardio/Weight', :ruck)
                                """),
                                {
                                    "id": log_id, "u_id": user_id, "date": log_date, "num": int(day_num) if day_num else 0, 
                                    "phase": str(phase), "w": float(weight), 
                                    "tp": float(prot) if prot is not None else 0.0, 
                                    "tf": float(fat) if fat is not None else 0.0, 
                                    "tc": float(carb) if carb is not None else 0.0,
                                    "cal": float(kcal) if kcal is not None else 0.0, 
                                    "def": float(defic) if defic is not None else 0.0, 
                                    "ruck": float(row.get('Cardio (min)', 0)) if pd.notna(row.get('Cardio (min)')) else 0.0
                                }
                            )
                        except Exception as e:
                            print(f"    [WARN] Skipped Alejandro: {e}")
                else:
                    base_weight = 70 + random.random() * 30
                    start_date = datetime.now(timezone.utc) - timedelta(days=30)
                    for i in range(30):
                        curr_date = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
                        if user["name"] in ["Elena", "Sofia"]: protein = 160 + random.randint(-10, 10)
                        elif user["name"] in ["Roberto", "Lucia"]: protein = 110
                        else: protein = 140
                             
                        weight = base_weight - (i * 0.05) + (random.random() * 0.4 - 0.2)
                        log_id = generate_id("log")
                        await conn_user.execute(
                            text("""
                                INSERT INTO daily_logs (daily_log_id, user_id, date, day_number, phase, weight, body_fat_percent, lbm, bmr, tdee, total_protein, total_fat, total_carbs, total_calories, deficit)
                                VALUES (:id, :u_id, :date, :num, 'deficit_a', :w, 20.0, 60.0, 1800.0, 2400.0, :tp, 60.0, 150.0, 1800.0, 600.0)
                            """),
                            {"id": log_id, "u_id": user_id, "date": curr_date, "num": i + 1, "w": float(weight), "tp": float(protein)}
                        )

    print("\n[SUCCESS] High-Fidelity Seeding complete.")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(seed_high_fidelity())
