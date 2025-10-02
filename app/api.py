from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from .db import SessionLocal
from . import models, cbr
from .schemas import DiagnoseRequest, DiagnoseResponse

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/v1/symptom-categories")
async def list_symptom_categories(db: Session = Depends(get_db)):
    rows = db.execute(select(models.SymptomCategory)).scalars().all()
    return [{"code": r.code, "name": r.name} for r in rows]


@router.get("/v1/symptoms")
async def list_symptoms(q: str | None = None, db: Session = Depends(get_db)):
    stmt = select(models.Symptom)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(models.Symptom.name.like(like))
    rows = db.execute(stmt.order_by(models.Symptom.code)).scalars().all()
    return [{"code": r.code, "name": r.name, "category_code": r.category_code} for r in rows]


@router.get("/v1/diseases")
async def list_diseases(db: Session = Depends(get_db)):
    rows = db.execute(select(models.Disease).order_by(models.Disease.code)).scalars().all()
    return [{"code": r.code, "name": r.name} for r in rows]


@router.get("/v1/solutions")
async def list_solutions(db: Session = Depends(get_db)):
    rows = db.execute(select(models.Solution).order_by(models.Solution.code)).scalars().all()
    return [{"code": r.code, "name": r.name} for r in rows]


@router.get("/v1/cases")
async def list_cases(disease_code: str | None = None, db: Session = Depends(get_db)):
    stmt = select(models.Case).where(models.Case.is_active == True)
    if disease_code:
        stmt = stmt.where(models.Case.disease_code == disease_code)
    rows = db.execute(stmt.order_by(models.Case.id.desc()).limit(100)).scalars().all()
    out = []
    for c in rows:
        out.append({
        "id": c.id,
        "disease_code": c.disease_code,
        "notes": c.notes,
        "symptom_weights": {w.symptom_code: float(w.weight) for w in c.symptom_weights},
        "solutions": [s.solution_code for s in c.solutions],
        })
    return out


@router.post("/v1/cases", status_code=201)
async def retain_case(payload: RetainRequest, db: Session = Depends(get_db)):
    disease = db.get(models.Disease, payload.disease_code)
    if not disease:
        raise HTTPException(422, detail="Unknown disease_code")


    sym_rows = db.execute(select(models.Symptom.code)).all()
    sym_codes = {row[0] for row in sym_rows}
    for k in payload.symptom_weights.keys():
        if k not in sym_codes:
            raise HTTPException(422, detail=f"Unknown symptom_code: {k}")


    sol_rows = db.execute(select(models.Solution.code)).all()
    sol_codes = {row[0] for row in sol_rows}
    for s in payload.solutions:
        if s not in sol_codes:
            raise HTTPException(422, detail=f"Unknown solution_code: {s}")


    c = models.Case(disease_code=payload.disease_code, notes=payload.notes)
    db.add(c); db.flush()
    for k, w in payload.symptom_weights.items():
        db.add(models.CaseSymptomWeight(case_id=c.id, symptom_code=k, weight=float(w)))
    for s in payload.solutions:
        db.add(models.CaseSolution(case_id=c.id, solution_code=s))
    db.commit()
    return {"id": c.id}

@router.post("/v1/diagnose", response_model=DiagnoseResponse)
async def diagnose(req: DiagnoseRequest, request: Request, db: Session = Depends(get_db)):
    # 1) Validación mínima
    if not req.symptoms and not req.weights:
        raise HTTPException(422, detail="Provide symptoms[] or weights{}")

    try:
        # --- Construir pesos válidos (filtrando códigos inexistentes) ---
        sym_codes = set(db.execute(select(models.Symptom.code)).scalars().all())

        weights: dict[str, float] = {}
        if req.weights:
            # tomar solo los códigos válidos y normalizar a float
            for k, v in req.weights.items():
                if k in sym_codes:
                    try:
                        w = float(v)
                    except Exception:
                        continue
                    # clamp por seguridad
                    if w < 0:
                        w = 0.0
                    if w > 1:
                        w = 1.0
                    weights[k] = w

        # añadir síntomas marcados sin peso (peso 1.0 por defecto)
        for code in (req.symptoms or []):
            if code in sym_codes and code not in weights:
                weights[code] = 1.0

        if not weights:
            raise HTTPException(422, detail="No valid symptom codes in request.")

        # 2) Recuperar casos activos y ejecutar CBR
        cases = db.execute(
            select(models.Case).where(models.Case.is_active == True)
        ).scalars().all()

        retrieved = cbr.retrieve(cases, weights)
        proposals = cbr.reuse(retrieved, top_k=req.top_k)

        # 3) Resolver nombres de soluciones por propuesta
        response_payload = []
        all_solution_codes: set[str] = set()

        for p in proposals:
            sol_codes = p.get("solutions", [])
            if sol_codes:
                all_solution_codes.update(sol_codes)
                sol_names = db.execute(
                    select(models.Solution.name).where(models.Solution.code.in_(sol_codes))
                ).scalars().all()
            else:
                sol_names = []

            response_payload.append({
                "disease_code": p["disease_code"],
                "similarity": p["similarity"],
                "matched_symptoms": p.get("matched_symptoms", []),
                "missing_from_query": p.get("missing_from_query", []),
                # devolvemos nombres para el cliente
                "solutions": sol_names,
            })

        # 4) Registrar la consulta en 'consults'
        #    IMPORTANTE: tu tabla 'consults' exige 'solutions' (constraint NOT NULL),
        #    así que guardamos al menos una lista JSON (por ejemplo, los códigos únicos).
        consult = models.Consult(
            top_k=req.top_k,
            query_weights=weights,  # JSON
            client_ip=(request.client.host if request.client else None),
            user_agent=request.headers.get("User-Agent"),
            solutions=list(sorted(all_solution_codes))  # JSON, NO vacío
        )
        db.add(consult)
        db.commit()

        return {"consult_id": consult.id, "proposals": response_payload}

    except HTTPException:
        # re-lanzar validaciones
        raise
    except SQLAlchemyError as e:
        db.rollback()
        # expone mensaje resumido; ver detalles en logs
        raise HTTPException(500, detail="Database error while storing consult.") from e
    except Exception as e:
        db.rollback()
        raise HTTPException(500, detail="Unexpected error.") from e