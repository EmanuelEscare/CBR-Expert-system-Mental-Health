# app/seed.py
from sqlalchemy.orm import Session
from .db import SessionLocal
from . import models
from .data import SYMPTOM_CATEGORIES, SYMPTOMS, SOLUTIONS, DISEASES, INITIAL_CASES


def bootstrap_if_empty():
    """Carga datos base de forma idempotente y en el orden correcto."""
    db: Session = SessionLocal()
    try:
        # 1) Tablas maestras: Disease, Solution, SymptomCategory
        if db.query(models.Disease).count() == 0:
            db.add_all([models.Disease(code=k, name=v) for k, v in DISEASES.items()])
        if db.query(models.Solution).count() == 0:
            db.add_all([models.Solution(code=k, name=v) for k, v in SOLUTIONS.items()])
        if db.query(models.SymptomCategory).count() == 0:
            db.add_all(
                [
                    models.SymptomCategory(code=k, name=v)
                    for k, v in SYMPTOM_CATEGORIES.items()
                ]
            )
        db.commit()

        # 2) Symptoms (después de categories)
        if db.query(models.Symptom).count() == 0:
            # Asegúrate de que este código exista en SYMPTOM_CATEGORIES
            default_cat = "S3"
            if not db.get(models.SymptomCategory, default_cat):
                # si no existe, toma cualquier categoría disponible
                any_cat = db.query(models.SymptomCategory.code).first()
                default_cat = any_cat[0] if any_cat else None

            items = []
            for code, name in SYMPTOMS.items():
                items.append(
                    models.Symptom(code=code, name=name, category_code=default_cat)
                )
            db.add_all(items)
            db.commit()

        # 3) Cases iniciales + pesos + soluciones demo
        if db.query(models.Case).count() == 0:
            for ic in INITIAL_CASES:
                c = models.Case(disease_code=ic["disease_code"], notes=ic.get("notes"))
                db.add(c)
                db.flush()  # ya tenemos c.id

                for sc, w in ic["symptom_weights"].items():
                    db.add(
                        models.CaseSymptomWeight(
                            case_id=c.id, symptom_code=sc, weight=float(w)
                        )
                    )

                demo = (
                    ["T03", "T10"]
                    if ic["disease_code"] != "P02"
                    else ["T02", "T03", "T09"]
                )
                for s in demo:
                    db.add(models.CaseSolution(case_id=c.id, solution_code=s))

            db.commit()

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
