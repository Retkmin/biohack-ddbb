"""
audit_user.py - Hoja de datos completa de un usuario SAM.
Uso: python audit_user.py <email>
"""
import asyncio
import sys
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text

USERS_DB_URL = "postgresql+asyncpg://postgres:postgres@localhost:5433/users_db"
SAM_DB_URL   = "postgresql+asyncpg://postgres:postgres@localhost:5433/sam_db"

async def audit(email: str):
    users_engine = create_async_engine(USERS_DB_URL, echo=False)
    sam_engine   = create_async_engine(SAM_DB_URL, echo=False)

    async with AsyncSession(users_engine) as session:
        result = await session.execute(
            text("SELECT * FROM users WHERE email = :email"), {"email": email}
        )
        user = result.mappings().one_or_none()

    if not user:
        print(f"\n❌  Usuario '{email}' NO encontrado en users_db.\n")
        return

    user_id = user["user_id"]

    # ── Cálculos Metabólicos ─────────────────────────────────────────
    w  = user["current_weight"] or 0
    bf = user["current_body_fat"] or 0
    if bf > 1:
        bf_dec = bf / 100
    else:
        bf_dec = bf
    lbm_calc  = round(w * (1 - bf_dec), 1)
    bmr_calc  = int(370 + 21.6 * lbm_calc)
    neat      = user["neat_calories"] or 0
    tdee_calc = int(bmr_calc + neat)

    print(f"\n{'='*60}")
    print(f"  HOJA DE DATOS — {email}")
    print(f"{'='*60}")
    print(f"\n{'─'*30} IDENTIDAD")
    print(f"  user_id        : {user['user_id']}")
    print(f"  email          : {user['email']}")
    print(f"  created_at     : {user['created_at']}")
    print(f"  updated_at     : {user['updated_at']}")

    print(f"\n{'─'*30} PERFIL ANTROPOMÉTRICO")
    print(f"  Edad           : {user['age']} años")
    print(f"  Sexo           : {user['sex']}")
    print(f"  Altura         : {user['height']} cm")
    print(f"  Peso Actual    : {w} kg")
    print(f"  % Grasa Corporal: {bf} {'(decimal)' if bf <= 1 else '(%)'}")

    print(f"\n{'─'*30} DATOS METABÓLICOS (en DB)")
    print(f"  LBM (DB)       : {user['current_lbm']} kg")
    print(f"  BMR (DB)       : {user['current_bmr']} kcal")
    print(f"  NEAT           : {neat} kcal")
    print(f"  Fase           : {user['current_phase']}")
    print(f"  Nivel Actividad: {user['activity_level']}")
    print(f"  Mantenimiento  : {user.get('required_maintenance_days', 'N/A')} días/semana")

    print(f"\n{'─'*30} RECÁLCULO LOCAL (marco maestro)")
    print(f"  LBM (calc)     : {lbm_calc} kg  {'✅ OK' if abs((user['current_lbm'] or 0) - lbm_calc) < 0.2 else '⚠️  DESVIACIÓN: DB=' + str(user['current_lbm'])}")
    print(f"  BMR (calc)     : {bmr_calc} kcal {'✅ OK' if abs((user['current_bmr'] or 0) - bmr_calc) < 5 else '⚠️  DESVIACIÓN: DB=' + str(user['current_bmr'])}")
    print(f"  TDEE Base      : {tdee_calc} kcal")

    async with AsyncSession(sam_engine) as session:
        # Logs
        logs_res = await session.execute(
            text("SELECT * FROM daily_logs WHERE user_id = :uid ORDER BY date DESC"),
            {"uid": user_id}
        )
        logs = logs_res.mappings().all()

        # Meals
        meals_res = await session.execute(
            text("""
                SELECT ms.slot_type, ms.total_protein, ms.total_fat, ms.total_carbs, ms.total_calories,
                       ms.is_simulation, dl.date
                FROM meal_slots ms
                JOIN daily_logs dl ON ms.daily_log_id = dl.daily_log_id
                WHERE dl.user_id = :uid
                ORDER BY dl.date DESC LIMIT 20
            """),
            {"uid": user_id}
        )
        meals = meals_res.mappings().all()

        # Recipes
        rec_res = await session.execute(
            text("SELECT COUNT(*) as cnt FROM recipes WHERE user_id = :uid"),
            {"uid": user_id}
        )
        recipe_count = rec_res.scalar()

    print(f"\n{'─'*30} HISTORIAL DIARIO (sam_db)")
    print(f"  Total registros: {len(logs)}")
    if logs:
        for log in logs[:7]:
            certified = "🔒" if log["is_certified"] else "🔓"
            print(f"  {certified} {log['date']} | Día {log['day_number']:>4} | {log['phase']:<12} | "
                  f"Peso: {log['weight']:.1f}kg | GC: {log['body_fat_percent']:.1f}% | "
                  f"LBM: {log['lbm']:.1f}kg | "
                  f"BMR: {log['bmr']:.0f} | TDEE: {log['tdee']:.0f} | "
                  f"Kcal: {log['total_calories']:.0f} | Déficit: {log['deficit']:.0f}")
        if len(logs) > 7:
            print(f"  ... y {len(logs)-7} registros más")

    print(f"\n{'─'*30} INGESTAS RECIENTES")
    if meals:
        for m in meals[:10]:
            sim = "[SIM]" if m["is_simulation"] else "     "
            print(f"  {sim} {m['date']} | {m['slot_type']:<12} | "
                  f"P:{m['total_protein']:.0f}g G:{m['total_fat']:.0f}g C:{m['total_carbs']:.0f}g | "
                  f"{m['total_calories']:.0f}kcal")
    else:
        print("  Sin ingestas registradas.")

    print(f"\n{'─'*30} OTRAS ENTIDADES")
    print(f"  Recetas        : {recipe_count}")
    print(f"\n{'='*60}\n")

if __name__ == "__main__":
    email = sys.argv[1] if len(sys.argv) > 1 else "darioalejandre@gmail.com"
    asyncio.run(audit(email))
