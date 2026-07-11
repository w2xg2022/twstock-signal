import requests,pandas as pd,os,time
OUT='/home/woody/stock-research/cache_full/per'; os.makedirs(OUT,exist_ok=True)
TOK=open('/home/woody/stock-research/FinMind.txt').read().strip()
codes=[c.strip() for c in open('/tmp/cand_codes.txt') if c.strip()]
T0=time.time(); log=lambda *a:print(*a,'| %.0fmin'%((time.time()-T0)/60),flush=True)
done=0; got=0; i=0; waits=0
while i<len(codes):
    code=codes[i]; fp=f'{OUT}/{code}.csv'
    if os.path.exists(fp): i+=1; done+=1; continue
    try:
        r=requests.get('https://api.finmindtrade.com/api/v4/data',params={'dataset':'TaiwanStockPER','data_id':code,'start_date':'2014-01-01','end_date':'2026-12-31','token':TOK},timeout=40)
        j=r.json()
    except Exception as e:
        log('EXC',code,str(e)[:50]); time.sleep(15); continue
    if r.status_code==200 and j.get('msg')=='success':
        pd.DataFrame(j.get('data',[])).to_csv(fp,index=False); i+=1; done+=1; got+=1; waits=0
        if got%100==0: log('已抓',got,'完成',done,'/',len(codes))
        time.sleep(0.2)
    else:
        m=str(j.get('msg')).lower(); waits+=1
        if waits>40: log('放棄(等太久) 完成',done,'/',len(codes)); break
        log(f'擋住({r.status_code} {m[:30]}) 等300s 第{waits}次 code',code); time.sleep(300)
log('DONE 新抓',got,'總完成',done,'/',len(codes))
