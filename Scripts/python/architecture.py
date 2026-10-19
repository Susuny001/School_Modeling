"""Editable architectural solids, apertures and stairs for Blender batch workflows.

Coordinates are metres; every returned mesh is a separate item with a local pivot.
No scene is modified until a function is called.
"""
import math
import bpy
import numpy as np
from mathutils import Vector
from shapely.geometry import box as rect
from geometry_prism import closed_prism


def material(name, color, roughness=.65, metallic=0., alpha=1.):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.diffuse_color = (*color, alpha)
    mat.use_nodes = True
    node = mat.node_tree.nodes.get('Principled BSDF')
    node.inputs['Base Color'].default_value = (*color, 1.)
    node.inputs['Roughness'].default_value = roughness
    node.inputs['Metallic'].default_value = metallic
    node.inputs['Alpha'].default_value = alpha
    if alpha < 1:
        mat.surface_render_method = 'DITHERED'
    return mat


def mesh_item(name, vertices, faces, mat, parent=None):
    vv = np.asarray(vertices, dtype=float)
    pivot = np.r_[vv[:, :2].mean(0), vv[:, 2].min()]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata((vv-pivot).tolist(), [], np.asarray(faces).tolist())
    mesh.materials.append(mat)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.parent = parent
    obj.location = pivot
    obj['independently_editable'] = True
    return obj


def solid(name, polygon, bottom, height, mat, parent=None):
    tri = closed_prism(polygon, height, bottom)
    return mesh_item(name, tri.vertices, tri.faces, mat, parent)


def box(name, lo, hi, mat, parent=None):
    x,y,z = lo; X,Y,Z = hi
    if min(X-x,Y-y,Z-z) <= 0:
        raise ValueError('Box dimensions must be positive')
    v = [(x,y,z),(X,y,z),(X,Y,z),(x,Y,z),(x,y,Z),(X,y,Z),(X,Y,Z),(x,Y,Z)]
    f = [(0,2,1),(0,3,2),(4,5,6),(4,6,7),(0,1,5),(0,5,4),
         (1,2,6),(1,6,5),(2,3,7),(2,7,6),(3,0,4),(3,4,7)]
    return mesh_item(name,v,f,mat,parent)


def wall(name, axis, plane, start, end, bottom, top, thickness, apertures, mat, parent=None):
    """Solid wall with actual through openings (u0,z0,u1,z1). axis is x=0/y=1."""
    shape = rect(start,bottom,end,top)
    for u0,z0,u1,z1 in apertures:
        shape = shape.difference(rect(u0,z0,u1,z1))
    tri = closed_prism(shape, thickness, plane-thickness/2)
    # Map local (u,z,depth) to a right-handed world frame.
    v = tri.vertices[:,[2,0,1]] if axis == 0 else tri.vertices[:,[0,2,1]]
    faces = tri.faces if axis == 0 else tri.faces[:,::-1]
    return mesh_item(name,v,faces,mat,parent)


def beam(name, a, b, width, mat, parent=None):
    a,b = Vector(a),Vector(b); direction=b-a
    helper=Vector((0,0,1)) if abs(direction.normalized().z)<.9 else Vector((1,0,0))
    u=direction.cross(helper).normalized()*width/2;v=direction.normalized().cross(u).normalized()*width/2
    pts=[tuple(p+su*u+sv*v) for p in [a,b] for su,sv in [(-1,-1),(1,-1),(1,1),(-1,1)]]
    faces=[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    return mesh_item(name,pts,faces,mat,parent)


def window(name, axis, plane, u0,u1,z0,z1, frame, glass, parent=None, columns=2, rows=2):
    """Thin glazing and individual frame members; no opaque backing panel."""
    def part(s,a,b,c,d,depth,mat):
        lo=[plane-depth/2,a,c] if axis==0 else [a,plane-depth/2,c]
        hi=[plane+depth/2,b,d] if axis==0 else [b,plane+depth/2,d]
        return box(name+s,lo,hi,mat,parent)
    part('_glazing',u0+.035,u1-.035,z0+.035,z1-.035,.015,glass)
    for i in range(columns+1):
        u=u0+(u1-u0)*i/columns
        part('_mullion_%02d'%i,u-.025,u+.025,z0,z1,.11,frame)
    for i in range(rows+1):
        z=z0+(z1-z0)*i/rows
        part('_transom_%02d'%i,u0,u1,z-.025,z+.025,.11,frame)


def u_stair(name, x0,y0,width,length,bottom,top, concrete, metal,parent=None):
    """Two opposed flights, real treads, intermediate/top landings and handrails.

    The upper floor opening must cover x0..x0+width, y0+1..y0+length.
    The top landing is at the starting end. Returns its void bounds and rise.
    """
    steps=math.ceil((top-bottom)/.18)
    steps += steps%2
    n=steps//2;rise=(top-bottom)/steps
    run=(length-2.1)/n;flight=(width-.18)/2
    box(name+'_lower_landing',(x0,y0,bottom-.15),(x0+width,y0+1.05,bottom),concrete,parent)
    mid=bottom+(top-bottom)/2
    box(name+'_half_landing',(x0,y0+length-1.05,mid-.16),(x0+width,y0+length,mid),concrete,parent)
    box(name+'_upper_landing',(x0,y0,top-.16),(x0+width,y0+1.05,top),concrete,parent)
    for flight_i in range(2):
        xa=x0 if flight_i==0 else x0+flight+.18
        for j in range(n):
            z=bottom+(flight_i*n+j+1)*rise
            ya=y0+1.05+j*run if flight_i==0 else y0+length-1.05-(j+1)*run
            box(name+f'_flight{flight_i+1}_tread{j+1:02d}',(xa,ya,z-.18),(xa+flight,ya+run+.008,z),concrete,parent)
        # Continuous structural waist below each flight.
        start=(xa+flight/2,y0+1.05,bottom-.12) if flight_i==0 else (xa+flight/2,y0+length-1.05,mid-.12)
        finish=(xa+flight/2,y0+length-1.05,mid-.12) if flight_i==0 else (xa+flight/2,y0+1.05,top-.12)
        a,b=Vector(start),Vector(finish)
        vs=[tuple(p+Vector((dx,0,dz))) for p in [a,b] for dx,dz in [(-flight/2,-.12),(flight/2,-.12),(flight/2,.02),(-flight/2,.02)]]
        mesh_item(name+f'_waist{flight_i}',vs,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],concrete,parent)
        for edge,xx in enumerate([xa+.045,xa+flight-.045]):
            p=a.copy();q=b.copy();p.x=q.x=xx;p.z+=1.05;q.z+=1.05
            beam(name+f'_rail{flight_i}_{edge}',p,q,.045,metal,parent)
            for j in range(0,n+1,2):
                u=j/n;v=a.lerp(b,u);v.x=xx
                beam(name+f'_baluster{flight_i}_{edge}_{j}',v+Vector((0,0,.12)),v+Vector((0,0,1.05)),.026,metal,parent)
    return dict(void=(x0,y0+1.05,x0+width,y0+length),rise=rise,tread=run,steps=steps)
