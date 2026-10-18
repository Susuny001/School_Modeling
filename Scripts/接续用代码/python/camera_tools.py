"""Camera functions reused by multiple actual render iterations. No model loading or rendering on import."""
import bpy
import numpy as np
from mathutils import Matrix,Vector
from bpy_extras.object_utils import world_to_camera_view

def camera(cam,pos,target,ortho=False):
    cam.location=pos;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler()
    cam.data.type='ORTHO' if ortho else 'PERSP';cam.data.ortho_scale=420 if ortho else 400;cam.data.lens=36

def calibrated(scene,cam,c):
    w,h=c['size'];K=np.array(c['K']);R=np.array(c['R'])
    rot=R.T@np.diag([1.,-1.,-1.]);cam.matrix_world=Matrix(np.block([[rot,np.array(c['C'])[:,None]],[np.zeros((1,3)),np.ones((1,1))]]).tolist())
    cam.data.type='PERSP';cam.data.sensor_fit='HORIZONTAL';cam.data.sensor_width=36
    cam.data.lens=float(K[0,0]*36/w);cam.data.shift_x=float((w/2-K[0,2])/w);cam.data.shift_y=float((K[1,2]-h/2)/w)
    scene.render.resolution_x=w;scene.render.resolution_y=h;scene.render.pixel_aspect_x=scene.render.pixel_aspect_y=1
    bpy.context.view_layer.update()
    errors=[]
    for q in [(0,0,0),(24,0,0),(0,24,0),(-40,70,17),(45,-70,13.6)]:
        p=K@(R@np.array(q)+np.array(c['t']));p=p[:2]/p[2]
        v=world_to_camera_view(scene,cam,Vector(q));actual=np.array([v.x*w,(1-v.y)*h]);errors.append(np.linalg.norm(p-actual))
    maximum=float(max(errors))
    print('CAMERA_PROJECTION_CHECK',maximum)
    if maximum>.03:raise RuntimeError('Blender camera and CV camera do not agree')
    return maximum
