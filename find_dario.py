import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text

USERS_DB_URL = "postgresql+asyncpg://postgres:postgres@localhost:5433/users_db"
SAM_DB_URL   = "postgresql+asyncpg://postgres:postgres@localhost:5433/sam_db"

async def find_user():
    engine = create_async_engine(USERS_DB_URL, echo=False)
    async with AsyncSession(engine) as s:
        r = await s.execute(text("SELECT user_id, email, age, sex, height, current_weight, current_body_fat, current_lbm, current_bmr, neat_calories, activity_level, current_phase, created_at FROM users WHERE email ILIKE :pat ORDER BY created_at"), {"pat": "%dario%"})
        rows = r.mappings().all()
    if not rows:
        print("No se encontró ningún usuario con 'dario' en el email.")
        # Show all users
        engine2 = create_async_engine(USERS_DB_URL, echo=False)
        async with AsyncSession(engine2) as s2:
            r2 = await s2.execute(text("SELECT user_id, email, current_phase, created_at FROM users ORDER BY created_at"))
            all_users = r2.mappings().all()
        print(f"\nUsuarios existentes ({len(all_users)}):")
        for u in all_users:
            print(f"  {u['email']} | {u['current_phase']} | {str(u['created_at'])[:19]}")
        return
    
    for row in rows:
        print("\n=== USUARIO ENCONTRADO ===")
        for k, v in row.items():
            print(f"  {k:25s}: {v}")
        
        uid = row["user_id"]
        w = row["current_weight"] or 0
        bf = row["current_body_fat"] or 0
        bf_dec = bf / 100 if bf > 1 else bf
        lbm_calc = round(w * (1 - bf_dec), 1)
        bmr_calc = int(370 + 21.6 * lbm_calc)
        neat = row["neat_calories"] or 0
        tdee_calc = int(bmr_calc + neat)

        print(f"\n=== RECÁLCULO (Marco Maestro) ===")
        print(f"  LBM calculado  : {lbm_calc} kg  (DB: {row['current_lbm']})")
        print(f"  BMR calculado  : {bmr_calc} kcal (DB: {row['current_bmr']})")
        print(f"  TDEE Base      : {tdee_calc} kcal")
        
        # sam_db logs
        engine_sam = create_async_engine(SAM_DB_URL, echo=False)
        async with AsyncSession(engine_sam) as ss:
            lr = await ss.execute(
                text("SELECT date, day_number, phase, weight, body_fat_percent, lbm, bmr, tdee, total_calories, deficit, is_certified FROM daily_logs WHERE user_id = :uid ORDER BY date DESC LIMIT 14"),
                {"uid": uid}
            )
            logs = lr.mappings().all()
            mr = await ss.execute(
                text("SELECT COUNT(*) FROM meal_slots ms JOIN daily_logs dl ON ms.daily_log_id = dl.daily_log_id WHERE dl.user_id = :uid"),
                {"uid": uid}
            )
            meal_count = mr.scalar()
            rr = await ss.execute(
                text("SELECT COUNT(*) FROM recipes WHERE user_id = :uid"),
                {"uid": uid}
            )
            recipe_count = rr.scalar()

        print(f"\n=== HISTORIAL DIARIO ({len(logs)} últimos registros) ===")
        for log in logs:
            cert = "🔒" if log["is_certified"] else "  "
            print(f"  {cert} {log['date']} | Día {log['day_number']:>3} | {log['phase']:<12} | "
                  f"{log['weight']:.1f}kg | GC:{log['body_fat_percent']:.1f}% | "
                  f"LBM:{log['lbm']:.1f} | BMR:{log['bmr']:.0f} | "
                  f"TDEE:{log['tdee']:.0f} | Kcal:{log['total_calories']:.0f} | Dif:{log['deficit']:.0f}")
        
        print(f"\n=== ENTIDADES ===")
        print(f"  Ingestas (meal_slots) : {meal_count}")
        print(f"  Recetas               : {recipe_count}")

asyncio.run(find_user())
