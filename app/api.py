from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from .db import SessionLocal
from . import models
from . import cbr
from .schemas import DiagnoseRequest, DiagnoseResponse, RetainRequest

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
    # 1) Validación y normalización de entrada
    if not req.symptoms and not req.weights:
        raise HTTPException(422, detail="Provide symptoms[] or weights{}")

    # Códigos de síntomas válidos
    sym_codes_db = set(db.execute(select(models.Symptom.code)).scalars().all())

    # Construir 'weights' finales (prioriza req.weights si viene)
    weights: dict[str, float] = {}
    if req.weights:
        unknown = [k for k in req.weights.keys() if k not in sym_codes_db]
        if unknown:
            raise HTTPException(422, detail=f"Unknown symptom_code(s) in weights: {', '.join(unknown)}")
        # filtra 0/None y castea a float
        weights = {k: float(v) for k, v in req.weights.items() if v is not None and float(v) != 0.0}
    else:
        unknown = [s for s in (req.symptoms or []) if s not in sym_codes_db]
        if unknown:
            raise HTTPException(422, detail=f"Unknown symptom_code(s): {', '.join(unknown)}")
        weights = {s: 1.0 for s in (req.symptoms or [])}

    if not weights:
        raise HTTPException(422, detail="Empty weights after validation")

    # 2) Recupera casos activos
    cases = db.execute(
        select(models.Case).where(models.Case.is_active.is_(True))
    ).scalars().all()

    top_k = req.top_k or 3

    # 3) Ejecuta CBR (si no hay casos, retorna vacío)
    retr = cbr.retrieve(cases, weights) if cases else []
    props = cbr.reuse(retr, top_k=top_k) if retr else []

    # 4) Persistencia y respuesta (con manejo de transacción)
    try:
        # IMPORTANTE: solutions=[] para cumplir el CHECK(JSON_VALID(solutions))
        consult = models.Consult(
            top_k=top_k,
            query_weights=weights,
            client_ip=(request.client.host if request.client else None),
            user_agent=request.headers.get("User-Agent"),
            solutions=[],  # no dejes NULL
        )
        db.add(consult)
        db.flush()  # para tener consult.id

        response_payload = []
        agg_sol_codes: set[str] = set()

        for i, p in enumerate(props, start=1):
            matched = list(p.get("matched_symptoms", []))          # evita sets
            missing = list(p.get("missing_from_query", []))
            sol_codes = list(p.get("solutions", []))
            agg_sol_codes.update(sol_codes)

            # Nombres de soluciones (opcional; devuelves nombres en la API pública)
            sol_names: list[str] = []
            if sol_codes:
                sol_names = db.execute(
                    select(models.Solution.name).where(models.Solution.code.in_(sol_codes))
                ).scalars().all()

            # Guarda resultado detallado
            db.add(models.ConsultResult(
                consult_id=consult.id,
                rank_pos=i,
                disease_code=p["disease_code"],
                similarity=float(p.get("similarity", 0)),
                matched={"codes": matched},
                missing={"codes": missing},
                solutions={"codes": sol_codes, "names": sol_names},
            ))

            # Respuesta pública (si prefieres códigos, cambia 'solutions': sol_names -> sol_codes)
            response_payload.append({
                "disease_code": p["disease_code"],
                "similarity": float(p.get("similarity", 0)),
                "matched_symptoms": matched,
                "missing_from_query": missing,
                "solutions": sol_names,
            })

        # Guarda un agregado de soluciones (códigos) en la propia consulta
        consult.solutions = sorted(agg_sol_codes)

        db.commit()
        return {"consult_id": consult.id, "proposals": response_payload}

    except Exception:
        db.rollback()
        raise