from pathlib import Path
import numpy as np, trimesh, vtk
from vtk.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray
OUT=Path(__file__).resolve().parent; R=OUT/'renders_v111';R.mkdir(exist_ok=True)
scene=trimesh.load(OUT/'campus_unified_V111.glb',force='scene')

def poly_from_mesh(m):
    pts=vtk.vtkPoints(); pts.SetData(numpy_to_vtk(np.asarray(m.vertices,dtype=np.float32),deep=True))
    faces=np.asarray(m.faces,dtype=np.int64)
    cells=np.empty((len(faces),4),dtype=np.int64);cells[:,0]=3;cells[:,1:]=faces
    ca=vtk.vtkCellArray();ca.SetCells(len(faces),numpy_to_vtkIdTypeArray(cells.ravel(),deep=True))
    pd=vtk.vtkPolyData();pd.SetPoints(pts);pd.SetPolys(ca)
    n=vtk.vtkPolyDataNormals();n.SetInputData(pd);n.ComputePointNormalsOn();n.ComputeCellNormalsOff();n.SplittingOff();n.ConsistencyOn();n.Update();return n.GetOutput()

def mat_color(g):
    try:
        f=np.asarray(g.visual.material.baseColorFactor,dtype=float)
        if f.max()>1.5:f=f/255.
        return tuple(float(x) for x in f[:3])
    except: return (.7,.7,.7)

def make_renderer():
    ren=vtk.vtkRenderer();ren.SetBackground(0.69,0.78,0.84);ren.UseShadowsOn();ren.SetAmbient(0.18,0.18,0.18);
    # actors
    for name,g in scene.geometry.items():
        if not isinstance(g,trimesh.Trimesh): continue
        mp=vtk.vtkPolyDataMapper();mp.SetInputData(poly_from_mesh(g));mp.ScalarVisibilityOff()
        a=vtk.vtkActor();a.SetMapper(mp);c=mat_color(g);a.GetProperty().SetColor(*c);a.GetProperty().SetAmbient(.24);a.GetProperty().SetDiffuse(.76);a.GetProperty().SetSpecular(.12);a.GetProperty().SetSpecularPower(18)
        if any(k in name.lower() for k in ['window','glass']):a.GetProperty().SetSpecular(.38);a.GetProperty().SetSpecularPower(42)
        ren.AddActor(a)
    # lights
    key=vtk.vtkLight();key.SetLightTypeToSceneLight();key.SetPosition(-260,-320,430);key.SetFocalPoint(0,20,0);key.SetIntensity(.92);key.SetColor(1.0,.96,.90);ren.AddLight(key)
    fill=vtk.vtkLight();fill.SetLightTypeToSceneLight();fill.SetPosition(300,180,260);fill.SetFocalPoint(0,0,0);fill.SetIntensity(.48);fill.SetColor(.78,.86,1.0);ren.AddLight(fill)
    rim=vtk.vtkLight();rim.SetLightTypeToSceneLight();rim.SetPosition(-20,350,350);rim.SetFocalPoint(0,60,0);rim.SetIntensity(.25);ren.AddLight(rim)
    return ren

def render(name,cam_pos,focal,viewup=(0,0,1),size=(1400,900),fov=35):
    ren=make_renderer();cam=ren.GetActiveCamera();cam.SetPosition(*cam_pos);cam.SetFocalPoint(*focal);cam.SetViewUp(*viewup);cam.SetViewAngle(fov);cam.SetClippingRange(.5,1600)
    rw=vtk.vtkRenderWindow();rw.SetOffScreenRendering(1);rw.SetSize(*size);rw.SetMultiSamples(8);rw.AddRenderer(ren)
    ren.ResetCameraClippingRange();rw.Render()
    wi=vtk.vtkWindowToImageFilter();wi.SetInput(rw);wi.SetInputBufferTypeToRGB();wi.ReadFrontBufferOff();wi.Update()
    wr=vtk.vtkPNGWriter();wr.SetFileName(str(R/name));wr.SetInputConnection(wi.GetOutputPort());wr.Write();rw.Finalize();print(name)


render('V111_topdown_layout.png',(0,65,620),(0,65,0),(0,1,0),fov=30)
render('V111_central_oblique.png',(190,-205,185),(0,5,8),fov=31)
render('V111_central_east.png',(170,-80,95),(15,5,8),fov=38)
render('V111_crescent_close.png',(-145,-120,85),(-48,5,8),fov=38)
render('V111_dome_close.png',(145,-75,70),(68,16,18),fov=36)
render('V111_sports.png',(210,135,170),(10,255,5),fov=37)
