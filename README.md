# SAM: Biohack Infrastructure & Database 🏛️

Este repositorio centraliza la infraestructura, las migraciones y la documentación estratégica del sistema **SAM (Surgical Audit Metabolic)**.

## 📌 Scope
Este es el "Centro de Mando" del proyecto. Contiene:
- **Orquestación**: Configuración de Docker Compose para levantar el ecosistema completo.
- **Persistencia**: Esquemas de base de datos (PostgreSQL) y gestión de caché (Redis).
- **Evolución**: Migraciones de base de datos via Alembic.
- **Gobernanza**: Documentación maestra, decisiones de arquitectura (ADR) y especificaciones técnicas originales.

## ⛔ Prerrequisitos Críticos (Entorno Real)
Para levantar el sistema de forma profesional y evitar "parches" locales, es obligatorio contar con:
1. **Docker Desktop**: Motor de contenedores (Recomendado con WSL2 Backend).
   - *Instalación rápida*: `winget install Docker.DockerDesktop`
2. **Node.js v18+**: Para el repositorio `biohack-front`.
3. **Python 3.11+**: Para el repositorio `biohack-back`.
4. **Git**: Para la gestión de los 3 repositorios paralelos.

## 🏗️ Arquitectura de Infrastructura
El sistema utiliza una arquitectura contenerizada para garantizar la paridad entre entornos:
- **Database**: PostgreSQL 15 para almacenamiento relacional persistente.
- **Cache/Broker**: Redis 7 para colas de tareas Celery y caché de sesiones.
- **Migraciones**: Alembic para el control de versiones del esquema (Sincronizado con el repo `biohack-back`).

## 🚀 Guía de Inicio Rápido

### Requisitos Previos
- Docker y Docker Compose instalados.
- Clonar los repositorios hermanos en la misma carpeta raíz:
  - `biohack-back`
  - `biohack-front`

### Levantar el Entorno Local
Desde la raíz de este repositorio:
```bash
docker-compose up --build
```

Esto levantará:
1. Base de datos PostgreSQL (Puerto 5432).
2. Servidor Redis (Puerto 6379).
3. API Backend (Puerto 8000) - *Construido desde el repo biohack-back*.
4. Worker de Celery - *Construido desde el repo biohack-back*.

## 🛠️ Herramientas de Base de Datos
- `python migrate_db.py`: Ejecuta las migraciones pendientes.
- `python reset_db.py`: Limpia la base de datos (⚠️ Solo desarrollo).
- `python seed_users.py`: Genera 5 usuarios de prueba con 7 días de historial metabólico distribuidos en ambas bases de datos.

## 🧪 Scripts de Carga (Seeders)
El script `seed_users.py` es fundamental para el testing funcional. Crea perfiles variados:
1. **Alejandro**: Powerlifter (Déficit).
2. **Elena**: Runner (Mantenimiento).
3. **Roberto**: Sedentario (Déficit B).
4. **Sofia**: Crossfit (Recomp).
5. **Carlos**: Oficina (Mantenimiento).

Requiere: `pip install sqlalchemy asyncpg`.

## 📄 Documentación Centralizada
Consulta la carpeta `/docs` para:
- [Architecture Decisions (ADR)](./docs/architecture_decisions.md)
- [Workflow de Desarrollo](./docs/workflow.md)
- [Especificaciones Maestras](./specs/Marco_Maestro_SAM_v1.4.docx)

---
**SAM Project** — *Surgical Precision in Metabolic Auditing.*
