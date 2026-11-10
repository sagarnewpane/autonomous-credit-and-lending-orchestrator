from datetime import datetime
from typing import Optional

from sqlalchemy import func
from sqlmodel import Field, Relationship, SQLModel


class LoanApplicationBase(SQLModel):
    """Base schema for LoanApplication with common fields."""

    applicant_name: str = Field(min_length=1, max_length=255)
    user_id: str = Field(min_length=1, max_length=100, index=True)
    loan_amount: float = Field(gt=0)
    loan_purpose: str
    monthly_income: float = Field(ge=0)
    monthly_debt: float = Field(ge=0)


class UploadedDocumentBase(SQLModel):
    """Base schema for UploadedDocument with common fields."""

    file_name: str = Field(min_length=1, max_length=255)
    content_type: Optional[str] = Field(default=None, max_length=100)
    file_size_bytes: Optional[int] = None


class UploadedDocument(UploadedDocumentBase, table=True):
    """ORM model for uploaded documents."""

    __tablename__ = "uploaded_documents"

    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    application_id: int = Field(foreign_key="loan_applications.id", index=True)
    uploaded_at: datetime = Field(
        default_factory=lambda: datetime.now(),
        sa_column_kwargs={"server_default": func.now()},
    )

    application: Optional["LoanApplication"] = Relationship(back_populates="documents")


class LoanApplication(LoanApplicationBase, table=True):
    """ORM model for loan applications."""

    __tablename__ = "loan_applications"

    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(),
        sa_column_kwargs={"server_default": func.now()},
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(),
        sa_column_kwargs={"server_default": func.now(), "onupdate": func.now()},
    )

    documents: list[UploadedDocument] = Relationship(
        back_populates="application",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


# Response schemas (for API responses)
class UploadedDocumentRead(UploadedDocumentBase):
    """Schema for reading uploaded documents."""

    id: int
    application_id: int
    uploaded_at: datetime


class LoanApplicationRead(LoanApplicationBase):
    """Schema for reading loan applications."""

    id: int
    created_at: datetime
    updated_at: datetime
    documents: list[UploadedDocumentRead] = []
