# 接续共用代码：什么时候调用

接手续改使用已有 `.blend`。本包提取的是多轮实际重复使用的功能代码；旧文件名的新旧不作为筛选标准。没有版本 seed、建筑修补入口、课堂翻向、树木替换、迁移、收尾、临时测试或模型文件。本次没有运行建模或导出模型。

## 按任务找脚本

| 要做的事 / 何时调用 | 脚本与函数 | 输入和调用方式 |
|---|---|---|
| 要从多边形、带孔轮廓做真实厚墙、楼板、弧边实体 | `python/geometry_prism.py` → `closed_prism(poly,height,z,delta=...)` | Python 导入函数，传 Shapely 多边形、厚度/高度、底面Z；返回 Trimesh。已包含浮点导出后闭合/绕序检查。修改实体轮廓时用，不是每次打开工程都调用。 |
| 要读取未压缩的材料批次 GLB，分析顶点/面，取出某物件的面段 | `python/glb_mmap.py` → `ActualGLB(path)`；`python/mesh_parts.py` → `getparts(row,G)` | `g=ActualGLB(path)`，用 `g.G` 的材料顶点/面数组配合物件清单 `row`。它不支持 Meshopt、任意交错属性；**不能直接喂当前压缩 GLB**。普通 Blender 编辑不需要调用。 |
| 修墙洞/板边时，要只切掉指定平面或包围盒内三角面 | `python/mesh_parts.py` → `flat_cut(parts,axis,plane,cut)` / `subtract_volume(parts,lower,upper)` | parts 是 `(材料名,顶点数组,三角面数组)` 列表；传裁切多边形或三维范围。它们切三角面，不自动补洞侧壁；需要实体闭合时配合上面的棱柱函数。 |
| 程序生成了材料合批网格，需要还原逐窗/逐门等独立对象和父级 | `python/semantic_native.py` → `build_semantic_native(data,acc,materials,manifest_path,glb_path,...,inventory_path=...)` | 在 Blender Python 中调用；传对应 GLB 数据、读取函数、Blender材质和**同一份网格的准确 face_runs 物件清单**。不在 import 时修改场景；调用会重建物件，使用工程副本。直接编辑当前 `.blend` 不必调用。**旧174清单不能套回已重排索引的175压缩GLB。** |
| 新一轮要按语义物件导出并核对独立 FBX | `python/fbx_export.py` → `export_campus_fbx(native,glb,fbx,audit,inventory_path)` | 先在 Blender 打开相应已保存工程，传同一版原生、查看GLB、目标FBX、核验输出及新物件清单。保留实际多轮用过的层级、退化面处理、透明兼容和核对核心；清单路径改为参数。普通手动 FBX 导出可直接用 Blender 菜单，无需强行使用这套清单流程。 |
| 新做了查看用 GLB，需要减小传输体积 | `glb/encode.mjs` | `node glb/encode.mjs 未压缩查看模型.glb 压缩查看模型.glb`。保留实际编码/焊接/重排/即时解码检查核心，去掉175专用输入、恢复旧材质和输出路径；不简化三角面，不量化位置。只接受本项目未压缩、POSITION、Uint32索引、三角面批次。源文件不能已经是 Meshopt。Node 18+，所需编码库已附，不需联网安装。 |
| 修改模型后，需要新的离线预览 HTML；或修改移动/光影/控制方式 | `viewer/embed_model.py` 与 `viewer/campus.template.html` | `python viewer/embed_model.py 新查看模型.glb 打开地图.html`。前者抽出146—174多轮相同的gzip/Base64嵌入步骤；后者是现用查看器去掉模型数据后的源码。改控制/着色/快捷相机时改模板；只换模型时调用嵌入脚本。输出要求新文件，不覆盖输入。 |
| 渲染检查时调整观察位置，或套用已经求得的原视频相机 | `python/camera_tools.py` → `camera(cam,pos,target,ortho=False)` / `calibrated(scene,cam,c)` | 在 Blender Python 中调用，传当前场景/相机；c 含 `size,K,R,t,C`。第二个函数沿用项目无畸变、同焦距的相机约定，并比较CV投影与Blender投影；不是自动标定视频的工具。这里只放相机核心，不带旧机位列表、重建场景或渲染任务入口。 |
| Unity 中只改一个物件的材质，避免同类物件一起变 | `unity/Editor/CampusIndependentMaterial175.cs` | 放进接手工程 Assets 下的 Editor 文件夹，场景中选物件，点 `Campus/V175/选中物件独立材质`。当前 unitypackage 已含同名脚本，有了就不要重复安装。名字保留175，但复制材质/重新绑定的核心在174、175实际复用，后续仍适用。 |

## 接续主线

手工继续建模：打开现有 `.blend` → 修改并另存 → 需要时导出/预览。**不要为了接手续改先运行语义重建函数**；它服务于程序网格流水线。

程序继续建模：几何/裁切核心 → 同步生成物件清单 → 需要时用语义重建及核验导出核心 → 查看GLB压缩 → 嵌入HTML。物件清单必须与当前网格面索引对应，不能拿旧数据顶替。

FBX 不必另传：Blender 接手续改有当前 `.blend` 即可；Unity 接续可给现有 `.unitypackage`，里面已有同一份 FBX。当前 GLB 是合批预览，不是逐物件编辑主文件。

## 复用依据和保留判断

- 棱柱函数虽源名带143，后续150科学楼外墙与174墙洞/楼板仍调用，保留。
- GLB内存映射读取器源名带146，150、174、175等生成/核对流程持续导入，保留。
- 按面段还原独立物件的主体来自144，经过160父级原点处理，173/174仍沿用；提取运行中实际采用的处理，不带160那次移动试验，保留。
- 三角面裁切/取物件面段跨多次窗洞、墙板修订复用；剥离建筑坐标和修补名单，保留。
- FBX函数主体149、169、174、175反复用于实际导出；保留最新透明兼容，去掉版本清单路径绑定，保留。
- 相机核心来自持续被后续渲染入口引用的144公共渲染代码；保留定位/投影函数，去掉整场景加载、灯光试验和具体渲染清单。
- 查看器及gzip嵌入跨多版本沿用；保留现用核心。GLB编码是近期新增但已用于有/无光影两种实际输出，后续每轮控制查看文件大小仍直接需要，保留编码核心，不传175那次植物替换或材质修复入口。
- Unity独立材质复制逻辑在174和175实际导入/编辑核验中复用；继续做Unity微调仍有用，保留。

这些是共用功能的提取，参数化只替换硬编码路径或原先依赖的全局变量；没有为交接另写一套模型生成器。复用的函数体出处在 `来源.json` 中。

## 依赖与范围

Python几何/网格模块使用 NumPy、Trimesh、Shapely 2.1+；Blender模块使用其自带 bpy/mathutils/NumPy，外部包须匹配该 Blender 的 Python 版本，不把其它 Python 的二进制包直接混进来。查看器/嵌入脚本不需要 Python 第三方包。Meshoptimizer 1.3.0 的必要运行文件。
