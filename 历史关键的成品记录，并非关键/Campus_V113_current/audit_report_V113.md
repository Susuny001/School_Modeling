# V113 静态/结构自检报告

- 通过：35
- 失败：0
- GLB SHA-256：`c8cf01c1477893b490a7aa2a040320718c36900910613d577feba1bebbcb200c`

- PASS — HTML contains no NUL bytes：nul_count=0
- PASS — No external HTML assets
- PASS — No network dependencies
- PASS — No stale viewer version labels
- PASS — Embedded GLB assignment found
- PASS — Embedded GLB byte-identical to standalone GLB：sha256=c8cf01c1477893b490a7aa2a040320718c36900910613d577feba1bebbcb200c
- PASS — JavaScript syntax check (node --check)
- PASS — Click anywhere enters pointer-lock mouse view
- PASS — Alt releases mouse
- PASS — Pointer lock exit call
- PASS — ESC left to browser pointer-lock handling
- PASS — Movement continues outside pointer lock
- PASS — WASD defaults
- PASS — Space up / Shift down
- PASS — Sensitivity setting
- PASS — Speed setting
- PASS — FOV setting
- PASS — Key rebinding
- PASS — Teleport inputs
- PASS — Teleport preserves angle by only replacing pos
- PASS — HUD coordinates to 0.1
- PASS — HUD angles to 0.1
- PASS — Six supplied view presets
- PASS — View preset 6 exact coordinate
- PASS — Material metallic factor parsed
- PASS — Material roughness factor parsed
- PASS — Reflective/specular shader enabled
- PASS — Movement code is not pointer-lock gated
- PASS — Mouse direction sign audit：movementX<0 increases yaw => turns left under +X/+Y convention
- PASS — Valid GLB 2.0 header：version=2, declared=9313772, actual=9313772
- PASS — GLB JSON chunk parses
- PASS — No textures/images/samplers/UV or vertex-color attributes：{'textures': 0, 'images': 0, 'samplers': 0}, texcoord_attributes=0, color_attributes=0
- PASS — Substantial geometry material groups：materials=70
- PASS — Flagpole GLB material is high-metal / low-roughness：metallic=0.92, roughness=0.16
- PASS — Trimesh reload succeeds with substantial geometry：geometry_groups=70, vertices=283511, faces=489152, bounds=[[-396.504638671875, -300.0, -1.251175045967102], [391.8020324707031, 461.26104736328125, 52.75715255737305]]

说明：此报告证明的是文件、控制代码、模型结构和禁止贴图约束；它不把静态代码检查伪装成真人浏览器体验，也不把当前画面伪装成已达到照片不可分辨。