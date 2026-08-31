import pandas as pd
EXCEL_PATH = r"D:\Trabajo\app-biohack\repos\biohack-ddbb\docs\Seguimiento Dieta Phase A.xlsx"
df = pd.read_excel(EXCEL_PATH, header=2)
print("--- ALL COLUMNS ---")
print(df.columns.tolist())
valid_dates = df[df['Fecha'].notna()]
print(f"Total rows with valid 'Fecha': {len(valid_dates)}")
print("--- FIRST 5 VALID ROWS ---")
print(valid_dates[['Fecha', 'Peso (kg)']].head())
print("--- LAST 5 VALID ROWS ---")
print(valid_dates[['Fecha', 'Peso (kg)']].tail())
