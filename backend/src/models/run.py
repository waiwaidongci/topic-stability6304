from sqlalchemy.orm import Mapped,mapped_column
from sqlalchemy import String,JSON,Integer,ForeignKey,DateTime
from datetime import datetime,timezone
from src.config.database import Base
class TopicRun(Base):
 __tablename__='topic_runs'
 id:Mapped[int]=mapped_column(primary_key=True)
 corpus_id:Mapped[int]=mapped_column(ForeignKey('corpora.id'))
 name:Mapped[str]=mapped_column(String(100))
 config:Mapped[dict]=mapped_column(JSON)
 status:Mapped[str]=mapped_column(String(20),default='queued')
 result:Mapped[dict]=mapped_column(JSON,default=dict)
 error:Mapped[str|None]=mapped_column(String(1000),nullable=True)
 creator_id:Mapped[int]=mapped_column(ForeignKey('users.id'))
 created_at:Mapped[datetime]=mapped_column(DateTime,default=lambda:datetime.now(timezone.utc))
 corpus_revision:Mapped[int]=mapped_column(Integer,default=0,server_default='0')
 validity:Mapped[str]=mapped_column(String(20),default='valid',server_default='valid')
 supersedes_run_id:Mapped[int|None]=mapped_column(ForeignKey('topic_runs.id'),nullable=True)
 invalidated_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
 invalidation_reason:Mapped[str]=mapped_column(String(500),default='',server_default='')
