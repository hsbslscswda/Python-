# 镜中取月 v0.4.3

本轮集成并修正Gemini v0.4.3候选：冰魔法完整冰系层次、正面朝向与双掌共鸣；纯净八角镜；镜/水下垂出画0.30秒消散、大开合保持；水火悬空及水球三种发射方式。详细判断见[审查回应](docs/GEMINI_REVIEW_RESPONSE.md)。

## 直接运行

下载[Windows运行包](https://github.com/hsbslscswda/Python-/releases/download/v0.4.3/MirrorMoon-Windows-v0.4.3.zip)，完整解压后双击「启动摄像头.cmd」。无需安装Python；保留_internal。标题应为v0.4.3。C关闭摄像头，Esc重置，空格暂停，F11全屏。所有功能本机运行，不依赖LLM或网络服务。

## 坐着也能操作

- 冰魔法：一手抬到胸/颈前握拳或横臂召唤，另一手开掌前伸输出冰枪寒雾；伸臂增强。副手搭腕/前臂，或在施法手旁同时开掌共鸣，可过载。施法手握拳停法留阵，放下收阵；腿/桌面低位不召唤。
- 镜界术：双手靠近停顿再拉开，平移/缩放/旋转；慢合保持收镜、快合碎镜。大开合一上一下/一左一右出画保持；双手均向下垂落出画连续0.30秒消散。单纯遮挡/追踪丢失保持，不能缺手触发碎镜。
- 水球术：任意一手握拳再摊开，水球悬浮掌上并有惯性；双掌明确张开/捏合、夹球保持后拉开放大。副手搭腕、近腕握拳助推，或主人手握拳压缩发射；拍掌或双臂下垂出画0.30秒结束，大开合出画/纯丢失保持。暂停冻结、主人锁定不自动换手。深度/人物碰撞是单目近似。
- 掌心火焰：左右分别先张开→有效完整拳累计2秒→再张开点火；半握缩小、全拳或翻掌向下熄灭。临界拳暂停，真正短缺失0.28秒宽限；缺失/恢复间隔不计2秒。双手独立，可同时点火，只需识别手。

手动切换免垂手；切换/重置/关闭摄像头清理状态。月刃和雷霆UI隐藏，内部索引保留供兼容测试。点“记录日志”开始/停止，不保存个人影像、不上传；反馈动作/现象和大致时间，Codex自行提取本机诊断。坐姿与视觉质量待真人复测。

## 开发者

Python3.12 x64，依赖锁在requirements-lock.txt。准备环境后：

```powershell
uv pip install --python .venv/Scripts/python.exe -r requirements-lock.txt
uv pip install --python .venv/Scripts/python.exe -e . --no-deps
.venv/Scripts/python.exe tools/prepare_models.py
.venv/Scripts/python.exe -m mirror_moon --autostart --diagnostics
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/ruff.exe check src tests tools
.venv/Scripts/python.exe tools/graphics_smoke.py
.venv/Scripts/python.exe tools/spell_smoke.py
.venv/Scripts/python.exe tools/spell_smoke.py --compat --output local/new-spells-compat
.venv/Scripts/python.exe tools/shader_probe.py
.venv/Scripts/python.exe tools/ui_smoke.py
.venv/Scripts/python.exe tools/build.py
.venv/Scripts/python.exe tools/package_smoke.py --app-dir '实际打包目录'
.venv/Scripts/python.exe tools/zip_smoke.py --app-dir '实际打包目录'
```

`--demo --mode water/fire`是构造输入，不是真人识别；`--video 路径`是明确标注的视频回放。最新[验证记录](docs/VALIDATION.md)区分软件、原生连通、构造输入和待真人项。[交接说明](docs/HANDOFF.md)给最短自测。精确5cm、真实深度/碰触、精确人体遮挡与完整流体仿真不作虚假承诺。D、最终课程报告、真实分工、教师模板和真人视频尚未完成。
