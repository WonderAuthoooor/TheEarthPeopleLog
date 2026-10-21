# 角色工坊0.2.0：直播复用与本机追踪
时间：2026-10-21T09:50:00+08:00；owner：Codex-20261021-avatar-live。用户授权继续开发，并新增未来虚拟直播、摄像头捕获本人部分动作要求；沿用C形象，不改地点程序。

## 已完成
- 按入口读取协作、状态、队列、决策及AVATAR，检查Git与锁后获取排他锁。新决策D034区分用户目标与工程首版范围。
- avatar_app/tracking.py：视觉后端与Motion参数分离，固定本地MediaPipe 0.10.31；Face Landmarker面部表情／旋转，Pose Landmarker轻量模型肩线倾斜；校准、有限范围映射、左右镜像与眼睛交换、时间平滑、失踪后回中性。
- avatar_app/live.py：Qt摄像头枚举／刷新／选择、手动开始／停止、QVideoSink视频帧转RGB、后台单槽最新帧推理。摄像头默认关，不存上次开启状态；停止／切回口播／退出释放摄像头、会话和线程。没有摄像头画面写盘或图像上传接口；没有开启麦克风。
- 角色Rig增加左右眼独立眨眼、小幅歪头、点头位移和肩线驱动侧倾，沿用0.1.1嘴部修复。不是完整三维转头、肩臂骨骼或标准Live2D模型；手臂／手指／举牌未实现。素材图未重新生成。
- Qt界面两页「口播素材／直播跟随」，独立「地球角色直播画面」纯角色绿幕窗口，只收到角色图像，没有真人视频或控制按钮。OBS等软件使用窗口捕获＋色度键的方案有官方文档支持，实际用户端捕获／去底／音画同步未实测。未集成虚拟摄像头、Spout／NDI、自动推流或平台账号。
- dist/avatar/0.2.0/EarthPeopleLogAvatar，根目录「地球角色工坊.lnk」已更新，仍使用.avatar。源入口／冻结doctor／隐藏公开样例自检已扩展；独立依赖／模型随包带齐，旧0.1.x包保留，不终止用户进程。
- 新增requirements-avatar-live.txt和scripts/setup-avatar-live.ps1，追踪依赖隔离于.runtime/avatar-live-python。未改变全局Python、其他项目或现有.runtime/python；新闻工作室与地点程序源码未改。

## 验证证据
state/verification/2026-10-21-avatar-live/：
- all-tests.txt：76项全项目检查通过，其中角色18项，新增10项覆盖校准、镜像、丢失回正、异常值、旋转／肩线置信、独立眼睛、嘴部黑块回归、启动不访问摄像头、单槽输入／停止清空与摄像头会话释放。
- 公开portrait.jpg与pose.jpg来自Google官方mediapipe-assets，input-sources.json记录链接，不是用户摄像头照片。
- source与frozen的live-result.json：实际本地模型识别人脸与肩线，Qt QVideoFrame→RGB→后台线程推理→角色窗口通过；frozen输出exit0。未启动QCamera，camera_started=false；枚举到2个视频设备不能等同于摄像头实机试用。
- frozen/live-window.png、output-window.png保存运行截图；motion-states.png是手工参数状态检查，不冒充真人动作捕捉。
- frozen-offline/：冻结GUI读取临时系统口播，实际导出319帧480×720／30fps透明MOV；逐帧嘴部区域alpha最低251，无0.1.0的透明横条。未人工试听正式音色，系统测试音不替代甜美解说。
- doctor.json：冻结0.2.0、自带MediaPipe／本地模型、camera_started=false、无需地点或工作室。verification.json和build-manifest.json归档当前验收。
- 构建源码与当前源码哈希一致；固定模型SHA256一致；地点0.2.0源码清单哈希仍一致。文明账本仍为空，无发布、采购、收费接口或定时推送恢复。

## 依赖与模型来源
官方面捕／姿态Python文档、OBS捕获与滤镜文档已查阅，链接统一维护于docs/AVATAR.md。模型URL、大小与SHA256在avatar_app/assets/tracking/models-source.json。重建先准备requirements-avatar.txt公共依赖，再运行setup-avatar-live.ps1、scripts/build-avatar.py、create-avatar-shortcut.ps1；源码入口自动添加两个项目级运行时路径。

本轮先下载考察了MediaPipe1.1.1及依赖，未采用／安装该版本；选择0.10.31固定接口。只安装requirements-avatar-live中六个固定依赖到隔离目录，numpy／Pillow／Qt仍使用原项目版本。多余调研wheel留在忽略的.runtime开发缓存，不打入应用。系统Temp的pip原子rename曾遇WinError6；临时目录改为本项目.runtime/avatar-pip-tmp的子进程环境后安装成功，不改全局TEMP。

## 用户最短试用步骤与未完成
1. 关闭自己正在用的旧角色窗口，再从根快捷入口打开0.2.0。
2. 直播跟随→选择摄像头→开启；睁眼闭嘴正视镜头后校准。双肩入画可测上身侧倾，镜像方向可切换。
3. 打开独立绿幕画面，之后在用户选定的直播软件捕获与去底，声音由直播软件选麦克风。

需要真人检查灯光、眼镜／刘海遮挡、正反方向、眨眼张嘴、头颈接缝／倾斜、捕捉延迟、设备占用／权限、长时间稳定性；现有样例与模拟检查不能代替。OBS／抖音直播伴侣／B站端、绿幕发丝／薄荷饰品边缘和干净Windows均未实测，不能宣称已完成直播。当前实时源360×540，窗口放大不提高源细节；未承诺实时30／60fps。

T021继续doing。下一步先用户实机试用，再补手臂／手势或转成熟Live2D模型制作；已有设计与参数协议可复用，自定义PNG模型不能直接导入VTube Studio。docs/AVATAR.md为唯一角色规范；STATUS/TASKS/DECISIONS及C模型清单已更新。无提交／推送；结束检查后释放锁。
