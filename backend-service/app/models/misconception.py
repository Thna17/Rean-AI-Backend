import uuid
from datetime import datetime, timezone
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.db_types import GUID, TZDateTime

class MisconceptionLog(Base):
    """Tracks specific learning misconceptions for precise topic-based feedback."""
    
    __tablename__ = "misconception_logs"
    
    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    subject: Mapped[str] = mapped_column(String(50), nullable=False) # Math, Physics, English
    sub_topic: Mapped[str] = mapped_column(String(100), nullable=False) # e.g. "Algebra 2.1"
    error_pattern: Mapped[str] = mapped_column(String(255), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=lambda: datetime.now(timezone.utc))
    
    user = relationship("User")
    
    def __repr__(self) -> str:
        return f"<MisconceptionLog {self.subject} - {self.sub_topic}>"
