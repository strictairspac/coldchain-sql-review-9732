"""Static frontend + /api proxy for local UI testing (mirrors nginx.conf: /api/ strips prefix)."""
import http.server,urllib.request,urllib.error
class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self,*a,**k):super().__init__(*a,directory='/workspace/frontend',**k)
    def do_GET(self):
        if self.path.startswith('/api/'):self.proxy()
        else:super().do_GET()
    def do_POST(self):self.proxy()
    def proxy(self):
        body=None
        if self.headers.get('Content-Length'):body=self.rfile.read(int(self.headers['Content-Length']))
        req=urllib.request.Request('http://127.0.0.1:8000'+self.path[4:],data=body,method=self.command)
        for h in ('Content-Type','Authorization'):
            if self.headers.get(h):req.add_header(h,self.headers[h])
        try:
            with urllib.request.urlopen(req) as r:data,code,ct=r.read(),r.status,r.headers.get('Content-Type')
        except urllib.error.HTTPError as e:data,code,ct=e.read(),e.code,e.headers.get('Content-Type')
        self.send_response(code);self.send_header('Content-Type',ct or 'application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    def log_message(self,*a):pass
http.server.ThreadingHTTPServer(('127.0.0.1',8080),H).serve_forever()
