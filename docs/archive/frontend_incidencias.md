# 🐞 Registro de Incidencias, Bugs y Mejoras (Front-End)

A continuación se detalla una revisión exhaustiva de los módulos de la aplicación front-end para el "Sistema de Auditoría Metabólica (SAM)". Se han encontrado vulnerabilidades tanto funcionales como de codificación.

---

## 🛑 Bugs Críticos (Prioridad Alta)

### 1. Parseo Numérico Inseguro en Inputs (`NaN` Bug)
Se ha detectado el uso generalizado de la coerción implícita de JavaScript `+e.target.value` en todos los formularios. 
*   **Problema:** Si el usuario teclea una coma (ej. `102,1` en lugar de `102.1`), la coerción resulta en `NaN`. Si el input se borra por completo (`""`), la coerción resulta en `0`, lo que enviará datos corrompidos a la API o fallará silenciosamente.
*   **Archivos Afectados:**
    *   `Dashboard.tsx` (Medición Matutina: `+morningData.weight`, `+morningData.bodyFat`).
    *   `MealSimulator.tsx` (Formulario Añadir Alimento: Macros y cantidad).
    *   `Exercise.tsx` (Registro de Ejercicio: `+duration`, `+speed`, `+effectiveWeight`).
    *   `Recipes.tsx` (Creación de Recetas: Macros, cantidad y tiempo de preparación).
*   **Solución:** Extraer y utilizar la función segura creada en `Onboarding.tsx` (`updateNumber`) a un hook genérico o a una utilidad global tipo `src/core/utils/numbers.ts` y aplicarla universalmente.

### 2. Gestión de Fechas Hardcodeadas y UTC
*   **Problema:** En `Planning.tsx` existe una fecha hardcodeada (`weekStartDate: '2026-04-14'`), lo que provocará que la planificación siempre empiece en el mismo día. 
*   **Problema:** En `Dashboard.tsx` y `Exercise.tsx` se utiliza `new Date().toISOString().split('T')[0]`. `toISOString()` siempre devuelve la fecha en UTC (Hora Zulú). Si un usuario registra una comida a las 01:00 AM en Madrid (GMT+1), el ISO String registrará el día anterior (23:00 UTC).
*   **Solución:** Cambiar el cálculo de fechas hacia una función local `toLocaleDateString('sv')` o utilizar un manipulador como `date-fns`.

---

## ⚠️ Errores Funcionales y de Lógica (Prioridad Media)

### 3. Falta de Tratamiento de Errores UX
*   **Problema:** En todos los `catch` block de llamadas al API (`apiService`) se utiliza `console.error(...)` pero no existe feedback visual al usuario si ocurre un fallo real, como "Servidor no disponible" o "Error guardando el ejercicio". (Ejemplo: `handleConfirm` en `MealSimulator.tsx` o `handleMorningSubmit` en `Dashboard.tsx`).
*   **Solución:** Implementar un sistema de notificaciones/Toast global (ej. con Zustand) para dar feedback claro al usuario si algo falla.

### 4. Precisión Flotante Mutando Estado (Client-Side Math)
*   **Problema:** En `MealSimulator.tsx` y `Recipes.tsx`, el front-end calcula calorías `(protein * 4) + (fat * 9) + (carbs * 4)` al vuelo. Los floats en JS sufren problemas de precisión (`0.1 + 0.2 = 0.30000000000000004`). 
*   **Solución:** Usar `Math.round()` al mostrar sumas parciales para evitar "154.000000002 g" en la interfaz.

### 5. Validaciones Negativas Ausentes
*   **Problema:** En formularios numéricos como macros o tiempos de cocinado, los inputs de tipo `number` permitirán por defecto introducir números negativos (`-15 minutos`, `-2g proteína`).
*   **Solución:** Añadir validación `min="0"` en los campos HTML de la interfaz y sanitización en el envío.

---

## 💡 Mejoras y Optimizaciones (Prioridad Baja)

### 6. Desdoblamiento del Estado en Simulador
*   **Mejora:** En `MealSimulator.tsx`, el estado temporal (`newFood`) está desvinculado de la validación. Valdría la pena construir un custom hook tipo `useFoodForm` para encapsular la lógica aburrida de actualizar macros y calcular calorías, manteniendo limpio el componente renderizado.

### 7. Feedback de Botones `Disabled`
*   **Mejora:** Bastantes botones se desactivan automáticamente si faltan datos en los formularios (ej. el botón "Calcular Día"). A nivel de experiencia usuario (UX), puede ser frustrante no saber **por qué** un botón está apagado. Es preferible mantener los botones activos y mostrar alertas de validación al hacer click (ej: "Por favor, rellena tu % de grasa para continuar").

### 8. Paginación de Recetario
*   **Mejora referenciada:** El endpoint `getRecipes` en `Recipes.tsx` actual asume cargar el array completo. Sería escalable prever paginación o carga bajo demanda `(lazy loading)` dado que el anexo D sugiere un recetario personal que puede crecer mucho con el tiempo.
