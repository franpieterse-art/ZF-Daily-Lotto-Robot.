import os,csv,io,json,random,hashlib,urllib.request,urllib.parse,urllib.error,datetime,collections,math,re,time
from flask import Flask,request,jsonify,send_file
app=Flask(__name__)
DATA=os.path.join(os.environ.get('DATA_DIR','.'),'daily_history.json'); STATE=os.path.join(os.environ.get('DATA_DIR','.'),'learning.json'); os.makedirs(os.path.dirname(os.path.abspath(DATA)),exist_ok=True)
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
 date=request.json.get('date','');attempt=int(request.json.get('attempt',0))
 if not 0<=attempt<=10000:return jsonify(error='Invalid attempt'),400
 try:
  datetime.date.fromisoformat(date);rows=predict(date,attempt=attempt);return jsonify(date=date,rows=rows,attempt=attempt,draws_before=sum(d<date for d in history()),mode='blind' if attempt==0 else 'alternative blind candidate; valid only if generated before reveal')
 except Exception as e:return jsonify(error=str(e)),400
@app.post('/api/reveal')
def reveal():
 d=request.json['date'];rows=request.json['rows'];h=history();actual=h.get(d)
 if len(rows)!=5 or any(len(r)!=6 or len(set(r))!=6 or any(not isinstance(n,int) or not 1<=n<=36 for n in r) for r in rows):return jsonify(error='Invalid prediction rows'),400
 if not actual and os.environ.get('RESULTSZA_API_KEY'):
  try:
   actual=fetch_draw(d)
   if actual:h[d]=actual;save(DATA,h)
  except ValueError as e:return jsonify(error=str(e)),502
 if not actual:return jsonify(error='No verified result for this date in the archive. Sync or import results, or configure RESULTSZA_API_KEY.'),404
 report=[]
 for i,row in enumerate(rows):
  hit=sorted(set(row)&set(actual));miss=sorted(set(actual)-set(row));report.append({'row':i+1,'hits':hit,'missed':miss,'count':len(hit),'extra':sorted(set(row)-set(actual))})
 return jsonify(actual=actual,report=report,best=max(x['count'] for x in report),unique_coverage=len(set(n for row in rows for n in row)&set(actual)),explanation='Misses reflect the model selecting other numbers. The draw is random: no causal explanation of misses is possible. Compare strategies on future unseen draws.' )
@app.post('/api/learn')
def learn():
 h=history();dates=sorted(h);usable=dates[60:];usable=usable[-min(100,len(usable)):]
 if len(usable)<20:return jsonify(error='Need at least 80 historical draws to evaluate learning.'),400
 base=weights();candidates=[base]
 for key in base:
  for mult in (.5,1.5,2):
   w=dict(base);w[key]*=mult;s=sum(w.values());candidates.append({k:v/s for k,v in w.items()})
 def evaluate(w,dates):
  hits=0;maxhits=0
  for d in dates:
   rows=predict(d,h,w);actual=set(h[d]);hits+=sum(len(set(r)&actual) for r in rows);maxhits+=max(len(set(r)&actual) for r in rows)
  return {'average_matches_per_row':round(hits/(5*len(dates)),4),'average_best_row':round(maxhits/len(dates),4),'draws':len(dates)}
 split=max(1,int(len(usable)*.7));train=usable[:split];test=usable[split:]
 ranked=sorted(((evaluate(w,train)['average_matches_per_row'],w) for w in candidates),key=lambda x:x[0],reverse=True)
 champion=ranked[0][1];baseline=evaluate(base,test);challenger=evaluate(champion,test)
 promoted=challenger['average_matches_per_row']>baseline['average_matches_per_row']+.01
 if promoted:save(STATE,champion)
 return jsonify(promoted=promoted,baseline=baseline,challenger=challenger,training_draws=len(train),holdout_draws=len(test),weights=champion if promoted else base,note='Weights are changed only if the challenger beats the previous weights on untouched holdout dates. This does not prove future predictive power.')
if __name__=='__main__':app.run(host='0.0.0.0',port=int(os.environ.get('PORT',5000)))
