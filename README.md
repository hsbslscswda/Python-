# 镜中取月

基于 MediaPipe 的 Windows 本地动作交互 AR 魔法舞台。Python 负责采集、同帧手部/人体识别、动作时序和容错，Qt/ModernGL 负责显示和 GPU 合成。运行不调用 AI API，不上传摄像头画面。

**当前为 v0.1.1 可运行候选，不是课程最终验收版。** 修复 v0.1.0 在中文安装目录打不开模型、导致黑屏的问题：Python 读取并校验模型，再以字节缓冲交给 MediaPipe。三套系统已有实现和构造轨迹测试；正面伸臂、握臂遮挡、真实误触与视觉体验仍须本人验证。详见 `docs/VALIDATION.md` 与 `docs/HANDOFF.md`。

## 最简单的运行方式

有打包文件时，解压整个 `MirrorMoon` 文件夹，双击 `MirrorMoon.exe`。不能只复制 EXE，`_internal` 与第三方许可证目录须一起保留。

1. 选择摄像头 0，点击「打开预览」，让双肩、双肘、双手进入画面。
2. 可选「20 秒校准」，按提示完成右臂弯曲与舒适伸直；样本不足不会覆盖原设置。当前左右臂共用这组端点，是待改进项。
3. 点击「开始施法」，先放下双手约半秒，再按底部提示操作。Esc 收招，空格暂停，F11 全屏。
4. 无摄像头可打开本机视频，界面明确标记「视频回放」。`MirrorMoon.exe --demo` 为构造动作展示，不能证明真人识别效果。显卡不兼容时使用 `MirrorMoon.exe --compat`。

## 三套动作

- 星环术：一手在胸前握拳召唤；另一手张开抬起，弯伸控制输出。施法手握拳/放下停止输出，胸前拳保持则法阵保留。施法中让召唤手靠近并握住施法前臂中段，进入掌前极限阵列；回胸恢复，脱离超时结束。
- 月刃术：手收至对侧肩前停留，向外横挥/斜挥。短暂恢复后同手反向挥可连斩。实际轨迹相交且夹角符合要求才认作十字。
- 镜界术：双手在胸前靠近开掌停留，再拉开；中点、距离和高差控制镜面。拉大保持后平移进入折镜。慢合收镜，快合碎镜；丢手本身不会触发碎镜。

切换系统、Esc 或暂停恢复后，都需要一次真实的中性姿态：放下双手或放松为非开掌/非拳姿态。鼠标操作界面时暂时抑制动作更新。

## 源码运行（PowerShell / Python 3.12 x64）

```powershell
uv venv --python 3.12 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements-lock.txt
uv pip install --python .venv/Scripts/python.exe -e . --no-deps
.venv/Scripts/python.exe tools/prepare_models.py
.venv/Scripts/python.exe -m mirror_moon
```

锁文件记录本机验证的组合；模型来自 Google 官方 version 1 地址，准备工具验证 `assets/models/manifest.json` 中的 SHA-256。应用运行期间不临时下载模型。

```powershell
# 构造动作，绝非真人识别证据
.venv/Scripts/python.exe -m mirror_moon --demo --mode mirror
# 真实摄像头，显示诊断；主动保存关键点/状态/时序，不保存 RGB
.venv/Scripts/python.exe -m mirror_moon --autostart --diagnostics --record-features local/G0.jsonl
# 本机录像回放，仍走同帧 Hands/Pose
.venv/Scripts/python.exe -m mirror_moon --video 'D:/videos/test.mp4'
# 关键点回放；可在 tracking 行补 expected_state 做人工标注断言
.venv/Scripts/python.exe tools/replay.py local/G0.jsonl --output local/replay-result.json
```

界面「记录 G0 日志」也可开始/停止记录。默认关闭；关键点同样属于个人测试资料，不自动纳入审查包。日志、校准和截图在 `%LOCALAPPDATA%/MirrorMoon`，源码目录不必可写。摄像头图像只在主动截图时保存。

## 验证与打包

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/ruff.exe check src tests tools
.venv/Scripts/python.exe tools/graphics_smoke.py
.venv/Scripts/python.exe tools/graphics_smoke.py --compat --output local/graphics-compat
.venv/Scripts/python.exe tools/build.py
```

图形测试使用构造数据，覆盖三套系统、冻结纹理碎镜、10 次缩放/全屏、图像方向与关闭。摄像头测试、真实动作成功率、端到端延迟与长时稳定性单列，不能由此替代。

## 工程入口

`pipeline.py` 是采集线程、同帧推理线程和容量一快照；`tracking.py` 负责 MediaPipe 边界及特征；`interaction.py` 是纯 Python 状态机；`transport.py` 保存有序瞬时事件；`render.py` 和 `assets/*.glsl`/`*.frag`/`*.vert` 是主线程渲染；`diagnostics.py` 是主动记录和回放解码。无需先拆成任务卡建议的多个同名目录。

课程原文保存在 `docs/COURSE_REQUIREMENTS.md`，产品规格在 `docs/SPEC.md`。源码、真实成员分工、实验报告和不超过五分钟视频仍须按教师模板完成，不能提交虚构实验数据。
