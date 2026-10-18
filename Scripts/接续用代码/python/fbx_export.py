"""Actual binary FBX export from the saved semantic native scene.
Replacement for the missing legacy v130 helper. No launch on import.
The saved .blend is never modified; any zero/duplicate-face fix is export-only.
"""
from pathlib import Path
import bpy,json,hashlib,numpy as np,time,struct
def export_campus_fbx(native,glb,fbx,audit,inventory_path):
 native,glb,fbx,audit=map(lambda p:Path(p).resolve(),[native,glb,fbx,audit])
 sha=lambda p:hashlib.file_digest(Path(p).open('rb'),'sha256').hexdigest()
 native_hash=sha(native);glb_hash=sha(glb);inv=json.loads(Path(inventory_path).read_text(encoding='utf-8'));assert inv['source_glb_sha256']==glb_hash
 bpy.context.view_layer.update();objects={o.name:o for o in bpy.context.scene.objects};wanted={r['name']for r in inv['objects']+inv['groups']};assert wanted<=set(objects)
 for o in bpy.context.scene.objects:o.select_set(False)
 for name in wanted:objects[name].select_set(True)
 bpy.context.view_layer.objects.active=objects[inv['objects'][0]['name']]
 bpy.context.scene.unit_settings.system='METRIC';bpy.context.scene.unit_settings.scale_length=1.;bpy.context.scene.unit_settings.length_unit='METERS'
 source_stats=[];expected=[];norms=[];swapped=[]
 def arrays(o):
  m=o.data;vv=np.empty(len(m.vertices)*3,dtype=np.float64);m.vertices.foreach_get('co',vv);vv=vv.reshape(-1,3);tot=np.empty(len(m.polygons),dtype=np.int32);m.polygons.foreach_get('loop_total',tot);assert np.all(tot==3),(o.name,'Non-triangle native face')
  ff=np.empty(len(m.loops),dtype=np.int32);m.loops.foreach_get('vertex_index',ff);ff=ff.reshape(-1,3);mi=np.empty(len(m.polygons),dtype=np.int32);m.polygons.foreach_get('material_index',mi);return vv,ff,mi
 def stats(o,vv,ff):
  matrix=np.array(o.matrix_world,dtype=np.float64);world=vv@matrix[:3,:3].T+matrix[:3,3];p=world[ff];area=float(np.linalg.norm(np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]),axis=1).sum()*.5);assert len(vv)and len(ff)and area>0,o.name;ids=np.unique(np.linspace(0,len(world)-1,min(8,len(world))).astype(int))
  return {'name':o.name,'parent':o.parent.name if o.parent else None,'semantic_path':o.get('semantic_path'),'vertices':len(vv),'polygons':len(ff),'surface_area_m2':area,'world_min':world.min(0).tolist(),'world_max':world.max(0).tolist(),'world_sample_points':world[ids].tolist()}
 for i,row in enumerate(inv['objects']):
  o=objects[row['name']];assert o.type=='MESH'and o.parent.name==row['parent'];vv,ff,mi=arrays(o);source=stats(o,vv,ff);source_stats.append(source);tri=vv[ff];areas=np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1);keep=areas>0;zero=int(np.count_nonzero(~keep));keys=np.sort(ff,axis=1);dup=len(keys)-len(np.unique(keys,axis=0))
  if zero or dup:
   original=o.data;good=ff[keep];mats=mi[keep]
   if dup:ev=vv[good].reshape(-1,3);ef=np.arange(len(ev)).reshape(-1,3)
   else:ev=vv;ef=good
   mesh=bpy.data.meshes.new(original.name+'_FBX_EXPORT_ONLY');mesh.from_pydata(ev.tolist(),[],ef.tolist())
   for mat in original.materials:mesh.materials.append(mat)
   mesh.polygons.foreach_set('material_index',mats);mesh.update();o.data=mesh;swapped.append((o,original));ev,ef,_=arrays(o);exported=stats(o,ev,ef);expected.append(exported);norms.append({'mesh':o.name,'zero_area_faces_removed_only_for_export':zero,'coincident_faces_separated_by_vertex_identity':int(dup+1 if dup else 0),'source_vertices':len(vv),'export_vertices':len(ev),'source_polygons':len(ff),'export_polygons':len(ef),'source_surface_area_m2':source['surface_area_m2'],'export_surface_area_m2':exported['surface_area_m2'],'saved_native_geometry_modified':False})
  else:expected.append(source)
  if i%15000==0:print('FBX_CORE_FBX_SOURCE_STATS',i,'/',len(inv['objects']),flush=True)
 assert not any(n.type=='TEX_IMAGE'for m in bpy.data.materials if m.use_nodes for n in m.node_tree.nodes)
 settings={'filepath':str(fbx),'check_existing':False,'use_selection':True,'use_visible':False,'global_scale':1.,'apply_unit_scale':True,'apply_scale_options':'FBX_SCALE_NONE','use_space_transform':True,'bake_space_transform':False,'axis_forward':'-Z','axis_up':'Y','object_types':{'MESH','EMPTY'},'use_mesh_modifiers':False,'mesh_smooth_type':'FACE','use_triangles':False,'add_leaf_bones':False,'bake_anim':False,'path_mode':'STRIP','embed_textures':False,'use_custom_props':True}
 # StandardFBX exports Principled Alpha, not glTF/Principled transmission.
 # Adapt only export-memory alpha for actual source transparent materials;
 # physical native/glTF material definitions and RGB remain unchanged.
 with glb.open('rb')as gf:
  gf.seek(12);jn,jt=struct.unpack('<II',gf.read(8));jd=json.loads(gf.read(jn))
 used={m.name for name in wanted for m in(objects[name].data.materials if objects[name].type=='MESH'else[])if m};alpha_changes=[];restore_alpha=[]
 for spec in jd['materials']:
  name=spec['name'];pm=spec.get('pbrMetallicRoughness',{});source_alpha=pm.get('baseColorFactor',[1,1,1,1])[3];tf=spec.get('extensions',{}).get('KHR_materials_transmission',{}).get('transmissionFactor',0)
  if name not in used or(tf<=0 and source_alpha>=.999):continue
  alpha=max(.08,min(source_alpha,1-.85*tf))if tf>0 else source_alpha;mat=bpy.data.materials[name];bs=mat.node_tree.nodes.get('Principled BSDF');restore_alpha.append((mat,bs,float(bs.inputs['Alpha'].default_value),tuple(mat.diffuse_color)));bs.inputs['Alpha'].default_value=alpha;c=list(mat.diffuse_color);c[3]=alpha;mat.diffuse_color=c;alpha_changes.append({'source_name':name,'source_gltf_alpha':source_alpha,'source_transmission':tf,'actual_fbx_alpha_fallback':alpha,'native_saved_file_unchanged':True})
 print('FBX_CORE_FBX_TRANSPARENCY_FALLBACK_MATERIALS',len(alpha_changes),flush=True)
 print('FBX_CORE_BINARY_FBX_EXPORT_STARTED',len(inv['objects']),len(inv['groups']),'export_only_normalized',len(norms),flush=True);result=bpy.ops.export_scene.fbx(**settings);assert result=={'FINISHED'}and fbx.stat().st_size>1000000
 for mat,bs,alpha,col in restore_alpha:bs.inputs['Alpha'].default_value=alpha;mat.diffuse_color=col
 for o,m in swapped:o.data=m
 assert sha(native)==native_hash,'Saved native file was modified during export';assert fbx.open('rb').read(23)==b'Kaydara FBX Binary  \x00\x1a\x00'
 doc={'format':'Actual binary FBX exported by Blender','native_project':str(native),'source_glb':str(glb),'source_glb_sha256':glb_hash,'source_native_sha256':native_hash,'fbx':str(fbx),'fbx_sha256':sha(fbx),'fbx_bytes':fbx.stat().st_size,'model_meshes':len(inv['objects']),'hierarchy':inv['groups'],'source_mesh_stats':source_stats,'expected_fbx_mesh_stats':expected,'export_only_normalization':norms,'axis_forward':'-Z','axis_up':'Y','unit_metres':True,'image_textures_embedded':False,'export_only_transparency_fallback':alpha_changes,'transparency_limit':'FBX scalar transparency preserves open glass visibility, not native physical refraction equivalence. Unity shader/GUI remains unverified.','export_scope':'Actual saved semantic native scene meshes and groups selected exactly by native manifest. Every object retained as its own node, no material-class joining. No importer/GUI or source-fidelity pass implied.','actual_exporter_options':{k:sorted(v)if isinstance(v,set)else v for k,v in settings.items()},'helper_replacement_reason':'Legacy fbx_export_hook_v130.py absent at actual149 export. This helper uses the installed Blender FBX exporter and writes actual source/per-export geometry evidence; Unity import remains required.'};audit.write_text(json.dumps(doc,ensure_ascii=False,separators=(',',':')),encoding='utf-8');print('FBX_CORE_BINARY_FBX_EXPORTED',doc['fbx_sha256'],doc['fbx_bytes'],flush=True);return doc
