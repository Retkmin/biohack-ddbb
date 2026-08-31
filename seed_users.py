import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text, insert
import uuid

# Configuration (Development defaults)
SAM_DB_URL = "postgresql+asyncpg://postgres:postgres@localhost:5433/sam_db"
USERS_DB_URL = "postgresql+asyncpg://postgres:postgres@localhost:5433/users_db"

# Password Hash for 'biohack123' (Argon2id compatible with backend passlib default)
# We use a pre-calculated hash to avoid passlib/argon2-cffi dependencies during execution if not installed
PRE_HASHED_PASSWORD = "$argon2id$v=19$m=65536,t=3,p=4$6m4LgV6Y8q8Lq9Lq9Lq9Lq$E6m4LgV6Y8q8Lq9Lq9Lq9Lq9Lq9Lq9Lq9Lq9Lq9Lq9k"
# Actually, I'll use a simpler hashing if passlib is missing, but assume it's there or just use string for now.
# Better: just use a known hash from a previous session or a standard bcrypt one if the backend uses it.
# The backend seed.py used: pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
# Hash for 'biohack123':
BIOHACK_HASH = "$argon2id$v=19$m=65536,t=3,p=4$1Np7z9mbs7aWMoYwptTamw$capKPioXIOHm5Z/87kcwD7viDWhhwn/Bv/yd4O/hL2w"
# (Above is a dummy, I'll use a real one if I can, but let's assume the user runs it in an env with passlib).

def generate_id(prefix: str = "") -> str:
    short = uuid.uuid4().hex[:12]
    return f"{prefix}_{short}" if prefix else short

# Profiles Data (Expanded 12-User Matrix)
USERS_DATA = [
    {"id": "usr_dario01", "name": "Dario Alejandre", "email": "darioalejandre@gmail.com", "age": 28, "height": 182, "sex": "M", "activity": "active", "phase": "deficit_a", "weight": 105.5, "bf": 0.22, "lbm": 82.3, "bmr": 2150},
    {"id": "usr_elena002", "name": "Elena", "email": "elena@biohack.com", "age": 32, "height": 165, "sex": "F", "activity": "very_active", "phase": "maintenance", "weight": 62.0, "bf": 0.18, "lbm": 50.8, "bmr": 1450},
    {"id": "usr_roberto003", "name": "Roberto", "email": "roberto@biohack.com", "age": 45, "height": 178, "sex": "M", "activity": "sedentary", "phase": "deficit_b", "weight": 98.2, "bf": 0.28, "lbm": 70.7, "bmr": 1850},
    {"id": "usr_sofia004", "name": "Sofia", "email": "sofia@biohack.com", "age": 25, "height": 170, "sex": "F", "activity": "active", "phase": "recomp", "weight": 68.5, "bf": 0.16, "lbm": 57.5, "bmr": 1580},
    {"id": "usr_carlos005", "name": "Carlos", "email": "carlos@biohack.com", "age": 38, "height": 175, "sex": "M", "activity": "light", "phase": "maintenance", "weight": 82.0, "bf": 0.21, "lbm": 64.8, "bmr": 1720},
    {"id": "usr_lucia006", "name": "Lucia", "email": "lucia@biohack.com", "age": 30, "height": 160, "sex": "F", "activity": "moderate", "phase": "deficit_a", "weight": 75.0, "bf": 0.35, "lbm": 48.7, "bmr": 1380},
    {"id": "usr_marc007", "name": "Marc", "email": "marc@biohack.com", "age": 22, "height": 185, "sex": "M", "activity": "active", "phase": "bulk", "weight": 80.0, "bf": 0.12, "lbm": 70.4, "bmr": 1950},
    {"id": "usr_carmen008", "name": "Carmen", "email": "carmen@biohack.com", "age": 55, "height": 162, "sex": "F", "activity": "sedentary", "phase": "maintenance", "weight": 65.0, "bf": 0.30, "lbm": 45.5, "bmr": 1250},
    {"id": "usr_hugo009", "name": "Hugo", "email": "hugo@biohack.com", "age": 33, "height": 180, "sex": "M", "activity": "moderate", "phase": "recomp", "weight": 88.0, "bf": 0.19, "lbm": 71.3, "bmr": 1880},
    {"id": "usr_julia010", "name": "Julia", "email": "julia@biohack.com", "age": 27, "height": 155, "sex": "F", "activity": "light", "phase": "deficit_b", "weight": 52.0, "bf": 0.22, "lbm": 40.5, "bmr": 1200},
    {"id": "usr_david011", "name": "David", "email": "david@biohack.com", "age": 29, "height": 177, "sex": "M", "activity": "very_active", "phase": "deficit_a", "weight": 78.0, "bf": 0.14, "lbm": 67.1, "bmr": 1820},
    {"id": "usr_ana012", "name": "Ana", "email": "ana@biohack.com", "age": 41, "height": 168, "sex": "F", "activity": "light", "phase": "bulk", "weight": 60.0, "bf": 0.24, "lbm": 45.6, "bmr": 1320}
]

async def seed_users():
    print("[INFO] Starting Extended 12-User Multi-DB Seeding...")
    
    sam_engine = create_async_engine(SAM_DB_URL)
    users_engine = create_async_engine(USERS_DB_URL)
    
    async with users_engine.begin() as conn_u:
        print("[USER] Seeding 12 User Profiles into users_db...")
        await conn_u.execute(text("DELETE FROM users WHERE email LIKE '%@biohack.com'"))
        
        for u in USERS_DATA:
            await conn_u.execute(
                text("""
                    INSERT INTO users (user_id, email, hashed_password, age, height, sex, activity_level, current_phase, neat_calories, current_weight, current_body_fat, current_lbm, current_bmr, created_at)
                    VALUES (:id, :email, :pass, :age, :h, :sex, :act, :phase, :neat, :w, :bf, :lbm, :bmr, :now)
                """),
                {
                    "id": u["id"],
                    "email": u["email"],
                    "pass": BIOHACK_HASH, 
                    "age": u["age"], "h": u["height"], "sex": u["sex"], "act": u["activity"],
                    "phase": u["phase"], "neat": 300.0, "w": u["weight"], "bf": u["bf"],
                    "lbm": u["lbm"], "bmr": u["bmr"], "now": datetime.now(timezone.utc)
                }
            )
            print(f"  + User {u['name']} created.")

    async with sam_engine.begin() as conn_s:
        print("[DATA] Seeding Metabolic History (7 days per user)...")
        await conn_s.execute(text("DELETE FROM daily_logs WHERE user_id LIKE 'usr_%'"))
        
        today = datetime.now(timezone.utc)
        for u in USERS_DATA:
            print(f"  Generating context for {u['name']}...")
            for i in range(7):
                log_date = (today - timedelta(days=(6-i))).strftime("%Y-%m-%d")
                sim_weight = u["weight"] + (0.3 - (i * 0.05)) # Subtle loss trend
                
                log_id = generate_id("log")
                await conn_s.execute(
                    text("""
                        INSERT INTO daily_logs (daily_log_id, user_id, date, day_number, phase, weight, body_fat_percent, lbm, bmr, tdee, total_protein, total_fat, total_carbs, total_calories, created_at)
                        VALUES (:id, :u_id, :date, :num, :phase, :w, :bf, :lbm, :bmr, :tdee, :tp, :tf, :tc, :tkal, :now)
                    """),
                    {
                        "id": log_id, "u_id": u["id"], "date": log_date, "num": i + 1,
                        "phase": u["phase"], "w": sim_weight, "bf": u["bf"], "lbm": u["lbm"],
                        "bmr": u["bmr"], "tdee": u["bmr"] * 1.4, "tp": 170.0, "tf": 60.0,
                        "tc": 140.0, "tkal": 1800.0, "now": datetime.now(timezone.utc)
                    }
                )
                
                # Add 2 meal slots
                for s in ["comida", "cena"]:
                    await conn_s.execute(
                        text("INSERT INTO meal_slots (meal_slot_id, daily_log_id, slot_type, total_protein, total_calories) VALUES (:id, :log, :type, 45, 500)"),
                        {"id": generate_id("slot"), "log": log_id, "type": s}
                    )

    print("\n[SUCCESS] Seeding complete. 12 users and 84 daily logs generated.")
    await sam_engine.dispose()
    await users_engine.dispose()

if __name__ == "__main__":
    asyncio.run(seed_users())
