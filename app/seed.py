from sqlalchemy.orm import Session
from .db import SessionLocal
from . import models
from .data import SYMPTOM_CATEGORIES, SYMPTOMS, SOLUTIONS, DISEASES, INITIAL_CASES


def bootstrap_if_empty():
    db: Session = SessionLocal()
    try:
        if db.query(models.Disease).count() == 0:
            for k, v in DISEASES.items():
                db.add(models.Disease(code=k, name=v))
                if db.query(models.Solution).count() == 0:
                    for k, v in SOLUTIONS.items():
                        db.add(models.Solution(code=k, name=v))
                if db.query(models.SymptomCategory).count() == 0:
                    for k, v in SYMPTOM_CATEGORIES.items():
                        db.add(models.SymptomCategory(code=k, name=v))
                if db.query(models.Symptom).count() == 0:
                    default_cat = "S3"
                    for k, v in SYMPTOMS.items():
                        db.add(models.Symptom(code=k, name=v, category_code=default_cat))
                db.commit()


        if db.query(models.Case).count() == 0:
            for ic in INITIAL_CASES:
                c = models.Case(disease_code=ic["disease_code"], notes=ic.get("notes"))
        db.add(c); db.flush()
        for sc, w in ic["symptom_weights"].items():
            db.add(models.CaseSymptomWeight(case_id=c.id, symptom_code=sc, weight=float(w)))
        demo = ["T03", "T10"] if ic["disease_code"] != "P02" else ["T02", "T03", "T09"]
        for s in demo:
            db.add(models.CaseSolution(case_id=c.id, solution_code=s))
        db.commit()
    finally:
        db.close()