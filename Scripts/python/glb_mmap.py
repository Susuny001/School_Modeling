"""Low-RAM actual GLB buffer reader. Never returns/generated geometry from a script."""
from pathlib import Path
import mmap,json,struct,numpy as np
class ActualGLB:
 def __init__(self,path):
  self.path=Path(path);self.file=self.path.open('rb');self.mm=mmap.mmap(self.file.fileno(),0,access=mmap.ACCESS_READ);assert struct.unpack_from('<I',self.mm,0)[0]==0x46546c67;n,t=struct.unpack_from('<II',self.mm,12);assert t==0x4e4f534a;self.J=json.loads(self.mm[20:20+n]);self.binstart=20+n+8;self.G={}
  for m in self.J['meshes']:
   for p in m['primitives']:self.G[self.J['materials'][p['material']]['name']]=(self.acc(p['attributes']['POSITION']),self.acc(p['indices']).reshape(-1,3))
 def acc(self,i):
  a=self.J['accessors'][i];v=self.J['bufferViews'][a['bufferView']];dt={5126:'<f4',5125:'<u4',5123:'<u2'}[a['componentType']];d={'SCALAR':1,'VEC3':3}[a['type']];r=np.frombuffer(self.mm,dtype=dt,count=a['count']*d,offset=self.binstart+v.get('byteOffset',0)+a.get('byteOffset',0));return r.reshape(-1,d)if d>1 else r