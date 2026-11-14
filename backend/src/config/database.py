from sqlalchemy import create_engine,inspect,text
from sqlalchemy.orm import DeclarativeBase,sessionmaker
from .settings import DATABASE_URL
class Base(DeclarativeBase): pass
engine=create_engine(DATABASE_URL,pool_pre_ping=True)
SessionLocal=sessionmaker(engine,expire_on_commit=False)
def get_db():
 with SessionLocal() as db: yield db

# create_all cannot add columns to an existing volume; keep pre-withdrawal
# deployments usable by adding only the additive columns introduced here.
UPGRADE_COLUMNS={
 'corpora':[('revision',"INTEGER NOT NULL DEFAULT 0")],
 'topic_runs':[('corpus_revision',"INTEGER NOT NULL DEFAULT 0"),('validity',"VARCHAR(20) NOT NULL DEFAULT 'valid'"),('supersedes_run_id',"INTEGER NULL"),('invalidated_at',"DATETIME NULL"),('invalidation_reason',"VARCHAR(500) NOT NULL DEFAULT ''")],
 'editorial_notes':[('superseded_by_note_id',"INTEGER NULL"),('quarantine_reason',"VARCHAR(500) NOT NULL DEFAULT ''")],
}
def ensure_columns():
 inspector=inspect(engine)
 existing=set(inspector.get_table_names())
 with engine.begin() as connection:
  for table,columns in UPGRADE_COLUMNS.items():
   if table not in existing:continue
   have={c['name'] for c in inspector.get_columns(table)}
   for name,ddl in columns:
    if name not in have:connection.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {ddl}'))
