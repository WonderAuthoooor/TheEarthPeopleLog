# M1实施：三维动作交换包0.1.2
时间：2026-10-21T19:00:52+08:00。
会话：Codex-20261021-avatar-M1。任务T028继续doing，T034工程完成。用户本轮明确已切换模型、继续开发。

## 实际完成
1. 读取协作／状态／任务／决策、AVATAR与前轮交接，检查Git和无锁后取得写锁（token 37bc7b1f-ee01-4f56-acaf-8e2e10d47125）。大量未跟踪项目文件保留，不提交、推送或清理用户文件。
2. 盘点卸载注册表与登记Steam库：OBS Studio 32.2.2在D:/app/steam/steamapps/common/OBS Studio；Unity Hub3.19.5／Editor6000.5.5f1已登记；一个Steam库、六个已安装manifest中未发现Warudo或VRoid。不排除其他便携安装。OBS主插件目录未发现Spout，用户插件目录未发现，未启动OBS验插件加载。报告见state/verification/2026-10-21-avatar-M1/inventory.json，不包含Steam用户标识／凭据。
3. 重查官方Warudo SDK资料，指定Unity2021.3.45f2；现有Unity6不能当作符合要求的SDK编辑器。未为此安装或改动系统。资料链接在AVATAR。
4. 实现motion_exchange.py与独立Blender转换worker；GUI新增导出／打开动作包按钮，串行于渲染、支持取消，失败不发布，保留原任务与模型。研发CLI为scripts/prepare-avatar-motion.py。三维版本0.1.2已构建，根目录快捷入口已更新到新EXE，原工作区.avatar3d保留。
5. 实际转换已有18帧／12fps的Seed-san挥手动作。发现并修正FBX重导入默认一帧偏移；裸骨架缺少蒙皮BindPose，导致休息姿势错误，改为附带绑定参考网格。逐帧检查51人形映射骨骼的头位置、方向、相对休息姿势旋转，以及帧率和关键帧范围。无叶骨FBX末端尾长可能重建，单列报告，不作为角色网格重建来源。保留原.blend母版和VRM。

## 成果位置与使用
- 程序：dist/avatar3d/0.1.2/EarthPeopleLogAvatar3D/EarthPeopleLogAvatar3D.exe；地球三维角色工坊.lnk已指向该版本。
- 窗口中先生成动画，再选已完成任务，点击“导出选中动作交换包（FBX）”；完成后点“打开最近导出的动作交换包”。不选任务时用最近完成项。任务未完成／损坏会报错，不复用错误文件。
- 输出在.avatar3d/exchanges/独立新目录。包含character.vrm、source.blend、animation.fbx、transparent.mov、preview.mp4、poster.png、model-metadata.json、manifest.json、roundtrip.json、使用说明和exchange-complete.json。FBX为骨骼动画中转，附蒙皮绑定参考，材质仍以VRM为准；表情／材质／道具曲线没有包含。
- 当前技术动作交付：工作素材/虚拟形象/20261021_M1动作交换验证/seed-wave-v05；该目录README明确早期v01／v02／v04失败与v03不完整验证不作为交付。Seed-san仍是署名样例，不是C。没有新建C模型或冒充造型已通过。

## 验证
- 21项相关测试通过（test_avatar3d*.py），覆盖源损坏／参数不符、已有目录保护、取消仅终止自身子进程、失败不写完成标记、包损坏、GUI拒绝未完成任务、避免并行渲染及原加载回归。
- 挥手FBX实测18帧／51骨骼，最大关节位置误差1.2278999872107638e-6米，方向和形变旋转误差报告0°；帧率与关键帧时间一致。这是Blender FBX往返，不能据此声称Unity Humanoid和Warudo兼容已验。
- 源码GUI与最终冻结EXE均走实际按钮：加载→真实离线渲染→导出动作包→逐帧FBX检查→完成校验，gui-exchange-result.error为空、public_export_button为true。本轮冻结GUI验证的是0.5秒中立预览，挥手长段由研发CLI另验，不混称同一次用例。
- 证据已归档state/verification/2026-10-21-avatar-M1/：inventory、focused-tests、source／frozen界面图与结果、往返／manifest／哈希、wave-roundtrip与build-manifest，最终verification.json汇总。完整技术包在工作素材；.runtime临时路径不保证永久保留。
- 已构建EXE、源代码清单和输入资产哈希核验；本轮未改新闻／地球／旧2D源码。旧角色技术样例来源／许可证保留。

## 仍待完成与具体限制
桌面控制技能已读并尝试node_repl的@oai/sky初始化，内核因MXC枚举Z盘被Windows来宾访问策略阻止（1272）退出；重置重试仍失败，未进行任何软件UI操作。未绕过Windows策略、未代替用户登录／摄像头授权。源码及冻结Qt自身验证由应用内部测试入口执行，不能视为Warudo／OBS／剪映客户端测试。

已异步请用户在Steam安装并启动一次Warudo（app2079120）或提供其他目录，目前尚无用户安装完成回执。T028的运行器导入／实时镜头／表情、自制动作在Unity Humanoid／Warudo播放、OBS透明输出和剪映叠加均为待验；M1没有整体通过。OBS／Unity是已安装，不能再让用户重新安装这些同版本工具；SDK匹配Editor与插件确实仍需准备。

## 下一条可执行动作
先读AVATAR当前基线与本交接，检查锁／Git，再继续T028。用户提供Warudo目录或完成安装后重新有界核查。桌面工具恢复时在Warudo导入交换包的character.vrm；以官方流程准备匹配Editor／SDK，将animation.fbx设置Humanoid并检查Avatar映射，提取动画、构建Mod后实测，不把FBX改扩展名当.warudo。

独立准备T030可编辑C资产仍可推进，现有参考在design/avatars/2026-10-20-concepts；不重问C、不继续旧2D贴图、不因缺安装转而重写运行器。没有用户反馈具体美术样稿时不宣称美术通过。摄像头、实际开播、采购／委托和外部联系按已有授权边界处理。

本轮只持有自己的锁，结束前完成静态／产物检查后释放；接续时实际查询，不从文字推定锁状态。没有待接管的后台构建／安装任务，源码与冻结GUI检查进程已结束。开始与结束Git为README修改及已有大量未跟踪项目文件，没有提交／推送。唯一规范AVATAR已更新，STATUS／TASKS／D043同步。
