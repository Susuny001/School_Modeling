"""Shared mesh extraction, primitive and triangle-clipping functions. No scene launcher."""
import numpy as np
import trimesh
from shapely.geometry import Polygon
from shapely import constrained_delaunay_triangles

def cub(ext,center):
 m=trimesh.creation.box(extents=ext);m.apply_translation(center);return m

def getparts(r,G):
 ps=[]
 for p in r['parts']:
  v,f=G[p['material']];ff=np.concatenate([f[a:a+n]for a,n in p['face_runs']]);u,inv=np.unique(ff.ravel(),return_inverse=True);ps.append((p['material'],v[u].copy(),inv.reshape(-1,3).astype('<u4')))
 return ps

def polys(p):
 if p.geom_type=='Polygon':return[p]if not p.is_empty and p.area>1e-10 else[]
 return[q for q in getattr(p,'geoms',[])if q.geom_type=='Polygon'and not q.is_empty and q.area>1e-10]

def flat_cut(ps,axis,plane,cut):
 """Subtract from only the selected planar faces; untouched triangles stay exact."""
 out=[];ax=[j for j in range(3)if j!=axis]
 for k,v,f in ps:
  tri=v[f];pick=np.all(abs(tri[:,:,axis]-plane)<1e-4,axis=1);ret=[tri[~pick]]
  for t in tri[pick]:
   p=Polygon(t[:,ax]);rest=p.difference(cut)
   if abs(p.area-rest.area)<1e-10:ret.append(t[None]);continue
   norm=np.cross(t[1]-t[0],t[2]-t[0])
   for poly in polys(rest):
    for q in constrained_delaunay_triangles(poly).geoms:
     xy=np.asarray(q.exterior.coords)[:3];nt=np.zeros((3,3));nt[:,ax]=xy;nt[:,axis]=plane
     if np.cross(nt[1]-nt[0],nt[2]-nt[0])@norm<0:nt=nt[::-1]
     ret.append(nt[None])
  vv=np.concatenate(ret).reshape(-1,3);ff=np.arange(len(vv)).reshape(-1,3)
  if len(ff):out.append((k,vv,ff))
 return out

def subtract_volume(ps,lower,upper):
 out=[];lower=np.asarray(lower);upper=np.asarray(upper)
 def split(poly,axis,bound,sign):
  a=[];b=[]
  for u,v in zip(poly,np.roll(poly,-1,axis=0)):
   du=sign*(u[axis]-bound);dv=sign*(v[axis]-bound);iu=du>=-1e-9;iv=dv>=-1e-9
   (a if iu else b).append(u)
   if iu!=iv:
    q=u+(v-u)*du/(du-dv);a.append(q);b.append(q)
  return np.asarray(a),np.asarray(b)
 for k,v,f in ps:
  tri=v[f];hit=np.all(tri.max(1)>lower+1e-7,axis=1)&np.all(tri.min(1)<upper-1e-7,axis=1);chunks=[tri[~hit]]
  for t in tri[hit]:
   inside=t;outside=[]
   for axis,bound,sign in [(i,float(lower[i]),1)for i in range(3)]+[(i,float(upper[i]),-1)for i in range(3)]:
    inside,other=split(inside,axis,bound,sign)
    if len(other)>=3:
     for j in range(1,len(other)-1):outside.append(other[[0,j,j+1]])
    if len(inside)<3:break
   if outside:chunks.append(np.asarray(outside))
  ts=np.concatenate(chunks);vv=ts.reshape(-1,3);ff=np.arange(len(vv)).reshape(-1,3);area=np.linalg.norm(np.cross(ts[:,1]-ts[:,0],ts[:,2]-ts[:,0]),axis=1);ff=ff[area>1e-10]
  if len(ff):out.append((k,vv,ff))
 return out
