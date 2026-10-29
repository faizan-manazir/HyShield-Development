import json, logging, shutil, sys, tempfile, time
from pathlib import Path
repo=Path(sys.argv[1]).resolve(); label=sys.argv[2]; sys.path.insert(0,str(repo))
from app import config,db
from app.ingest import Ingestor
root=Path(tempfile.mkdtemp(prefix='hyshield-live-phase-')); config.DATA=root; config.DB_PATH=root/'hyshield.db'; config.SETTINGS_PATH=root/'settings.json'; config.LOG_PATH=root/'cowrie.json'; config.SETTINGS_PATH.write_text('{"logRetention":90}',encoding='utf-8'); db.init()
src=root/'cowrie.json'
def ev(eventid,ts,**kw):
 d={'eventid':eventid,'timestamp':ts,'session':'live-test-session','src_ip':'192.0.2.10'}; d.update(kw); return json.dumps(d,separators=(',',':'))
src.write_text(ev('cowrie.session.connect','2026-10-28T19:00:00.000000Z')+'\n'+ev('cowrie.session.closed','2026-10-28T19:00:05.000000')+'\n',encoding='utf-8')
class Capture(logging.Handler):
 def __init__(self): super().__init__(); self.records=[]
 def emit(self,r): self.records.append(self.format(r))
cap=Capture(); cap.setFormatter(logging.Formatter('%(levelname)s:%(message)s')); logger=logging.getLogger('hyshield.ingest'); logger.setLevel(logging.ERROR); logger.addHandler(cap)
ing=Ingestor(src,interval=0.2); ing._last_retention_cleanup=time.monotonic(); ing.start(); time.sleep(0.9)
def snapshot():
 conn=db.connect()
 try:
  rows=conn.execute('SELECT eventid,timestamp FROM raw_events ORDER BY rowid').fetchall(); ck=conn.execute('SELECT last_offset FROM checkpoints').fetchone()
  return len(rows),[r['eventid'] for r in rows],ck[0] if ck else None
 finally: conn.close()
before=snapshot(); errors_before=len(cap.records)
with src.open('a',encoding='utf-8') as f: f.write(ev('cowrie.command.input','2026-10-28T19:00:06.000000Z',input='whoami')+'\n')
time.sleep(0.9); after=snapshot(); errors_after=len(cap.records)-errors_before
ing.stop(); ing.join(timeout=1); logger.removeHandler(cap)
print(f'case={label}')
print(f'phase1_errors={errors_before}; phase1_rows={before[0]}; phase1_eventids={before[1]}; phase1_checkpoint={before[2]}')
print(f'phase2_new_errors={errors_after}; phase2_rows={after[0]}; phase2_eventids={after[1]}; phase2_checkpoint={after[2]}; file_size={src.stat().st_size}; checkpoint_at_eof={after[2]==src.stat().st_size}')
if cap.records: print('first_error='+cap.records[0].splitlines()[-1])
shutil.rmtree(root,ignore_errors=True)
