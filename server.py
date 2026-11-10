import os,csv,io,json,random,hashlib,urllib.request,urllib.parse,urllib.error,datetime,collections,math,re,time,sqlite3,uuid,threading
from flask import Flask,request,jsonify,send_file
app=Flask(__name__)
DATA=os.path.join(os.environ.get('DATA_DIR','.'),'daily_history.json'); STATE=os.path.join(os.environ.get('DATA_DIR','.'),'learning.json'); os.makedirs(os.path.dirname(os.path.abspath(DATA)),exist_ok=True)
DB=os.path.join(os.environ.get('DATA_DIR','.'),'learning_history.sqlite3')
def connect():
 c=sqlite3.connect(DB,timeout=15);c.row_factory=sqlite3.Row;c.execute('PRAGMA busy_timeout=15000');return c
def initdb():
 with connect() as c:
  c.execute('CREATE TABLE IF NOT EXISTS predictions (id TEXT PRIMARY KEY, draw_date TEXT, created_at TEXT, attempt INTEGER, rows_json TEXT, weights_json TEXT, status TEXT, draws_before INTEGER, result_json TEXT, best INTEGER, average REAL, coverage INTEGER)')
  c.execute('CREATE TABLE IF NOT EXISTS learning_runs (id TEXT PRIMARY KEY, created_at TEXT, training_count INTEGER, holdout_count INTEGER, baseline_json TEXT, challenger_json TEXT, old_weights_json TEXT, candidate_weights_json TEXT, promoted INTEGER, reason TEXT)')
initdb()
def utcnow():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def rowdict(r):return dict(r) if r else None
def load(path,default):
 try:
  with open(path) as f:return json.load(f)
 except:return default
def save(path,obj):
 with open(path,'w') as f:json.dump(obj,f)
def parse(rows):
 out={}
 for r in rows:
  r={str(k).strip().lower().replace(' ','_'):v for k,v in r.items() if k is not None}
  game=str(r.get('game',r.get('game_type','daily lotto'))).lower().replace(' ','').replace('_','')
  if game not in ('dailylotto',''):continue
  date=str(r.get('date',r.get('draw_date',''))).strip()[:10]
  try:datetime.date.fromisoformat(date)
  except:continue
  nums=r.get('numbers',r.get('winning_numbers',None))
  if nums is None:
   for keys in [('n1','n2','n3','n4','n5'),('number1','number2','number3','number4','number5'),('ball1','ball2','ball3','ball4','ball5')]:
    if all(k in r for k in keys):nums=[r[k] for k in keys];break
  if isinstance(nums,str):
   import re
   nums=re.findall(r'\d+',nums)
  try:
   ns=list(map(int,nums))
   if len(ns)==5 and len(set(ns))==5 and all(1<=n<=36 for n in ns):out[date]=sorted(ns)
  except (TypeError,ValueError):pass
 return out
def history():return load(DATA,{})
def weights():return load(STATE,{'hot':.25,'recent':.2,'gap':.15,'cold':.15,'pair':.1,'long':.15})
def predict(date,h=None,w=None,attempt=0):
 h=h or history();w=w or weights(); dates=sorted(d for d in h if d<date);hist=[h[d] for d in dates]
 if len(hist)<30:raise ValueError('At least 30 earlier Daily Lotto draws are required')
 recent=hist[-30:];mid=hist[-90:];long=hist[-365:];cnt=lambda seq:collections.Counter(n for row in seq for n in row)
 c30,c90,c365=cnt(recent),cnt(mid),cnt(long);scores={};last={n:next((i for i,row in enumerate(reversed(hist)) if n in row),len(hist)) for n in range(1,37)}
 pairs=collections.Counter(tuple(sorted((a,b))) for row in mid for a in row for b in row if a<b)
 for n in range(1,37):
  vals={'hot':c90[n]/max(1,len(mid)),'recent':c30[n]/30,'gap':min(last[n],50)/50,'cold':1-c90[n]/max(1,len(mid)),'long':c365[n]/max(1,len(long)),'pair':sum(v for (a,b),v in pairs.items() if n in (a,b))/max(1,len(mid)*10)}
  scores[n]=sum(w[k]*vals[k] for k in w)
 rng=random.Random(int(hashlib.sha256((date+json.dumps(w,sort_keys=True)+':'+str(attempt)).encode()).hexdigest()[:15],16));rows=[]
 for i in range(5):
  pool=list(range(1,37));chosen=[]
  while len(chosen)<6:
   adjusted=[max(.001,scores[n])*(1/(1+sum(n in r for r in rows)*.7)) for n in pool]
   n=rng.choices(pool,weights=adjusted)[0];chosen.append(n);pool.remove(n)
  rows.append(sorted(chosen))
 return rows
@app.get('/')
def index():return send_file('index.html')
@app.get('/api/status')
def status():
 h=history();return jsonify(draws=len(h),first=min(h) if h else None,last=max(h) if h else None,weights=weights(),api_configured=bool(os.environ.get('RESULTSZA_API_KEY')))
def fetch_draw(date):
 key=os.environ.get('RESULTSZA_API_KEY','').strip()
 if not key:raise ValueError('RESULTSZA_API_KEY is not configured in Render Environment. Add your own key from resultsza.co.za.')
 params=urllib.parse.urlencode({'api_key':key,'date':date})
 req=urllib.request.Request('https://resultsza.co.za/api/get_daily_lotto_results?'+params,headers={'User-Agent':'ZF-Daily-Lotto-Research/2.0','Accept':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=12) as resp:obj=json.load(resp)
 except urllib.error.HTTPError as e:
  if e.code==404:return None
  if e.code in (401,403):raise ValueError('ResultsZA rejected the API key or access (HTTP %s).'%e.code)
  if e.code==429:raise ValueError('ResultsZA API rate limit reached (429). Try a smaller date range later.')
  raise ValueError('ResultsZA returned HTTP %s'%e.code)
 except (urllib.error.URLError,TimeoutError) as e:raise ValueError('Could not contact ResultsZA: '+str(e))
 if obj.get('status')=='error':raise ValueError(str(obj.get('message','Provider returned an error')))
 rows=obj.get('results',[])
 if isinstance(rows,dict):rows=[rows]
 parsed=parse([dict(r,game='Daily Lotto') for r in rows if isinstance(r,dict)])
 return parsed.get(date)

@app.post('/api/sync')
def sync():
 body=request.get_json(silent=True) or {}
 try:
  start=datetime.date.fromisoformat(body.get('start','2026-10-01'))
  end=datetime.date.fromisoformat(body.get('end',datetime.date.today().isoformat()))
  if end<start:raise ValueError('End date must not be before start date.')
  if end>datetime.date.today():raise ValueError('Cannot sync future dates.')
  if (end-start).days>60:raise ValueError('Sync at most 61 dates at a time to limit API usage. Run again for the next period.')
  if not os.environ.get('RESULTSZA_API_KEY'):raise ValueError('Add RESULTSZA_API_KEY in Render Environment before automatic sync.')
  h=history();new=0;checked=0;skipped=0;errors=[]
  for offset in range((end-start).days+1):
   d=(start+datetime.timedelta(days=offset)).isoformat()
   if d in h:skipped+=1;continue
   try:
    nums=fetch_draw(d);checked+=1
    if nums:h[d]=nums;new+=1;save(DATA,h)
   except ValueError as e:
    errors.append({'date':d,'error':str(e)});break
  return jsonify(imported=new,total=len(h),checked=checked,skipped=skipped,errors=errors,first=min(h) if h else None,last=max(h) if h else None)
 except ValueError as e:return jsonify(error=str(e)),400

@app.post('/api/import')
def imp():
 f=request.files.get('file')
 if not f:return jsonify(error='Choose CSV'),400
 rows=list(csv.DictReader(io.StringIO(f.read().decode('utf-8-sig'))));parsed=parse(rows);
 if not parsed:return jsonify(error='No valid Daily Lotto draws found. Use date,n1,n2,n3,n4,n5 or date,numbers. Dates must be YYYY-MM-DD.'),400
 h=history();h.update(parsed);save(DATA,h);return jsonify(imported=len(parsed),total=len(h))
@app.post('/api/predict')
def pred():
 body=request.get_json(silent=True) or {};date=body.get('date','')
 try:
  datetime.date.fromisoformat(date)
  attempt=int(body.get('attempt',0))
  if not 0<=attempt<=10000:raise ValueError('Invalid attempt')
  h=history();w=weights();rows=predict(date,h,w,attempt)
  with connect() as c:
   prior=c.execute('SELECT 1 FROM predictions WHERE draw_date=? AND status="revealed" LIMIT 1',(date,)).fetchone()
   status='post_reveal' if prior else 'blind'
   pid=str(uuid.uuid4());c.execute('INSERT INTO predictions (id,draw_date,created_at,attempt,rows_json,weights_json,status,draws_before) VALUES (?,?,?,?,?,?,?,?)',(pid,date,utcnow(),attempt,json.dumps(rows),json.dumps(w),status,sum(d<date for d in h)))
  return jsonify(id=pid,date=date,rows=rows,attempt=attempt,draws_before=sum(d<date for d in h),mode=status)
 except (ValueError,TypeError) as e:return jsonify(error=str(e)),400
@app.post('/api/reveal')
def reveal():
 body=request.get_json(silent=True) or {};pid=body.get('id')
 with connect() as c:r=c.execute('SELECT * FROM predictions WHERE id=?',(pid,)).fetchone()
 if not r:return jsonify(error='Prediction ID not found. Generate predictions first.'),404
 d=r['draw_date'];rows=json.loads(r['rows_json']);h=history();actual=h.get(d)
 if not actual and os.environ.get('RESULTSZA_API_KEY'):
  try:
   actual=fetch_draw(d)
   if actual:h[d]=actual;save(DATA,h)
  except ValueError as e:return jsonify(error=str(e)),502
 if not actual:return jsonify(error='No result found for this date. Import CSV or sync the archive.'),404
 report=[]
 for i,row in enumerate(rows):
  hit=sorted(set(row)&set(actual));report.append({'row':i+1,'hits':hit,'missed':sorted(set(actual)-set(row)),'count':len(hit),'extra':sorted(set(row)-set(actual))})
 best=max(x['count'] for x in report);average=sum(x['count'] for x in report)/5;coverage=len(set(n for row in rows for n in row)&set(actual))
 with connect() as c:c.execute('UPDATE predictions SET result_json=?,best=?,average=?,coverage=?,status=? WHERE id=?',(json.dumps(actual),best,average,coverage,'post_reveal' if r['status']=='post_reveal' else 'revealed',pid))
 return jsonify(actual=actual,report=report,best=best,average=average,unique_coverage=coverage,mode=r['status'],explanation='Missed numbers were not selected by this strategy. Random draws have no known causal pattern. Only chronological unseen-draw testing can establish whether a strategy improves historical performance.')
@app.get('/api/history')
def audit_history():
 with connect() as c:
  preds=[dict(x) for x in c.execute('SELECT id,draw_date,created_at,attempt,status,draws_before,best,average,coverage FROM predictions ORDER BY created_at DESC LIMIT 150')]
  runs=[dict(x) for x in c.execute('SELECT * FROM learning_runs ORDER BY created_at DESC LIMIT 30')]
 for r in runs:
  for k in ('baseline_json','challenger_json','old_weights_json','candidate_weights_json'):
   r[k[:-5]]=json.loads(r.pop(k))
 return jsonify(predictions=preds,learning_runs=runs)
@app.get('/api/history.csv')
def history_csv():
 with connect() as c:rows=c.execute('SELECT id,draw_date,created_at,attempt,status,draws_before,best,average,coverage,rows_json,result_json,weights_json FROM predictions ORDER BY created_at').fetchall()
 out=io.StringIO();writer=csv.writer(out);writer.writerow(['id','draw_date','created_at','attempt','status','draws_before','best','average','coverage','predictions','actual','weights'])
 for r in rows:writer.writerow(list(r))
 from flask import Response
 return Response(out.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=zf_daily_prediction_audit.csv'})
@app.post('/api/learn')
def learn():
 h=history();dates=sorted(h);usable=dates[60:][-30:]
 if len(usable)<20:return jsonify(error='Need at least 80 historical draws to evaluate learning.'),400
 base=weights();candidates=[base]
 for key in base:
  for mult in (.5,1.5):
   w=dict(base);w[key]*=mult;total=sum(w.values());candidates.append({k:v/total for k,v in w.items()})
 def evaluate(w,ds):
  hits=best=0
  for d in ds:
   rows=predict(d,h,w);actual=set(h[d]);counts=[len(set(row)&actual) for row in rows];hits+=sum(counts);best+=max(counts)
  return {'average_matches_per_row':round(hits/(5*len(ds)),4),'average_best_row':round(best/len(ds),4),'draws':len(ds)}
 split=20;train=usable[:split];test=usable[split:]
 ranked=sorted(((evaluate(w,train)['average_matches_per_row'],w) for w in candidates),key=lambda x:x[0],reverse=True)
 champion=ranked[0][1];baseline=evaluate(base,test);challenger=evaluate(champion,test)
 promoted=challenger['average_matches_per_row']>baseline['average_matches_per_row']+.05
 reason='Challenger improved holdout average by more than 0.05 matches per row' if promoted else 'No meaningful holdout improvement; existing weights retained'
 if promoted:save(STATE,champion)
 with connect() as c:c.execute('INSERT INTO learning_runs VALUES (?,?,?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),utcnow(),len(train),len(test),json.dumps(baseline),json.dumps(challenger),json.dumps(base),json.dumps(champion),int(promoted),reason))
 return jsonify(promoted=promoted,baseline=baseline,challenger=challenger,training_draws=len(train),holdout_draws=len(test),weights=champion if promoted else base,reason=reason,note='This is a small historical holdout, not evidence of forecasting advantage. Repeated reuse of the same holdout causes overfitting.')
if __name__=='__main__':app.run(host='0.0.0.0',port=int(os.environ.get('PORT',5000)))
