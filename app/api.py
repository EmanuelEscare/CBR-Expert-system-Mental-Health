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
    if not req.symptoms and not req.weights:
        raise HTTPException(422, detail="Provide symptoms[] or weights{}")
    weights = req.weights or {s: 1.0 for s in (req.symptoms or [])}

    # 1) Casos activos
    cases = db.execute(select(models.Case).where(models.Case.is_active == True)).scalars().all()

    # 2) Retrieve/Reuse
    retr = cbr.retrieve(cases, weights)
    props = cbr.reuse(retr, top_k=req.top_k)

    # 3) Guarda cabecera de la consulta (sin tocar columna solutions)
    consult = models.Consult(
        top_k=req.top_k,
        query_weights=weights,
        client_ip=(request.client.host if request.client else None),
        user_agent=request.headers.get("User-Agent"),
    )
    db.add(consult); db.flush()

    # 4) Guarda resultados y arma payload
    response_payload = []
    for i, p in enumerate(props, start=1):
        sol_names = db.execute(
            select(models.Solution.name).where(models.Solution.code.in_(p["solutions"]))
        ).scalars().all()

        db.add(models.ConsultResult(
            consult_id=consult.id,
            rank_pos=i,
            disease_code=p["disease_code"],
            similarity=p["similarity"],
            matched={"codes": p["matched_symptoms"]},
            missing={"codes": p["missing_from_query"]},
            solutions={"codes": p["solutions"], "names": sol_names},
        ))

        response_payload.append({**p, "solutions": sol_names})

    db.commit()
    return {"consult_id": consult.id, "proposals": response_payload}
