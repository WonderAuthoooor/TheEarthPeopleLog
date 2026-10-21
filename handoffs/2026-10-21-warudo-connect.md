# Warudo目录核实与技术模型准备
时间：2026-10-21T19:50:57+08:00。会话Codex-20261021-warudo-connect，任务T028继续doing。

用户先确认“已安装在其他目录”，后给出D:/app/steam/steamapps/common/Warudo。本轮重新核实EXE／Warudo_Data／StreamingAssets/Characters及Steam app2079120、build24066794、StateFlags4；前轮未发现结果不再作为当前状态。没有重新安装、启动或宣称加载成功。

新增scripts/prepare-warudo-model.py和tests/test_warudo_prepare.py：模型／目录验证、同哈希复用、同名异内容保护、复制后校验、临时文件原子发布及失败清理。三个测试通过（日志state/verification/2026-10-21-warudo-connect/tests.txt）。

已实际执行准备，将技术交换包seed-wave-v05/character.vrm新增至用户指定安装的Warudo_Data/StreamingAssets/Characters/AvatarLab_Test_624d0d554bc2.vrm；SHA256为624d0d554bc205bbdc33e22a68a2c3c20edebb3e573011ead8878a65e5329b23，内嵌名称Seed-san，VirtualCast, Inc.。仅新文件，不改场景、设置、原模型或程序，模型元数据和许可证保留。复制结果在model-prepared.json，安装信息在installation.json。

已读电脑控制技能并沿用其流程；node_repl @oai/sky仍无法初始化，重置重试报MXC枚举Z盘Windows来宾访问策略错误1272。没有客户端窗口操作、摄像头调用、公开推流或采购。程序版本仍0.1.2；既有EXE源清单未变，新增研发脚本不在包内，不能声称有新的应用入口。

已异步请用户：启动Warudo，在编辑器Basic Setup→Get Started，从列表选Seed-san（或AvatarLab_Test_624d0d554bc2），先跳过摄像头并反馈主窗口是否显示。当前没有加载结果回执，warudo_load_verified=false。下一轮先处理该反馈，别再重问安装目录／要求重装；如用户给界面截图，按实际界面定位，不凭猜测反复操作。若列表找不到，核对Menu→Open data folder是否当前实例使用此目录；若加载出错，收集对应局部错误，不抓整份含隐私的应用日志。

M1剩余：实时模型／镜头／表情、自制动作的Unity Humanoid与Warudo播放、OBS透明和剪映叠加。SDK匹配Unity2021.3.45f2仍未准备，不用现有Unity6冒充兼容；不因为桌面工具错误直接重写引擎。正式C仍未制作，T030可继续独立推进。

状态／任务／D044／AVATAR已同步；用户安装事实与文件准备是本轮实证，客户端结果保持待验。验证文件在state/verification/2026-10-21-warudo-connect/。开始与结束Git为README修改及既有未跟踪项目，未提交／推送。排他锁token b21d00d5-9e7e-43c5-917b-456247ef7a0c，检查完成后释放；后续实际查询锁。
