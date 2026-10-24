# C角色代码制作与初稿交付
时间：2026-10-22T15:37:36+08:00｜owner：Codex-20261022-c-code-model｜T030仍doing

## 授权与实际结果
用户允许AI代码制作，自己只检查效果。全程未用Computer Use，不要求用户建.vroid。来源为历史VRoid beta HairSample_Male CC0基础网格（非Seed-san），保留来源与SHA记录。Blender Python重构外套，新增高领、饰边和配件，调整脸型、颜色与纹理；不是从零原创全部网格，也未获正式造型认可。

当前交付：[v005说明](../工作素材/虚拟形象/C角色/代码初模-v005/使用说明.md)、[预览页](../工作素材/虚拟形象/C角色/代码初模-v005/预览.html)。含可编辑Blender母版、VRM1、多视图、4秒转台与1.5秒技术挥手；技术预览480×720/12fps，透明ProRes4444与棋盘MP4并存。修复VRM0网格180度对象变换导致前后裁切错误、外套肩袖断开和覆盖区域穿模。保留旧稿诊断，不覆盖用户素材。

## 可复用入口
- scripts/build-c-character.py：来源哈希、拒绝已有输出、隔离Blender、超时处理、完成清单校验。
- avatar3d/character_build.py：骨架／权重与形态键保留、空间变换烘焙、服装拓扑加工、材质／配件与实际多视图。
- avatar3d/character_review.py：仅打开通过本地完成哈希的源工程，禁用脚本自动执行，VRM1映射／表情迁移、母版保存和48帧转台。
- design/avatars/2026-10-20-concepts/c-build-recipe.json：0.1.4-draft配方；c-base-source.json为来源，c-model-brief.json为当前阶段。
- 复建用现有.runtime/avatar3d/runtime.json、缓存.runtime/avatar3d/sources/vroid-beta/HairSample_Male.vrm和全新输出目录。生成后review脚本由相同Blender运行，参数--folder输出目录 --addon运行时插件目录。

## 检查与边界
实际完成：54个人形映射骨骼；VRM1导出后经现有BlenderBackend重导入并渲染6帧；48帧转台；18帧技术挥手；既有PyAV编码器完整解码并检查帧数和MOV Alpha；两项CLI失败路径检查通过。见[轻量证据](../state/verification/2026-10-22-c-code-model/result.json)。已人工查看实际前／三分之四与重导入画面、挥手中间帧；这不代表用户验收或全姿态无穿模。

未完成：脸型偏年轻、衣领偏硬、发型与参考差距；头发弹簧物理未迁移／验证，自然动作及C的Warudo／剪映测试未完成。基础表情映射转换成功不等于所有脸部效果检查。新改作未设置公开再分发许可，不把基础CC0外推整套作品。现有EXE仍0.1.3，本轮不重打包、不改Warudo场景。

## 接续
请先收V09的体型／脸型／外套轮廓反馈再大规模精修和扩自然动作；人工清单已给可直接看的材料。OBS/V08仍按用户空闲时间验证，不重复催促。可独立完善构建复现与兼容，但不回退2D拼图或重做整套技术选型。保留所有前轮未提交代码，不默认提交／推送。结束释放本轮锁。
