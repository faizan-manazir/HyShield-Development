import sys, random, tempfile, time, json, shutil
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import fault_harness as fh

def main(siem_dir,n=200,seed=20261021):
    sys.path.insert(0,siem_dir)
    from app import config,db
    from app.ingest import Ingestor
    tmp=Path(tempfile.mkdtemp(prefix='hyshield-targeted-'))
    config.DATA=tmp; config.SETTINGS_PATH=tmp/'settings.json'
    def run_ingest(data):
        src=tmp/'cowrie.json'; src.write_bytes(data)
        config.DB_PATH=tmp/'run.db'
        for p in tmp.glob('run.db*'): p.unlink()
        db.init(); ing=Ingestor(src,interval=0.01); ing._last_retention_cleanup=time.monotonic()
        crashed=False; persistent=False
        try: ing.poll()
        except Exception:
            crashed=True
            try: ing.poll()
            except Exception: persistent=True
        conn=db.connect()
        try:
            rows=conn.execute('SELECT eventid FROM raw_events').fetchall()
            sessions=conn.execute('SELECT COUNT(*) FROM sessions').fetchone()[0]
        finally: conn.close()
        ev=[r['eventid'] for r in rows]; stored=[e for e in ev if not (e or '').startswith('error.')]
        errors=len(ev)-len(stored)
        return len(stored),sum(e=='cowrie.command.input' for e in stored),sessions,(errors>0 or ing.stats['errors']>0),crashed,persistent
    rng=random.Random(seed); traces=[]
    for _ in range(n):
        lines=fh.make_trace(rng,benign_skew=rng.random()<0.10)
        data=fh.to_bytes(lines); traces.append((lines,fh.audit(data)))
    # Consume RNG exactly as the full harness does for the earlier fault types.
    target_index=next(i for i,x in enumerate(fh.FAULTS) if x[0]=='ts_naive')
    for key,label,fn in fh.FAULTS[:target_index]:
        for lines,base in traces: fn(rng,lines)
    counts={'flag':0,'src_db':0,'baseline':0,'crash':0,'persistent':0,'silent':0}
    for lines,base in traces:
        key,label,fn=fh.FAULTS[target_index]
        data=fn(rng,lines)
        stored,commands,sessions,flag,crash,persistent=run_ingest(data)
        mismatch=fh.source_object_count(data) != stored if hasattr(fh,'source_object_count') else False
        # Equivalent source-object count calculation from the harness.
        count=0
        for raw in data.split(b'\n')[:-1]:
            if not raw.strip(): continue
            try:
                if isinstance(json.loads(raw.decode('utf-8',errors='replace')),dict): count+=1
            except ValueError: pass
        mismatch=count != stored
        baseline=(stored,commands,sessions)!=(base['records'],base['commands'],base['sessions'])
        vals={'flag':flag,'src_db':mismatch,'baseline':baseline,'crash':crash,'persistent':persistent,'silent':not(flag or mismatch or baseline or crash)}
        for k,v in vals.items(): counts[k]+=int(v)
    print('condition=ts_naive n=',n)
    for k,v in counts.items(): print(f'{k}={v}/{n} ({v/n*100:.1f}%)')
    shutil.rmtree(tmp,ignore_errors=True)
if __name__=='__main__': main(sys.argv[1],int(sys.argv[2]) if len(sys.argv)>2 else 200)
