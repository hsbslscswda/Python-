# 镜中取月

## 直接下载 Windows 程序

**[打开 Windows 运行包下载页](https://github.com/hsbslscswda/Python-/releases)**

发布页的 Windows ZIP 才是已上传的运行程序；开发分支可能先更新，以发布附件的版本号为准。

下载 **MirrorMoon-Windows-v0.3.2.zip**，完整解压，再双击里面的 **启动摄像头.cmd**。无需配置 Python。不要下载自动生成的 “Source code” 来找 EXE，也不要只取出 MirrorMoon.exe，旁边的 `_internal` 必须保留。

窗口标题应显示 **v0.3.2**。本轮集成第二份八文件升级包：哥特玫瑰花窗、多层星盘与36格程序化铭文、FiligreePanel卷草雕纹和星盘水印。修正遮罩导致的大片发白、逆序GLSL边界及冻结折镜映射；保留134°、28%放大和此前动作修复。这是修复候选，**新版真人动作与视觉体验尚待复验，不是课程最终验收版**。旧版已收到真实失败反馈，旧测试通过不代表好用。

## 怎么用

1. 启动后按右侧法典火柴人示范操作，让上半身、双肩与双肘入画。左右手均可。可选择左/右臂分别做 20 秒校准。
2. 星环术：一手在胸前或肩前松握拳；另一手开掌抬起，朝镜头弯伸。开始施法后召唤手可以自由活动；搭住施法前臂增强至110–150%；放开恢复普通。施法手握拳停法留阵，放下施法手收阵。无需固定九十度肘角。
3. 本轮按用户要求在下拉框隐藏月刃术；内部 index 1 与实现保留，图形脚本仍检查出刃与连斩。界面仅展示星环术、镜界术。
4. 镜界术：双掌略错开靠近，稍停后拉开。镜面可连续旋转；转动约24°并稍停进入折镜。慢合并停约0.3秒关闭；可见快合到约两拳距离碎镜，不必拍掌。丢手不能触发碎镜。
5. **关闭摄像头：点「封印视界 (C)」或按 C**，窗口可保留；再点「开启魔镜」重新打开。Esc 收招，空格暂停，F11 全屏。切换系统后自然放下手稍停即可，不要求手掌留在画面内。

点「铭刻星轨日志」开始记录，再点一次停止。点 **开启卷轴库** 直接找到 JSONL，记录位置也会持续显示。日志含关键点/状态/时间，不保存摄像头图像；默认不记录，不上传。截图只有主动点击才保存。

图形不兼容时双击随包「兼容画质.cmd」。无摄像头可打开本机视频回放。构造动作演示仅展示软件与效果，不能验证真人识别。

## 这是什么项目

Python 课程设计：MediaPipe Tasks 双手+单人 Pose、OpenCV、NumPy、PySide6、ModernGL/GLSL、QtMultimedia。Python 承担识别、时序、状态与容错。运行时不用 LLM、付费 AI API 或网络服务，不上传摄像头画面。

只使用程序时，不必查看左侧 Files：`src` 是源码，`assets` 是资源，`tests` 是自动测试，`tools` 是开发工具，`docs` 是说明。它们不是可双击程序。[验证记录](docs/VALIDATION.md)区分真实摄像头连通、构造测试与待真人复验；[交接说明](docs/HANDOFF.md)给最短复测步骤。

## 开发者运行（Python 3.12 x64）

```powershell
uv venv --python 3.12 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements-lock.txt
uv pip install --python .venv/Scripts/python.exe -e . --no-deps
.venv/Scripts/python.exe tools/prepare_models.py
.venv/Scripts/python.exe -m mirror_moon --autostart --diagnostics
```

锁文件是本机验证的版本组合。模型下载来自 Google 官方版本地址，按清单校验 SHA-256；打包后运行不下载模型。

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/ruff.exe check src tests tools
.venv/Scripts/python.exe tools/graphics_smoke.py
.venv/Scripts/python.exe tools/graphics_smoke.py --compat --output local/graphics-compat
.venv/Scripts/python.exe tools/shader_probe.py
.venv/Scripts/python.exe tools/ui_smoke.py
.venv/Scripts/python.exe tools/build.py
.venv/Scripts/python.exe tools/package_smoke.py --app-dir '实际解压目录'
.venv/Scripts/python.exe tools/zip_smoke.py --app-dir '实际打包目录'
```

`--demo` 是构造动作；`--video 'D:/test.mp4'` 为录像。`--record-features local/G0.jsonl` 主动记录；`tools/replay.py` 回放，可加 `expected_state` 标注断言。`pipeline.py` 负责容量一采集、同帧推理与绑定视频快照；`features.py` 做坐标/身份/角度，`star_ring.py` 与 `interaction.py` 是纯 Python 规则，`transport.py` 独立消费瞬时事件，`render.py` 使用 Qt 当前 FBO。

课程原文在 [COURSE_REQUIREMENTS](docs/COURSE_REQUIREMENTS.md)，规格变更在 [SPEC](docs/SPEC.md)。最终报告、真实成员分工、教师模板和不超过五分钟真人视频仍未完成；D 摘影术是未实现扩展。完全侧身遮挡、真实物理接触与精确深度不在当前可靠承诺内。
