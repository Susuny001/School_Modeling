import math, json, struct, shutil, base64
from pathlib import Path
import numpy as np
import trimesh
from trimesh.transformations import rotation_matrix, translation_matrix
from shapely.geometry import Polygon, LineString, Point
from shapely.ops import triangulate
from shapely.affinity import rotate as shp_rotate, translate as shp_translate

OUT=Path(__file__).resolve().parent; OUT.mkdir(parents=True, exist_ok=True)

# Manually authored material palette after visual review of the footage. No video pixels, crops,
# sampled colors, extracted images, UV textures, or texture-like projected imagery are used.
COLORS={
 'ground':(77,91,64,255),'grass':(54,88,52,255),'grass2':(63,97,56,255),'grass_dark':(37,70,41,255),
 'path':(153,118,101,255),'path_light':(181,153,132,255),'plaza':(211,201,177,255),'plaza_light':(226,219,199,255),
 'plaza_dark':(76,76,72,255),'plaza_teal':(91,112,105,255),'plaza_joint':(158,151,137,255),'plaza_red':(137,62,58,255),'stone_warm':(204,194,171,255),'road':(76,79,76,255),'road2':(68,72,70,255),'curb':(187,184,175,255),
 'white':(229,228,216,255),'offwhite':(211,212,202,255),'cream':(228,224,207,255),'wall_warm':(220,216,202,255),'wall_cool':(216,220,213,255),
 'red':(123,40,39,255),'red2':(145,47,43,255),'roof':(43,42,39,255),'roof2':(61,59,55,255),'roof_patch':(79,68,58,255),'roof_fade':(70,67,61,255),
 'window':(76,104,110,255),'window_dark':(40,54,59,255),'glass':(78,113,116,255),'glass_roof':(91,128,127,255),'metal':(103,108,104,255),
 'dome':(211,214,208,255),'dome_dark':(108,114,113,255),'tree_trunk':(88,64,45,255),
 'tree_leaf':(43,79,43,255),'tree_leaf2':(54,91,49,255),'tree_leaf3':(69,104,56,255),
 'track':(128,54,58,255),'track_apron':(53,104,88,255),'field':(47,96,57,255),'field2':(59,111,66,255),'court':(180,169,151,255),'court_joint':(151,144,132,255),'court_line':(226,225,210,255),
 'green_metal':(63,139,88,255),'blue':(76,110,143,255),'dark':(40,42,41,255),'stone':(219,218,207,255),
 'gold':(166,135,56,255),'car_white':(208,208,199,255),'car_dark':(45,48,48,255),'car_red':(133,44,42,255),
 'brick':(139,72,65,255),'brick2':(156,84,74,255),'brick3':(119,64,59,255),'ac_body':(201,203,196,255),'ac_grill':(72,77,76,255),
 'admin_wall':(143,145,141,255),'admin_wall2':(112,115,112,255),'admin_trim':(154,154,148,255),
 'glass_blue':(67,108,124,255),'glass_light':(132,158,163,255),'glass_silver':(158,176,178,255),'flag_red':(198,32,40,255),'flagpole':(220,224,225,255),
 'admin_light':(164,166,162,255),'admin_pale':(188,190,185,255),'mountain':(61,87,62,255),'mountain2':(72,100,68,255),'urban':(181,185,181,255),'urban_dark':(126,133,134,255)
}

class Builder:
    def __init__(self): self.groups={}; self.counts={}; self.active_transform=np.eye(4)
    def set_transform(self, M=None): self.active_transform=np.eye(4) if M is None else np.asarray(M,float)
    def reset_transform(self): self.active_transform=np.eye(4)
    def add(self,mesh,key,transform=None):
        if mesh is None or len(mesh.faces)==0:return
        mesh=mesh.copy()
        T=self.active_transform if transform is None else self.active_transform@transform
        if not np.allclose(T,np.eye(4)): mesh.apply_transform(T)
        self.groups.setdefault(key,[]).append(mesh); self.counts[key]=self.counts.get(key,0)+1
    def box(self,extents,center,key,rotz=0,rotx=0,roty=0):
        m=trimesh.creation.box(extents=extents); T=translation_matrix(center)
        if rotz:T=T@rotation_matrix(math.radians(rotz),[0,0,1])
        if roty:T=T@rotation_matrix(math.radians(roty),[0,1,0])
        if rotx:T=T@rotation_matrix(math.radians(rotx),[1,0,0])
        self.add(m,key,T)
    def cyl(self,radius,height,center,key,sections=24,rotz=0,rotx=0,roty=0):
        m=trimesh.creation.cylinder(radius=radius,height=height,sections=sections); T=translation_matrix(center)
        if rotz:T=T@rotation_matrix(math.radians(rotz),[0,0,1])
        if roty:T=T@rotation_matrix(math.radians(roty),[0,1,0])
        if rotx:T=T@rotation_matrix(math.radians(rotx),[1,0,0])
        self.add(m,key,T)
    def sphere(self,radius,center,key,subdivisions=1,scale=(1,1,1)):
        m=trimesh.creation.icosphere(subdivisions=subdivisions,radius=radius); S=np.eye(4);S[0,0],S[1,1],S[2,2]=scale
        self.add(m,key,translation_matrix(center)@S)
    def extrude(self,poly,height,z,key):
        if not poly.is_valid: poly=poly.buffer(0)
        if poly.is_empty:return
        tris=[]; geoms=list(poly.geoms) if poly.geom_type=='MultiPolygon' else [poly]
        for g in geoms:
            for t in triangulate(g):
                if g.covers(t.representative_point()):tris.append(t)
        if not tris:return
        vmap={}; verts=[]; faces=[]
        def vid(pt):
            k=(round(pt[0],8),round(pt[1],8))
            if k not in vmap:vmap[k]=len(verts);verts.append([pt[0],pt[1]])
            return vmap[k]
        for t in tris:
            c=list(t.exterior.coords)[:3];faces.append([vid(x) for x in c])
        try:m=trimesh.creation.extrude_triangulation(np.asarray(verts,float),np.asarray(faces,int),height=height)
        except Exception:return
        m.apply_translation((0,0,z));self.add(m,key)
    def cylinder_between(self,a,b,r,key,sections=8):
        a=np.array(a,float);b=np.array(b,float);v=b-a;L=np.linalg.norm(v)
        if L<1e-8:return
        m=trimesh.creation.cylinder(radius=r,height=L,sections=sections);d=v/L;z=np.array([0.,0.,1.]);axis=np.cross(z,d);dot=float(np.clip(np.dot(z,d),-1,1))
        T=translation_matrix((a+b)/2)
        if np.linalg.norm(axis)>1e-8:T=T@rotation_matrix(math.acos(dot),axis)
        elif dot<0:T=T@rotation_matrix(math.pi,[1,0,0])
        self.add(m,key,T)
    def finalize(self):
        scene=trimesh.Scene(); stats={}
        for key,arr in self.groups.items():
            m=arr[0] if len(arr)==1 else trimesh.util.concatenate(arr)
            rgba=COLORS[key]
            metallic = 0.92 if key=='flagpole' else (0.18 if key in ('metal','green_metal','glass','glass_blue','glass_light','glass_silver') else 0.0)
            roughness = 0.16 if key=='flagpole' else (0.30 if key in ('glass','glass_blue','glass_light','glass_silver','window','window_dark') else 0.74)
            mat=trimesh.visual.material.PBRMaterial(name=key,baseColorFactor=[c/255 for c in rgba],metallicFactor=metallic,roughnessFactor=roughness)
            m.visual=trimesh.visual.TextureVisuals(material=mat)
            scene.add_geometry(m,node_name=key,geom_name=key)
            stats[key]={'parts':len(arr),'vertices':int(len(m.vertices)),'faces':int(len(m.faces))}
        return scene,stats
b=Builder()

def sector_polygon(r0,r1,a0,a1,n=80,center=(0,0)):
    aa=np.linspace(math.radians(a0),math.radians(a1),n)
    outer=[(center[0]+r1*math.cos(a),center[1]+r1*math.sin(a)) for a in aa]
    inner=[(center[0]+r0*math.cos(a),center[1]+r0*math.sin(a)) for a in aa[::-1]]
    return Polygon(outer+inner)
def ellipse_poly(cx,cy,rx,ry,n=140): return Polygon([(cx+rx*math.cos(t),cy+ry*math.sin(t)) for t in np.linspace(0,2*math.pi,n,endpoint=False)])
def ring(r0,r1,z,key,h=.10,segments=128,center=(0,0)):
    m=trimesh.creation.annulus(r_min=r0,r_max=r1,height=h,sections=segments);m.apply_translation((center[0],center[1],z+h/2));b.add(m,key)

def gable_roof(cx,cy,L,W,z,rotz,key='red2',rise=None):
    rise=rise if rise is not None else W*.34
    v=np.array([[-L/2,-W/2,0],[L/2,-W/2,0],[L/2,W/2,0],[-L/2,W/2,0],[-L/2,0,rise],[L/2,0,rise]],float)
    f=np.array([[0,1,5],[0,5,4],[3,4,5],[3,5,2],[0,4,3],[1,2,5]])
    m=trimesh.Trimesh(v,f,process=False); b.add(m,key,translation_matrix((cx,cy,z))@rotation_matrix(math.radians(rotz),[0,0,1]))

def add_tree(x,y,scale=1.0,variant=0):
    th=3.4*scale;b.cyl(.20*scale,th,(x,y,th/2),'tree_trunk',sections=8)
    # irregular layered crown rather than a single sphere
    offs=[(0,0,1.5),(1.05,.1,1.15),(-.8,.7,1.0),(.3,-.95,1.0),(-.3,-.4,2.0)]
    for k,(ox,oy,oz) in enumerate(offs):
        key=('tree_leaf','tree_leaf2','tree_leaf3')[(k+variant)%3]
        b.sphere(1.55*scale,(x+ox*scale,y+oy*scale,th+oz*scale),key,subdivisions=1,scale=(1.05,.95,.85))

def add_shrub(x,y,s=.55): b.sphere(s,(x,y,.50*s+0.25),'tree_leaf2',subdivisions=1,scale=(1.25,1,.70))

def add_ac_unit(cx,cy,z,rotz,normal=(0,1),scale=1.0):
    """Small wall-mounted condenser represented as geometry, including front grille and brackets."""
    nx,ny=normal
    b.box((1.05*scale,.48*scale,.70*scale),(cx,cy,z),'ac_body',rotz=rotz)
    # front grille is a dark inset plate plus pale ribs; no decal/texture.
    fx=cx+nx*.255*scale; fy=cy+ny*.255*scale
    b.box((.68*scale,.035*scale,.46*scale),(fx,fy,z+.01*scale),'ac_grill',rotz=rotz)
    th=math.radians(rotz);ux=np.array([math.cos(th),math.sin(th)])
    for du in [-.25,-.125,0,.125,.25]:
        q=np.array([fx,fy])+ux*(du*scale);b.box((.025*scale,.055*scale,.39*scale),(q[0],q[1],z+.01*scale),'ac_body',rotz=rotz)
    # two steel support brackets below the box.
    for du in [-.34,.34]:
        q=np.array([cx,cy])+ux*(du*scale)
        b.box((.06*scale,.55*scale,.07*scale),(q[0],q[1],z-.43*scale),'metal',rotz=rotz)

def add_brick_strip(center,L,z0,z1,rotz=0,side_offset=0.0,rows=12,cols=8):
    """Relief brick courses for source-visible red masonry zones; each brick is separate geometry."""
    cx,cy=center;th=math.radians(rotz);ux=np.array([math.cos(th),math.sin(th)]);uy=np.array([-math.sin(th),math.cos(th)])
    h=(z1-z0)/rows; bw=L/cols
    for r in range(rows):
        shift=(bw*.5 if r%2 else 0)
        for c in range(cols+1):
            u=-L/2+c*bw+shift
            if u<-L/2+.08 or u>L/2-.08: continue
            q=np.array([cx,cy])+ux*u+uy*side_offset
            key=('brick','brick2','brick3')[(r+c)%3]
            b.box((bw*.88,.10,h*.72),(q[0],q[1],z0+(r+.5)*h),key,rotz=rotz)

def roof_clutter(center,L,W,z,rotz=0,seed=1,count=7):
    """Geometry-only roof wear/service detail: raised repair plates, vents and low equipment."""
    rng=np.random.default_rng(seed);cx,cy=center;th=math.radians(rotz);ux=np.array([math.cos(th),math.sin(th)]);uy=np.array([-math.sin(th),math.cos(th)])
    for i in range(count):
        ss=rng.uniform(-L*.38,L*.38);tt=rng.uniform(-W*.28,W*.28);p=np.array([cx,cy])+ux*ss+uy*tt
        ll=rng.uniform(2.0,6.5);ww=rng.uniform(.8,2.2);b.box((ll,ww,.05),(p[0],p[1],z+.05),'roof_patch' if i%2==0 else 'roof_fade',rotz=rotz)
    for i in range(max(2,count//3)):
        ss=rng.uniform(-L*.34,L*.34);tt=rng.uniform(-W*.24,W*.24);p=np.array([cx,cy])+ux*ss+uy*tt
        b.cyl(.22,.65,(p[0],p[1],z+.35),'metal',sections=10)

def add_car(x,y,rotz=0,key='car_white',scale=1.0):
    # low body + tapered cabin + four wheels; all actual geometry.
    b.box((4.25*scale,1.82*scale,.62*scale),(x,y,.55*scale),key,rotz=rotz)
    # cabin wedge in local coordinates
    L=2.35*scale;W=1.58*scale;zb=.80*scale;zt=1.48*scale;topL=1.45*scale
    v=np.array([[-L/2,-W/2,zb],[L/2,-W/2,zb],[L/2,W/2,zb],[-L/2,W/2,zb],[-topL/2,-W*.46,zt],[topL/2,-W*.46,zt],[topL/2,W*.46,zt],[-topL/2,W*.46,zt]],float)
    f=np.array([[0,1,5],[0,5,4],[1,2,6],[1,6,5],[2,3,7],[2,7,6],[3,0,4],[3,4,7],[4,5,6],[4,6,7]])
    m=trimesh.Trimesh(v,f,process=False);b.add(m,key,translation_matrix((x,y,0))@rotation_matrix(math.radians(rotz),[0,0,1]))
    # dark windows as thin panels on both long sides
    th=math.radians(rotz);ux=np.array([math.cos(th),math.sin(th)]);uy=np.array([-math.sin(th),math.cos(th)])
    for side in [-1,1]:
        p=np.array([x,y])+uy*side*(W/2+.01);b.box((1.45*scale,.06,0.44*scale),(p[0],p[1],1.13*scale),'window_dark',rotz=rotz)
    # wheels
    for ss in [-1.35,1.35]:
        for side in [-1,1]:
            c=np.array([x,y])+ux*(ss*scale)+uy*(side*.93*scale)
            # short cylinder along local width direction
            uy3=np.array([uy[0],uy[1],0.0]);a=np.array([c[0],c[1],.42*scale])-uy3*.11*scale;d=np.array([c[0],c[1],.42*scale])+uy3*.11*scale
            b.cylinder_between(a,d,.31*scale,'dark',sections=12)

# ---------------- Terrain and hardscape ----------------
N=34;xs=np.linspace(-360,360,N);ys=np.linspace(-300,430,N);verts=[]
for y in ys:
    for x in xs:
        z=-.65+.0018*y+.10*math.sin(x/62)*math.cos(y/74);verts.append((x,y,z))
faces=[]
for j in range(N-1):
    for i in range(N-1):a=j*N+i;faces.extend([(a,a+1,a+N+1),(a,a+N+1,a+N)])
b.add(trimesh.Trimesh(np.asarray(verts),np.asarray(faces),process=False),'ground')
# campus roads and edge walks based on aerial references
for poly in [
 Polygon([(-175,-105),(170,-105),(170,-94),(-175,-94)]),
 Polygon([(138,-175),(150,-175),(150,176),(138,176)]),
 Polygon([(-175,113),(160,113),(160,126),(-175,126)]),
 Polygon([(-166,-170),(-154,-170),(-154,168),(-166,168)]),
 Polygon([(-145,68),(-120,82),(-86,88),(-50,85),(-35,78),(-38,68),(-90,72),(-128,60)])
]: b.extrude(poly,.10,-.08,'road')
# Explicit asphalt repair plates and utility covers; separate geometry, not procedural or image texture.
for x,y,L,W,r in [(-120,-100,18,2.2,0),(58,-100,11,1.6,0),(144,-30,2.0,18,0),(-160,38,2.4,14,0),(22,118,16,2.0,0)]:
    b.box((L,W,.018),(x,y,.035),'road2',rotz=r)
for x,y in [(-80,-100),(96,-100),(144,72),(-160,-40)]: b.cyl(.48,.025,(x,y,.045),'metal',sections=20)

# ---------------- Central ceremonial plaza ----------------
# Footage: broad pale outer circle, dark triangular annulus, pale inner annulus, red-grey center and white stepped monument.
ring(0,7.0,.05,'plaza_red',.10); ring(7.0,15.5,.05,'plaza_light',.10); ring(15.5,20.5,.05,'plaza_dark',.10); ring(20.5,28.5,.05,'plaza',.10)
# Hand-authored paving blocks: many separate stone pieces with small material differences; no UVs/images.
for k in range(48):
    a0=k*7.5; a1=(k+1)*7.5
    key=('plaza','stone_warm','plaza_light')[k%3]
    b.extrude(sector_polygon(20.65,28.35,a0+.18,a1-.18,8),.012,.158,key)
for k in range(32):
    a0=k*11.25; a1=(k+1)*11.25
    key=('plaza_light','stone_warm','plaza')[k%3]
    b.extrude(sector_polygon(7.15,15.35,a0+.22,a1-.22,7),.010,.158,key)
# eight broad radial sectors in the central disc, matching segment 10 close footage.
for k in range(8):
    if k%2==0:
        p=sector_polygon(.15,6.75,k*45+2,(k+1)*45-2,24)
        b.extrude(p,.035,.165,'plaza_teal')
for k in range(24):
    a0=2*math.pi*k/24;a1=2*math.pi*(k+1)/24;am=(a0+a1)/2;rin,rout=15.6,20.3
    p=Polygon([(rin*math.cos(a0),rin*math.sin(a0)),(rout*math.cos(am),rout*math.sin(am)),(rin*math.cos(a1),rin*math.sin(a1))])
    b.extrude(p,.055,.16,'plaza_red' if k%2==0 else 'plaza')
# paving-joint geometry: radial and concentric seams visible in the aerial footage (no texture maps).
for a in np.linspace(0,360,48,endpoint=False):
    ar=math.radians(a);r=24.5;x,y=r*math.cos(ar),r*math.sin(ar)
    b.box((8.0,.045,.018),(x,y,.178),'plaza_joint',rotz=a)
for rr in [21.5,23.7,25.8,27.8]: ring(rr-.035,rr+.035,.175,'plaza_joint',.018,128)
for rr in [9.0,12.0,14.7]: ring(rr-.025,rr+.025,.172,'plaza_joint',.016,128)

# central stepped white monument with four radial stairs, balustrade posts and flagpole
for rad,z,h in [(5.4,.19,.28),(4.6,.47,.26),(3.7,.73,.26)]: ring(0,rad,z,'stone',h)
# square/octagonal core platform
core=Point(0,0).buffer(2.9,resolution=4);b.extrude(core,.42,.98,'stone')
for ang in [0,90,180,270]:
    th=math.radians(ang);u=np.array([math.cos(th),math.sin(th)]);v=np.array([-math.sin(th),math.cos(th)])
    # stair treads
    for j in range(5):
        c=u*(3.1+j*.55); z=.10+j*.16
        b.box((1.25+2*j*.1,3.4,.16),(c[0],c[1],z+.08),'stone',rotz=ang)
    # side balustrades/posts
    for side in [-1,1]:
        for s in np.linspace(2.8,5.1,5):
            p=u*s+v*side*1.9;b.box((.34,.34,1.05),(p[0],p[1],1.38),'stone',rotz=ang)
        b.box((2.8,.28,.24),(*(u*3.95+v*side*1.9),1.88),'stone',rotz=ang)
# octagonal upper-platform posts/rails visible in the close segment-10 pass.
for k in range(8):
    a=math.radians(k*45+22.5);x,y=3.05*math.cos(a),3.05*math.sin(a)
    b.box((.34,.34,1.45),(x,y,1.78),'stone',rotz=k*45)
for k in range(8):
    a0=math.radians(k*45+22.5);a1=math.radians((k+1)*45+22.5)
    p0=np.array([3.05*math.cos(a0),3.05*math.sin(a0),2.20]);p1=np.array([3.05*math.cos(a1),3.05*math.sin(a1),2.20])
    b.cylinder_between(p0,p1,.105,'stone',sections=8)

# central plinth, polished flag pole, top cap and actual red cloth geometry
b.cyl(.86,1.0,(0,0,1.78),'stone',sections=20)
b.cyl(.085,19.2,(0,0,11.9),'flagpole',sections=24)
b.sphere(.16,(0,0,21.55),'gold',subdivisions=2)
# Waving red flag: geometry only, double-sided triangles, no texture/image pixels.
ny,nz=9,5
v=[];f=[]
for iz in range(nz):
    z=19.95-iz*(2.25/(nz-1))
    for iy in range(ny):
        y=.10+iy*(3.45/(ny-1))
        x=.10*math.sin(iy*.95+iz*.45)+.045*(iy/(ny-1))**1.5
        v.append((x,y,z))
for iz in range(nz-1):
    for iy in range(ny-1):
        a=iz*ny+iy;c=a+1;d=(iz+1)*ny+iy;e=d+1
        f.extend([(a,d,e),(a,e,c),(e,d,a),(c,e,a)])
b.add(trimesh.Trimesh(np.asarray(v,float),np.asarray(f,int),process=False),'flag_red')

# ---------------- West administration / flag-plaza building ----------------
# The source building is not a smooth arc. It is rebuilt as five straight, slightly angled masses.
def add_admin_building():
    """Straight, non-curved administration building reconstructed from comparison views 1/2.

    East facade faces the ceremonial flag plaza. All facade details are modeled solids; no decals,
    photos, sampled pixels or projected image planes are used.
    """
    cx,cy=-35.0,0.0
    depth,length,h=20.0,94.0,23.6
    # one truly straight main mass: user explicitly rejected the former crescent/arc reading
    b.box((depth,length,h),(cx,cy,h/2+.05),'admin_wall')
    b.box((depth-.8,length-.8,.34),(cx,cy,h+.20),'roof')
    east_x=cx+depth/2+.14
    west_x=cx-depth/2-.14
    floors=7
    zrows=[2.25+i*3.05 for i in range(floors)]

    # East/front facade. Central 26 m is the ceremonial entrance; side wings use source-like paired windows.
    for z in zrows:
        for y in np.linspace(-43,43,23):
            if abs(y)<13.6: continue
            # leave space for the blue stair towers
            if abs(abs(y)-29.0)<4.1: continue
            b.box((.18,1.72,1.45),(east_x,y,z),'glass_silver')
            b.box((.22,1.96,.10),(east_x+.035,y,z+1.00),'admin_trim')
    # subtle floor bands and vertical facade joints visible on the painted wall panels
    for z in [3.75,6.80,9.85,12.90,15.95,19.0,22.05]:
        b.box((.11,length-1.4,.085),(east_x+.06,cy,z),'admin_wall2')
    for y in np.linspace(-44,44,17):
        if abs(y)<13.6 or abs(abs(y)-29)<4.5: continue
        b.box((.11,.08,h-1.2),(east_x+.07,y,(h-1.2)/2+.45),'admin_wall2')

    # Two tall blue glass staircase towers on the same straight plane.
    for y0 in [-29.0,29.0]:
        b.box((2.55,7.4,21.3),(east_x+.95,y0,10.75),'glass_blue')
        for z in np.linspace(1.55,20.2,8):
            b.box((.22,7.52,.11),(east_x+2.25,y0,z),'admin_trim')
        for yy in np.linspace(y0-3.35,y0+3.35,4):
            b.box((.22,.11,20.8),(east_x+2.24,yy,10.55),'admin_trim')
        # narrow operable window panels visible in the tower
        for z in [5.0,11.1,17.2]: b.box((.12,1.0,.48),(east_x+2.39,y0+.7,z),'glass_light')

    # Central glazed atrium: broad lower lobby, upper vertical glass, triangular glazed gable.
    b.box((.34,25.0,5.2),(east_x+.30,0,2.75),'glass_light')
    b.box((.34,15.2,13.6),(east_x+.26,0,12.2),'glass_silver')
    for yy in np.linspace(-7.2,7.2,7): b.box((.39,.14,14.0),(east_x+.43,yy,12.2),'admin_trim')
    for zz in [6.0,8.8,11.6,14.4,17.2,20.0]: b.box((.39,15.1,.14),(east_x+.43,0,zz),'admin_trim')
    # Entrance doors and transoms are actual geometry.
    for yy in [-4.5,-1.5,1.5,4.5]:
        b.box((.13,2.15,2.80),(east_x+.53,yy,1.55),'glass_blue')
        b.box((.16,.10,3.0),(east_x+.62,yy+1.08,1.62),'admin_trim')

    # Source-like colonnade and deep projecting canopy in front of the lobby.
    canopy_x=east_x+3.15
    b.box((5.8,27.0,.38),(canopy_x,0,6.20),'admin_trim')
    for yy in [-10.5,-6.3,-2.1,2.1,6.3,10.5]:
        b.cyl(.42,5.9,(canopy_x+.15,yy,3.18),'admin_pale',sections=24)
        # muted red cladding on the four central columns as in the real entrance
        if abs(yy)<7: b.cyl(.47,3.5,(canopy_x+.15,yy,3.0),'brick2',sections=24)
    # broad entrance steps
    for k in range(5):
        b.box((1.20+k*.62,25.4-k*.35,.13),(east_x+1.05+k*.56,0,.12+k*.13),'stone_warm')

    # Triangular gable above the central atrium, with real mullion bars.
    basez=h+.10; gx=east_x+.28
    vv=np.array([[gx,-8.2,basez],[gx,8.2,basez],[gx,0,28.5],
                 [gx-.32,-8.2,basez],[gx-.32,8.2,basez],[gx-.32,0,28.5]],float)
    ff=np.array([[0,1,2],[5,4,3],[0,3,4],[0,4,1],[1,4,5],[1,5,2],[2,5,3],[2,3,0]],int)
    b.add(trimesh.Trimesh(vv,ff,process=False),'glass_silver')
    for yy in np.linspace(-7.4,7.4,7):
        topz=28.5-(abs(yy)/8.2)*(28.5-basez)
        b.cylinder_between((gx+.10,yy,basez),(gx+.10,yy,topz),.072,'admin_trim',sections=6)
    b.cylinder_between((gx+.10,-8.2,basez),(gx+.10,0,28.5),.085,'admin_trim',sections=6)
    b.cylinder_between((gx+.10,0,28.5),(gx+.10,8.2,basez),.085,'admin_trim',sections=6)

    # Tall slab fins at both ends and beside the atrium; these are the conspicuous straight roofline shapes in view 1.
    for y0,zh in [(-45.0,26.0),(45.0,25.3),(-18.3,25.2),(18.3,25.0)]:
        b.box((2.9,2.4,zh),(east_x-.65,y0,zh/2+.05),'admin_wall2')

    # West/rear facade uses the newer pale repaint language but remains fully modeled.
    b.box((.20,length-1.2,h-1.0),(west_x-.02,0,(h-1.0)/2+.2),'admin_light')
    for z in zrows:
        for y in np.linspace(-43,43,23):
            if abs(y)<8.5: continue
            b.box((.18,1.68,1.42),(west_x-.15,y,z),'glass_silver')
    b.box((.25,16.0,17.2),(west_x-.22,0,11.1),'glass_blue')
    for yy in np.linspace(-7.4,7.4,6): b.box((.10,.12,17.3),(west_x-.37,yy,11.1),'admin_trim')
    for zz in np.linspace(4.2,18.8,6): b.box((.10,15.9,.12),(west_x-.37,0,zz),'admin_trim')

    # Small service housings and aerials observed on the roof.
    for y0,w,d,z0 in [(-30,9.0,5.8,24.8),(28,7.0,5.2,24.6),(6,5.0,4.2,24.5)]:
        b.box((5.4,w,2.1),(cx,y0,z0),'admin_wall2')
    for y0 in [-34,11,34]: b.cyl(.085,3.2,(cx-1.2,y0,27.0),'metal',sections=10)
add_admin_building()

# ---------------- Bespoke linear buildings ----------------
def add_linear(center,L,W,floors,rotz=0,red_trim=True,entry=True,roof_houses=True,side_bays=True):
    cx,cy=center;h=floors*3.15+1.0;th=math.radians(rotz);ux=np.array([math.cos(th),math.sin(th)]);uy=np.array([-math.sin(th),math.cos(th)])
    # stepped massing: long central bar plus slightly taller end stair towers
    b.box((L,W,h),(cx,cy,h/2+.05),'white',rotz=rotz)
    for end in [-1,1]:
        p=np.array([cx,cy])+ux*end*(L/2-3.0);b.box((6.2,W+1.0,h+1.4),(p[0],p[1],(h+1.4)/2+.05),'offwhite',rotz=rotz)
        if red_trim:b.box((6.5,W+1.4,1.0),(p[0],p[1],h+.9),'red',rotz=rotz)
    b.box((L-8,W-2,.30),(cx,cy,h+.25),'roof',rotz=rotz)
    # long side façades: windows inset between projected piers, red floor lines
    n=max(8,int(L/3.3))
    for side in [-1,1]:
        for f in range(floors):
            z=2.15+f*3.15
            for i in range(n):
                s=-L/2+3.4+(L-6.8)*i/(n-1);p=np.array([cx,cy])+ux*s+uy*side*(W/2+.12)
                b.box((1.62,.22,1.48),(p[0],p[1],z),'window_dark',rotz=rotz)
                # Separate lower infill panels keep the facade from reading as one flat color plane.
                pk=('offwhite','wall_warm','wall_cool')[(i+f+(0 if side<0 else 1))%3]
                b.box((1.82,.10,.42),(p[0],p[1],z-1.02),pk,rotz=rotz)
            if red_trim:
                p=np.array([cx,cy])+uy*side*(W/2+.15);b.box((L-7,.18,.28),(p[0],p[1],z+1.18),'red',rotz=rotz)
        if side_bays:
            for s in np.linspace(-L/2+7,L/2-7,7):
                p=np.array([cx,cy])+ux*s+uy*side*(W/2+.28);b.box((.36,.52,h-1.2),(p[0],p[1],(h-1.2)/2+.3),'offwhite',rotz=rotz)
        # Exterior condenser units are repeatedly visible in the corridor/teaching-building footage.
        # Place them sparsely below selected windows so the facade is not a flat repeated grid.
        nrm=uy*side
        for f in range(1,floors):
            for i in range(1,n-1,4):
                ss=-L/2+3.4+(L-6.8)*i/(n-1);q=np.array([cx,cy])+ux*ss+uy*side*(W/2+.47)
                add_ac_unit(q[0],q[1],1.35+f*3.15,rotz,normal=(nrm[0],nrm[1]),scale=.86)
    # source-visible red masonry stair/end-core relief; individual courses instead of a flat red patch.
    if red_trim:
        for end in [-1,1]:
            ep=np.array([cx,cy])+ux*end*(L/2-3.05)
            for side in [-1,1]:
                # narrow brick strip on the outer face of each end tower
                add_brick_strip((ep[0],ep[1]),4.6,.65,min(h-.8,12.8),rotz,side_offset=side*(W/2+.54),rows=max(10,floors*4),cols=4)
    # end windows and staircase vertical glass slit
    for end in [-1,1]:
        for f in range(floors):
            z=2.15+f*3.15
            for s in [-W*.22,W*.22]:
                p=np.array([cx,cy])+ux*end*(L/2+.12)+uy*s;b.box((1.45,.20,1.42),(p[0],p[1],z),'window_dark',rotz=rotz+90)
        p=np.array([cx,cy])+ux*end*(L/2+.2);b.box((2.8,.18,h-2.2),(p[0],p[1],h/2),'glass',rotz=rotz+90)
    if entry:
        p=np.array([cx,cy])+uy*(W/2+3.2);b.box((13,6.0,.42),(p[0],p[1],5.2),'white',rotz=rotz)
        for s in [-5,-1.7,1.7,5]:q=p+ux*s+uy*1.65;b.box((.58,.58,5.0),(q[0],q[1],2.55),'white',rotz=rotz)
        b.box((10.6,.18,2.8),(p[0],p[1],2.7),'glass',rotz=rotz)
    if roof_houses:
        for frac in [-.26,.29]:
            p=np.array([cx,cy])+ux*frac*L;b.box((5.0,4.8,2.4),(p[0],p[1],h+1.35),'offwhite',rotz=rotz);b.box((3.0,.18,1.3),(p[0],p[1]+.05,h+1.4),'glass',rotz=rotz)
    roof_clutter((cx,cy),L-10,W-4,h+.48,rotz,seed=int(abs(cx*7+cy*3))+11,count=max(4,int(L/15)))
    return h

# Observatory / science building on the east side, rebuilt from source 5/6.
def add_observatory(center=(0,-90),L=142,W=21.5,floors=5,rotz=0):
    """Science/observatory wing from comparison views 3/5/6.

    The central vehicle gateway is a genuine open void: the two wings and upper bridge are separate solids.
    """
    cx,cy=center;h=18.6
    th=math.radians(rotz);ux=np.array([math.cos(th),math.sin(th)]);uy=np.array([-math.sin(th),math.cos(th)])
    gap=30.0; wing=(L-gap)/2
    # separate left/right wings so the gateway is not a fake dark rectangle on a solid wall
    for sg in [-1,1]:
        pc=np.array([cx,cy])+ux*sg*(gap/2+wing/2)
        b.box((wing,W,h),(pc[0],pc[1],h/2+.05),'white',rotz=rotz)
        b.box((wing-.8,W-1.0,.30),(pc[0],pc[1],h+.18),'roof',rotz=rotz)
    # upper bridge over gateway, leaving ~7 m of clear drive-through below
    bridge_bottom=7.15
    bridge_h=h-bridge_bottom
    b.box((gap,W,bridge_h),(cx,cy,bridge_bottom+bridge_h/2),'white',rotz=rotz)
    b.box((gap-.5,W-1,.30),(cx,cy,h+.18),'roof',rotz=rotz)

    # Long red floor bands and real window solids on both long facades.
    for side in [-1,1]:
        face=np.array([cx,cy])+uy*side*(W/2+.14)
        for z in [4.0,7.15,10.35,13.55,16.75]:
            # split band at central opening on the front side for more faithful gateway read
            if side==-1 and z<7.2:
                for sg in [-1,1]:
                    q=face+ux*sg*(gap/2+(L-gap)/4)
                    b.box(((L-gap)/2-.5,.18,.26),(q[0],q[1],z),'red',rotz=rotz)
            else:b.box((L-2,.18,.26),(face[0],face[1],z),'red',rotz=rotz)
        for fl in range(5):
            z=2.25+fl*3.15
            for ss in np.linspace(-L/2+5,L/2-5,28):
                if side==-1 and abs(ss)<15.5 and z<7.2: continue
                # upper central greenhouse occupies several bays
                if side==-1 and abs(ss)<9 and z>7.0: continue
                q=np.array([cx,cy])+ux*ss+uy*side*(W/2+.15)
                b.box((1.62,.20,1.52),(q[0],q[1],z),'glass_silver',rotz=rotz)

    # Three dark glass stair shafts: two flank the gateway and one is near the far right end.
    for ss in [-22.0,22.0,L/2-7.2]:
        q=np.array([cx,cy])+ux*ss
        b.box((5.6,W+1.55,h+1.2),(q[0],q[1],(h+1.2)/2),'offwhite',rotz=rotz)
        qf=q+uy*(-1)*(W/2+.90)
        b.box((3.15,.22,h-2.0),(qf[0],qf[1],h/2),'glass_blue',rotz=rotz)
        for zz in np.linspace(2.5,h-1.8,6): b.box((3.20,.30,.12),(qf[0],qf[1],zz),'admin_trim',rotz=rotz)

    # Central glazed greenhouse/gable above the real opening.
    side=-1
    front=np.array([cx,cy])+uy*side*(W/2+.25)
    b.box((17.2,.30,9.4),(front[0],front[1],13.0),'glass_light',rotz=rotz)
    for ss in np.linspace(-7.8,7.8,7):
        q=front+ux*ss;b.box((.16,.42,9.7),(q[0],q[1],13.0),'offwhite',rotz=rotz)
    for zz in [9.4,12.0,14.6,17.2]: b.box((17.2,.42,.16),(front[0],front[1],zz),'offwhite',rotz=rotz)
    left=front+ux*(-8.6);right=front+ux*8.6;peak=np.array([front[0],front[1],h+5.1])
    b.add(trimesh.Trimesh(np.array([[left[0],left[1],h+.15],[right[0],right[1],h+.15],peak],float),np.array([[0,1,2],[2,1,0]],int),process=False),'glass_roof')
    b.cylinder_between((left[0],left[1],h+.15),peak,.09,'green_metal',sections=6)
    b.cylinder_between(peak,(right[0],right[1],h+.15),.09,'green_metal',sections=6)
    for ss in np.linspace(-7.0,7.0,6):
        q=front+ux*ss; topz=h+.15+(1-abs(ss)/8.6)*(5.0)
        b.cylinder_between((q[0],q[1],h+.15),(q[0],q[1],topz),.06,'green_metal',sections=5)

    # Open gateway architecture: upper beam and four tall columns, actual empty space between them.
    gate=front+uy*side*2.55
    b.box((29.0,4.5,.95),(gate[0],gate[1],7.55),'roof2',rotz=rotz)
    for ss in [-10.0,-3.4,3.4,10.0]:
        q=gate+ux*ss;b.box((1.18,1.18,7.0),(q[0],q[1],3.58),'offwhite',rotz=rotz)
        b.box((1.32,1.32,.35),(q[0],q[1],.28),'admin_trim',rotz=rotz)
    # dark fascia panel above the driveway and short red end caps
    b.box((23.0,.22,1.15),(gate[0]+uy[0]*2.12,gate[1]+uy[1]*2.12,7.05),'roof2',rotz=rotz)

    # Geodesic observatory dome at left roof wing, moderate scale (not the former oversized sphere).
    dp=np.array([cx,cy])+ux*(-48.0)+uy*(1.0)
    drum_r=6.9; dome_r=6.25
    b.cyl(drum_r,3.4,(dp[0],dp[1],h+1.85),'offwhite',sections=64)
    for a in np.linspace(0,360,16,endpoint=False):
        ar=math.radians(a);x=dp[0]+(drum_r+.07)*math.cos(ar);y=dp[1]+(drum_r+.07)*math.sin(ar)
        b.box((1.25,.18,1.50),(x,y,h+1.85),'window_dark',rotz=a)
    sph=trimesh.creation.icosphere(subdivisions=3,radius=dome_r)
    # flatten the lower hemisphere a little so it reads like the real roof dome rather than a full ball
    sph.vertices[:,2]*=.82
    sph.apply_translation((dp[0],dp[1],h+3.15+dome_r*.72))
    b.add(sph,'dome')
    for e in sph.edges_unique:
        a=sph.vertices[e[0]];c=sph.vertices[e[1]]
        if a[2]>h+2.6 and c[2]>h+2.6:b.cylinder_between(a,c,.047,'dome_dark',sections=5)

    # roof service rooms, vents and weathering plates
    for ss in [-18,18,48]:
        q=np.array([cx,cy])+ux*ss;b.box((7.5,5.3,2.3),(q[0],q[1],h+1.45),'offwhite',rotz=rotz)
    roof_clutter((cx,cy),L-15,W-5,h+.45,rotz,seed=513,count=13)
    return h,dp

# Aerial review places the dome-bearing long wing on the east side, running roughly north-south.
b.set_transform(rotation_matrix(math.radians(90),[0,0,1]))
h_east,dc=add_observatory()
b.reset_transform()

# ---------------- East science forecourt / parking / main gate ----------------
# Comparison views 5/6 show a large paved forecourt, parked cars, clipped tree rows and a campus gate
# between the camera and the science building. Everything below is modeled geometry.
b.extrude(Polygon([(110,-48),(192,-48),(192,49),(110,49)]),.08,.02,'road2')
# central pedestrian/vehicle axis to the science gateway
b.extrude(Polygon([(103,-10),(198,-10),(198,10),(103,10)]),.06,.11,'plaza_light')
# parking bay joints
for yy in [-42,-35,-28,28,35,42]: b.box((69,.055,.018),(149,yy,.13),'court_joint')
for xx in np.linspace(118,186,13):
    for yy in [-35,35]: b.box((.055,13,.018),(xx,yy,.13),'court_joint')
# two dense car rows; varied colors and slight offsets prevent a toy-like exact grid
car_keys=['car_white','car_dark','car_white','car_red','car_white']
for row,yy in enumerate([-37.5,37.5]):
    for i,xx in enumerate(np.linspace(119,184,12)):
        if (i+row)%7==0: continue
        add_car(xx,yy+(0.45 if i%3==0 else 0),rotz=(90 if row==0 else -90),key=car_keys[(i+2*row)%len(car_keys)],scale=.82)
# clipped tree rows flanking the central approach
for yy in [-18.5,18.5]:
    for i,xx in enumerate(np.linspace(116,181,10)):
        add_tree(xx,yy,scale=.78+(i%3)*.08,variant=i)
        add_shrub(xx+2.0,yy*.93,.70)
# low hedges seen along the left approach of view 5
for xx in np.linspace(114,170,15): b.box((2.9,1.25,1.05),(xx,-23.5,.60),'tree_leaf2')

# Gate nearest comparison view 6. Broad horizontal lintel with two chunky side pylons and center plaque.
gate_x=160.0
# open gate is built from separate pylons and lintel solids, leaving the drive-through physically empty.
b.box((4.8,9.0,7.2),(gate_x,-20.2,3.65),'admin_pale')
b.box((4.8,9.0,7.2),(gate_x,20.2,3.65),'admin_pale')
b.box((4.8,31.0,1.25),(gate_x,0,6.55),'admin_pale')
b.box((.22,8.0,2.7),(gate_x-2.52,-20.2,3.1),'glass_blue')
b.box((.22,8.0,2.7),(gate_x-2.52,20.2,3.1),'glass_blue')
# center signboard and modeled red/gold vertical strokes (not text/image texture)
b.box((.22,7.2,4.2),(gate_x-2.58,0,3.25),'admin_pale')
for z0 in [4.5,3.6,2.7,1.8]:
    b.box((.12,2.2,.16),(gate_x-2.73,0,z0),'gold')
    b.box((.12,.16,.72),(gate_x-2.73,-.72,z0),'gold')
# physical sliding-bar fence sections either side of gate
for yy0 in [-42,-34,34,42]:
    for zz in [.7,1.55,2.4]: b.box((.09,7.5,.07),(gate_x-1.8,yy0,zz),'metal')
    for yy in np.linspace(yy0-3.3,yy0+3.3,6): b.box((.09,.07,2.4),(gate_x-1.8,yy,1.3),'metal')

# Large mature trees framing supplied comparison view 2.
for x0,y0,sc,var in [(34,-13,2.25,0),(36,13,2.35,1),(27,-20,1.8,2),(28,21,1.95,0),(41,-23,1.55,1),(41,24,1.65,2)]:
    add_tree(x0,y0,sc,var)
for x0,y0,sc,var in [(44.0,-12.5,3.0,1),(44.2,13.0,3.1,2)]: add_tree(x0,y0,sc,var)
# lower hedges along the approach from view 2
for y0 in np.linspace(-26,26,10): add_shrub(25.5,y0,.85)

# ---------------- Distant urban edge and mountain ridges ----------------
# These are geometry-only horizon masses seen in the aerial comparison views; they also keep the enlarged
# ground from ending in a hard rectangular edge in long-distance views.
def add_mountain_ridge(points, width=72, base=-.55, key='mountain'):
    # Densified 7-row terrain ribbon. It is still pure geometry, but avoids the old giant flat triangles.
    dense=[]
    for i in range(len(points)-1):
        a=np.asarray(points[i],float);c=np.asarray(points[i+1],float)
        for k in range(8):
            t=k/8.0;q=a*(1-t)+c*t
            # gentle non-repeating height break-up derived mathematically, not sampled from imagery
            q[2]+=2.6*math.sin((i*8+k)*1.31)+1.3*math.sin((i*8+k)*.47)
            dense.append(q)
    dense.append(np.asarray(points[-1],float))
    rows=np.linspace(-1,1,7);verts=[];faces=[]
    for j,q in enumerate(dense):
        x,y,z=q;l=max(1.0,math.hypot(x,y));nx,ny=x/l,y/l
        for u in rows:
            fall=(1-abs(u)**1.55)
            zz=base+(z-base)*fall + 1.2*math.sin(j*.73+u*2.1)*fall
            verts.append((x+nx*u*width*.52,y+ny*u*width*.52,zz))
    nr=len(rows)
    for j in range(len(dense)-1):
        for r in range(nr-1):
            a=j*nr+r;c=(j+1)*nr+r;faces.extend([(a,c,c+1),(a,c+1,a+1)])
    b.add(trimesh.Trimesh(np.asarray(verts,float),np.asarray(faces,int),process=False),key)
# west / north / northeast ridgelines, irregular enough to avoid a synthetic smooth wall
add_mountain_ridge([(-340,-230,18),(-355,-130,31),(-345,-30,46),(-350,70,39),(-340,170,52),(-325,280,38)],85,-.55,'mountain')
add_mountain_ridge([(-290,390,20),(-180,405,31),(-65,414,38),(50,405,34),(165,398,49),(285,385,42)],92,-.55,'mountain2')
add_mountain_ridge([(335,320,34),(350,220,46),(352,120,39),(350,20,28),(345,-90,41),(335,-205,30)],80,-.55,'mountain')
for a in np.linspace(-145,145,24):
    ar=math.radians(a); rr=305+12*math.sin(a*.17); add_tree(rr*math.cos(ar),rr*math.sin(ar)+80,.72+(int(a)%3)*.10,int(a)%3)
# distant city blocks beyond science / in aerial horizon; intentionally simple because they remain hundreds of metres away.
for ix,x0 in enumerate([-250,-210,-165,-120,-75,15,60,110,160,215,260]):
    for jy,y0 in enumerate([330,360]):
        hh=14+((ix*7+jy*11)%17)
        b.box((26,18,hh),(x0,y0,hh/2),'urban' if (ix+jy)%2 else 'urban_dark')
        for z0 in np.arange(4,hh-1,3.2):
            for xx in np.linspace(x0-9,x0+9,4): b.box((1.7,.14,1.2),(xx,y0-9.1,z0),'glass_silver')

# Courtyard classroom / dormitory blocks seen around plaza and gardens.
# Source-guided central layout revision: the two northern teaching bars sit northwest/north of the
# ceremonial circle; the southern teaching bars run north-south.  The old V110/V111 placements
# incorrectly put three long bars through the west garden and are intentionally removed.
add_linear((-76,119),72,16.5,5,90,True,False,True,True)
add_linear((-28,119),72,16.5,5,90,True,False,True,True)
add_linear((-95,202),54,15.5,5,90,True,False,True,True)
add_linear((-124,202),58,15.5,5,90,True,False,True,True)
add_linear((-153,201),52,15,5,90,True,False,True,True)
# Three south-side bars visible in the near-vertical segment-02 passes.  They remain clear of the
# west garden and read as a parallel teaching/courtyard group rather than unrelated west blocks.
add_linear((-38,-104),82,16,4,90,True,False,True,True)
add_linear((12,-106),86,16,5,90,True,True,True,True)
add_linear((111,-102),78,15.5,4,90,True,False,True,True)

# Source 4: geometry-only vertical red encouragement banner on the west-facing facade.
banner_x,banner_y=-46.15,-121.0
b.box((.18,6.0,13.6),(banner_x,banner_y,8.2),'red')
# Gold strokes are separate small solids, not a decal or image texture.
for k,z0 in enumerate([13.2,10.8,8.4,6.0,3.6]):
    for dy,ww,hh in [(-1.2,2.1,.24),(0,1.4,.24),(1.15,1.8,.24)]:
        b.box((.13,ww,hh),(banner_x-.12,banner_y+dy,z0),'gold')
    if k%2==0:b.box((.13,.28,1.55),(banner_x-.12,banner_y,z0),'gold')
# comparison view 4 foreground is a dense planted garden rather than bare ground
for ix,x0 in enumerate(np.linspace(-92,-52,8)):
    for iy,y0 in enumerate(np.linspace(-132,-82,7)):
        if (ix+2*iy)%3==0: add_tree(x0,y0,.72+((ix+iy)%4)*.12,(ix+iy)%3)
        elif (ix+iy)%2==0: add_shrub(x0,y0,.52+((ix*iy)%3)*.09)

# Open corridor/balcony skins on several classroom blocks, matching ground-level footage of red-trimmed external galleries.
def open_corridor(center,L,W,floors,rotz=0,side=1):
    cx,cy=center;th=math.radians(rotz);ux=np.array([math.cos(th),math.sin(th)]);uy=np.array([-math.sin(th),math.cos(th)])
    for f in range(1,floors):
        z=f*3.15+.15;p=np.array([cx,cy])+uy*side*(W/2+1.1)
        b.box((L-7,2.0,.18),(p[0],p[1],z),'offwhite',rotz=rotz)
        # red rail / fascia and slim uprights
        p2=np.array([cx,cy])+uy*side*(W/2+2.0);b.box((L-7,.12,.28),(p2[0],p2[1],z+.72),'red',rotz=rotz)
        for ss in np.linspace(-L/2+5,L/2-5,max(6,int(L/5))):
            q=np.array([cx,cy])+ux*ss+uy*side*(W/2+1.95);b.box((.12,.12,1.15),(q[0],q[1],z+.55),'offwhite',rotz=rotz)
        # structural gallery columns and alternating door/window openings behind the rail.
        for j,ss in enumerate(np.linspace(-L/2+6,L/2-6,max(5,int(L/7)))):
            qc=np.array([cx,cy])+ux*ss+uy*side*(W/2+1.72);b.box((.30,.30,2.75),(qc[0],qc[1],z+1.48),'offwhite',rotz=rotz)
            qw=np.array([cx,cy])+ux*(ss+1.55)+uy*side*(W/2+.14);b.box((1.45,.18,2.12),(qw[0],qw[1],z+1.28),'window_dark' if j%2 else 'glass',rotz=rotz)
open_corridor((-76,119),72,16.5,5,90,-1)
open_corridor((-28,119),72,16.5,5,90,1)
# South parallel blocks carry the same source-visible open gallery language.
open_corridor((-38,-104),82,16,4,90,-1)
open_corridor((12,-106),86,16,5,90,1)
open_corridor((111,-102),78,15.5,4,90,-1)
open_corridor((-95,202),54,15.5,5,90,-1)
open_corridor((-124,202),58,15.5,5,90,-1)

# Red-gable ancillary building seen in rooftop/pass-through shots
b.box((35,14,8.3),(-84,-164,4.2),'white'); gable_roof(-84,-164,37,16,8.35,0,'red2',5.3)
for yside in [-171.1,-156.9]:
    for x in np.linspace(-98,-70,9): b.box((1.7,.24,1.7),(x,yside,4.6),'window_dark')
# translucent/metal rooftop canopies as real framing geometry
for cx,cy in [(-58,-160),(-34,-160)]:
    for xx in np.linspace(cx-7,cx+7,5):
        b.cylinder_between((xx,cy-4,10.0),(xx,cy+4,10.0),.08,'green_metal',sections=6)
    for yy in np.linspace(cy-4,cy+4,4):b.cylinder_between((cx-7,yy,10),(cx+7,yy,10),.08,'green_metal',sections=6)

# ---------------- East glass atrium / assembly hall ----------------
def add_atrium_hall(cx=94,cy=5,L=72,W=52):
    # Source-like hall: broad white plinth, large two-plane pitched glass roof and a long muted-red ridge.
    base_h=6.8
    b.box((L,W,base_h),(cx,cy,base_h/2+.05),'offwhite')
    # articulate the lower perimeter rather than leaving a blank box
    for side in [-1,1]:
        yy=cy+side*(W/2+.12)
        for xx in np.linspace(cx-L/2+7,cx+L/2-7,14): b.box((2.15,.20,1.55),(xx,yy,3.6),'window_dark')
        b.box((L-8,.28,.28),(cx,yy,5.25),'red')
    # short white corner stair/service masses visible around the glass shed
    for ex in [-1,1]:
        b.box((7.2,W+1.0,9.2),(cx+ex*(L/2-3.7),cy,4.65),'white')
        for yy in np.linspace(cy-W/2+5,cy+W/2-5,7):
            b.box((.20,2.6,1.25),(cx+ex*(L/2+.02),yy,4.0),'window_dark',rotz=90)
    # pitched roof as two actual planar meshes; eaves low, ridge high
    xe0,xe1=cx-L/2+5.0,cx+L/2-5.0
    y0,y1=cy-W/2+3.0,cy+W/2-3.0
    ze,zr=7.15,14.9
    vv=np.array([[xe0,y0,ze],[xe1,y0,ze],[xe1,cy,zr],[xe0,cy,zr],
                 [xe0,cy,zr],[xe1,cy,zr],[xe1,y1,ze],[xe0,y1,ze]],float)
    ff=np.array([[0,1,2],[0,2,3],[4,5,6],[4,6,7]])
    b.add(trimesh.Trimesh(vv,ff,process=False),'glass_roof')
    # dense physical roof grid / truss lines on both slopes
    for side in [-1,1]:
        ye=y0 if side<0 else y1
        for frac in np.linspace(0,1,7):
            yy=ye+(cy-ye)*frac; zz=ze+(zr-ze)*frac
            b.cylinder_between((xe0,yy,zz+.08),(xe1,yy,zz+.08),.065,'green_metal',sections=6)
        for xx in np.linspace(xe0,xe1,12):
            b.cylinder_between((xx,ye,ze+.08),(xx,cy,zr+.08),.065,'green_metal',sections=6)
    # triangular glazed end gables and explicit perimeter frames
    for xx in [xe0,xe1]:
        tri=np.array([[xx,y0,ze],[xx,y1,ze],[xx,cy,zr]],float)
        # two-sided skinny triangular plate in x
        eps=.07; verts=np.vstack([tri+[-eps,0,0],tri+[eps,0,0]])
        faces=np.array([[0,1,2],[3,5,4],[0,3,4],[0,4,1],[1,4,5],[1,5,2],[2,5,3],[2,3,0]])
        b.add(trimesh.Trimesh(verts,faces,process=False),'glass')
        b.cylinder_between((xx,y0,ze),(xx,cy,zr),.10,'offwhite',sections=6)
        b.cylinder_between((xx,y1,ze),(xx,cy,zr),.10,'offwhite',sections=6)
        b.cylinder_between((xx,y0,ze),(xx,y1,ze),.10,'offwhite',sections=6)
        for frac in [.25,.5,.75]:
            yy=y0+(y1-y0)*frac
            zline=ze+(zr-ze)*(1-abs((yy-cy)/((y1-y0)/2)))
            b.cylinder_between((xx-.10,yy,ze+.1),(xx-.10,yy,zline),.045,'green_metal',sections=5)
    # long red ridge cap and raised skylight strip; geometry only
    b.box((L-9,2.6,.42),(cx,cy,zr+.16),'red2')
    b.box((L-13,1.15,.55),(cx,cy,zr+.52),'roof2')
    # diagonal X braces along long eaves as in the source roof frame
    for side in [-1,1]:
        ye=y0 if side<0 else y1
        for x0 in np.linspace(xe0,xe1-12,5):
            b.cylinder_between((x0,ye,ze+.16),(x0+10,cy,zr-.1),.07,'green_metal',sections=6)
            b.cylinder_between((x0+10,ye,ze+.16),(x0,cy,zr-.1),.07,'green_metal',sections=6)
    # weathering/service objects as raised meshes, not texture maps
    for xx,yy,ang in [(cx-21,cy-10,0),(cx+15,cy+12,0),(cx+3,cy-17,0)]:
        b.box((5.5,1.1,.08),(xx,yy,7.25),'roof_patch',rotz=ang)

# Source aerial passes place the glass-roof assembly hall in the northeast court, beyond the two
# northern teaching bars and clear of the dome-bearing east wing.
add_atrium_hall(96,142,72,52)
# small red-gable service annex northeast of the atrium
b.box((22,12,7.0),(132,108,3.55),'white');gable_roof(132,108,24,14,7.1,0,'red2',4.2)
for xx in np.linspace(124,140,5): b.box((1.5,.18,1.4),(xx,101.9,3.7),'window_dark')

# ---------------- Gardens ----------------
west=Polygon([(-149,-63),(-86,-61),(-66,-28),(-70,28),(-76,78),(-139,89),(-151,58)]);b.extrude(west,.09,.02,'grass2')
# court/plaza-side planted strip
for poly in [Polygon([(-40,50),(40,50),(40,92),(-40,92)]),Polygon([(-38,126),(42,126),(42,160),(-38,160)])]:b.extrude(poly,.08,.02,'grass')
# visible winding paths with circular nodes
paths=[
 [(-138,4),(-122,21),(-132,38),(-111,58),(-90,77)],
 [(-137,75),(-112,56),(-93,45),(-83,26)],
 [(-125,12),(-104,8),(-86,17)],
 [(-68,-1),(-84,10),(-95,22),(-108,27)],
 [(-33,55),(-18,69),(0,58),(16,72),(31,55)],
 [(-34,82),(-18,69),(2,84),(24,70),(37,84)],
 [(-31,136),(-10,146),(10,137),(31,149)]
]
for pts in paths:b.extrude(LineString(pts).buffer(1.25,cap_style=1,join_style=1),.09,.12,'path_light')
for x,y in [(-122,21),(-111,58),(-93,45),(-104,8),(-18,69),(24,70),(-10,146)]:ring(0,2.2,.14,'path',.06,48,(x,y))
# central approach paving
for poly in [Polygon([(-9,41),(9,41),(9,104),(-9,104)]),Polygon([(-55,-8),(-41,-8),(-41,8),(-55,8)]),Polygon([(44,-7),(72,-7),(72,7),(44,7)])]:b.extrude(poly,.10,.10,'path_light')

# Paved/tree-lined pedestrian courts immediately around the observatory and north teaching blocks.
b.extrude(Polygon([(-44,-54),(70,-54),(70,-49),(-44,-49)]),.075,.055,'path')
b.extrude(Polygon([(83,40),(134,40),(134,112),(83,112)]),.075,.045,'path_light')
# planted islands in the east courtyard
for x0 in [91,116]:
    b.extrude(Polygon([(x0,52),(x0+8,52),(x0+8,102),(x0,102)]),.10,.10,'grass_dark')
# evenly spaced small courtyard trees matching the aerial rows
for yy in np.linspace(48,104,8):
    add_tree(88,yy,.72,int(yy)%3);add_tree(130,yy,.72,(int(yy)+1)%3)
for i,xx in enumerate(np.linspace(-38,60,12)): add_tree(xx,-53,.70,i%3)
# low benches along the plaza-to-observatory walk
for xx in np.linspace(-32,54,6):
    b.box((.45,2.2,.18),(xx,-48.5,.50),'offwhite');b.box((.16,.16,.55),(xx,-49.3,.27),'metal');b.box((.16,.16,.55),(xx,-47.7,.27),'metal')

# Chinese pavilion in west garden: curved/upturned double eaves, columns, brackets and railings.
def pagoda_roof(cx,cy,z,half,peak,upturn,key='red2',N=14,thick=.16):
    # square hipped roof with curved eaves; corners turn upward. Generate a thin closed shell from a regular grid.
    xs=np.linspace(-half,half,N);ys=np.linspace(-half,half,N);verts=[]
    def zz(x,y):
        q=max(abs(x),abs(y))/half
        base=peak*(1-q**1.15)
        corner=upturn*((abs(x*y)/(half*half))**3.2)
        return z+base+corner
    for layer in [0,-thick]:
        for y in ys:
            for x in xs:verts.append((cx+x,cy+y,zz(x,y)+layer))
    faces=[];off=N*N
    for j in range(N-1):
        for i in range(N-1):
            a=j*N+i;c=a+1;d=(j+1)*N+i;e=d+1
            faces.extend([(a,c,e),(a,e,d),(off+a,off+e,off+c),(off+a,off+d,off+e)])
    # close four perimeter sides
    for i in range(N-1):
        # bottom/top y edges
        for a,c in [(i,i+1),((N-1)*N+i,(N-1)*N+i+1)]:faces.extend([(a,off+a,off+c),(a,off+c,c)])
        # left/right x edges
        for a,c in [(i*N,(i+1)*N),(i*N+N-1,(i+1)*N+N-1)]:faces.extend([(a,c,off+c),(a,off+c,off+a)])
    b.add(trimesh.Trimesh(vertices=np.asarray(verts),faces=np.asarray(faces),process=False),key)

def pavilion(cx=-140,cy=36):
    b.box((11,11,.55),(cx,cy,.32),'plaza_light')
    for dx in [-3.5,3.5]:
      for dy in [-3.5,3.5]:
        b.cyl(.28,4.7,(cx+dx,cy+dy,2.65),'red2',sections=18)
        # layered bracket arms below eaves
        for z0,span in [(4.15,1.5),(4.42,2.0)]:
            b.box((span,.30,.18),(cx+dx,cy+dy,z0),'gold',rotz=0);b.box((.30,span,.18),(cx+dx,cy+dy,z0),'gold',rotz=0)
    pagoda_roof(cx,cy,4.50,6.4,2.25,.72,'red2',16,.18)
    pagoda_roof(cx,cy,6.40,3.65,1.55,.45,'red2',14,.16)
    # four roof ridge ornaments
    for ang in [45,135,225,315]:
        ar=math.radians(ang);b.cylinder_between((cx,cy,7.88),(cx+3.7*math.cos(ar),cy+3.7*math.sin(ar),6.95),.08,'gold',sections=6)
    b.cyl(.15,2.2,(cx,cy,8.7),'gold',sections=12);b.sphere(.24,(cx,cy,9.85),'gold',subdivisions=2)
    # dense visible underside structure from the pavilion footage: radial rafters + orthogonal beams, all actual meshes.
    for ang in np.linspace(0,360,16,endpoint=False):
        ar=math.radians(ang);b.cylinder_between((cx,cy,5.05),(cx+5.55*math.cos(ar),cy+5.55*math.sin(ar),4.72),.075,'dark',sections=6)
    for d in [-3.6,-2.4,-1.2,0,1.2,2.4,3.6]:
        b.box((8.8,.13,.13),(cx,cy+d,4.83),'gold');b.box((.13,8.8,.13),(cx+d,cy,4.81),'gold')
    b.cyl(1.05,.22,(cx,cy,4.68),'dome_dark',sections=24);b.cyl(.46,.30,(cx,cy,4.48),'gold',sections=20)
    # railings around platform
    for dx in [-4.4,4.4]:
      for yy in np.linspace(-3.6,3.6,7):b.box((.15,.15,1.05),(cx+dx,cy+yy,1.1),'red2')
    for dy in [-4.4,4.4]:
      for xx in np.linspace(-3.6,3.6,7):b.box((.15,.15,1.05),(cx+xx,cy+dy,1.1),'red2')
pavilion()

# Table-tennis garden immediately west of the crescent.  Near-vertical segment-02 footage shows
# four long pale slabs in a 2x2 arrangement, not the previous single paired strip.
for cy_strip in [42,-27]:
    for cx_strip in [-116,-93]:
        b.extrude(Polygon([(cx_strip-7,cy_strip-23),(cx_strip+7,cy_strip-23),(cx_strip+7,cy_strip+23),(cx_strip-7,cy_strip+23)]),.075,.05,'plaza_light')
        for yy in np.linspace(cy_strip-17,cy_strip+17,7):
            b.box((3.0,1.45,.10),(cx_strip,yy,.86),'blue');b.box((.12,1.3,.25),(cx_strip,yy,1.02),'court_line')
            for dx in [-1.1,1.1]:b.box((.18,.18,.78),(cx_strip+dx,yy,.42),'metal')
# clipped hedge borders and compartment breaks around all four slabs.
for xh in [-124.0,-104.5,-84.5]:
    b.box((1.55,114.0,1.15),(xh,7.5,0.67),'tree_leaf',rotz=0)
for yy in [-51.5,-3.5,18.5,65.5]:
    b.box((40.0,1.4,1.05),(-104.0,yy,0.62),'tree_leaf2')

# Secondary court of tables farther north/east as seen in other aerial passes.
b.extrude(Polygon([(47,126),(108,126),(108,163),(47,163)]),.08,.05,'path_light')
for rowy in [132,144,156]:
    for x in np.linspace(54,101,6):
        b.box((3.0,1.45,.10),(x,rowy,.86),'blue');b.box((.12,1.3,.25),(x,rowy,1.02),'court_line');b.box((.18,.18,.78),(x-1.1,rowy,.42),'metal');b.box((.18,.18,.78),(x+1.1,rowy,.42),'metal')

# ---------------- Basketball complex ----------------
def court_lines(cx,cy,L=40,W=20):
    # one complete physical court: boundary, half-court, center circle, keys and green hoops
    for y in [-W/2,W/2]: b.box((L,.10,.025),(cx,cy+y,.19),'court_line')
    for x in [-L/2,L/2,0]: b.box((.10,W,.025),(cx+x,cy,.19),'court_line')
    m=trimesh.creation.annulus(r_min=2.15,r_max=2.27,height=.03,sections=48);m.apply_translation((cx,cy,.19));b.add(m,'court_line')
    # key rectangles and semicircle proxies, physical strips
    for side in [-1,1]:
        kx=cx+side*(L/2-5.0)
        b.box((.10,6.2,.025),(cx+side*(L/2-8.2),cy,.19),'court_line')
        for yy in [cy-3.1,cy+3.1]: b.box((6.8,.10,.025),(cx+side*(L/2-4.8),yy,.19),'court_line')
        hx=cx+side*(L/2-2.0)
        b.cyl(.12,3.25,(hx,cy,1.72),'green_metal',sections=12)
        b.cylinder_between((hx,cy,3.15),(hx-side*.80,cy,3.15),.075,'green_metal',sections=8)
        b.box((.12,1.86,1.08),(hx-side*.84,cy,3.05),'glass')
        # rim ring oriented vertically enough to read in aerial and oblique views
        b.cyl(.46,.06,(hx-side*1.23,cy,2.93),'red2',sections=24,roty=90)

# Footage s03_8: a broad pale concrete slab, 4 columns x 2 rows, directly against south straight of the running track.
# access road immediately south of the basketball fence.
b.extrude(Polygon([(-90,170),(112,170),(112,180),(-90,180)]),.07,.01,'road')
bb_x0,bb_x1,bb_y0,bb_y1=-72,100,182,228
b.extrude(Polygon([(bb_x0,bb_y0),(bb_x1,bb_y0),(bb_x1,bb_y1),(bb_x0,bb_y1)]),.08,.06,'court')
# physical expansion joints in the concrete, no texture
for x in np.linspace(bb_x0+8,bb_x1-8,9): b.box((.045,bb_y1-bb_y0,.014),(x,(bb_y0+bb_y1)/2,.165),'court_joint')
for y in np.linspace(bb_y0+7,bb_y1-7,5): b.box((bb_x1-bb_x0,.045,.014),((bb_x0+bb_x1)/2,y,.165),'court_joint')
xs=[-50.5,-8.0,34.5,77.0]; ys_c=[193.5,216.0]
for yy in ys_c:
    for xx in xs: court_lines(xx,yy,40.5,20.5)
# tall white/metal perimeter fence and dark-green stadium-side fence line
for x in np.linspace(bb_x0,bb_x1,58):
    for yy in [bb_y0,bb_y1]: b.box((.09,.09,3.0),(x,yy,1.55),'curb')
for y in np.linspace(bb_y0,bb_y1,22):
    for xx in [bb_x0,bb_x1]: b.box((.09,.09,3.0),(xx,y,1.55),'curb')
for yy in [bb_y0,bb_y1]:
    b.box((bb_x1-bb_x0,.08,.08),((bb_x0+bb_x1)/2,yy,1.1),'curb');b.box((bb_x1-bb_x0,.08,.08),((bb_x0+bb_x1)/2,yy,2.75),'curb')
for xx in [bb_x0,bb_x1]:
    b.box((.08,bb_y1-bb_y0,.08),(xx,(bb_y0+bb_y1)/2,1.1),'curb');b.box((.08,bb_y1-bb_y0,.08),(xx,(bb_y0+bb_y1)/2,2.75),'curb')
# dark green stadium-side fence layer seen in the overhead footage.
for x in np.linspace(bb_x0,bb_x1,72): b.box((.08,.08,3.4),(x,bb_y1,1.75),'green_metal')
b.box((bb_x1-bb_x0,.08,.08),((bb_x0+bb_x1)/2,bb_y1,3.35),'green_metal')
# teal-green apron strip between basketball fence and red running track as seen overhead
b.extrude(Polygon([(-79,228), (107,228),(107,234),(-79,234)]),.06,.05,'track_apron')

# red-gable low service building beside the basketball/stadium zone visible in s03_4.
b.box((28,12,7.2),(-82,239,3.65),'white'); gable_roof(-82,239,30,14,7.25,0,'red2',4.5)
for xx in np.linspace(-92,-72,6): b.box((1.5,.18,1.45),(xx,232.9,3.8),'window_dark')

# ---------------- Athletic field / stadium ----------------
# Rebuilt as a true capsule track (straightaways + semicircular ends) matching the overhead field footage.
cx,cy=15,265
outer=LineString([(cx-52,cy),(cx+52,cy)]).buffer(38,cap_style=1,resolution=48)
inner=LineString([(cx-52,cy),(cx+52,cy)]).buffer(29.5,cap_style=1,resolution=48)
b.extrude(outer.difference(inner),.10,.02,'track')
# lane dividers as concentric capsule curves
for j in range(1,6):
    lane=LineString([(cx-52,cy),(cx+52,cy)]).buffer(38-j*1.42,cap_style=1,resolution=48).boundary.buffer(.055)
    b.extrude(lane,.025,.145,'court_line')
# rectangular football turf within the track
field_poly=Polygon([(cx-51,cy-28.5),(cx+51,cy-28.5),(cx+51,cy+28.5),(cx-51,cy+28.5)])
b.extrude(field_poly,.08,.08,'field')
# alternating mow/turf bands visible in the near-vertical stadium footage; real thin geometry, no image map.
for i,x0 in enumerate(np.linspace(cx-51,cx+51,13)[:-1]):
    x1=np.linspace(cx-51,cx+51,13)[i+1]
    if i%2==0:
        b.extrude(Polygon([(x0,cy-28.5),(x1,cy-28.5),(x1,cy+28.5),(x0,cy+28.5)]),.012,.165,'field2')
# pitch markings as physical white strips
for y in [cy-28.0,cy,cy+28.0]:b.box((102,.10,.025),(cx,y,.20),'court_line')
for x in [cx-51,cx,cx+51]:b.box((.10,56,.025),(x,cy,.20),'court_line')
# penalty/goal areas and center circle
for side in [-1,1]:
    gx=cx+side*50.5;b.box((.10,18,.025),(gx,cy,.20),'court_line')
    px=cx+side*39.5;b.box((.10,34,.025),(px,cy,.20),'court_line')
    for yy in [cy-17,cy+17]:b.box((11,.10,.025),(cx+side*45,yy,.20),'court_line')
    # simple white goals
    postx=cx+side*50.0
    for yy in [cy-3.7,cy+3.7]:b.box((.10,.10,2.45),(postx,yy,1.3),'court_line')
    b.box((.10,7.5,.10),(postx,cy,2.5),'court_line')
m=trimesh.creation.annulus(r_min=7.7,r_max=7.82,height=.025,sections=64);m.apply_translation((cx,cy,.20));b.add(m,'court_line')
# long white terrace, with a shorter central covered grandstand as seen from field level.
stand_y=307
b.box((104,8.0,3.2),(cx,stand_y,1.65),'white')
# stepped seating runs most of the long side
for i in range(8):b.box((100-i*1.8,1.35,.48),(cx,stand_y+4.0+i*1.10,.42+i*.48),'offwhite')
# front wall openings / doors
for x in np.linspace(cx-44,cx+44,15):b.box((2.2,.18,1.45),(x,stand_y-4.05,1.65),'window_dark')
# visible guard rails and two stair aisles on the stepped seating.
for xrail in [cx-48,cx+48]: b.box((.10,10.5,1.05),(xrail,stand_y+8.0,4.55),'metal')
for aisle in [cx-22,cx+22]:
    for i in range(8): b.box((3.0,1.38,.10),(aisle,stand_y+4.0+i*1.10,.72+i*.48),'stone')

# central roof only, supported by steel truss/columns
b.box((43,13,.48),(cx,stand_y+5.4,8.65),'roof2')
for x in np.linspace(cx-19,cx+19,5):
    b.cylinder_between((x,stand_y+1.0,3.25),(x,stand_y+4.8,8.35),.14,'dark',sections=8)
    b.cylinder_between((x,stand_y+10.0,3.25),(x,stand_y+6.0,8.35),.14,'dark',sections=8)
# roof fascia/banner beam as geometry, deep red like the footage
b.box((39,.35,.62),(cx,stand_y-.8,6.55),'red')
# two backdrop teaching/lab masses immediately behind the grandstand, visible in segment 04.
add_linear((-20,334),46,17,5,0,False,False,False,True)
add_linear((38,334),50,18,4,0,False,False,False,True)

# flanking campus buildings behind the field
add_linear((-83,326),54,15,4,0,False,False,False,True)
add_linear((103,326),58,15,4,0,False,False,False,True)

# ---------------- Landscape population ----------------
rng=np.random.default_rng(93);pos=[]
# garden dense clusters
for _ in range(92):
    x=rng.uniform(-145,-78);y=rng.uniform(-2,86)
    if west.contains(Point(x,y)):pos.append((x,y))
for _ in range(80):pos.append((rng.uniform(-38,38),rng.uniform(52,160)))
for y in np.linspace(-88,110,20):pos.extend([(-151,y),(130,y)])
for x in np.linspace(-145,126,25):pos.append((x,112))
for _ in range(55):pos.append((rng.uniform(45,140),rng.uniform(-155,-82)))
for _ in range(35):pos.append((rng.uniform(65,135),rng.uniform(-74,28)))
for i,(x,y) in enumerate(pos):
    if x*x+y*y<29*29:continue
    add_tree(x,y,rng.uniform(.72,1.18),i%3)
# clipped hedges / shrubs along plaza and building edges
for a in np.linspace(0,2*math.pi,24,endpoint=False):
    x,y=31.0*math.cos(a),31.0*math.sin(a);add_shrub(x,y,.70)
for x in np.linspace(-35,35,17):
    add_shrub(x,48,.58);add_shrub(x,92,.58)
# mature north-edge tree belt visible behind the ceremonial circle; intentionally irregular, all geometry.
for i,a in enumerate(np.linspace(58,112,13)):
    ar=math.radians(a); rr=35.0+(i%3)*1.1; add_tree(rr*math.cos(ar),rr*math.sin(ar),.92+0.06*(i%4),i%3)

# additional mature trees at source-visible east and southwest planting belts.
for yy in [-58,-6,72]:
    for i,xx in enumerate(np.linspace(-145,-72,10)): add_tree(xx,yy,.68+(i%3)*.05,(i+1)%3)
for i,(xx,yy) in enumerate([(62,47),(72,51),(82,54),(103,58),(115,54),(121,28),(119,-20),(112,-34),(-62,-32),(-66,-51),(-63,-70)]): add_tree(xx,yy,.86+(i%3)*.07,i%3)


# Source 2 foreground tree frame: large mature trees along the east approach road, geometry-only.
for i,(xx,yy,ss) in enumerate([(36,-22,1.35),(38,-11,1.28),(37,12,1.30),(35,23,1.38),(29,-30,1.15),(29,30,1.12)]):
    add_tree(xx,yy,ss,(i+1)%3)

# lamps around plaza
for a in np.linspace(0,2*math.pi,20,endpoint=False):
    x,y=32.5*math.cos(a),32.5*math.sin(a);b.cyl(.08,4.2,(x,y,2.15),'metal',sections=8);b.sphere(.18,(x,y,4.35),'stone',subdivisions=1)

# ---------------- Ground-level colonnades / corridors ----------------
# Deep covered corridor attached to the east face of the central south teaching bar.  The previous
# horizontal corridor floated through unrelated masses after the layout correction; this version
# runs north-south with the source building and leaves a clear walkable passage.
port_x,port_y=21.1,-106.0
b.box((6.4,74,.12),(port_x,port_y,.08),'stone')
b.box((.18,74,.22),(port_x-3.05,port_y,.18),'dark');b.box((.18,74,.22),(port_x+3.05,port_y,.18),'dark')
for y in np.linspace(-138,-74,17):b.box((.56,.56,5.0),(port_x,y,2.55),'white')
for y in np.linspace(-138,-74,17):b.box((.70,.70,.34),(port_x,y,.24),'dark')
b.box((6.2,73,.58),(port_x,port_y,5.35),'white');b.box((.55,72,.26),(port_x+3.0,port_y,1.0),'red')
for y in np.linspace(-134,-78,12):b.box((.16,2.65,3.05),(port_x+2.85,y,2.4),'glass',rotz=90)
# recessed ceiling light discs, represented as small physical cylinders.
for y in np.linspace(-134,-78,10):
    for x in [port_x-1.6,port_x,port_x+1.6]: b.cyl(.15,.045,(x,y,5.01),'stone',sections=16)
# tiled ceiling geometry (thin strips) to avoid a featureless slab.
for y in np.linspace(-138,-74,17):b.box((5.8,.05,.04),(port_x,y,5.04),'dark')
for x in np.linspace(port_x-2.6,port_x+2.6,8):b.box((.05,70,.04),(x,port_y,5.04),'dark')

# Small ceremonial court from segment 10: patterned concentric floor and accurately blocky white stepped monument.
scx,scy=145,-120
ring(0,12.5,.06,'plaza_red',.06,96,(scx,scy));ring(12.5,16,.06,'plaza_dark',.06,96,(scx,scy));ring(16,23.5,.06,'plaza',.06,96,(scx,scy))
for ang in [0,90,180,270]:
    th=math.radians(ang);u=np.array([math.cos(th),math.sin(th)]);v=np.array([-math.sin(th),math.cos(th)])
    for j in range(4):
        c=np.array([scx,scy])+u*(1.8+j*.55);b.box((1.2+2*j*.1,2.7,.18),(c[0],c[1],.20+j*.18),'stone',rotz=ang)
    for side in [-1,1]:
        for s in np.linspace(1.8,4.2,5):p=np.array([scx,scy])+u*s+v*side*1.55;b.box((.30,.30,.95),(p[0],p[1],1.05),'stone')
b.box((4.2,4.2,.65),(scx,scy,.6),'stone');b.cyl(.08,10,(scx,scy,5.6),'metal',sections=10)

# sparse vehicles seen in the footage, placed on roads / building forecourts.
add_car(-38,-55,18,'car_white',.92)
add_car(43,-96,2,'car_dark',1.0)
add_car(136,-92,92,'car_dark',1.03)
add_car(118,118,0,'car_white',.90)
add_car(-155,15,90,'car_white',.88)
add_car(148,16,90,'car_red',.90)

# ---------------- Export ----------------
scene,stats=b.finalize();scene.metadata={'name':'Campus unified scene V113','units':'meters','textures':0,'source':'geometry-only reconstruction from 10 uploaded video segments + 6 supplied comparison stills'}
glb=OUT/'campus_unified_V113.glb';glb.write_bytes(scene.export(file_type='glb'))
raw=glb.read_bytes();magic,ver,ln=struct.unpack_from('<III',raw,0);posi=12;j={}
while posi<len(raw):
    clen,ctype=struct.unpack_from('<II',raw,posi);posi+=8;ch=raw[posi:posi+clen];posi+=clen
    if ctype==0x4E4F534A:j=json.loads(ch.decode('utf-8').rstrip(' \t\r\n\x00'));break
strict={'textures':len(j.get('textures',[])),'images':len(j.get('images',[])),'samplers':len(j.get('samplers',[])),'texcoord_attributes':0,'color_attributes':0}
for mesh in j.get('meshes',[]):
    for p in mesh.get('primitives',[]):
        at=p.get('attributes',{});strict['texcoord_attributes']+=sum(1 for q in at if q.startswith('TEXCOORD'));strict['color_attributes']+=sum(1 for q in at if q.startswith('COLOR'))
(OUT/'zero_texture_check.json').write_text(json.dumps(strict,indent=2),encoding='utf-8')
summary={'scene_file':glb.name,'material_groups':len(stats),'parts_before_merge':sum(v['parts'] for v in stats.values()),'vertices':sum(v['vertices'] for v in stats.values()),'faces':sum(v['faces'] for v in stats.values()),'features':['stepped flagpole monument instead of prior fountain proxy','straight-faceted grey administration building with source-like glass towers, gabled atrium and entrance colonnade','source-like east science wing with moderate roof dome, central glass gable and elevated four-column gateway','secondary ceremonial court moved away from the science-wing dome to avoid the previous overlap','geometry-only Chinese pavilion with bracket/eave/rafter detail','four source-matched table-tennis slabs arranged 2x2 in the west garden','two north teaching bars plus three south north-south teaching bars instead of the former west-garden intrusions','northeast pitched-glass assembly hall and adjoining service annex','eight-court 4x2 basketball complex with green hoops, concrete joints and perimeter fence','capsule running track, football markings, stepped terrace and central truss-roof grandstand','modeled AC condensers, relief brick courses, roof repairs/vents, external galleries, tiled/lighted covered corridor, block-by-block plaza paving, road repairs and vehicles','zero UV textures, zero images, zero samplers, zero TEXCOORD/COLOR attributes']}
(OUT/'model_stats.json').write_text(json.dumps({'summary':summary,'groups':stats},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2));print('STRICT',strict)
