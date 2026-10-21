# 本地视频草稿流水线构建交接
日期：2026-10-18｜时区：Asia/Shanghai（+08:00）。

## 授权和结果
用户明确要求继续流水线构建。本轮完成本地桌面工具与实际渲染，未开设账号、购买服务、发布视频或改正式文明账本。没有启用后台定时任务。用户原视频和其他模型/项目保持原位。

## 文件与运行
- 根目录启动流水线.cmd；scripts/run-pipeline.ps1负责寻找本机Python，执行python -m pipeline。
- pipeline/core.py：原子任务保存、修订号冲突保护、独立任务锁、素材哈希导入、媒体读取、X URL限制与单帖下载、SRT/ASS、截图叠加、原声压低与混音、评分建议校验、版本渲染/缓存与审核记录。
- pipeline/gui.py：四个操作页；工作线程期间禁用编辑；密钥只保存在当前进程；任务自动保存/恢复；可播放原片和输出。
- pipeline/providers.py：可选MiniMax写稿及逐段配音，段落缓存，接口失败不自动重试；写稿20000字符、TTS1500字单次上限。原生写稿API官方标记deprecated，待后续迁移。未测真实服务质量或费用。
- requirements-pipeline.txt及scripts/setup-pipeline.ps1：固定项目依赖；本机pip目标安装触发WinError6临时目录重命名错误，改为下载wheel并解压到项目.runtime/python。Pillow12.3.0、imageio-ffmpeg0.6.0、PyAV16.1.0、yt-dlp2026.8.19。FFmpeg7.1来自wheel；使用Windows微软雅黑。未改全局Python、PATH或用户配置。
- docs/AUTOMATION.md是唯一设计/使用入口，已标清已实现与规划边界；README、STATUS、TASKS、D017更新。

## 本机数据
运行数据.pipeline和依赖.runtime均忽略Git。迁移工作区需要单独复制任务，不能只克隆代码就声称任务可恢复。
用户原素材：工作素材/20261018  中国贫困人数变化/angeloinchina-2111423703263379903-01.mp4，实测44.744853秒、1080×1080、有音轨。
默认可编辑试剪任务：.pipeline/jobs/20261018-55d72b73/job.json；输出output/60659b61ee05affa/preview.mp4。8秒，明确内部草稿、统计来源待核查，没有网友截图或新旁白，仅原片音轨和测试字幕。默认入口记录在.pipeline/recent.json。

## 实际检查
1. `python -X utf8 -m unittest discover -s tests -p test_pipeline.py -v`：15项通过。覆盖锁冲突/异常释放、旧窗口保护、去重与原片不改、URL伪装拒绝、SRT时码、字幕注入转义、评分、越界选段/配音、评论遮挡、零长度口播、无凭证/材料不请求收费服务、密钥不落盘与配音局部缓存。付费接口用模拟返回，不是假称真实API验收。
2. `python -X utf8 tests/smoke_pipeline.py`：合成横屏片/之前竖屏样片/用户方形视频三种输入，实际输出6/6/8秒、1080×1920/30fps、有音轨；重复运行复用输出。三条是技术测试，不计真实账号作品。横屏测试截图明确写非网友评论、音频为测试音。
3. 实际查看两处输出抽帧，画面、字幕与测试图未见明显截断；没有独立听音或逐帧验收。用户素材统计内容未核实，不因工具成功就升级为新闻成稿。
4. `tests/check_x_download.py https://x.com/angeloinchina/status/2111423703263379903`：实测下载成功，无X订阅、API Key或Cookie；任务.pipeline/jobs/20261018-4ee0fe7b/source.json含原帖返回记录。该结果不保证所有帖子成功，不代表版权许可或图表事实可靠。
5. `tests/check_voice_render.py`：使用模拟TTS响应中的真实测试音频，实际合并、540×960渲染；更改配音起点后SRT开始时间正确移动；改稿后旧生成字幕被拒绝。无收费请求。
6. Tk GUI实例创建、加载准备任务、中文字段及保存已执行通过；没有使用屏幕控制，未作全面人工UI验收。run-pipeline.ps1 doctor通过；compileall及git diff --check通过。新文件未跟踪，git diff --check不等于全量文件检查。

## 待做与边界
先用用户素材、真实评论和甜美解说音频做一条真实内容验收。可以无API Key制作草稿；模型建议仍须选取口播部分并审核。
自动搜索热点/评论抓取/原帖截图/语音转录/外部自动核查/逐字字幕对齐/剪映多轨草稿/跨平台发布/定时调度/每日API预算均未实现。无准确SRT时字幕按字数估时；TTS用实测段落长度但段内仍估时。导入SRT按成片时间轴，原生生成字幕可跟随配音起点移动。
没有Claude独立接续测试。当前工作区有大量历史未提交/未跟踪文件和用户素材，均保留；未commit/push。结束检查后释放本轮工作区锁，运行时任务另用自己的锁。
