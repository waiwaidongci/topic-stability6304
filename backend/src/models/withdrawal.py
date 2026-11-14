from sqlalchemy.orm import Mapped,mapped_column
from sqlalchemy import String,JSON,ForeignKey,DateTime,UniqueConstraint
from datetime import datetime,timezone
from src.config.database import Base
class DocumentWithdrawal(Base):
 __tablename__='document_withdrawals'
 __table_args__=(UniqueConstraint('document_id'),)
 id:Mapped[int]=mapped_column(primary_key=True)
 corpus_id:Mapped[int]=mapped_column(ForeignKey('corpora.id'))
 document_id:Mapped[int]=mapped_column(ForeignKey('token_documents.id'))
 reference:Mapped[str]=mapped_column(String(80))
 title:Mapped[str]=mapped_column(String(120))
 reason:Mapped[str]=mapped_column(String(500))
 actor:Mapped[str]=mapped_column(String(120))
 content_sha256:Mapped[str]=mapped_column(String(64))
 token_count:Mapped[int]=mapped_column(default=0)
 corpus_revision:Mapped[int]=mapped_column(default=0)
 affected_run_ids:Mapped[list]=mapped_column(JSON,default=list)
 replacement_run_ids:Mapped[list]=mapped_column(JSON,default=list)
 affected_note_ids:Mapped[list]=mapped_column(JSON,default=list)
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
