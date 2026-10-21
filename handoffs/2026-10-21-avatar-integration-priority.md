# 表情微调后置与动作／输出依赖准备
时间：2026-10-21T21:20:22+08:00。会话Codex-20261021-avatar-integration-priority，T028仍doing。

用户明确“表情细节的微调优先级可以不用那么高，后续再调整”。已把二值／淡入淡出／强度微调后置，不再让用户调整五种表情，也不把该项当成动作或双输出的前置门槛；基础模型／合并待机／表情触发已由用户确认。用户随后对OBS插件加载检查选择“稍后再验证”，不重复追问，不设置提醒，不扩大理解成暂停所有工作。

## 实际完成
- 重新查本机：Unity登记Editor仍只有6000.5.5f1，现有OBS主插件目录先前没有Spout；已有桌面工具MXC错误，本轮没有重复尝试或修改安全策略。
- 从官方Off-World-Live/obs-spout2-plugin的1.12.0发布下载portable.zip（973897字节），SHA256为6c5a31d6f30a44277b1955d4f85a1da1c0baa97a13075594d2bbca475104ee8a，与官方发布及GitHub资产digest一致。来源https://github.com/Off-World-Live/obs-spout2-plugin/releases/tag/1.12.0。
- 在未发现obs64.exe运行时，预检查全部目标冲突与x64 PE格式，通过后向D:/app/steam/steamapps/common/OBS Studio仅新增8个运行文件。4 DLL为Spout.dll／SpoutDX.dll／SpoutLibrary.dll／win-spout.dll，4 locale在data/obs-plugins/win-spout/locale。不复制PDB，不覆盖已有异内容文件，不修改用户配置／场景。逐文件哈希与新建清单在state/verification/2026-10-21-avatar-integration-priority/spout-installed.json；它是安装文件收据，不是运行兼容证明。
- 当前OBS32.2.2，插件发布说明构建基线OBS32.1.2；实际加载仍需测试，不能从版本相近直接认定兼容通过。若需要回退，只处理收据中本轮新增且哈希仍匹配的文件，不删除整个OBS目录或用户数据；此轮没有回退／卸载。
- SDK来自官方文档链接https://docs.warudo.app/sdk/Warudo-Mod-Tool-0.14.5.1.tgz，缓存.runtime/warudo-sdk/0.14.5.1/。43,539,736字节，本地SHA256为9e3f85a4b1cdc88fda9996afab73c04937e336b5108c66e61dc5b634f6a63dc3；包manifest名称app.warudo.modtool、版本0.14.5。文件名版本与manifest分别原样记录，不擅自改包。没有外部发布哈希，不能伪称已验发布者校验。未解压安装／执行SDK，也未下载数GiB的Unity编辑器。

## 下一步与待验
SDK需要Unity2021.3.45f2，现有Unity6不能当作匹配SDK。编辑器尚未就绪，自制挥手目前只有Blender往返通过的FBX技术包，未生成／播放.warudo。后续准备匹配编辑器与SDK导入，再验证Humanoid映射／动画Mod；不要改扩展名冒充可用文件。

OBS方面已告知用户打开／重启OBS，在来源+菜单查看“Spout2 捕获”（英文Spout2 Capture）；用户选择稍后。待其主动继续：确认来源能加载，再在Warudo摄像机1启用透明背景与Spout输出，在OBS选择对应发送者，合成模式选“预乘 Alpha”，底层放彩色色源验边缘／透明。具体发送者名以现场列表为准；黑底预览不证明Alpha。官方依据https://docs.warudo.app/docs/assets/camera。不要在本轮再次要求该人工验证。

本轮无自有程序源码／EXE更新，不运行无关旧应用测试；验证限于下载归属／包哈希、PE架构、文件冲突／安装哈希、SDK清单读取和文档检查。安装的插件代码未由助手运行，真实加载、GPU共享、Alpha与剪映仍待验。没有摄像头、公开推流、采购、外部联系或自动任务。

STATUS／TASKS／D045／AVATAR已同步，证据目录state/verification/2026-10-21-avatar-integration-priority/。Git保留原README修改与未跟踪项目，无提交／推送。持锁token e9a98823-282f-4121-b1d5-6eb3a0f3717b，检查后释放，接续实际查询。
