"""gb-4101 账单调号实测：互换 / 链式腾出号 / 冲突退回 / 并发争空号 / 无关账单照常写 /
落库后断线幂等重试 / 两侧同一版 / 旧证据保留原号码 / 只读限制。
Runs against the local stack started by run_stack.sh (uvicorn :8000, postgres :15432).
"""
import json,socket,threading,time,urllib.request,urllib.error,uuid
import psycopg2
API='http://127.0.0.1:8000'
RUN=uuid.uuid4().hex[:8]
results=[]
def check(name,cond,detail=''):
    results.append((name,bool(cond),detail))
    print(('PASS' if cond else 'FAIL'),name,('— '+str(detail)[:300] if detail and not cond else ''))
def api(method,path,token=None,body=None,raw=False):
    req=urllib.request.Request(API+path,method=method,data=json.dumps(body).encode() if body is not None else None)
    req.add_header('Content-Type','application/json')
    if token:req.add_header('Authorization','Bearer '+token)
    try:
        with urllib.request.urlopen(req) as r:return r.status,json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:return e.code,json.loads(e.read())
        except Exception:return e.code,{}
def login(email):
    s,d=api('POST','/auth/login',body={'email':email,'password':'ColdChain!17'})
    assert s==200,(s,d)
    return d['token']
db=psycopg2.connect(host='127.0.0.1',port=15432,user='app',password='local_demo_4101',dbname='query_review')
db.autocommit=True
def sql(q,args=()):
    with db.cursor() as c:c.execute(q,args);return c.fetchall()
def row(n):
    r=sql('SELECT customer,route,amount::text,temperature::text,status FROM invoices WHERE invoice_id=%s',(n,))
    return r[0] if r else None
def snapshot():
    return {r[0]:r[1:] for r in sql('SELECT invoice_id,customer,route,amount::text,temperature::text,status FROM invoices')}
def renumber(token,name,key,moves):
    return api('POST','/renumbers',token,{'name':name,'idempotency_key':key,'moves':[{'from':a,'to':b} for a,b in moves]})

op=login('operator@chenggang.test');viewer=login('viewer@chenggang.test');admin=login('admin@chenggang.test')
snap0=snapshot()
check('前置：演示账单 600 条、号码 1..600',len(snap0)==600 and min(snap0)==1 and max(snap0)==600,len(snap0))

# 1. 只读限制保留
s,_=api('POST','/renumbers',viewer,{'name':'v-'+RUN,'idempotency_key':'vk-'+RUN,'moves':[{'from':301,'to':971}]})
check('只读限制：viewer 调号被拒 403',s==403,s)
s,d=api('GET','/renumbers',viewer)
check('只读限制：viewer 可查询调号记录',s==200,s)

# 2. 参数校验 422
for label,moves in [('新旧同号',[{'from':1,'to':1}]),('同批撞目标',[{'from':1,'to':900},{'from':2,'to':900}]),('空调号单',[])]:
    s,_=api('POST','/renumbers',op,{'name':'bad-'+RUN,'idempotency_key':'bad-'+RUN+label,'moves':moves})
    check('参数校验 422：'+label,s==422,s)
s,d=api('POST','/renumbers',op,{'name':'smoke-1','idempotency_key':'name-clash-'+RUN,'moves':[{'from':301,'to':971}]})
check('批次重名 409',s==409,(s,d))

# 3. 互换
s,d=renumber(op,'swap-'+RUN,'k-swap-'+RUN,[(101,202),(202,101)])
ok=s==200 and d['status']=='applied' and all(m['state']=='applied' for m in d['moves'])
check('互换：整批生效',ok,(s,d))
check('互换：101 拿到原 202 的账单内容',row(101)==snap0[202],row(101))
check('互换：202 拿到原 101 的账单内容',row(202)==snap0[101],row(202))

# 4. 链式腾出号
s,d=renumber(op,'chain-'+RUN,'k-chain-'+RUN,[(103,104),(104,105),(105,961)])
ok=s==200 and d['status']=='applied'
check('链式腾出号：整批生效',ok,(s,d))
check('链式：104=原103、105=原104、961=原105、103 已腾出',row(104)==snap0[103] and row(105)==snap0[104] and row(961)==snap0[105] and row(103) is None,(row(104),row(105),row(961),row(103)))

# 5. 冲突退回（目标号被批外账单占用；同批其他明细一并退回）
before106,before107,before108=row(106),row(107),row(108)
s,d=renumber(op,'conflict-'+RUN,'k-conflict-'+RUN,[(106,107),(108,969)])
ok=s==200 and d['status']=='rejected'
conf=[m for m in d['moves'] if m['state']=='conflict'];skip=[m for m in d['moves'] if m['state']=='skipped']
check('冲突退回：整批 rejected',ok,(s,d))
check('冲突退回：标出冲突号 107，其余随批退回',len(conf)==1 and conf[0]['to']==107 and len(skip)==1 and skip[0]['to']==969,d['moves'])
check('冲突退回：账单未改动',row(106)==before106 and row(107)==before107 and row(108)==before108 and row(969) is None,(row(106),row(107),row(108),row(969)))
s2,d2=api('GET','/renumbers/'+str(d['id']),viewer)
check('冲突结论可查询（含 viewer）',s2==200 and d2['status']=='rejected' and d2['moves']==d['moves'],(s2,d2))

# 6. 空号生效
s,d=renumber(op,'vacant-'+RUN,'k-vacant-'+RUN,[(108,962)])
check('空号：整批生效',s==200 and d['status']=='applied',(s,d))
check('空号：962=原108、108 已腾出',row(962)==snap0[108] and row(108) is None,(row(962),row(108)))

# 7. 并发争空号：同一空号只准一批生效
barrier=threading.Barrier(3);outcomes={}
def contend(tag,mv):
    barrier.wait();outcomes[tag]=renumber(op,'race-'+tag+'-'+RUN,'k-race-'+tag+'-'+RUN,[mv])
t1=threading.Thread(target=contend,args=('a',(109,963)));t2=threading.Thread(target=contend,args=('b',(110,963)))
t1.start();t2.start();barrier.wait();t1.join();t2.join()
stats=[o[1]['status'] for o in outcomes.values()]
check('并发争空号：恰好一批生效、一批退回',sorted(stats)==['applied','rejected'],outcomes)
winner='a' if outcomes['a'][1]['status']=='applied' else 'b'
loser_src=110 if winner=='a' else 109
check('并发争空号：963 归胜方、败方源号未动',row(963)==snap0[109 if winner=='a' else 110] and row(loser_src)==snap0[loser_src],(winner,row(963),row(loser_src)))
rej=outcomes['b' if winner=='a' else 'a'][1]
check('并发争空号：败方明细标出冲突号 963',any(m['state']=='conflict' and m['to']==963 for m in rej['moves']),rej['moves'])

# 8. 并发无关批次：照常写
barrier2=threading.Barrier(3);out2={}
def disjoint(tag,mv):
    barrier2.wait();out2[tag]=renumber(op,'free-'+tag+'-'+RUN,'k-free-'+tag+'-'+RUN,[mv])
t1=threading.Thread(target=disjoint,args=('a',(111,964)));t2=threading.Thread(target=disjoint,args=('b',(112,965)))
t1.start();t2.start();barrier2.wait();t1.join();t2.join()
check('无关账单照常写：两批都生效',all(o[1]['status']=='applied' for o in out2.values()),out2)
check('无关账单照常写：964=原111、965=原112',row(964)==snap0[111] and row(965)==snap0[112],(row(964),row(965)))

# 9. 落库后断线：重试不重复调号，原结论可查
key='k-drop-'+RUN;payload=json.dumps({'name':'drop-'+RUN,'idempotency_key':key,'moves':[{'from':113,'to':966}]}).encode()
req=(f'POST /renumbers HTTP/1.1\r\nHost: 127.0.0.1:8000\r\nAuthorization: Bearer {op}\r\nContent-Type: application/json\r\nContent-Length: {len(payload)}\r\nConnection: close\r\n\r\n').encode()+payload
sock=socket.create_connection(('127.0.0.1',8000));sock.sendall(req);sock.close()  # 客户端立即断线，不等响应
time.sleep(2)
s,d=renumber(op,'drop-'+RUN,key,[(113,966)])  # 断线重试
check('断线重试：返回结论且批次唯一',s==200 and d['status']=='applied',(s,d))
ident=d['id']
s,d3=renumber(op,'drop-'+RUN,key,[(113,966)])
check('断线重试：再次重试命中幂等，同一批次',s==200 and d3['id']==ident and d3['deduplicated'] is True,(s,d3))
_,allb=api('GET','/renumbers',op)
check('断线重试：该幂等键只落库一次',len([b for b in allb if b['idempotency_key']==key])==1,key)
check('断线重试：113 只被调走一次，966=原113',row(113) is None and row(966)==snap0[113],(row(113),row(966)))
s,d4=api('GET','/renumbers/'+str(ident),op)
check('断线重试：原结论仍可查询',s==200 and d4['status']=='applied' and d4['moves'][0]['from']==113,(s,d4))

# 10. 两侧查询读同一版号码（REPEATABLE READ 快照）
conn=psycopg2.connect(host='127.0.0.1',port=15432,user='app',password='local_demo_4101',dbname='query_review')
conn.autocommit=True;cur=conn.cursor()
cur.execute('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY')
cur.execute('SELECT invoice_id FROM invoices WHERE invoice_id IN (120,121) ORDER BY 1');side1=[r[0] for r in cur.fetchall()]
s,d=renumber(op,'ver-'+RUN,'k-ver-'+RUN,[(120,967),(121,968)])
check('调号在另一事务提交',s==200 and d['status']=='applied',(s,d))
cur.execute('SELECT invoice_id FROM invoices WHERE invoice_id IN (120,121) ORDER BY 1');side2=[r[0] for r in cur.fetchall()]
cur.execute('SELECT invoice_id FROM invoices WHERE invoice_id IN (967,968) ORDER BY 1');side2new=[r[0] for r in cur.fetchall()]
cur.execute('COMMIT')
check('同一事务内两侧读同一版号码（不受并发调号影响）',side1==side2==[120,121] and side2new==[],(side1,side2,side2new))
cur.execute('SELECT invoice_id FROM invoices WHERE invoice_id IN (967,968) ORDER BY 1');after=[r[0] for r in cur.fetchall()]
check('提交后新事务读到新版号码',after==[967,968],after)
conn.close()

# 11. 旧证据保留原号码；新复核两侧读同一版新号
s,samples=api('GET','/samples',op)
sample=next((x for x in samples if x['name']=='调号一致性样本'),None)
if not sample:
    s,sample=api('POST','/samples',op,{'name':'调号一致性样本','description':'验证调号前后证据口径','original_sql':'SELECT invoice_id, customer, amount FROM invoices WHERE invoice_id IN (120,121) ORDER BY invoice_id'})
check('登记一致性样本',s in (200,201),(s,sample))
def run_review(name,sample_id,sql_text):
    s,b=api('POST','/batches',op,{'name':name,'sample_id':sample_id,'candidate_sql':sql_text})
    assert s in (200,201,202),(s,b)
    for _ in range(60):
        time.sleep(1)
        _,bs=api('GET','/batches',op)
        cur=next(x for x in bs if x['id']==b['id'])
        if cur['status'] in ('passed','different','failed'):return cur
    raise TimeoutError('worker timeout')
# 注意：120/121 已在第 10 步被调走，先调回，保证证据里是原号码
s,d=renumber(op,'ver-restore-'+RUN,'k-ver-restore-'+RUN,[(967,120),(968,121)])
check('调回 120/121 以备旧证据',s==200 and d['status']=='applied',(s,d))
b1=run_review('ev-before-'+RUN,sample['id'],'SELECT invoice_id, customer, amount FROM invoices WHERE invoice_id IN (120,121) ORDER BY invoice_id')
_,ev1=api('GET','/evidence/'+str(b1['id']),op)
ids1=[r[0] for r in ev1['result']['original']['rows']]
check('旧证据生成：两侧一致且含原号码 120/121',b1['status']=='passed' and ids1==['120','121'] and ev1['result']['equivalent'],(b1['status'],ids1))
s,d=renumber(op,'ev-move-'+RUN,'k-ev-move-'+RUN,[(120,967),(121,968)])
check('再次调走 120/121',s==200 and d['status']=='applied',(s,d))
_,ev1b=api('GET','/evidence/'+str(b1['id']),op)
ids1b=[r[0] for r in ev1b['result']['original']['rows']]
check('旧证据保留原号码（不回改）',ids1b==['120','121'],ids1b)
s,sample2=api('POST','/samples',op,{'name':'调号一致性样本-新号-'+RUN,'description':'调号后按新号码复核','original_sql':'SELECT invoice_id, customer, amount FROM invoices WHERE invoice_id IN (967,968) ORDER BY invoice_id'})
check('登记新号样本',s in (200,201),(s,sample2))
b2=run_review('ev-after-'+RUN,sample2['id'],'SELECT invoice_id, customer, amount FROM invoices WHERE invoice_id IN (967,968) ORDER BY invoice_id')
_,ev2=api('GET','/evidence/'+str(b2['id']),op)
lo=[r[0] for r in ev2['result']['original']['rows']];lc=[r[0] for r in ev2['result']['candidate']['rows']]
check('新复核两侧读同一版新号码 967/968 且一致',b2['status']=='passed' and lo==lc==['967','968'] and ev2['result']['equivalent'],(b2['status'],lo,lc))

# 12. 审计留痕
s,logs=api('GET','/audit',admin)
check('审计记录调号写操作',s==200 and any('POST /renumbers' in x['action'] for x in logs),s)

# 13. 还原演示数据并全量校验
restore=[(202,101),(101,202)]  # 先换回互换（当前 101=原202, 202=原101）
s,d=renumber(op,'restore-swap-'+RUN,'k-restore-swap-'+RUN,restore)
r1=s==200 and d['status']=='applied'
s,d=renumber(op,'restore-chain-'+RUN,'k-restore-chain-'+RUN,[(104,103),(105,104),(961,105)])
r2=s==200 and d['status']=='applied'
moves_back=[(962,108),(963,109 if winner=='a' else 110),(964,111),(965,112),(966,113),(967,120),(968,121)]
s,d=renumber(op,'restore-misc-'+RUN,'k-restore-misc-'+RUN,moves_back)
r3=s==200 and d['status']=='applied'
check('还原批次全部生效',r1 and r2 and r3,(r1,r2,r3))
snap1=snapshot()
diff={k for k in snap0 if snap0[k]!=snap1.get(k)}|{k for k in snap1 if k not in snap0}
check('演示数据全量还原（600 条与初始一致）',len(diff)==0,sorted(diff)[:10])

failed=[r for r in results if not r[1]]
print('\n==== 汇总：%d 项通过，%d 项失败 ===='%(len(results)-len(failed),len(failed)))
for name,ok,detail in failed:print('FAIL:',name,detail)
raise SystemExit(1 if failed else 0)
