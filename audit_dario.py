import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text

SAM_DB_URL = "postgresql+asyncpg://postgres:postgres@localhost:5433/sam_db"
USERS_DB_URL = "postgresql+asyncpg://postgres:postgres@localhost:5433/users_db"
USER_ID = "usr_4f2bf9993862"
EMAIL = "darioalejandre@gmail.com"


async def main():
    # --- USERS DB ---
    eng_u = create_async_engine(USERS_DB_URL, echo=False)
    async with AsyncSession(eng_u) as s:
        r = await s.execute(
            text("SELECT * FROM users WHERE user_id = :uid"),
            {"uid": USER_ID}
        )
        user = r.mappings().one_or_none()

    if not user:
        print("Usuario no encontrado")
        return

    w = user["current_weight"] or 0.0
    bf = user["current_body_fat"] or 0.0
    bf_dec = bf / 100 if bf > 1 else bf
    lbm_calc = round(w * (1 - bf_dec), 1)
    bmr_calc = int(370 + 21.6 * lbm_calc)
    neat = user["neat_calories"] or 0
    tdee_calc = int(bmr_calc + neat)
    lbm_db = user["current_lbm"] or 0
    bmr_db = user["current_bmr"] or 0
    lbm_diff = abs(lbm_db - lbm_calc)
    bmr_diff = abs(bmr_db - bmr_calc)

    print("=" * 70)
    print(" HOJA DE DATOS: " + EMAIL)
    print("=" * 70)
    print()
    print("--- IDENTIDAD ---")
    print("user_id     : " + str(user["user_id"]))
    print("email       : " + str(user["email"]))
    print("created_at  : " + str(user["created_at"])[:19])
    print()
    print("--- ANTROPOMETRIA ---")
    print("Edad        : " + str(user["age"]) + " años")
    print("Sexo        : " + str(user["sex"]))
    print("Altura      : " + str(user["height"]) + " cm")
    print("Peso        : " + str(w) + " kg")
    print("% Grasa     : " + str(bf))
    print()
    print("--- METABOLISMO EN DB ---")
    print("LBM (DB)    : " + str(lbm_db) + " kg")
    print("BMR (DB)    : " + str(bmr_db) + " kcal")
    print("NEAT        : " + str(neat) + " kcal")
    print("TDEE Base   : " + str(int((bmr_db or 0) + neat)) + " kcal")
    print("Fase        : " + str(user["current_phase"]))
    print("Actividad   : " + str(user["activity_level"]))
    req_md = user.get("required_maintenance_days", "N/A") if user else "N/A"
    print("Mantenimiento: " + str(req_md) + " dias/semana")
    print()
    print("--- RECALCULO MARCO MAESTRO ---")
    lbm_ok = "OK" if lbm_diff < 0.5 else "DESVIACION: " + str(round(lbm_diff, 2)) + " kg"
    bmr_ok = "OK" if bmr_diff < 10 else "DESVIACION: " + str(int(bmr_diff)) + " kcal"
    print("LBM (calc)  : " + str(lbm_calc) + " kg   => " + lbm_ok)
    print("BMR (calc)  : " + str(bmr_calc) + " kcal => " + bmr_ok)
    print("TDEE (calc) : " + str(tdee_calc) + " kcal")

    # --- SAM DB ---
    eng_s = create_async_engine(SAM_DB_URL, echo=False)
    async with AsyncSession(eng_s) as s:
        lr = await s.execute(
            text("SELECT date, day_number, phase, weight, body_fat_percent, lbm, bmr, tdee, total_calories, total_protein, total_fat, total_carbs, deficit, is_certified FROM daily_logs WHERE user_id = :uid ORDER BY date DESC LIMIT 20"),
            {"uid": USER_ID}
        )
        logs = lr.mappings().all()
        mr = await s.execute(
            text("SELECT COUNT(*) FROM meal_slots ms JOIN daily_logs dl ON ms.daily_log_id = dl.daily_log_id WHERE dl.user_id = :uid"),
            {"uid": USER_ID}
        )
        meal_count = mr.scalar()
        rr = await s.execute(
            text("SELECT COUNT(*) FROM recipes WHERE user_id = :uid"),
            {"uid": USER_ID}
        )
        recipe_count = rr.scalar()
        
        # Check for simulation slots
        sim_r = await s.execute(
            text("SELECT COUNT(*) FROM meal_slots ms JOIN daily_logs dl ON ms.daily_log_id = dl.daily_log_id WHERE dl.user_id = :uid AND ms.is_simulation = true"),
            {"uid": USER_ID}
        )
        sim_count = sim_r.scalar()

    print()
    print("--- HISTORIAL SAM_DB (" + str(len(logs)) + " registros) ---")
    print("FECHA       | Dia | Fase         | Peso   | GC%   | LBM  | BMR  | TDEE | Kcal | Deficit | Cert")
    print("-" * 100)
    for log in logs:
        cert = "[CERT]" if log["is_certified"] else "      "
        row = (
            str(log["date"]) + " | " +
            str(log["day_number"]).rjust(3) + " | " +
            str(log["phase"]).ljust(12) + " | " +
            str(round(log["weight"], 1)).rjust(6) + " | " +
            str(round(log["body_fat_percent"], 1)).rjust(5) + " | " +
            str(round(log["lbm"], 1)).rjust(4) + " | " +
            str(int(log["bmr"] or 0)).rjust(4) + " | " +
            str(int(log["tdee"] or 0)).rjust(4) + " | " +
            str(int(log["total_calories"] or 0)).rjust(4) + " | " +
            str(int(log["deficit"] or 0)).rjust(7) + " | " +
            cert
        )
        print(row)

    print()
    print("--- ENTIDADES ---")
    print("Ingestas (meal_slots) : " + str(meal_count) + " (" + str(sim_count) + " simulaciones sin confirmar)")
    print("Recetas               : " + str(recipe_count))
    print()
    print("=" * 70)


asyncio.run(main())
