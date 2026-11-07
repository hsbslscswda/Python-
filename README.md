# 镜中取月 v0.4.1

本轮集成Gemini特效候选：冰晶式定向射流、透明折射水球、火焰细节与切角折镜，并补齐CPU冻结采样/不规则碎片。保留已有结束规则、普通名称和双元素选择；逐项判断见[审查回应](docs/GEMINI_REVIEW_RESPONSE.md)。

## 直接运行

下载[Windows运行包](https://github.com/hsbslscswda/Python-/releases/download/v0.4.1/MirrorMoon-Windows-v0.4.1.zip)，完整解压后双击「启动摄像头.cmd」。无需安装Python；保留_internal。标题应为v0.4.1。C关闭摄像头，Esc重置，空格暂停，F11全屏。所有功能本机运行，不依赖LLM或网络服务。

## 坐着也能操作

- 星环术：身前横臂，或松握拳；胸前/颈前均可，无90度要求。另一手开掌抬起输出定向射流，弯伸调强度。搭腕/前臂过载，握拳停法留阵，放下施法臂收阵。暖色金属法阵与蓝/紫释放物分色，默认低辉光。
- 镜界术：双手稍靠近后拉开。平移/缩放/旋转，慢合保持收镜，快合碎镜。手或镜面超出画面时保持；能看见手臂就用手臂估计控制，全部丢失则冻结镜面，回来后继续，不因丢手自动关闭或碎裂。
- 水球术：任意一手握拳再摊开。水球随掌心惯性跟随，双掌相对夹住拉开可变大；另一手搭腕/前臂发射，拍掌结束。丢手和身体遮挡不取消状态，暂停冻结；发射后水球会回凝，仍属于同一次施法。近大远小、重力、人物/镜头碰撞为单目近似。
- 掌心火焰：先张开→握拳满2秒解锁该手→再张开点火。左右手独立；半握时缩小、完全握拳或翻掌朝下熄灭，之后张开可重燃。掉点不是握拳，解锁短缺失暂停且不计入2秒，超过宽限渐熄。只需识别手，无需身体或站姿。

手动切换不要求垂手或先拍到垂下的手。切换/重置/关闭摄像头是明确的清理操作；水球在追踪条件变化时只有拍掌才结束。月刃菜单继续隐藏，内部实现/index 1保留。点「记录日志」开始/停止，点「打开日志文件夹」找到JSONL；不默认保存影像、不上传。

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
