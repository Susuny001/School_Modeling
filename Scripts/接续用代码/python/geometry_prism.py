"""Shared closed-prism construction, including holes and float32 closure checks."""
import numpy as np
import trimesh
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient
from shapely import constrained_delaunay_triangles

def closed_prism(poly,height,z,delta=(0.,0.,0.)):
    delta=np.asarray(delta,float)
    def snap(ring):
        a=np.asarray(ring.coords,float);a=(a+delta[:2]).astype(np.float32).astype(float)-delta[:2]
        return a
    src=[]
    def collect(p):
        if p.geom_type=='Polygon':
            if not p.is_empty and p.area>1e-12:src.append(p)
        elif hasattr(p,'geoms'):
            for child in p.geoms:collect(child)
    collect(poly)
    assert src,'No positive-area polygon to extrude'
    shapes=[]
    for p in src:
        q=Polygon(snap(p.exterior),[snap(r) for r in p.interiors])
        if not q.is_valid:q=q.buffer(0)
        shapes.extend([q] if q.geom_type=='Polygon' else list(q.geoms))
    verts=[];faces=[];lookup={}
    def vid(xy,top):
        v=(float(xy[0]),float(xy[1]),float(np.float32(z+height if top else z)))
        if v not in lookup:lookup[v]=len(verts);verts.append(v)
        return lookup[v]
    for shape in shapes:
        if shape.is_empty:continue
        shape=orient(shape,sign=1.)
        for tri in constrained_delaunay_triangles(shape).geoms:
            p=np.asarray(tri.exterior.coords,float)[:3]
            area=(p[1,0]-p[0,0])*(p[2,1]-p[0,1])-(p[1,1]-p[0,1])*(p[2,0]-p[0,0])
            assert area!=0,'Exact zero cap triangle'
            if area<0:p=p[::-1]
            faces.append([vid(q,True) for q in p]);faces.append([vid(q,False) for q in p[::-1]])
        for ring in [shape.exterior,*shape.interiors]:
            co=np.asarray(ring.coords,float)
            for a,c in zip(co[:-1],co[1:]):
                if np.array_equal(a,c):continue
                ia,ic,ta,tc=vid(a,False),vid(c,False),vid(a,True),vid(c,True)
                faces.extend([[ia,ic,tc],[ia,tc,ta]])
    mesh=trimesh.Trimesh(np.asarray(verts),np.asarray(faces),process=False)
    actual=(mesh.vertices+delta).astype(np.float32).astype(float);v,inv=np.unique(actual,axis=0,return_inverse=True)
    tested=trimesh.Trimesh(v,inv[mesh.faces],process=False)
    assert np.all(tested.area_faces>0),'Zero faces after actual float32 export'
    assert tested.is_watertight and tested.is_winding_consistent and tested.volume>0,'Open or inverted actual float32 prism'
    return mesh
