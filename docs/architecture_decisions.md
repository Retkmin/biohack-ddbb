# Registro de Decisiones de Arquitectura (ADR)

Este documento centraliza todas las decisiones tecnológicas y arquitectónicas tomadas durante el desarrollo del proyecto Biohack.

## Estándar del Registro

Cada entrada debe seguir este formato:

- **ID y Título:** ADR-[N]: [Título descriptivo]
- **Fecha:** AAAA-MM-DD
- **Estado:** [Propuesto / Aceptado / Superado]
- **Contexto:** ¿Qué problema estamos resolviendo?
- **Decisión:** ¿Qué solución hemos elegido?
- **Consecuencias:** ¿Qué beneficios o deudas técnicas genera?

---

## Decisiones Tomadas

### ADR-000: Inicialización del Registro
- **Fecha:** 2026-04-11
- **Estado:** Aceptado
- **Contexto:** Necesidad de trazabilidad en las decisiones técnicas según el nuevo flujo de trabajo definido por el PO.
- **Decisión:** Se establece este archivo como la única fuente de verdad para decisiones de arquitectura.
- **Consecuencias:** Mayor transparencia y facilidad de onboarding para nuevos desarrolladores.

### [Ejemplo] ADR-001: Separación de Scopes Backend/Frontend
- **Fecha:** 2026-04-11
- **Estado:** Aceptado
- **Contexto:** Evitar cuellos de botella y asegurar que el testing sea modular.
- **Decisión:** Prohibir dependencias directas en tiempo de desarrollo entre ambos dominios.
- **Consecuencias:** Facilita el uso de agentes de test especializados por ámbito.
