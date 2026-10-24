# 自制挥手SDK构建与部署

时间：2026-10-22T08:28:33+08:00。会话Codex-20261022-warudo-build；T028仍doing，不冒称整个M1完成。

## 结果与证据

用户继续授权开发。继真实Humanoid提取后，在同一独立工程完成SDK导入／编译，最后导入进程退出0；使用核实过签名的UMod公开ExportSettings／CreateNewExportProfile／StartBuild入口，真实生成 `AvatarLabWave1a8b0452b3f5.warudo`，构建进程退出0，47,383字节，SHA256 `4011b6fce65f065dc201307ee6030cc6610affcfae9264e58501f2122983e274`。源Animation.anim SHA256 `1a8b0452b3f54b4648f62183451a4dc9ff04c4248f5f0c113d5067877a776c1b`，与此前Unity报告一致。

构建run `20261022T002628597Z-9018cf42`，位于 `.avatar3d/unity-projects/seed-wave-v01/AvatarBridge/Builds/`。经部署脚本复制到用户指定既有安装的 `D:/app/steam/steamapps/common/Warudo/Warudo_Data/StreamingAssets/CharacterAnimations/AvatarLabWave1a8b0452b3f5.warudo`，源／副本哈希一致；只新增该动作文件，不改场景、模型、摄像头、表情或OBS。工作素材/虚拟形象/20261022_Warudo挥手技术包保存动作包、说明、构建报告与媒体清单。

证据：`state/verification/2026-10-22-warudo-build/` 下verification.json、build-report.json、installation.json、sdk-settings.txt、project-manifest.json、packages-lock.json。完整Unity日志留本地.runtime及工程内，不提交许可证／机器日志。SDK归档文件名0.14.5.1，内部manifest0.14.5，沿用固定本地校验值，未谎称发布者签名。

## 实施与排错

- 新增WarudoBridge.cs，实际配置.NET Framework（枚举实际读回NET_Unity_4_8）及assemblyVersionValidation=False，并枚举公开SDK签名；未通过私有GUI反射调用构建。
- 原官方tgz根布局为`./package.json`，本机旧UPM按tarball导入报找不到package.json。保留原包，校验后安全展开为LocalPackages文件夹并用官方支持的file:本地引用；不改SDK脚本。SDK实际展开由本轮工具执行，后固化为stage脚本，脚本fixture部署检查通过。
- 默认共享UPM缓存发生EBADF重命名错误，终止本轮PID25048（自有测试Editor）后，仅在随后启动的进程环境指定UPM_CACHE_ROOT为仓库.runtime/unity-upm-cache。未改用户级配置或清理共享缓存；首次失败的默认缓存写入尝试不伪称从未发生。
- SDK内嵌VRM声明Timeline1.7.6但根包没有显式依赖，首次编译ITimeControl缺失；按内置VRM/package.json补入Timeline1.7.6，另加入UGUI／TMP和Editor现有内置模块，未下载额外平台支持。
- 构建脚本首次放入SDKEditor，未被Unity视为Editor目录，BuildEngine引用失败；改到真正的Editor目录后编译成功，保留失败日志，不能把第一次尝试写为通过。编译退出遗留空UnityLockfile不代表仍运行，交给Unity原生进程锁判定。

复用入口：avatar3d/warudo_sdk.py＋scripts/stage-warudo-sdk.py准备固定SDK（已有部署不覆盖）；avatar3d/unity/WarudoAnimationBuilder.cs＋scripts/build-warudo-animation.py校验源报告／动画，独立构建目录、报告／退出码／SHA通过才返回；avatar3d/warudo_deploy.py＋scripts/install-warudo-animation.py只部署已验证包，同内容可复用，同名异内容停止，临时复制校验后CreateNew硬链接发布。SDK阶段才放入构建脚本，纯Unity工程可先单独排错；prepare-unity-motion会带基础配置脚本。

15项相关Python检查通过：SDK展开／配置4、部署3、构建入口失败／超时2、Unity准备6。未改其他应用功能，不重复全量107项。实际SDK编译和构建另有真实Editor结果，不以mock测试代替；技术包仍原12fps／约1.42秒，不声称30fps正式自然动作。

## 下一步

人工清单V08已移入“现在可做”，列出已安装动作名、临时切换待机与恢复、列表缺失时保存重启、与原预览对照的操作。用户有空再验证列表识别／播放／关节／位置与恢复，不催测、不设置提醒；不把复制文件当作运行器已加载。此轮没有桌面操作、Warudo实际播放、真人摄像头或OBS／剪映合成验证；一次性动作按钮和正式混合仍未交付。SDK构建能力不等于正式C形象完成，后续继续T030可编辑C资产，正式C出现后再做自然动作与输入。

程序EXE仍0.1.2，新增研发CLI未嵌入客户端。STATUS、TASKS、AVATAR与人工清单已同步；本轮无新增长期产品决策、无提交／推送／开播／外部发布。检查后释放自己的写入锁。
