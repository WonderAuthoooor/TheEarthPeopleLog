# TheEarthPeopleLog
地球人日志：以长期盈利为目标的多平台原创热点观察内容项目。

当前版本：v0.1（试运行规范）｜建立日期：2026-10-11｜时区：Asia/Shanghai。

## 独立虚拟形象研发入口
虚拟形象现按独立项目推进，目标为同一3D角色用于直播与透明剪辑素材。当前唯一[研发执行方案](docs/AVATAR.md)和[切换模型实施交接](handoffs/2026-10-21-avatar-implementation-handoff.md)已整理；下一任务T028，先实测成熟工具与资产复用。程序已更新0.1.2，新增动作交换包，正式C模型尚未完成；[最新实施交接](handoffs/2026-10-21-avatar-M1-exchange.md)。

## 本地视频草稿工具
三维角色工坊0.1.2：双击根目录「地球三维角色工坊.lnk」，点击「加载官方测试模型并预览」或导入VRM后自动生成首次画面，重复加载复用预览；可选择骨骼姿势／视角并导出透明MOV和可编辑scene.blend；选中已完成任务，可点“导出选中动作交换包（FBX）”，生成含VRM／源工程／动作及校验的独立目录。独立.avatar3d与项目内Blender环境，队列／取消／中断重试／成品检查已实现。官方样例Seed-san不是正式C，C三维建模、实时骨架拖拽／3D面捕／直播未完成，使用和边界见[AVATAR](docs/AVATAR.md)。

用户已反馈旧角色0.3.0身体／手臂比例及拼接观感不合格；以下为保留的2D功能原型，不能当作形象已过稿，不再继续扩充贴图动作。

虚拟角色试验版0.3.0：双击项目根目录「地球角色工坊.lnk」；「口播素材」导出透明MOV，「直播跟随」手动开启摄像头与绿幕输出，「表情动作」提供讲解、吐槽、思考、惊讶、无奈、指向、挥手、评分牌、大笑、生气及待机。支持按钮／可选快捷键，评分默认待评。与地点工具独立；手势为预设，非实时手指捕捉，尚非完整Live2D模型，真人摄像头／直播软件实际接入待验，见[角色工具说明](docs/AVATAR.md)。

新版：项目根目录双击 `地球人日志工作室.lnk`，进入Qt一屏工作台，左侧“＋快速切片”适合短新闻/产品演示。也可直接运行 `dist/0.3.1/EarthPeopleLogStudio/EarthPeopleLogStudio.exe`；自带Python和FFmpeg，无需CMD或Codex。原声切片、批量切点、模板、封面和发布文案操作见[快速模式说明](docs/DESKTOP_APP.md#11-021短素材快速切片)，工作区与可靠性见同文第10节。当前为0.3.1内部测试版，未做全新Windows机器验收。

旧版仍保留：[启动流水线.cmd](启动流水线.cmd)及[自动化方案](docs/AUTOMATION.md)。新版通过“导入旧版任务”复制迁移，旧任务不改写；两版均不会自动发布。应用二进制和工作区被Git忽略，需通过构建脚本或本地交付包取得，不随源码自动出现。

## 从这里开始
- 人类阅读：[内容主体设计](docs/CONTENT.md)、[项目定位](docs/PROJECT.md)。
- Codex 入口：[AGENTS.md](AGENTS.md)。
- Claude Code 入口：[CLAUDE.md](CLAUDE.md)。
- 其他模型或普通聊天客户端：手动提供本文件、[协作规范](docs/COLLABORATION.md)、[当前状态](state/STATUS.md)，再按任务提供专题文件。
- 接续工作前必须读取状态、任务和决策记录。文件可共享，聊天历史不保证共享。

## 文件地图
| 文件 | 唯一负责的内容 |
|---|---|
| [PROJECT](docs/PROJECT.md) | 商业目标、用户已确认要求、待验证假设 |
| [CONTENT](docs/CONTENT.md) | 受众、栏目、叙事、幽默、标题、平台适配 |
| [EDITORIAL](docs/EDITORIAL.md) | 证据、素材、审核、发布、更正 |
| [CIVILIZATION](docs/CIVILIZATION.md) | 文明评分算法和账本口径 |
| [COLLABORATION](docs/COLLABORATION.md) | 多模型接入、文件锁、交接、变更规范 |
| [AUTOMATION](docs/AUTOMATION.md) | 本地视频草稿工具、使用步骤与后续自动化设计 |
| [DESKTOP_APP](docs/DESKTOP_APP.md) | 正式桌面应用产品、架构、可靠性与验收设计 |
| [SOURCES](docs/SOURCES.md) | 外部研究来源与适用边界 |
| [STATUS](state/STATUS.md) | 当前阶段、阻塞和下一步 |
| [TASKS](state/TASKS.md) | 工作队列 |
| [DECISIONS](state/DECISIONS.md) | 决策及其依据、用户要求与假设的区别 |
| [文明账本](state/score-ledger.json) | 已正式记账的事件；当前为空 |
| [稿件模板](templates/STORY.md) | 每篇稿件从线索到发布的记录 |
| [交接模板](templates/HANDOFF.md) | 每次工作后的可接续记录 |
| [写入锁工具](scripts/workspace-lock.ps1) | 同目录协作的排他写入协议 |

## 新会话启动提示
> 请先读取 AGENTS.md、docs/COLLABORATION.md、state/STATUS.md、state/TASKS.md 和 state/DECISIONS.md，简述当前目标、已完成事项、下一步。按本次任务读取专题规范，检查 Git 状态和写入锁后再修改文件。不要将示例、历史聊天或旧热点当作已核实事实，不要覆盖其他会话的修改。

## 当前范围
本仓库已有内容规范与本地视频草稿工具；尚无公开发布回执、真实经营数据或已开通收益功能记录。所有指标、栏目比例和平台组合均为试验参数，不是收益保证。

## 本地文件维护
保留当前 `dist/0.3.1/` 与 `dist/EarthPeopleLogStudio-0.3.1-Setup.exe`；旧0.2二进制、构建中间文件及重复测试媒体已清理。历史交接中的临时路径表示当时测试位置，报告与截图已[归档](handoffs/2026-10-19-cleanup.md)。`.runtime/python`、`.runtime/wheels` 和项目级NSIS用于开发、离线重建及许可证收集，继续保留。

`工作素材/`、`.studio/`、`.pipeline/`、`content/` 包含素材或项目记录，不能当缓存删除；Git忽略不代表文件无用。后续清理须持项目写入锁，先检查运行中的任务、文件引用与重建条件，再删除确认可再生的产物。

## 每日资讯与栏目动画
[今日选题包](content/digests/2026-10-20/briefing.md)含新闻和视频入口；以后由用户主动发起时搜集，原定时任务暂停，见[AUTOMATION](docs/AUTOMATION.md)。

地点动画现为独立应用：双击根目录「地球地点动画.lnk」，使用.globe工作区；目录版dist/globe/0.2.0/EarthPeopleLogGlobe，独立安装包dist/EarthPeopleLogGlobe-0.2.0-Setup.exe。支持1,252城市中文／英文搜索、详细地点文字、复古夸张／原版两种风格、旋转定位与可选开场大手；复古开场包含形变／多圈旋转与推近，转场先拉远再转向推近，导出干净MP4，不加载虚拟角色或评分；全部画面文字默认关闭，六项可独立勾选。操作、旧资料边界和构建见[GLOBE](docs/GLOBE.md)。原工作室0.3.1保留用于新闻切片，不代表其旧动画界面已升级。

虚拟主播独立开发，用户选择C「深色发通讯员」造型方向，当前已有自定义分层试验模型、口播／面捕与预设动作程序，尚非标准Cubism模型，见[AVATAR](docs/AVATAR.md)。在剪映中分别组合新闻、地点转场和角色层。
