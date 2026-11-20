"""Minimal RESP server for local testing only (no Redis in this sandbox).
Implements exactly what the app uses: PING, CLIENT/SELECT/CONFIG/QUIT, RPUSH, LPUSH, BLPOP, LLEN.
"""
import socket,threading,time
class Store:
    def __init__(self):self.lists={};self.cond=threading.Condition()
store=Store()
def read_cmd(f):
    line=f.readline()
    if not line:return None
    line=line.rstrip(b'\r\n')
    if not line:return None
    if line.startswith(b'*'):
        args=[]
        for _ in range(int(line[1:])):
            hdr=f.readline();data=f.read(int(hdr[1:]));f.read(2);args.append(data)
        return args
    return line.split()
def bulk(x):return b'$'+str(len(x)).encode()+b'\r\n'+x+b'\r\n'
def handle(conn):
    f=conn.makefile('rb')
    while True:
        try:args=read_cmd(f)
        except Exception:break
        if not args:break
        cmd=args[0].upper()
        try:
            if cmd==b'PING':out=b'+PONG\r\n'
            elif cmd in (b'CLIENT',b'SELECT',b'CONFIG',b'SET',b'RESET'):out=b'+OK\r\n'
            elif cmd in (b'RPUSH',b'LPUSH'):
                key=args[1]
                with store.cond:
                    lst=store.lists.setdefault(key,[])
                    if cmd==b'RPUSH':lst.extend(args[2:])
                    else:
                        for v in args[2:]:lst.insert(0,v)
                    store.cond.notify_all();out=b':'+str(len(lst)).encode()+b'\r\n'
            elif cmd==b'LLEN':
                with store.cond:out=b':'+str(len(store.lists.get(args[1],[]))).encode()+b'\r\n'
            elif cmd==b'BLPOP':
                timeout=float(args[-1]);keys=args[1:-1];deadline=time.time()+timeout;out=None
                with store.cond:
                    while True:
                        hit=next((k for k in keys if store.lists.get(k)),None)
                        if hit is not None:
                            v=store.lists[hit].pop(0);out=b'*2\r\n'+bulk(hit)+bulk(v);break
                        remain=deadline-time.time()
                        if timeout and remain<=0:out=b'*-1\r\n';break
                        store.cond.wait(remain if timeout else 1)
            elif cmd==b'QUIT':out=b'+OK\r\n'
            else:out=b'-ERR unknown command\r\n'
        except Exception as e:out=b'-ERR '+str(e).encode()[:120]+b'\r\n'
        try:conn.sendall(out)
        except Exception:break
        if cmd==b'QUIT':break
    conn.close()
def serve(port):
    s=socket.socket();s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    s.bind(('127.0.0.1',port));s.listen(50)
    print('mini-redis on',port,flush=True)
    while True:
        c,_=s.accept();threading.Thread(target=handle,args=(c,),daemon=True).start()
if __name__=='__main__':serve(16379)
