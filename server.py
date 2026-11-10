import os,csv,io,json,random,hashlib,urllib.request,datetime,collections,math
from flask import Flask,request,jsonify,send_file
app=Flask(__name__)
DATA='daily_history.json'; STATE='learning.json'
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
def predict(date,h=None,w=None):
 h=h or history();w=w or weights(); dates=sorted(d for d in h if d<date);hist=[h[d] for d in dates]
 if len(hist)<30:raise ValueError('At least 30 earlier Daily Lotto draws are required')
 recent=hist[-30:];mid=hist[-90:];long=hist[-365:];cnt=lambda seq:collections.Counter(n for row in seq for n in row)
 c30,c90,c365=cnt(recent),cnt(mid),cnt(long);scores={};last={n:next((i for i,row in enumerate(reversed(hist)) if n in row),len(hist)) for n in range(1,37)}
 pairs=collections.Counter(tuple(sorted((a,b))) for row in mid for a in row for b in row if a<b)
 for n in range(1,37):
  vals={'hot':c90[n]/max(1,len(mid)),'recent':c30[n]/30,'gap':min(last[n],50)/50,'cold':1-c90[n]/max(1,len(mid)),'long':c365[n]/max(1,len(long)),'pair':sum(v for (a,b),v in pairs.items() if n in (a,b))/max(1,len(mid)*10)}
  scores[n]=sum(w[k]*vals[k] for k in w)
 rng=random.Random(int(hashlib.sha256((date+json.dumps(w,sort_keys=True)).encode()).hexdigest()[:15],16));rows=[]
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
 h=history();return jsonify(draws=len(h),first=min(h) if h else None,last=max(h) if h else None,weights=weights())
@app.post('/api/sync')
def sync():
 return jsonify(error='The previous public archive URL is unavailable (404). Please import a Daily Lotto CSV below. No results have been imported or changed.',hint='Use CSV with date and five numbers. Sync will require a verified provider API endpoint.'),503
@app.post('/api/import')
def imp():
 f=request.files.get('file')
 if not f:return jsonify(error='Choose CSV'),400
 rows=list(csv.DictReader(io.StringIO(f.read().decode('utf-8-sig'))));parsed=parse(rows);
 if not parsed:return jsonify(error='No valid Daily Lotto draws found. Use date,n1,n2,n3,n4,n5 or date,numbers. Dates must be YYYY-MM-DD.'),400
 h=history();h.update(parsed);save(DATA,h);return jsonify(imported=len(parsed),total=len(h))
@app.post('/api/predict')
def pred():
 date=request.json.get('date','')
 try:
  datetime.date.fromisoformat(date);rows=predict(date);return jsonify(date=date,rows=rows,draws_before=sum(d<date for d in history()))
 except Exception as e:return jsonify(error=str(e)),400
@app.post('/api/reveal')
def reveal():
 d=request.json['date'];rows=request.json['rows'];h=history();actual=h.get(d)
 if not actual:
  key=os.environ.get('RESULTSZA_API_KEY')
  if key:
   try:
    url='https://resultsza.co.za/api/get_daily_lotto_results?api_key='+key+'&date='+d
    obj=json.load(urllib.request.urlopen(url,timeout=15));actual=parse([dict(r,game='Daily Lotto') for r in obj.get('results',[])]).get(d)
    if actual:h[d]=actual;save(DATA,h)
   except:pass
 if not actual:return jsonify(error='No verified result for this date in the archive. Sync or import results, or configure RESULTSZA_API_KEY.'),404
 report=[]
 for i,row in enumerate(rows):
  hit=sorted(set(row)&set(actual));miss=sorted(set(actual)-set(row));report.append({'row':i+1,'hits':hit,'missed':miss,'count':len(hit),'extra':sorted(set(row)-set(actual))})
 return jsonify(actual=actual,report=report,best=max(x['count'] for x in report),unique_coverage=len(set(n for row in rows for n in row)&set(actual)),explanation='The missing numbers were not selected by this historical scoring model. Frequency and gaps describe the past; they do not establish why a random draw occurred.' )
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
