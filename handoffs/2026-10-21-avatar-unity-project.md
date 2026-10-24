# Unity动作转换工程离线准备

时间：2026-10-21T23:06:12+08:00。会话Codex-20261021-unity-project；T028仍doing。

用户确认编辑器正在下载，询问可继续开发内容。沿既有授权，新增avatar3d/unity_project.py、avatar3d/unity/AvatarBridge.cs与scripts/prepare-unity-motion.py，不改旧EXE、用户场景或源交换包。脚本验证已完成包的来源／哈希／时间／必要骨骼、固定SDK本地哈希，生成独立新工程；拇指按VRM版本映射，不覆盖已有目录，复制失败留诊断、不发布成功标记。

已用真实seed-wave-v05包生成 `.avatar3d/unity-projects/seed-wave-v01`，包含FBX、来源记录、SDK缓存、固定ProjectVersion与C#编辑器脚本。SDK尚未安装，纯Unity检查与SDK导入分步排错。C#目标菜单 `Avatar Bridge/Validate and Extract Animation`，批处理 `AvatarLab.Editor.AvatarBridge.RunBatch`；实际执行才生成独立Runs报告和Animation.anim，Humanoid／时长检查失败则不报通过。Warudo动作Mod仍用官方New Mod／Build Mod，不猜测私有构建API。

6项新增Python检查实际通过：损坏资产、重新封装但时间／模型不一致、SDK不匹配、输出已存在、复制失败不发布及骨骼映射；真实工程准备成功，文件哈希检查结果见state/verification/2026-10-21-avatar-unity-project/verification.json。未运行全量107项（未改既有功能）；C#在指定Editor的编译／运行、SDK导入、Humanoid姿势观感、Mod生成／播放均未测，不能称Unity转换完成。

下一步：确认安装后的2021.3.45f2 Unity.exe，用这个独立工程真实编译并运行检查，按实际报告修正导入映射或T-pose；通过后按官方SDK安装要求配置.NET Framework和Assembly Version Validation，再构建动作Mod并验证Warudo。不要使用Unity6代替兼容证明。技术样例不代替正式C；人工清单V04／V08已同步，OBS与表情不催测。无提交／推送／外部发布。
