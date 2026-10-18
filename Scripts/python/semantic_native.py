"""Rebuild Blender/native assets from exact GLB face spans into authored item objects."""
from pathlib import Path
import bpy,json,hashlib,numpy as np
from mathutils import Matrix

def build_semantic_native(data,acc,materials,manifest_path,glb_path,keep_existing=False,reuse_names=None,inventory_path=None):
 manifest_path=Path(manifest_path);doc=json.loads(manifest_path.read_text(encoding='utf-8'))
 src={}
 for m in data['meshes']:
  for p in m['primitives']:
   key=data['materials'][p['material']]['name'];src[key]=(acc(p['attributes']['POSITION']),acc(p['indices']).reshape(-1,3),materials[p['material']])
 assert all(n>=0 for n in doc['material_groups'].values());assert set(src)=={k for k,n in doc['material_groups'].items()if n>0}
 for key,(_,faces,_) in src.items():assert len(faces)==doc['material_groups'][key],key
 counts={k:np.zeros(len(v[1]),dtype=np.uint8) for k,v in src.items()}
 for row in doc['logical_objects']:
  for part in row['parts']:
   for start,count in part['face_runs']:counts[part['material']][start:start+count]+=1
 assert all(np.all(v==1) for v in counts.values()),'Object spans must cover every source face exactly once'
 del counts
 expected_names={q['name'] for q in doc['logical_objects']}
 obsolete=[o for o in bpy.context.scene.objects if o.type=='MESH' and (not keep_existing or o.name not in expected_names or (reuse_names is not None and o.name not in reuse_names))]
 old_data={o.data for o in obsolete}
 if obsolete:bpy.data.batch_remove(ids=obsolete)
 unused=[me for me in old_data if me.users==0]
 if unused:bpy.data.batch_remove(ids=unused)
 print('SEMANTIC_OBSOLETE_BATCH_REMOVED',len(obsolete),flush=True)
 # Root/group anchors at world origin keep all independent item pivots in world metres.
 # Each item itself has a local base/centre pivot, not the former campus-wide origin.
 parents={o.get('semantic_path'):o for o in bpy.context.scene.objects if keep_existing and o.type=='EMPTY' and o.get('semantic_path')};groups=[]
 existing={o.name:o for o in bpy.context.scene.objects if keep_existing and o.type=='MESH'}
 def parent(path):
  if path in parents:return parents[path]
  o=bpy.data.objects.new(path.split('/')[-1]+'__'+hashlib.sha1(path.encode()).hexdigest()[:8],None);bpy.context.scene.collection.objects.link(o)
  o['semantic_path']=path;o['semantic_role']='group';o.empty_display_type='PLAIN_AXES';o.empty_display_size=.12
  if '/' in path:o.parent=parent(path.rsplit('/',1)[0])
  if path in doc.get('group_origin_overrides',{}):
   o.matrix_world=Matrix.Translation(doc['group_origin_overrides'][path]);bpy.context.view_layer.update()
  parents[path]=o;groups.append({'name':o.name,'path':path,'parent':o.parent.name if o.parent else None});return o
 rows=[]
 for i,row in enumerate(doc['logical_objects']):
  if row['name'] in existing:
   ob=existing[row['name']];rows.append({'name':ob.name,'path':row['path'],'parent':ob.parent.name,'vertices':len(ob.data.vertices),'polygons':len(ob.data.polygons),'pivot':list(ob.matrix_world.translation),'material_slots':[m.name for m in ob.data.materials]});continue
  vertices=[];faces=[];face_material=[];mats=[]
  for part in row['parts']:
   v,f,mat=src[part['material']]
   ix=np.concatenate([np.arange(start,start+n) for start,n in part['face_runs']]);ff=f[ix]
   unique,inv=np.unique(ff.ravel(),return_inverse=True);offset=sum(len(q) for q in vertices)
   vertices.append(v[unique].astype(np.float64));faces.append(inv.reshape(-1,3)+offset)
   if mat not in mats:mats.append(mat)
   face_material.extend([mats.index(mat)]*len(ff))
  vv=np.concatenate(vertices);ff=np.concatenate(faces);lo=vv.min(0);hi=vv.max(0)
  pivot=np.array(row.get('pivot',[(lo[0]+hi[0])/2,(lo[1]+hi[1])/2,float(lo[2])]),float)
  me=bpy.data.meshes.new(row['name']);me.from_pydata((vv-pivot).tolist(),[],ff.tolist());me.update()
  for mat in mats:me.materials.append(mat)
  me.polygons.foreach_set('material_index',np.array(face_material,dtype=np.int32))
  ob=bpy.data.objects.new(row['name'],me);bpy.context.scene.collection.objects.link(ob);ob.parent=parent(row['path'].rsplit('/',1)[0]);ob.matrix_world=Matrix.Translation(pivot.tolist())
  ob['semantic_path']=row['path'];ob['semantic_category']=row['path'].split('/')[-2];ob['independently_editable']=True;ob['source_part_count']=len(row['parts'])
  if '/Trees/' in row['path']:
   for poly in me.polygons:
    if 'trunk' in me.materials[poly.material_index].name:poly.use_smooth=True
  rows.append({'name':ob.name,'path':row['path'],'parent':ob.parent.name,'vertices':len(me.vertices),'polygons':len(me.polygons),'pivot':pivot.tolist(),'material_slots':[m.name for m in mats]})
  if i%5000==0:print('SEMANTIC_OBJECTS_CREATED',i,'/',len(doc['logical_objects']),flush=True)
 bpy.context.view_layer.update();scene=bpy.context.scene
 scene['independent_object_requirement']='Every authored physical item has its own Transform/mesh and useful item pivot; building/floor/classroom/desk parents are retained in FBX.'
 scene['batched_glb_rendering_note']='GLB rendering remains material-batched for viewer performance; native/FBX exact face-span reconstruction preserves independent authored objects.'
 needed=set()
 for row in doc['logical_objects']:
  path=row['path'].rsplit('/',1)[0]
  while path:
   needed.add(path);path=path.rsplit('/',1)[0] if '/' in path else ''
 # No retained item has an ancestor in this set; remove unused groups together.
 obsolete_groups=[ob for path,ob in parents.items() if path not in needed]
 if obsolete_groups:bpy.data.batch_remove(ids=obsolete_groups)
 groups=[{'name':o.name,'path':o.get('semantic_path',''),'parent':o.parent.name if o.parent else None,'world_origin':list(o.matrix_world.translation)} for o in bpy.context.scene.objects if o.type=='EMPTY']
 proof={'source_glb_sha256':hashlib.sha256(Path(glb_path).read_bytes()).hexdigest(),'source_manifest_sha256':hashlib.sha256(manifest_path.read_bytes()).hexdigest(),'all_source_faces_assigned_exactly_once':True,'meshes':len(rows),'groups':groups,'objects':rows,'result':'PASS structure construction; actual FBX/Unity reimport still required','scope':'No source realism or whole-project completion acceptance'}
 (Path(inventory_path) if inventory_path is not None else manifest_path.with_name(manifest_path.stem.replace('object_manifest','native_object_structure')+'.json')).write_text(json.dumps(proof,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
 print('SEMANTIC_NATIVE_COMPLETE',len(rows),'item meshes',len(groups),'parents',flush=True)
 return proof


