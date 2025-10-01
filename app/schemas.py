from pydantic import BaseModel, Field
from typing import Dict, List, Optional


class DiagnoseRequest(BaseModel):
    symptoms: Optional[List[str]] = None
    weights: Optional[Dict[str, float]] = None
    top_k: int = Field(default=3, ge=1, le=20)


class Proposal(BaseModel):
    disease_code: str
    disease_name: str
    similarity: float
    matched_symptoms: List[str]
    missing_from_query: List[str]
    solutions: List[str]


class DiagnoseResponse(BaseModel):
    consult_id: int
    proposals: List[Proposal]


class RetainRequest(BaseModel):
    disease_code: str
    symptom_weights: Dict[str, float]
    solutions: List[str] = []
    notes: Optional[str] = None