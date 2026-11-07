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

## 用户提供的 Gemini 八文件升级包（v0.3.1）

来源为用户在本会话提供的「镜中取月_v0.3.1_Gemini前端与算法升级包.zip」，SHA256：`65a4349633e925bdc58606d84960bb09797275328eb46d1e4709647e46616458`。包含stage.frag以及app/guide/render/star_ring/control/interaction/features七个Python文件，均先逐字节覆盖并校验；render.py与原v0.3.0内容相同。原始包和覆盖前文件保留在本机，不能宣称对端“87项测试/彻底消抖”已在本机或真人上成立。

后续适配：按用户指定统一界面、状态机、流水线和控制器的134°默认端点；稳态强度时间常数调至0.24秒，快速变化路径仍0.050秒；修正与新端点冲突的旧测试期望，新增行为与丢失负例。不是从独立开源仓库导入，不据此推定MIT许可或第三方commit。未新增外部贴图/音轨/字体或依赖。

## 用户提供的第二份八文件升级包（交付v0.3.2）

来源为本会话「镜中取月_v0.3.1_Gemini前端与算法升级包 (1).zip」，SHA256：`ec0217d5998256036ac4f11b5bc6bbc6b2f242f89ad6ad1a025f45e08de7b96a`。八个文件先按字节覆盖并备份。相对已发布v0.3.1，render/star_ring/interaction/features完全相同；新增内容主要在stage.frag、app.py和guide.py，control.py则带回了上一轮修复前的148°/0.19秒。

保留当前134°/0.24秒；修正着色器遮罩将无效区变成零距离导致整片发光、符文分隔带填满及四处逆序smoothstep；同步mirror_texture.py中的冻结图像映射/色彩/折镜雕纹，新增实际GL检查。新面板、花窗/铭文结构和配色予以保留。没有新增第三方贴图、音轨、字体或依赖，也不据文件名推断独立开源许可或仓库commit。

## v0.4.0 原理参考

本轮没有下载/复制第三方纹理、人物图片或Shader整段代码。新水球、射流、火焰和物理状态由本项目实现。水体折射、噪声分层与流体渲染原理参考NVIDIA GPU Gems 3第30章：https://developer.nvidia.com/gpugems/gpugems3/part-v-physics-simulation/chapter-30-real-time-simulation-and-rendering-3d-fluids ，水体焦散参考GPU Gems第2章：https://developer.nvidia.com/gpugems/gpugems/part-i-natural-effects/chapter-2-rendering-water-caustics 。没有声称把该章完整3D流体求解器集成进来。

多Pose选项/输出语义参考Google官方：https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker?tab=Python 。num_poses=2的原生加载不等于双人真人识别成功率已验证。既有库/模型/Qt/PyInstaller许可继续随包保留，无新付费API、服务或字体素材。
