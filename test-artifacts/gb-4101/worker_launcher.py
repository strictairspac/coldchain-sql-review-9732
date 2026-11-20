"""Run the real worker locally: only the /artifacts path is redirected to /tmp/artifacts
(the sandbox cannot create /artifacts; docker mounts a volume there). Logic unchanged."""
import pathlib,sys
class P(pathlib.PosixPath):
    def __new__(cls,*a):
        a=tuple(x.replace('/artifacts','/tmp/artifacts') if isinstance(x,str) else x for x in a)
        return super().__new__(cls,*a)
pathlib.Path=P
sys.path.insert(0,'/workspace/backend')
import src.worker
