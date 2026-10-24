# 新安装Unity与真实人形动作提取验证

时间：2026-10-22T08:07:18+08:00。会话Codex-20261022-unity-validation；T028仍doing。

用户确认编辑器已下载安装并要求检查。查到C:/Program Files/Unity/Hub/Editor/2021.3.45f2/Editor/Unity.exe，文件版本2021.3.45f2_88f88f591b2e；既有Unity6保留，无需再索取安装路径。

在持锁后用该Editor后台运行已有独立工程.avatar3d/unity-projects/seed-wave-v01，参数-batchmode -nographics -executeMethod AvatarLab.Editor.AvatarBridge.RunBatch。新建隐藏测试进程PID21784，等待其自然退出0；未终止其他进程，无用户工程／Warudo／OBS场景修改，无额外模块安装。首次资源导入与C#编译成功，真实报告runId=20261022T000646470Z-cd1c0f2d、passed=true：51骨骼映射，Avatar有效且为Humanoid，动画为人形，12fps，预期1.4166666269秒、实测1.4166667461秒，符合既定容差。独立生成Animation.anim，保存后重载验证及SHA256核验通过。没有修改C#以规避失败。

证据在state/verification/2026-10-22-unity-validation/：report.json原报告、Animation.anim实际提取文件、verification.json执行／来源校验摘要。clip SHA256=1a8b0452b3f54b4648f62183451a4dc9ff04c4248f5f0c113d5067877a776c1b；FBX SHA256=ac139a336bb856fef8f6e626865d88c85011fcafa3f758d75d22ef77b978d7c7；源码与工程内C#一致。完整本地运行日志.runtime/unity-validation-20261022/unity.log不提交，以免包含许可证／机器相关信息。原prepare-complete为生成时快照，Unity已正常产生Library／meta／ProjectSettings，不要求这些运行生成文件与离线快照逐字相同。

仅确认编辑器及Unity转换结构可用，未观察实时动作美术效果。SDK仍未导入、无.warudo、Warudo播放／OBS Alpha／剪映合成未验，正式C仍未建模，原EXE仍0.1.2。没有源码功能变更，不重复跑离线测试；仅此次真实Editor执行、输出哈希和文档差异检查。

下一步：在同一隔离工程按官方SDK要求配置.NET Framework和关闭Assembly Version Validation，导入已缓存SDK；再通过已核实SDK流程创建独立动作Mod、构建并接入Warudo。SDK成功不等于运行器播放通过；按人工清单V08给出准确素材与操作，用户有空再测，不催OBS／表情。STATUS／TASKS／AVATAR与人工清单V04／V08已更新，无提交／推送。
