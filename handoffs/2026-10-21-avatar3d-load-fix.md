# 三维工坊0.1.1加载模型反馈修复
记录：2026-10-21T14:43:00+08:00。Owner：Codex-20261021-avatar3d-load-fix。用户反馈点击「加载官方技术测试模型」无反应。

## 原因与修复
读取用户.avatar3d/models已有Seed-san元数据，0.1.0按钮确实入库，但不生成左侧画面，重复点击同模型只设置相同下拉索引就返回，没有状态变化。这是交互缺口，之前smoke直接load_model后另外add_job，漏测用户单独点按钮的路径。

0.1.1按钮为「加载官方测试模型并预览」；导入／选择后自动中立预览（320×480，0.5秒，12fps），立即显示已加载／生成／排队。Jobs.matching通过不可变请求查询进行中去重和完成预览查找；成品校验后复用，损坏另建任务修复。重开恢复选中模型预览；重复点击不重复排队。完成任务只在其模型仍被选中时更新图片，避免旧任务覆盖新选择。

## 验证
- 全项目97项通过，新增4项Qt用户路径检查：真实QPushButton.click连点仅一任务与明确提示，完成预览／重开复用，缓存损坏重建，缺失模型提示，旧模型结果不覆盖新模型画面。测试临时工作区隔离，不改用户真实任务；完成缓存单测媒体为明确fixture，实际媒体另作冻结验证。
- 新EXE dist/avatar3d/0.1.1/EarthPeopleLogAvatar3D。smoke已改为点击公开按钮两次，未再额外调用add_job；实际独立Blender渲染6帧、透明编码及左侧显示通过，完成后再点仍复用同任务。gui-result.error为空，load_button_auto_preview／repeated_click_reuses_preview为true。证据state/verification/2026-10-21-avatar3d-load-fix，含all-tests.txt及frozen-ui/loading.png／window.png／gui-result.json。
- 构建期间源码未变，manifest记录源码哈希；最终完成清单及6帧媒体复核见verification.json。根目录「地球三维角色工坊.lnk」已更新0.1.1，继续原.avatar3d和便携环境。

## 接续边界
需要用户关闭已开的旧0.1.0窗口后重开快捷入口；没有强行终止用户程序或改用户素材／工作区。已有0.1.0包保留。首次编译仍需等待，不是即时3D视口，重复点击不能加速渲染。此次不改变模型／骨骼动画／C形象／实时面捕／直播范围，不恢复定时资讯、不采购、不发布、不提交／推送。

STATUS／TASKS／README／AVATAR同步更新，常规修复沿用D037授权，无长期路线变更。结束检查后释放自己锁，接续仍检查真实锁状态。
