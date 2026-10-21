# 独立虚拟形象：下一模型实施交接
时间：2026-10-21T17:58:00+08:00。
会话：Codex-20261021-avatar-handoff-plan。任务：T029完成；下一项T028。

## 用户本轮要求与唯一方案
用户：“你制定好研发路线和方案后，我在切换slo模型开发”。本轮只整理可执行方案，不切换模型、不创建新聊天、不实施产品。之前“按照路线开发”的授权仍有效，下一模型可直接推进日常本地研发，不重问是否开始。

先读AGENTS.md、docs/COLLABORATION.md、state/STATUS.md、TASKS.md、DECISIONS.md，再读[AVATAR执行基线](../docs/AVATAR.md)。规范只有AVATAR一份；本交接说明当前环境和起步动作，不另立架构。检查Git与写锁后领取T028。用户选定C深色发通讯员；正式C未建模，官方Seed-san不是C；旧2D观感被否定，不继续拼贴扩库。

当前仍在D:/work/TheEarthPeopleLog；虚拟形象业务独立，物理迁仓尚未执行。现有新闻／地点应用不属于本轮修改范围。大量源码／规范是未跟踪的合法工作成果，不当作垃圾；不自动提交、推送、删除或移动素材。

## 第一轮必须完成什么
1. 领取T028并取得自己的排他写锁。核对avatar3d版本、构建清单和本机依赖；旧源文件基线见本轮verification报告。先用现有代码，不重写队列／透明编码。
2. 对Warudo、OBS、VRoid做有界安装盘点：标准路径、卸载注册表项和已有Steam库位置／应用入口。之前仅查两个默认路径不存在，不能声称机器未装。记录真实版本／位置；只读盘点不收集账号或凭据。
3. 建立一份M1验证记录：模型导入、实时自由镜头、手动动作／基础表情、OBS干净透明输出、现有MOV在剪映叠加、自制挥手跨工具、失败／恢复。各项先标待验，实际运行才改状态。采用AVATAR默认路线，不再写一轮候选工具百科。
4. 先用现有Seed-san验证直播端与离线端；M1内置动作通过后，还须让一条自制骨骼挥手从同一可编辑母版进入两端。Warudo角色动画Mod需要匹配的Unity／SDK与Humanoid导入；不要假设能直接读Python曲线、.blend或VRMA。记录真实转换步骤和限制，保留样例署名。
5. 同步整理已有C参考与建模差异清单，准备T030可编辑初模。已有C参考见下文，不重发角色选择题。造型需要用户看到真实样稿反馈；其他独立研发可以继续。无法达到美术门槛须说明具体缺项，不能用测试模型充数。
6. 缺安装／账号登录时先完成可自动化的核查、配置模板、验证素材和资产准备，再给用户当前必需的最短操作。登录、付费或真人摄像头交互不能伪造完成；不能因为需登录就直接开做替代引擎。无需真实公开开播即可完成OBS本地合成验收。

第一轮交付应至少有真实环境盘点、可复现技术样段或明确失败证据、兼容矩阵和下一项资产工作；未完成的客户端／用户交互项保持待验。不要用测试数量或新增按钮替代这些成果。M1通过后按T030—T033实施；T027仅按明确缺口启动。

## 可直接复用的文件与运行环境
- 唯一方案：docs/AVATAR.md；C参考：design/avatars/2026-10-20-concepts/c-reference-v1.png、concepts-v1.png、c-model-brief.json。参考PNG不是3D源工程。
- 当前源代码：avatar3d/与avatar3d_entry.py；构建scripts/build-avatar3d.py；测试tests/test_avatar3d.py、tests/test_avatar3d_ui.py。
- 当前EXE：dist/avatar3d/0.1.1/EarthPeopleLogAvatar3D/EarthPeopleLogAvatar3D.exe；build-manifest.json在同目录。根目录地球三维角色工坊.lnk为当前入口，用户进程可能仍开着，不擅自终止。
- 用户工作区.avatar3d；运行配置.runtime/avatar3d/runtime.json；便携Blender位于.runtime/avatar3d/blender-4.5.13-windows-x64/blender.exe；VRM插件.runtime/avatar3d/plugin/io_scene_vrm。版本／下载哈希在avatar3d/assets/runtime-lock.json。
- Python：C:/Users/WonderMan/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe。项目依赖.runtime/python。QtWebEngine／WebChannel已存在，但不代表实现了实时Tab。
- 样例模型avatar3d/assets/Seed-san.vrm，VirtualCast, Inc.；许可证与出处保留。技术素材在工作素材/虚拟形象/20261021_3D骨骼技术验证；.runtime、dist、用户工作区和工作素材均忽略Git，忽略不等于允许删除。

PowerShell命令（仓库根目录执行）：

```powershell
& scripts/workspace-lock.ps1 -Action Status
# 确认无其他锁后，用新的本轮标识获取锁，记录返回token
& scripts/workspace-lock.ps1 -Action Acquire -Owner "Codex-avatar-M1" -Summary "T028成熟运行器与双用途验证"

# 代码改变后运行相关测试；这轮文档整理没有重跑
& 'C:/Users/WonderMan/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 -m unittest discover -s tests -p 'test_avatar3d*.py' -v

# 需要源码GUI验证时，使用隔离工作区，不连接用户任务数据库
& 'C:/Users/WonderMan/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 avatar3d_entry.py --workspace '.runtime/avatar-M1-workspace' --runtime '.runtime/avatar3d/runtime.json'
```

脚本输出的进程仍运行时记录会话并继续观察，不直接报告通过。需要GUI安装／操作时先使用当时可用的工具与对应技能，不假定本交接的模型具备原生桌面控制能力。命令权限报错应报告具体环境限制，不擅自扩大系统设置。

## 已有实现与易回归点
- app.py左侧是离线PNG预览；点击模型会排队生成，非实时3D。0.1.1已修重复请求、缓存校验和旧模型任务覆盖新模型画面；不要回退。
- motion.py仅技术曲线，不能宣称完整动作库。blender_worker.py生成骨骼／相机关键帧并保存可编辑scene.blend；正式动作应引入母版读取／适配，不能继续用任意方向角冒充自然表演。
- models.py检查VRM／骨架与外部资源，哈希导入；contracts.py为schema1。当前UI离线24fps，AVATAR的30fps是开发目标。
- jobs.py为SQLite持久队列；service.py编码透明MOV／棋盘预览，核验帧数、解码Alpha、哈希后才完成。未来新后端调整输出协议，不能伪造.blend绕过完成门槛。
- 冻结Python与Blender自带Python存在ABI差异：backend.py已隔离_PYI_/PYTHON环境并处理Windows DLL搜索目录。不要向Blender sys.path注入整个打包_internal，否则会加载不兼容的_ctypes.pyd。
- 入口用QLockFile保护同一工作区。测试使用独立.runtime子目录，避免干扰用户；此机系统临时目录曾出现原子替换WinError6，使用项目内测试目录。取消只能终止本任务子进程。

## 本轮完成、证据与未完成
本轮合并AVATAR顶部重复方案，保留下方历史版本说明；同步STATUS、TASKS、DECISIONS D042、README，增加本交接和静态验证记录。T029记录方案完成，T030—T033是待执行工作包，T021仍为总体目标。

程序仍0.1.1，无源码修改、软件安装、角色制作、摄像头调用、付费／联系或外部发布。本轮没有新客户端／性能测试；此前0.1.1的97项检查和冻结GUI证据在state/verification/2026-10-21-avatar3d-load-fix/verification.json，不冒充本轮重跑。正式C、美术质量与双端适用性均未验收。

本轮静态检查记录：state/verification/2026-10-21-avatar-implementation-plan/verification.json（UTF-8、文档本地链接、任务／决策编号、关键路径和源码哈希不变；git diff --check）。写锁owner为Codex-20261021-avatar-handoff-plan，仅在检查完成后释放；下一模型始终实际查询锁状态，不能从交接文字推定无锁。未启动后台任务，没有待接管的安装／构建进程。

开始与结束Git均为README修改及已有大量未跟踪项目文件；本轮不提交／推送。开发模型接续时不必再次请求路线确认，直接执行T028并按协作规范交接。
