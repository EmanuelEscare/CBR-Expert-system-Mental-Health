# Psych CBR API (FastAPI + MySQL)


> **Aviso**: Proyecto **didáctico**. No es una herramienta médica. No reemplaza evaluación clínica profesional.


## Stack
- FastAPI, Uvicorn
- SQLAlchemy 2.x, PyMySQL
- MySQL
- Nginx (reverse proxy)


## Endpoints
- `GET /api/psych-cbr/health`
- `GET /api/psych-cbr/v1/symptom-categories`
- `GET /api/psych-cbr/v1/symptoms?q=`
- `GET /api/psych-cbr/v1/diseases`
- `GET /api/psych-cbr/v1/solutions`
- `GET /api/psych-cbr/v1/cases?disease_code=`
- `POST /api/psych-cbr/v1/cases` (retain)
- `POST /api/psych-cbr/v1/diagnose`


### Ejemplos
```bash
curl -X POST https://api.tu-dominio.com/api/psych-cbr/v1/diagnose \
-H 'Content-Type: application/json' \
-d '{"symptoms":["G06","G34","G58","G15","G49"],"top_k":5}'