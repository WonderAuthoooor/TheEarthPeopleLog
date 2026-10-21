# 三维角色工坊0.1.0离线技术底座
记录：2026-10-21T12:22:00+08:00。Owner：Codex-20261021-avatar-3d-core。用户授权3D继续开发，强调规范／可用性／复用。T025底座交付，T021角色本身继续doing。

## 实际交付
- 新目录包dist/avatar3d/0.1.0/EarthPeopleLogAvatar3D，新根目录「地球三维角色工坊.lnk」，.avatar3d独立工作区。旧角色与地点程序／源码／快捷入口保留未改；新程序依赖项目内.runtime/avatar3d，不是新机器独立安装包。
- 版本化RenderSpec、VRM0／1骨骼／资源检查、按SHA复制模型及快照；标准骨架姿势方向、实际蒙皮变形、正／斜／侧相机及三视角动作。自然站姿、屈肘讲解、挥手、持物姿势为首批预设；不是已完成实时IK拖拽或外部动作导入。
- Qt界面后台线程→独立Blender进程→透明PNG→流式ProRes4444 MOV与棋盘MP4→真实解码检查与完成清单，保留烘焙骨骼／相机关键帧和打包纹理的scene.blend，原VRM未改。静音，无3D口型／摄像头／评分道具／直播。
- SQLite WAL／事务领取／不可变请求，队列串行、取消仅终止自己的Popen子进程，启动时运行态变中断、重试另建任务不覆盖。入口QLockFile单工作区单实例；完成文件哈希复核；坏模型／失败／取消不显示成品。任务列表只显示最近100条，但调度独立查询最早排队，避免旧任务被历史页挤掉。
- Blender 4.5.13 LTS便携官方ZIP约380MiB，官方SHA256核对；VRM插件4.10.2归档固定SHA。setup-avatar3d.py不写全局PATH／用户插件／注册表；build与快捷脚本动态读版本并记录源码哈希。模型和程序来源／版本／校验在avatar3d/assets/runtime-lock.json。
- 官方技术模型Seed-san（VirtualCast, Inc.），VRM嵌入元数据允许everyone／corporation／再分发及修改，要求署名。保留来源、credit和VRM Public License 1.0 PDF；明确它不是C角色或用户认可的形象，不用于冒充原创C建模完成。

## 分层位置
avatar3d/contracts.py为纯协议；models.py为检查／复制／元数据；motion.py为语义姿势；jobs.py为持久账本；backend.py为可替换进程适配；blender_worker.py为Blender场景；service.py为任务编排／编码；app.py为Qt；avatar3d_entry.py负责启动与实例锁。只有固定本项目worker脚本被执行，不打开第三方blend；当前后端仅接受单人形骨架、保持角色层级。AVATAR为唯一规范正文。

## 实际验证及修复
- 全项目93项通过，新增10项三维边界／任务／恢复／编码／子进程环境检查，包含模型损坏／外部URI、无效请求、重复领取、>100队列、取消／失败不成品、源模型修改前拦截、编码透明与父环境不被改。日志state/verification/2026-10-21-avatar3d/all-tests.txt。
- 源码GUI导入与导出通过；真实18帧／1.5秒骨骼挥手、6帧90°侧面通过，已看编码／渲染帧。独立重开生成.blend确认动作关键帧有变化、骨段长度稳定、无未打包外部纹理、无意外Cube；baked-motion.json有数值记录。
- 首轮素材被材质库引入的默认Cube遮挡，固定只保留角色层级；初版动作渲染反复评估首帧，修正实际frame_set／四元数模式及关键帧保存后再检查动态，不把早期静态图当作挥手成功。
- 冻结版首两轮失败（各gui-result.error非空），定位为Blender Python3.11与工坊Python3.12的DLL／pyd路径污染；按PyInstaller官方指引隔离／恢复DLL搜索路径、清理子环境，并以私有命名空间只导入纯Python协议，避免把_internal整个目录加入Blender路径。最终重新构建，frozen-ui-v3实际模型→Blender→6帧透明MOV／MP4→完成清单通过，不能以进程exit0替代业务结果检查。
- 实际取消在约2.19秒返回，取消状态／无完成标记通过；仅代码持有的子进程被终止。崩溃恢复为数据库状态回归测试，未谎称已运行整机断电／干净Windows矩阵。
- verify.py复核最终冻结产物、真实帧数／透明通道／波动、全部新源码与构建一致；旧角色0.3.0与地点0.2.0源哈希均未改，正式账本仍为空。

## 样片与证据
用户素材：工作素材/虚拟形象/20261021_3D骨骼技术验证，骨骼挥手／侧面检查／冻结版导出与技术样例一览.png；均为Seed-san静音技术测试。verify.py从实际任务归档，不覆盖旧用户素材。源技术任务分别在.runtime/avatar3d-wave、avatar3d-side、avatar3d-frozen-workspace-v3，临时路径不是唯一交接；核心证据归档在state/verification/2026-10-21-avatar3d。先前失败日志／任务保留供诊断，不把它们作为当前成功包。

## 下一步和边界
正式C三维模型／服装权重／表情尚未制作；优先统一比例和关节视觉样段，再导入当前工作流。实时拖拽骨架、双手持评分牌IK、3D音频口型／面捕、Warudo或其他直播适配继续未做，旧2D功能不会自动迁移。当前高可用落实为单机隔离／恢复，不是分布式服务或固定帧率承诺；第二种真实后端、干净Windows／分发安装和剪映透明合成待验。

本机检测RTX 5070 Ti Laptop GPU；不从32位AdapterRAM猜显存。未安装VRoid／Warudo、收费采购、外部发布／联系或恢复定时资讯；未改其他Claude项目，不提交／推送。结束静态检查后释放本轮锁，接续按AGENTS查看真实状态。
