# 主线接续：当前C待机／讲解的Warudo接入

2026-10-25T14:09:21+08:00｜Codex-20261025-live-actions｜T028／T031。用户要求继续主要流程，停止扩展分段口播辅助功能；人工仍按D058暂停。此前自动审批因账户用量限制中断，用户明确要求继续后，检查已有子进程、日志与真实产物再收尾，沿用自己的排他锁，没有重复渲染或抢占其他锁。

## 实际交付

- 采用当前C肩领v004D，模型SHA256 `090301c984f13ba7b7b11223c9b556844fdd7aa332672c7b96390da82952bc70`，没有改脸型、服装或母版。
- `工作素材/虚拟形象/20261025_直播基础动作/离线动作-v002`：待机／讲解各3秒90帧30fps，320×480审阅视频、透明MOV、兼容网页、scene.blend。根预览为该目录的预览.html。
- `交换包/idle`：视频90帧，FBX附加首帧闭合为91帧，完整3秒循环；`交换包/explain`：90帧单次，首末关键帧89/30秒。两者均有当前VRM、源工程、模型元数据及完整文件哈希。
- `Warudo构建-v002/idle`、`explain`：实际Unity2021.3.45f2及固定SDK构建。已新增安装 `AvatarLabIdlea5c207ac973a.warudo`（SHA dde3b9bfa4ff4f4ef6813474fabb1aff18de60a8f269cf04c53f4f0531b60c74）、`AvatarLabExplaind69ac459edb6.warudo`（SHA 3f42f19d5291fad6dfd97d8c4fbcf4e29028ebaf775b0bb075aec6a6966cc806）到用户既有Warudo的CharacterAnimations。
- `单次讲解-Ctrl-Alt-F9.json`：按保存的C_Test_v001中角色1生成，未修改源场景。Warudo0.15.1本机程序集只读反射确认F9枚举67。原F8挥手、表情蓝图保留；F9蓝图需以后由用户导入并在原生动画选择器选一次新讲解包。
- 接续说明.md与人工V25准备完毕，不要求用户现在操作。已验证保存场景JSON及缩略图前后哈希相同。

## 工程修复与复用

motion_exchange新增循环闭合导出：只改内存中的导出副本，源blend／视频不加重复帧，清单分别记录源帧数与FBX帧数。worker验证全部骨骼逐帧往返及循环首尾，Unity再次验证loopTime和首尾曲线；SDK按actionId命名并验证循环标识，旧无actionId挥手报告仍可读。

新增avatar3d/warudo_pipeline.py与scripts/convert-warudo-motion.py：交换包验证→复用已配置研发工程→真实Unity提取→SDK构建→校验复制→输入恢复。Python构建服务从旧CLI抽到warudo_build.py，旧CLI参数保持。转换时备份FBX／meta／请求／C#模板／ExportSettings，CreateNew排他锁阻止重复调度；运行中的Unity会话锁阻止修改；异常保留日志及备份，不发布complete。还原输入后验哈希。

实际发现并修复：复用Seed工程时FBX meta仍带原骨架hips／Root映射，首次C导入失败。现在在备份后去除输入FBX的旧meta，让Unity从当前模型生成导入设置，结束再恢复原meta与FBX。第二次两动作均54映射骨骼有效。初次失败保留在Warudo构建/idle和轻量证据initial-import-failure.json，不当成成功资产。

第一次样片在Windows进度JSON替换时遇到短暂共享占用。models.atomic_json改为最多8次、每次50ms的有限PermissionError重试，仍保留原子发布、持久错误上抛及临时文件清理；首次不完整离线动作目录保留诊断。第二次离线动作-v002完整通过。

## 验证

39项针对性单元／回归通过，覆盖循环时长、交换包损坏、旧请求兼容、导入设置重建／失败恢复、重复调度锁、F8／F9共存／冲突、进度写入短暂占用和持久失败。测试日志在state/verification/2026-10-25-live-actions/tests.txt。

真实结果：待机91帧、讲解90帧，每帧54骨骼FBX往返；待机首尾位置／旋转误差0。Unity人形有效、30fps，待机3.000000238秒且循环端点曲线误差0，讲解2.966666937秒且不循环。SDK成功、安装与构建哈希相同、原工程输入恢复。两段MOV／MP4／WebM全部90帧，PTS及Alpha检查通过；检查脚本check_outputs.py可复核，verified.json为结果。AI查看了待机和讲解保持姿态的实际渲染，不代替连续动作和原生重定向观感。

## 状态边界及接续

桌面入口保持0.1.7，没有为此次资产交付重新打包EXE；新转换源码／Windows进度修复尚未进入该冻结版。旧功能、用户素材和场景均保留，无提交／推送。

本轮已补齐待机／讲解两个直播动作资产，与此前挥手组成首批三动作。FBX只带骨骼，离线眨眼、口型及头发物理不自动转移。V25当前C待机／讲解／F8共存与返回、V15当前C原生加载仍待用户恢复；旧V08暂过、V16已过仅限此前Seed测试配置。T032摄像头脸头跟随、失跟恢复、预设混合及OBS仍未验收，不宣称全主线完成。服饰穿模T035按用户要求后置，分段口播扩展停止。

后续优先在用户恢复时按V15→V25→OBS／真人跟随验证；未恢复时可准备这些已明确主线的接续材料，不重复扩展口播编辑器、生成更多美术候选或要求重复测已过项。构建脚本复用既有`.avatar3d/unity-projects/seed-wave-v01`，输出必须新目录，失败资料不得当成功包。完成差异／链接检查后释放本轮锁。
