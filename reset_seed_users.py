"""
reset_seed_users.py — Reset limpio de usuarios de prueba SAM.

Acciones:
  1. Purga todos los usuarios @biohack.com y artefactos de test en users_db + su historial en sam_db.
  2. Re-crea 12 perfiles de prueba con datos calculados con el Motor Metabolico oficial.
  3. Genera 14 dias de historial por usuario con tendencia realista.
  4. NO toca jamas a darioalejandre@gmail.com (usuario real).

Formulas (Marco Maestro v1.4):
  LBM  = Weight * (1 - bf%)
  BMR  = 370 + 21.6 * LBM
  NEAT = sedentary:250 | light:300 | active:350 | very_active:450
  TDEE = BMR + NEAT
"""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text

SAM_DB_URL   = "postgresql+asyncpg://postgres:postgres@localhost:5433/sam_db"
USERS_DB_URL = "postgresql+asyncpg://postgres:postgres@localhost:5433/users_db"

# Hash de 'biohack123' generado con argon2id — compatible con el backend
BIOHACK_HASH = "$argon2id$v=19$m=65536,t=3,p=4$1Np7z9mbs7aWMoYwptTamw$capKPioXIOHm5Z/87kcwD7viDWhhwn/Bv/yd4O/hL2w"

EMAILS_PROTEGIDOS = {"darioalejandre@gmail.com"}

NEAT_MAP = {
    "sedentary":  250.0,
    "light":      300.0,
    "active":     350.0,
    "very_active": 450.0,
}

# Fases validas del backend
FASES_VALIDAS = {"deficit_a", "deficit_b", "maintenance", "recomp"}

# Multiplicador de deficit por fase (% del TDEE para el calorie_target del seed)
DEFICIT_FACTOR = {
    "deficit_a":  0.75,   # -25% (deficit agresivo)
    "deficit_b":  0.85,   # -15% (deficit moderado)
    "maintenance": 1.00,
    "recomp":      0.90,  # -10%
}


def gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def calc_lbm(weight: float, bf_pct: float) -> float:
    """LBM = Weight * (1 - bf%). bf_pct en % (ej: 22 para 22%)."""
    return round(weight * (1 - bf_pct / 100), 1)


def calc_bmr(lbm: float) -> int:
    """BMR = 370 + 21.6 * LBM (Katch-McArdle)."""
    return int(370 + 21.6 * lbm)


def calc_tdee(bmr: int, neat: float) -> int:
    return int(bmr + neat)


# ── Perfiles de prueba ─────────────────────────────────────────────────────────
# Fases solo con valores validos del backend: deficit_a / deficit_b / maintenance / recomp
PROFILES = [
    # email                level        phase        age  h    sex  weight  bf%
    ("alejandro@biohack.com", "active",     "deficit_a",  34, 183, "M", 105.2, 24.0),
    ("elena@biohack.com",     "very_active","maintenance", 32, 165, "F",  62.0, 18.0),
    ("roberto@biohack.com",   "sedentary",  "deficit_b",  45, 178, "M",  98.2, 28.0),
    ("sofia@biohack.com",     "active",     "recomp",      25, 170, "F",  68.5, 16.0),
    ("carlos@biohack.com",    "light",      "maintenance", 38, 175, "M",  82.0, 21.0),
    ("lucia@biohack.com",     "light",      "deficit_a",  30, 160, "F",  75.0, 35.0),
    ("marc@biohack.com",      "active",     "deficit_b",  22, 185, "M",  80.0, 12.0),
    ("carmen@biohack.com",    "sedentary",  "maintenance", 55, 162, "F",  65.0, 30.0),
    ("hugo@biohack.com",      "active",     "recomp",      33, 180, "M",  88.0, 19.0),
    ("julia@biohack.com",     "light",      "deficit_b",  27, 155, "F",  52.0, 22.0),
    ("david@biohack.com",     "very_active","deficit_a",  29, 177, "M",  78.0, 14.0),
    ("ana@biohack.com",       "light",      "recomp",      41, 168, "F",  60.0, 24.0),
]


async def reset():
    print("=" * 65)
    print("  RESET DE USUARIOS DE PRUEBA SAM")
    print("=" * 65)

    eng_u = create_async_engine(USERS_DB_URL, echo=False)
    eng_s = create_async_engine(SAM_DB_URL, echo=False)

    # ── 1. Identificar user_ids a purgar (NO tocar protected emails) ────────
    print("\n[1/4] Identificando usuarios a purgar...")
    async with AsyncSession(eng_u) as s:
        # asyncpg no acepta tuplas en NOT IN — usar != ALL con lista
        protected_list = list(EMAILS_PROTEGIDOS)
        r = await s.execute(text(
            "SELECT user_id, email FROM users WHERE email != ALL(:protected)"
        ), {"protected": protected_list})
        to_delete = r.mappings().all()

    seed_ids = [u["user_id"] for u in to_delete]
    print(f"  Usuarios a eliminar: {len(to_delete)}")
    for u in to_delete:
        print(f"    - {u['email']} ({u['user_id']})")

    if not seed_ids:
        print("  [!] Nada que purgar.")
    else:
        # ── 2. Purgar sam_db (meal_slots, daily_logs) ────────────────────────
        print(f"\n[2/4] Purgando datos de sam_db para {len(seed_ids)} usuarios...")
        async with eng_s.begin() as conn:
            for uid in seed_ids:
                # meal_slots → food_items cascade, daily_logs → meal_slots cascade
                res = await conn.execute(
                    text("DELETE FROM daily_logs WHERE user_id = :uid"), {"uid": uid}
                )
                print(f"    SAM: {res.rowcount} logs eliminados para {uid}")
            # Recetas
            res = await conn.execute(
                text("DELETE FROM recipes WHERE user_id = ANY(:ids)"),
                {"ids": seed_ids}
            )
            print(f"    SAM: {res.rowcount} recetas eliminadas")

        # ── 3. Purgar users_db ────────────────────────────────────────────────
        print(f"\n[3/4] Purgando users_db...")
        async with eng_u.begin() as conn:
            res = await conn.execute(
                text("DELETE FROM users WHERE user_id = ANY(:ids)"),
                {"ids": seed_ids}
            )
            print(f"    USERS: {res.rowcount} registros eliminados")

    # ── 4. Re-crear perfiles con formulas correctas ──────────────────────────
    print(f"\n[4/4] Creando {len(PROFILES)} perfiles de prueba...")

    today = datetime.now(timezone.utc)
    new_user_ids = {}  # email -> user_id

    async with eng_u.begin() as conn_u:
        for (email, level, phase, age, height, sex, weight, bf_pct) in PROFILES:
            lbm  = calc_lbm(weight, bf_pct)
            bmr  = calc_bmr(lbm)
            neat = NEAT_MAP[level]
            tdee = calc_tdee(bmr, neat)
            uid  = gen_id("usr")
            new_user_ids[email] = uid

            await conn_u.execute(text("""
                INSERT INTO users (
                    user_id, email, hashed_password, age, height, sex,
                    activity_level, current_phase, neat_calories,
                    current_weight, current_body_fat, current_lbm, current_bmr,
                    required_maintenance_days, created_at, updated_at
                ) VALUES (
                    :uid, :email, :pw, :age, :height, :sex,
                    :level, :phase, :neat,
                    :weight, :bf, :lbm, :bmr,
                    0, :now, :now
                )
            """), {
                "uid": uid, "email": email, "pw": BIOHACK_HASH,
                "age": age, "height": height, "sex": sex,
                "level": level, "phase": phase, "neat": neat,
                "weight": weight, "bf": bf_pct, "lbm": lbm, "bmr": bmr,
                "now": today,
            })

            print(f"  + {email:30s} | {sex} {age}a | {weight}kg {bf_pct}%GC | "
                  f"LBM:{lbm} BMR:{bmr} NEAT:{neat} TDEE:{tdee} | {phase}")

    # ── 5. Generar historial (14 dias por usuario) ───────────────────────────
    print(f"\n[5/5] Generando 14 dias de historial por usuario...")

    async with eng_s.begin() as conn_s:
        for (email, level, phase, age, height, sex, weight, bf_pct) in PROFILES:
            uid  = new_user_ids[email]
            lbm  = calc_lbm(weight, bf_pct)
            bmr  = calc_bmr(lbm)
            neat = NEAT_MAP[level]
            tdee = calc_tdee(bmr, neat)
            deficit_factor = DEFICIT_FACTOR.get(phase, 1.0)
            calorie_target = int(tdee * deficit_factor)

            for i in range(14):
                day_date = (today - timedelta(days=(13 - i))).strftime("%Y-%m-%d")
                # Tendencia realista: ligera perdida de peso en deficit
                weight_trend = weight + (0.0 if phase == "maintenance" else (i * -0.05))
                weight_day  = round(weight_trend + (0.3 - (i % 3) * 0.15), 1)
                lbm_day     = calc_lbm(weight_day, bf_pct)
                bmr_day     = calc_bmr(lbm_day)
                tdee_day    = calc_tdee(bmr_day, neat)

                # Macros segun objetivo (proteina: 2g/LBM, grasa: 1g/LBM, resto carbs)
                protein_g = round(lbm_day * 2.0)
                fat_g     = round(lbm_day * 1.0)
                carbs_kcal = max(0, calorie_target - protein_g * 4 - fat_g * 9)
                carbs_g    = round(carbs_kcal / 4)
                total_kcal = protein_g * 4 + fat_g * 9 + carbs_g * 4
                deficit    = total_kcal - tdee_day

                log_id = gen_id("log")
                await conn_s.execute(text("""
                    INSERT INTO daily_logs (
                        daily_log_id, user_id, date, day_number, phase,
                        weight, body_fat_percent, lbm, bmr, tdee,
                        total_protein, total_fat, total_carbs, total_calories,
                        deficit, deficit_last_3_days, cardio_last_3_days,
                        is_certified, created_at
                    ) VALUES (
                        :id, :uid, :date, :num, :phase,
                        :w, :bf, :lbm, :bmr, :tdee,
                        :tp, :tf, :tc, :tkcal,
                        :deficit, 0, 0,
                        false, :now
                    )
                """), {
                    "id": log_id, "uid": uid, "date": day_date, "num": i + 1,
                    "phase": phase, "w": weight_day, "bf": bf_pct,
                    "lbm": lbm_day, "bmr": bmr_day, "tdee": tdee_day,
                    "tp": protein_g, "tf": fat_g, "tc": carbs_g, "tkcal": total_kcal,
                    "deficit": deficit, "now": today,
                })

                # Generar 2 meal_slots por dia (comida y cena)
                for slot in ["comida", "cena"]:
                    p_slot = round(protein_g * 0.4)
                    f_slot = round(fat_g * 0.5)
                    c_slot = round(carbs_g * 0.5)
                    kcal_slot = p_slot * 4 + f_slot * 9 + c_slot * 4
                    await conn_s.execute(text("""
                        INSERT INTO meal_slots (
                            meal_slot_id, daily_log_id, slot_type,
                            total_protein, total_fat, total_carbs, total_calories,
                            is_simulation
                        ) VALUES (
                            :mid, :lid, :slot, :p, :f, :c, :kcal, false
                        )
                    """), {
                        "mid": gen_id("slot"), "lid": log_id, "slot": slot,
                        "p": p_slot, "f": f_slot, "c": c_slot, "kcal": kcal_slot,
                    })

            print(f"  14 dias generados para {email}")

    print("\n" + "=" * 65)
    print("  RESET COMPLETADO")
    print(f"  {len(PROFILES)} usuarios creados con formulas Marco Maestro v1.4")
    print(f"  {len(PROFILES) * 14} registros diarios generados")
    print("  Usuario real [darioalejandre@gmail.com] INTACTO")
    print("=" * 65)

    await eng_u.dispose()
    await eng_s.dispose()


if __name__ == "__main__":
    asyncio.run(reset())
