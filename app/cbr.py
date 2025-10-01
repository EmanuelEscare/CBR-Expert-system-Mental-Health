from typing import Dict, Iterable, List, Tuple
from .models import Case


# sim = peso_intersección / peso_total_del_caso


def _case_total_weight(case: Case) -> float:
    return float(sum(float(w.weight) for w in case.symptom_weights)) or 1.0


def retrieve(cases: List[Case], query_symptoms: Iterable[str] | Dict[str, float]):
    weights = {s: 1.0 for s in query_symptoms} if not isinstance(query_symptoms, dict) else {k: float(v) for k, v in query_symptoms.items()}
    results: List[Tuple[Case, float, dict]] = []
    for c in cases:
        sw = {cw.symptom_code: float(cw.weight) for cw in c.symptom_weights}
        matched = sorted(set(weights).intersection(sw))
        match_weight = sum(sw[s] for s in matched)
        total_weight = _case_total_weight(c)
        similarity = match_weight / total_weight
        details = {
        "matched": matched,
        "missing_from_query": sorted(set(sw).difference(weights)),
        "extra_in_query": sorted(set(weights).difference(sw)),
        "match_weight": match_weight,
        "case_total_weight": total_weight,
        }
        results.append((c, similarity, details))
    results.sort(key=lambda t: t[1], reverse=True)
    return results


def reuse(retrievals: List[Tuple[Case, float, dict]], top_k: int = 3):
    proposals = []
    for case, sim, det in retrievals[:top_k]:
        proposals.append({
        "disease_code": case.disease_code,
        "disease_name": case.disease.name if case.disease else case.disease_code,
        "similarity": round(float(sim), 3),
        "matched_symptoms": det["matched"],
        "missing_from_query": det["missing_from_query"],
        "solutions": [s.solution_code for s in case.solutions],
        })
    return proposals