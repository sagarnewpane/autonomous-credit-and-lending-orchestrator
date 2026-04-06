from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class LoanApplication(Base):
    __tablename__ = "loan_applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    applicant_name: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    loan_amount: Mapped[float] = mapped_column(Float, nullable=False)
    loan_purpose: Mapped[str] = mapped_column(Text, nullable=False)
    monthly_income: Mapped[float] = mapped_column(Float, nullable=False)
    monthly_debt: Mapped[float] = mapped_column(Float, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    documents: Mapped[list["UploadedDocument"]] = relationship(
        "UploadedDocument",
        back_populates="application",
        cascade="all, delete-orphan",
    )


class UploadedDocument(Base):
    __tablename__ = "uploaded_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("loan_applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    application: Mapped["LoanApplication"] = relationship(
        "LoanApplication",
        back_populates="documents",
    )
