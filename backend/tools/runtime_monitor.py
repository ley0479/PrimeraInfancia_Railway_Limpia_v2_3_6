#!/usr/bin/env python3
"""Sonda externa de disponibilidad para local, túnel o producción."""
from __future__ import annotations
import argparse, json, time, urllib.error, urllib.request
from datetime import datetime, timezone
from pathlib import Path

def probe(url: str, timeout: float) -> dict:
 started=time.perf_counter()
 try:
  req=urllib.request.Request(url,headers={'User-Agent':'PrimeraInfancia-Monitor/2.7.0'})
  with urllib.request.urlopen(req,timeout=timeout) as resp:
   raw=resp.read(1024*1024); status=int(resp.status)
   data=json.loads(raw.decode('utf-8')) if raw else {}
  return {'ok':200<=status<300 and data.get('status') in {'ok','ready'},'http_status':status,'latency_ms':round((time.perf_counter()-started)*1000,2),'payload':data}
 except Exception as exc:
  return {'ok':False,'latency_ms':round((time.perf_counter()-started)*1000,2),'error':f'{type(exc).__name__}: {exc}'}

def main():
 p=argparse.ArgumentParser(); p.add_argument('--url',default='http://127.0.0.1:5000/api/ready'); p.add_argument('--timeout',type=float,default=5); p.add_argument('--interval',type=float,default=0); p.add_argument('--max-failures',type=int,default=1); p.add_argument('--log',default='data/integrity/runtime_monitor.jsonl'); a=p.parse_args()
 path=Path(a.log).resolve(); path.parent.mkdir(parents=True,exist_ok=True); failures=0
 while True:
  result=probe(a.url,a.timeout); result.update({'timestamp':datetime.now(timezone.utc).isoformat(timespec='seconds'),'url':a.url})
  with path.open('a',encoding='utf-8') as fh: fh.write(json.dumps(result,ensure_ascii=False)+'\n')
  print(json.dumps(result,ensure_ascii=False))
  failures=0 if result['ok'] else failures+1
  if a.interval<=0 or failures>=max(1,a.max_failures): return 0 if result['ok'] else 2
  time.sleep(max(.5,a.interval))
if __name__=='__main__': raise SystemExit(main())
