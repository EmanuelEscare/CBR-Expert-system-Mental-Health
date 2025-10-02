from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean, ForeignKey, JSON, VARCHAR, CHAR, func
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from .db import Base


class SymptomCategory(Base):
    __tablename__ = "symptom_categories"
    code: Mapped[str] = mapped_column(CHAR(3), primary_key=True)
    name: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)


class Symptom(Base):
    __tablename__ = "symptoms"
    code: Mapped[str] = mapped_column(CHAR(3), primary_key=True)
    name: Mapped[str] = mapped_column(VARCHAR(255), nullable=False)
    category_code: Mapped[str] = mapped_column(CHAR(3), ForeignKey("symptom_categories.code"), nullable=False)


class Disease(Base):
    __tablename__ = "diseases"
    code: Mapped[str] = mapped_column(CHAR(3), primary_key=True)
    name: Mapped[str] = mapped_column(VARCHAR(150), nullable=False)


class Solution(Base):
    __tablename__ = "solutions"
    code: Mapped[str] = mapped_column(CHAR(3), primary_key=True)
    name: Mapped[str] = mapped_column(VARCHAR(255), nullable=False)


class Case(Base):
    __tablename__ = "cases"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    disease_code: Mapped[str] = mapped_column(CHAR(3), ForeignKey("diseases.code"), nullable=False)
    notes: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[str] = mapped_column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))


    disease = relationship("Disease")
    symptom_weights = relationship("CaseSymptomWeight", cascade="all, delete-orphan")
    solutions = relationship("CaseSolution", cascade="all, delete-orphan")


class CaseSymptomWeight(Base):
    __tablename__ = "case_symptom_weights"
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), primary_key=True)
    symptom_code: Mapped[str] = mapped_column(CHAR(3), ForeignKey("symptoms.code"), primary_key=True)
    weight: Mapped[float] = mapped_column(DECIMAL(5,2), default=1.0, nullable=False)


class CaseSolution(Base):
    __tablename__ = "case_solutions"
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), primary_key=True)
    solution_code: Mapped[str] = mapped_column(CHAR(3), ForeignKey("solutions.code"), primary_key=True)


class Consult(Base):
    __tablename__ = "consults"
    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    top_k = Column(Integer, nullable=False)
    query_weights = Column(JSON, nullable=False)  # JSON con los pesos de la consulta
    client_ip = Column(String(64))
    user_agent = Column(String(255))
    # Si tu tabla ya tiene columna `solutions` con constraint, déjala modelada para que SQLAlchemy la conozca:
    # solutions = Column(JSON, nullable=True)

    results = relationship(
        "ConsultResult",
        back_populates="consult",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

class ConsultResult(Base):
    __tablename__ = "consult_results"
    id = Column(Integer, primary_key=True, autoincrement=True)
    consult_id = Column(Integer, ForeignKey("consults.id", ondelete="CASCADE"), nullable=False, index=True)
    rank_pos = Column(Integer, nullable=False)
    disease_code = Column(String(10), ForeignKey("diseases.code"), nullable=False)
    similarity = Column(Float, nullable=False)
    matched = Column(JSON, nullable=False)   # p.ej. {"codes": [...]}
    missing = Column(JSON, nullable=False)   # p.ej. {"codes": [...]}
    solutions = Column(JSON, nullable=False) # p.ej. {"codes": [...], "names": [...]}

    consult = relationship("Consult", back_populates="results")