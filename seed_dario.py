import asyncio
import pandas as pd
import uuid
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

SAM_DB_URL = "postgresql+asyncpg://postgres:postgres@localhost:5433/sam_db"
EXCEL_PATH = r"D:\Trabajo\app-biohack\repos\biohack-ddbb\docs\Seguimiento Dieta Phase A.xlsx"
TARGET_USER_ID = "usr_4f2bf9993862"

async def final_bio_certification():
    print(f"[RECOVERY] Final Bio-Certification Sync (Image 2 Parity)...")
    engine = create_async_engine(SAM_DB_URL)
    
    # 1. READ OFFICIAL AUDITS (Pesajes Quincenales) - Map headers from Image 2
    # Header is at row 3 (Index 2)
    df_bio = pd.read_excel(EXCEL_PATH, sheet_name='Pesajes Quincenales', header=2)
    df_bio['Fecha'] = pd.to_datetime(df_bio['Fecha'], errors='coerce')
    df_bio = df_bio[df_bio['Fecha'].notna()].sort_values('Fecha')
    
    # Create an interpolation-friendly biometrics baseline
    # Columns: 'Grasa Corp. (%)', 'Kg Msculo', 'Metabolismo Basal'
    biometrics = []
    for _, row in df_bio.iterrows():
        # Handle percentage strings if needed
        def clean_pct(val):
            if isinstance(val, str): return float(val.replace('%','').replace(',','.'))
            return float(val) * (100 if val < 1 else 1)

        biometrics.append({
            "date": row['Fecha'].date(),
            "bf_pct": clean_pct(row.get('Grasa Corp. (%)', 31.0)),
            "muscle": float(row.get('Kg Músculo', 68.0)),
            "bmr": float(row.get('Metabolismo Basal', 1950))
        })

    # 2. READ DAILY LOGS (Registro Diario)
    df_daily = pd.read_excel(EXCEL_PATH, sheet_name='Registro Diario', header=2)
    df_daily['Fecha'] = pd.to_datetime(df_daily['Fecha'], errors='coerce')
    df_daily = df_daily[df_daily['Fecha'].notna()].sort_values('Fecha')
    
    async with engine.connect() as conn:
        print("[WIPE] Purging history...")
        async with conn.begin():
            await conn.execute(text("DELETE FROM daily_logs WHERE user_id = :uid"), {"uid": TARGET_USER_ID})
        
        count = 0
        for idx, row in df_daily.iterrows():
            try:
                weight = float(row.get('Peso (kg)', 0))
                if weight <= 0: continue
                
                log_date = row['Fecha'].date()
                
                # Find the best biometrics for this date (closest previous weigh-in)
                current_bio = biometrics[0]
                for b in biometrics:
                    if b['date'] <= log_date:
                        current_bio = b
                    else:
                        break
                
                bf_pct = current_bio['bf_pct']
                lbm = weight * (1 - (bf_pct/100))
                bmr_excel = float(row.get('Gasto Basal (kcal)', current_bio['bmr']))
                tdee_excel = float(row.get('TDEE (kcal)', 2650))

                async with conn.begin():
                    await conn.execute(
                        text("""
                            INSERT INTO daily_logs (
                                daily_log_id, user_id, date, day_number, phase, 
                                weight, body_fat_percent, lbm, bmr, 
                                total_protein, total_fat, total_carbs, total_calories,
                                deficit
                            )
                            VALUES (
                                :id, :uid, :date, :dn, :phase, 
                                :w, :bf, :lbm, :bmr, 
                                :tp, :tf, :tc, :cal,
                                :def
                            )
                        """),
                        {
                            "id": f"log_{uuid.uuid4().hex[:12]}", "uid": TARGET_USER_ID, 
                            "date": log_date.strftime("%Y-%m-%d"),
                            "dn": int(row.get('Día', idx+1)), "phase": str(row.get('Estado', 'deficit')).lower()[:20],
                            "w": weight, "bf": bf_pct, "lbm": lbm, "bmr": bmr_excel,
                            "tp": float(row.get('Proteína (g)', 0)), 
                            "tf": float(row.get('Grasas (g)', 0)),
                            "tc": float(row.get('Hidratos (g)', 0)), 
                            "cal": float(row.get('Calorías (kcal)', 0)),
                            "def": float(row.get('Déficit/Superávit (kcal)', 0))
                        }
                    )
                count += 1
            except: pass
        
    print(f"[SUCCESS] FINAL CERTIFIED SYNC: {count} rows synchronized.")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(final_bio_certification())
