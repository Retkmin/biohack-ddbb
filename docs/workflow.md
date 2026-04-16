# Flujo de Trabajo y Estándares de Desarrollo

Este documento define el ciclo de vida del desarrollo de software para el proyecto Biohack, garantizando la calidad y la trazabilidad de cada feature.

## 1. Ciclo de Desarrollo por Scope

El desarrollo se realiza de manera aislada basándose en el **Scope** (Ámbito) de la tarea. Un scope puede ser una funcionalidad del Backend, un componente del Frontend, o una integración específica.

### Independencia de Dominios
*   **Backend:** Su desarrollo y pruebas deben mantenerse dentro de su propio ámbito funcional y técnico. No debe depender de cambios pendientes en el frontend para ser validado.
*   **Frontend:** Su desarrollo y pruebas se limitan a la interfaz y lógica de cliente. Debe utilizar mocks o contratos definidos si el backend no está disponible, asegurando que el scope sea autónomo.

## 2. Decisiones de Arquitectura (ADR)

Cualquier decisión que afecte la estructura, patrones de diseño o tecnologías del proyecto **debe ser documentada** de manera obligatoria en el archivo [architecture_decisions.md](file:///d:/Trabajo/app-biohack/docs/architecture_decisions.md).

## 3. Proceso de Validación

Tras implementar una feature, se debe seguir estrictamente el siguiente flujo de agentes:

1.  **Agente de Test de Scope:**
    *   **Cuándo:** Inmediatamente después de finalizar la implementación y pruebas unitarias/locales.
    *   **Objetivo:** Validar que el código cumple con los requisitos técnicos del scope específico.
    *   **Salida:** Reporte de cobertura y éxito de pruebas de ámbito.

2.  **Agente de QA Funcional:**
    *   **Cuándo:** Una vez que el Agente de Test de Scope ha finalizado satisfactoriamente.
    *   **Objetivo:** Validar la funcionalidad desde la perspectiva del usuario final y el cumplimiento de las reglas de negocio descritas en la documentación maestra.
    *   **Salida:** Certificación de la feature para despliegue.

---
**Firmado:** Product Owner (PO)
