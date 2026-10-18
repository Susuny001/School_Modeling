from pathlib import Path
import math, numpy as np, trimesh, vtk
from vtk.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray
ROOT=Path(__file__).resolve().parent; OUT=ROOT/'renders_v113'; OUT.mkdir(exist_ok=True)
scene=trimesh.load(ROOT/'campus_unified_V113.glb',force='scene')

def poly_from_mesh(m):
    pts=vtk.vtkPoints(); pts.SetData(numpy_to_vtk(np.asarray(m.vertices,dtype=np.float32),deep=True))
    faces=np.asarray(m.faces,dtype=np.int64); cells=np.empty((len(faces),4),dtype=np.int64); cells[:,0]=3; cells[:,1:]=faces
    ca=vtk.vtkCellArray(); ca.SetCells(len(faces),numpy_to_vtkIdTypeArray(cells.ravel(),deep=True))
    pd=vtk.vtkPolyData(); pd.SetPoints(pts); pd.SetPolys(ca)
    n=vtk.vtkPolyDataNormals(); n.SetInputData(pd); n.ComputePointNormalsOn(); n.SplittingOff(); n.ConsistencyOn(); n.Update(); return n.GetOutput()

def mat_color(g):
    try:
        f=np.asarray(g.visual.material.baseColorFactor,dtype=float)
        if f.max()>1.5:f=f/255.
        return tuple(float(x) for x in f[:3])
    except:return (.7,.7,.7)

def make_renderer():
    ren=vtk.vtkRenderer(); ren.SetBackground(0.78,0.84,0.87); ren.SetAmbient(0.34,0.34,0.34); ren.UseShadowsOn()
    for name,g in scene.geometry.items():
        if not isinstance(g,trimesh.Trimesh):continue
        mp=vtk.vtkPolyDataMapper(); mp.SetInputData(poly_from_mesh(g)); mp.ScalarVisibilityOff()
        a=vtk.vtkActor(); a.SetMapper(mp); a.GetProperty().SetColor(*mat_color(g)); a.GetProperty().SetAmbient(.34); a.GetProperty().SetDiffuse(.70)
        lname=name.lower()
        if 'flagpole' in lname:
            a.GetProperty().SetSpecular(.95); a.GetProperty().SetSpecularPower(90)
        elif any(k in lname for k in ['glass','window','dome']):
            a.GetProperty().SetSpecular(.42); a.GetProperty().SetSpecularPower(48)
        else:
            a.GetProperty().SetSpecular(.10); a.GetProperty().SetSpecularPower(16)
        ren.AddActor(a)
    key=vtk.vtkLight(); key.SetLightTypeToSceneLight(); key.SetPosition(190,-240,360); key.SetFocalPoint(0,0,0); key.SetIntensity(.92); key.SetColor(1.0,.96,.91); ren.AddLight(key)
    fill=vtk.vtkLight(); fill.SetLightTypeToSceneLight(); fill.SetPosition(-260,180,220); fill.SetFocalPoint(0,0,0); fill.SetIntensity(.38); fill.SetColor(.78,.88,1.0); ren.AddLight(fill)
    return ren

def render(i,pos,yaw,pitch,size):
    ren=make_renderer(); cam=ren.GetActiveCamera(); ya=math.radians(yaw); pi=math.radians(pitch); cp=math.cos(pi)
    d=np.array([cp*math.cos(ya),cp*math.sin(ya),math.sin(pi)])
    focal=np.array(pos)+d*100
    cam.SetPosition(*pos); cam.SetFocalPoint(*focal); cam.SetViewUp(0,0,1); cam.SetViewAngle(60); cam.SetClippingRange(.08,1800)
    rw=vtk.vtkRenderWindow(); rw.SetOffScreenRendering(1); rw.SetSize(*size); rw.SetMultiSamples(8); rw.AddRenderer(ren); ren.ResetCameraClippingRange(); rw.Render()
    wi=vtk.vtkWindowToImageFilter(); wi.SetInput(rw); wi.SetInputBufferTypeToRGB(); wi.ReadFrontBufferOff(); wi.Update()
    out=OUT/f'V113_match_{i}.png'; wr=vtk.vtkPNGWriter(); wr.SetFileName(str(out)); wr.SetInputConnection(wi.GetOutputPort()); wr.Write(); rw.Finalize(); print(out.name)

cams={
1:((-2.4,-46.4,3.1),118.2,15.6,(1280,960)),
2:((48.4,0.8,3.1),176.2,4.1,(1080,810)),
3:((-86.3,-114.0,37.9),44.5,-12.1,(1200,540)),
4:((-111.1,-109.6,37.9),0.7,-18.8,(1200,540)),
5:((156.8,27.0,38.9),178.7,-14.9,(1200,590)),
6:((209.2,0.8,38.9),178.9,-18.1,(1200,540)),
}
for i,(pos,y,p,s) in cams.items():render(i,pos,y,p,s)
