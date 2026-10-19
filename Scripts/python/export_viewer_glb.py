"""Export a Blender scene as world-space POSITION/Uint32 material batches.

For the bundled campus viewer. The native .blend retains all editable items.
No mesh simplification, transform rewriting or material joining in the source file.
"""
from pathlib import Path
import json
import struct
import bpy
import numpy as np


def export_viewer_glb(path):
    path = Path(path)
    if path.exists():
        raise FileExistsError('Choose a new output file')
    bpy.context.view_layer.update()
    batches = {}
    for obj in bpy.context.scene.objects:
        if obj.type != 'MESH' or obj.hide_render:
            continue
        mesh = obj.data
        mesh.calc_loop_triangles()
        if not mesh.loop_triangles:
            continue
        v = np.empty(len(mesh.vertices)*3, dtype=np.float32)
        mesh.vertices.foreach_get('co', v)
        v = v.reshape(-1,3)
        transform = np.asarray(obj.matrix_world, dtype=np.float64)
        v = (v @ transform[:3,:3].T + transform[:3,3]).astype('<f4')
        faces = np.empty(len(mesh.loop_triangles)*3, dtype=np.int32)
        mesh.loop_triangles.foreach_get('vertices', faces)
        faces = faces.reshape(-1,3)
        if np.linalg.det(transform[:3,:3]) < 0:
            faces = faces[:,::-1]
        mi = np.empty(len(faces), dtype=np.int32)
        mesh.loop_triangles.foreach_get('material_index', mi)
        for index in np.unique(mi):
            mat = mesh.materials[int(index)] if int(index) < len(mesh.materials) else None
            ff = faces[mi==index]
            used, remap = np.unique(ff.ravel(),return_inverse=True)
            bucket = batches.setdefault(mat, [[],[],0])
            bucket[0].append(v[used]);bucket[1].append(remap.reshape(-1,3).astype('<u4')+bucket[2]);bucket[2]+=len(used)
    doc = {'asset': {'version':'2.0','generator':'Campus native scene material batch exporter',
                    'extras':{'campus_color_encoding':'LINEAR_GLTFFACTORS_V143','native_scene_version':int(bpy.context.scene.get('version',0))}},
           'scene':0,'scenes':[{'nodes':[]}],'nodes':[],'meshes':[],
           'materials':[],'accessors':[],'bufferViews':[]}
    chunks=[];offset=0;triangles=0
    def store(array, typ, component):
        nonlocal offset
        pad=(-offset)%4
        if pad:chunks.append(bytes(pad));offset+=pad
        view=len(doc['bufferViews']);data=array.tobytes()
        doc['bufferViews'].append({'buffer':0,'byteOffset':offset,'byteLength':len(data)})
        offset+=len(data);chunks.append(data)
        acc={'bufferView':view,'componentType':component,'count':len(array),'type':typ}
        if typ=='VEC3':acc.update(min=array.min(0).tolist(),max=array.max(0).tolist())
        doc['accessors'].append(acc)
        return len(doc['accessors'])-1
    for mat,(vs,fs,_) in batches.items():
        v=np.concatenate(vs);f=np.concatenate(fs).ravel().astype('<u4');triangles+=len(f)//3
        color=list(mat.diffuse_color) if mat else [.7,.7,.7,1]
        roughness=mat.roughness if mat else .7;metallic=mat.metallic if mat else 0
        transmission=0
        if mat and mat.use_nodes:
            bsdf=next((n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None)
            if bsdf:
                roughness=float(bsdf.inputs['Roughness'].default_value)
                metallic=float(bsdf.inputs['Metallic'].default_value)
                transmission=float(bsdf.inputs['Transmission Weight'].default_value)
                color[3]=min(color[3],float(bsdf.inputs['Alpha'].default_value))
        if transmission:color[3]=min(color[3],max(.08,1-.85*transmission))
        material={'name':mat.name if mat else 'default','doubleSided':True,'pbrMetallicRoughness':{'baseColorFactor':color,'metallicFactor':metallic,'roughnessFactor':roughness}}
        if color[3]<.99:material['alphaMode']='BLEND'
        index=len(doc['materials']);doc['materials'].append(material)
        pa=store(v,'VEC3',5126);ia=store(f,'SCALAR',5125)
        doc['meshes'].append({'name':material['name'],'primitives':[{'attributes':{'POSITION':pa},'indices':ia,'material':index,'mode':4}]})
        doc['nodes'].append({'mesh':index});doc['scenes'][0]['nodes'].append(index)
    binary=b''.join(chunks);binary+=bytes((-len(binary))%4);doc['buffers']=[{'byteLength':len(binary)}]
    metadata=json.dumps(doc,separators=(',',':')).encode();metadata+=b' '*((-len(metadata))%4)
    total=28+len(metadata)+len(binary)
    with path.open('wb') as out:
        out.write(struct.pack('<III',0x46546c67,2,total));out.write(struct.pack('<II',len(metadata),0x4e4f534a));out.write(metadata);out.write(struct.pack('<II',len(binary),0x004e4942));out.write(binary)
    return {'path':str(path),'triangles':triangles,'materials':len(batches),'bytes':total}
