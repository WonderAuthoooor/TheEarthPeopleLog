# Warudo 单次挥手触发交接

时间：2026-10-22T22:06:27+08:00｜owner：Codex-20261022-warudo-hotkey。

用户先要求配置动作触发，随后要求完成上次未完成工作。上次工具审批配额中断，本轮按相同锁接续；默认沙箱仍报MXC/Z1272，经正常审批的命令已可运行。

## 实际交付

- scripts/prepare-warudo-hotkey.py：只读已保存场景，核对角色ID，复用原生按键节点结构，以新GUID生成独立JSON；Ctrl＋Alt＋F8（本机Keystroke.F8=66）。同键位冲突、未知角色、已有输出均拒绝；不写外部应用场景。
- 工作素材/虚拟形象/20261022_Warudo挥手触发/：单次挥手-Ctrl-Alt-F8.json、使用说明.md。两节点连线：OnKeystrokePressed.Exit → PlayOneShotCharacterAnimation.Enter。
- 本机Warudo0.15.1 DLL仅ReflectionOnly元数据核对：按键类型d341c82e-d6d2-4910-bdb6-2f9719470619；单次类型3c8f47ba-5430-4061-8506-19812b4d2ec0，字段Character/Animation/TransitionTime/Weight/Speed/Masked/Additive，完成输出OnAnimationEnd。不是运行插件或修改应用。
- 角色默认预填已保存场景角色1：29399e49-1c26-41bb-b40f-294dc0590f68。过渡0.2秒、速度／权重1、非加法／无遮罩。动画资源URI未推测，导入后由用户在原生选择器选已有AvatarLabWave1a8b0452b3f5一次。

## 检查和限制

state/verification/2026-10-22-warudo-hotkey/checks.json：5项自动检查通过（引用与独立ID、源文件不变、键位冲突拒绝、错误角色拒绝、已有输出保护）。验证脚本在忽略的.runtime/check-warudo-hotkey.py；诊断脚本.runtime/warudo-hotkey-reflect.ps1。未执行Warudo原生导入／运行，不能把JSON结构检查当原生验收。全部既有改动保留；未提交／推送。

脚本适配当前0.15.1已保存格式，冲突检查只看输入场景，不代表现场未保存状态或全系统无冲突。没有额外防连点或取消节点。角色换成新资产需重新绑定。官方单次节点自动退出，但实际过渡观感仍待验。

## 下一步

用户手动导入（按既有鼠标操作分工），恢复原待机、选一次动画、保存并测试Ctrl＋Alt＋F8。按V16记录原生导入／单次／返回／重开；同时补V08自制动作播放和视觉结果。此前截图仅确认动作列表识别；未误标V08通过。V07剪映已过，V09/V14暂过，其他待验继续保持。

官方依据：
- https://docs.warudo.app/docs/blueprints/tutorials/dance
- https://docs.warudo.app/docs/blueprints/overview

本轮结束释放原锁；以workspace-lock状态为准。
