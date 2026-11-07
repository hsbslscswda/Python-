# 第三方来源与本项目实现

核查日期：2026-11-07。精确安装版本见 `requirements-lock.txt`。本项目没有复制第三方完整魔法应用，没有使用电影纹章、音轨或未知来源贴图。

## 运行库

| 项目 | 已安装版本 | wheel 元数据许可 | 来源 / 用途 |
|---|---|---|---|
| MediaPipe | 1.2.2 | Apache 2.0 | https://github.com/google-ai-edge/mediapipe ，手/人体模型运行时 |
| OpenCV contrib Python | 5.0.0.93 | Apache 2.0 | https://github.com/opencv/opencv-python ，采集与色彩转换 |
| NumPy | 2.5.4 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | https://numpy.org/ ，数组及有界网格 |
| PySide6 / Shiboken | 6.12.0 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only | https://code.qt.io/cgit/pyside/pyside-setup.git/ ，Qt 界面、OpenGL 控件及音效 |
| ModernGL / glcontext | 5.13.0 / 3.1.0 | MIT | https://github.com/moderngl/moderngl ，当前 Qt 上下文中的绘制 |

PySide6/Qt 使用动态库；发行目录 `_internal` 中保留动态链接形式，第三方许可证与依赖清单在 `THIRD_PARTY_LICENSES`。Qt/PySide 源码入口分别为 https://code.qt.io/cgit/qt/qtbase.git/ 与上述 pyside-setup；按相应版本获取源码及许可。Qt 组件、编解码器等附属许可不能简单概括为 MIT。构建工具收集安装包内许可文件，不删除其通知。

发行程序还包含 PyInstaller 6.22.3 bootloader；其 GPL v2 或更新版本及专门发行例外原文保存在 `THIRD_PARTY_LICENSES/pyinstaller`。PyInstaller 源码：https://github.com/pyinstaller/pyinstaller 。构建工具本身不是 MediaPipe 算法贡献。

## 官方模型（与库源码分别核查）

- Hand Landmarker float16/1：官方地址、字节数和完整 SHA-256 在 `assets/models/manifest.json`。官方 [Hand Tracking model card](https://storage.googleapis.com/mediapipe-assets/Model%20Card%20Hand%20Tracking%20%28Lite_Full%29%20with%20Fairness%20Oct%202021.pdf) 第 2 页列出 Apache License 2.0。
- Pose Landmarker Lite float16/1：同一 manifest 固定来源和哈希。官方 [BlazePose GHUM 3D model card](https://storage.googleapis.com/mediapipe-assets/Model%20Card%20BlazePose%20GHUM%203D.pdf) 第 2 页列出 Apache License 2.0。
- 模型权重未经修改；准备工具显式下载，正式本地包内携带。模型不是本组训练的成果。

## 本次自研与 AI 辅助

状态时序、角色关联策略、容量一流水线、事件消费、诊断/回放、GLSL 法阵/折镜/碎片网格与界面为本次项目代码，借助 Codex 生成、审阅、调试。音效由 `audio.py` 的原创合成公式生成，未引用外部录音。字体使用系统已有字体，不随包额外分发字体文件。

One Euro 采用公开论文的自适应低通公式自行实现，未复制候选仓库文件。算法来源：[Casiez 等，CHI 2012](https://gery.casiez.net/1euro/)。MediaPipe 的模型/坐标语义、Qt 的 FBO 所有权、ModernGL 的接口参考各自官方文档；没有将参考示例整段作为原创提交。

方案列出的其它 GitHub 候选本次未引入代码或素材，因此没有可宣称复用的 commit/文件。项目自身授权由仓库所有者决定，第三方许可证不自动适用于自研代码。

## 用户提供的 Gemini 候选（v0.3.0）

来源为本会话用户提供的审查文本，附件标识 `04f54740-fe70-491e-bc53-7e18d15a889c`，原文SHA256：`2ca18645f7ba08b369e2b908015af17565ebf45cd0801e874e674cc6b2ca5df4`。采用范围：`assets/stage.frag`、`src/mirror_moon/guide.py`、`app.py`的STYLE候选。它不是另一个开源仓库，不宣称其为MIT或有已核实的第三方repo commit。

修改包括GLSL边界/亮度/投影来源、镜面与碎片纹理一致性、uniform绑定、引导阶段插值/动作速度/文案及校准状态。源码与diff标明实际集成内容，不能把AI候选或模型算法说成本组独立发明。基础仓库未整套照搬其它作品；许可证仍按上述依赖逐项保留。
