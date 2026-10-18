from pathlib import Path
import base64, hashlib, json, re, struct, subprocess, tempfile, sys
import trimesh

ROOT=Path(__file__).resolve().parent
HTML=ROOT/'打开地图_V113.html'
GLB=ROOT/'campus_unified_V113.glb'
checks=[]
def check(cond,name,detail=''):
    checks.append({'name':name,'ok':bool(cond),'detail':detail}); return bool(cond)

raw=HTML.read_bytes(); text=raw.decode('utf-8')
check(raw.count(b'\x00')==0,'HTML contains no NUL bytes',f"nul_count={raw.count(b'\x00')}")
check('<script src=' not in text and '<link rel=' not in text and '<img src=' not in text,'No external HTML assets')
check(all(x not in text for x in ['http://','https://','fetch(','XMLHttpRequest','WebSocket']),'No network dependencies')
check('V111' not in text and 'V112' not in text,'No stale viewer version labels')

m=re.search(r"const GLB_B64='([A-Za-z0-9+/=]+)';",text)
check(m is not None,'Embedded GLB assignment found')
model=GLB.read_bytes()
if m:
    embedded=base64.b64decode(m.group(1),validate=True)
    check(embedded==model,'Embedded GLB byte-identical to standalone GLB',f"sha256={hashlib.sha256(model).hexdigest()}")

# JS syntax, replacing giant model payload.
sm=re.search(r'<script>(.*)</script>',text,re.S)
if sm:
    js=re.sub(r"const GLB_B64='[A-Za-z0-9+/=]*';","const GLB_B64='AA==';",sm.group(1),count=1)
    with tempfile.NamedTemporaryFile('w',suffix='.js',encoding='utf-8',delete=False) as f:
        f.write(js); tmp=Path(f.name)
    try:
        pr=subprocess.run(['node','--check',str(tmp)],capture_output=True,text=True,timeout=30)
        check(pr.returncode==0,'JavaScript syntax check (node --check)',(pr.stderr or pr.stdout).strip())
    except Exception as e: check(False,'JavaScript syntax check (node --check)',repr(e))
    finally: tmp.unlink(missing_ok=True)
else: check(False,'Inline script block found')

# Requested interaction behavior.
needles={
 'Click anywhere enters pointer-lock mouse view':"canvas.addEventListener('click'",
 'Alt releases mouse':"e.code==='AltLeft'||e.code==='AltRight'",
 'Pointer lock exit call':'document.exitPointerLock()',
 'ESC left to browser pointer-lock handling':"if(e.code==='Escape')return",
 'Movement continues outside pointer lock':"function update(now){let dt=",
 'WASD defaults':"forward:'KeyW',backward:'KeyS',left:'KeyA',right:'KeyD'",
 'Space up / Shift down':"up:'Space',down:'ShiftLeft'",
 'Sensitivity setting':'id="sens" type="range" min="0.20" max="2.00"',
 'Speed setting':'id="speed" type="range" min="2" max="30"',
 'FOV setting':'id="fov" type="range" min="35" max="80"',
 'Key rebinding':'rebinding=a',
 'Teleport inputs':'id="tx"',
 'Teleport preserves angle by only replacing pos':'state.pos=[x,y,z]',
 'HUD coordinates to 0.1':'state.pos[0].toFixed(1)',
 'HUD angles to 0.1':'yd.toFixed(1)',
 'Six supplied view presets':'const suppliedViews={1:{pos:[-2.4,-46.4,3.1]',
 'View preset 6 exact coordinate':'6:{pos:[209.2,.8,38.9],yaw:178.9,pitch:-18.1}',
 'Material metallic factor parsed':'pm.metallicFactor',
 'Material roughness factor parsed':'pm.roughnessFactor',
 'Reflective/specular shader enabled':'float spec=pow(max(dot(N,H),0.0),gloss)',
}
for name,needle in needles.items(): check(needle in text,name)
# Explicitly ensure movement function is not gated on pointer lock.
mm=re.search(r'function update\(now\)\{(.*?)\}\s*function render',text,re.S)
check(mm is not None and 'pointerLockElement' not in mm.group(1),'Movement code is not pointer-lock gated')
check("state.yaw-=e.movementX*k" in text,'Mouse direction sign audit','movementX<0 increases yaw => turns left under +X/+Y convention')

# GLB structure and no-texture audit.
magic,ver,total=struct.unpack_from('<III',model,0)
check(magic==0x46546C67 and ver==2 and total==len(model),'Valid GLB 2.0 header',f'version={ver}, declared={total}, actual={len(model)}')
pos=12; gltf=None
while pos+8<=len(model):
    clen,ctype=struct.unpack_from('<II',model,pos); pos+=8; chunk=model[pos:pos+clen]; pos+=clen
    if ctype==0x4E4F534A:
        gltf=json.loads(chunk.decode('utf-8').rstrip(' \t\r\n\x00')); break
check(gltf is not None,'GLB JSON chunk parses')
if gltf:
    counts={k:len(gltf.get(k,[])) for k in ['textures','images','samplers']}
    texcoords=colors=0
    for mesh in gltf.get('meshes',[]):
        for prim in mesh.get('primitives',[]):
            attrs=prim.get('attributes',{})
            texcoords += sum(1 for k in attrs if k.startswith('TEXCOORD'))
            colors += sum(1 for k in attrs if k.startswith('COLOR'))
    check(counts['textures']==0 and counts['images']==0 and counts['samplers']==0 and texcoords==0 and colors==0,
          'No textures/images/samplers/UV or vertex-color attributes',f'{counts}, texcoord_attributes={texcoords}, color_attributes={colors}')
    check(len(gltf.get('materials',[]))>=65,'Substantial geometry material groups',f"materials={len(gltf.get('materials',[]))}")
    # flagpole material must be reflective in GLB, not just a UI claim.
    flagm=None
    for mat in gltf.get('materials',[]):
        if mat.get('name')=='flagpole': flagm=mat; break
    pm=(flagm or {}).get('pbrMetallicRoughness',{})
    check(flagm is not None and pm.get('metallicFactor',0)>=.9 and pm.get('roughnessFactor',1)<=.2,
          'Flagpole GLB material is high-metal / low-roughness',f"metallic={pm.get('metallicFactor')}, roughness={pm.get('roughnessFactor')}")

try:
    sc=trimesh.load(GLB,force='scene')
    geoms=[g for g in sc.geometry.values() if isinstance(g,trimesh.Trimesh)]
    v=sum(len(g.vertices) for g in geoms); f=sum(len(g.faces) for g in geoms)
    check(len(geoms)>=65 and v>=280000 and f>=480000,'Trimesh reload succeeds with substantial geometry',f'geometry_groups={len(geoms)}, vertices={v}, faces={f}, bounds={sc.bounds.tolist()}')
except Exception as e: check(False,'Trimesh reload succeeds with substantial geometry',repr(e))

report={
 'project':'Campus V113','viewer':HTML.name,'model':GLB.name,
 'html_bytes':len(raw),'glb_bytes':len(model),'sha256_glb':hashlib.sha256(model).hexdigest(),
 'passed':sum(c['ok'] for c in checks),'failed':sum(not c['ok'] for c in checks),'checks':checks,
 'runtime_note':'Static/self-contained validation completed in this sandbox. Pointer-lock click behavior was source-verified but not browser-automated because the sandbox does not provide a user-interactive local-file browser session.'
}
(ROOT/'audit_report_V113.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
lines=['# V113 静态/结构自检报告','',f"- 通过：{report['passed']}",f"- 失败：{report['failed']}",f"- GLB SHA-256：`{report['sha256_glb']}`",'']
for c in checks: lines.append(f"- {'PASS' if c['ok'] else 'FAIL'} — {c['name']}"+(f"：{c['detail']}" if c['detail'] else ''))
lines += ['','说明：此报告证明的是文件、控制代码、模型结构和禁止贴图约束；它不把静态代码检查伪装成真人浏览器体验，也不把当前画面伪装成已达到照片不可分辨。']
(ROOT/'audit_report_V113.md').write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps({'passed':report['passed'],'failed':report['failed'],'sha256':report['sha256_glb']},ensure_ascii=False))
if report['failed']:
    for c in checks:
        if not c['ok']: print('FAIL',c['name'],c['detail'])
    sys.exit(1)
