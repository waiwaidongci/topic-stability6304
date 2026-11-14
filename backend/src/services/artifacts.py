from pathlib import Path
from src.config.settings import ARTIFACT_DIR
def path_for(run_id):return Path(ARTIFACT_DIR,f'topic-{run_id}.json')
def quarantine(run_id):
 path=path_for(run_id)
 try:path.unlink()
 except FileNotFoundError:return
 except OSError:
  try:path.rename(path.with_suffix('.quarantined'))
  except OSError:pass
def remove(run_id):
 try:path_for(run_id).unlink()
 except (FileNotFoundError,OSError):pass
