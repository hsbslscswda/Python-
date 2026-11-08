# 镜中取月 v0.4.3 工程交接

更新2026-11-08。持续职责/固定交付流程见[WORKFLOW.md](WORKFLOW.md)，最新规则见[SPEC.md末尾](SPEC.md)，逐项判断见[GEMINI_REVIEW_RESPONSE.md](GEMINI_REVIEW_RESPONSE.md)。Codex为主要实现者和默认唯一集成者；用户只负责转交、真实动作和视觉反馈，Gemini意见由Codex结合代码/证据处理。

## 最新需求与当前版本

最新输入是Downloads的`镜中取月_v0.4.3_Gemini特效与交互终极升级包 (1).zip`，SHA d3ad651bad5ef932c8153225d4935422ab3338a09624b47f9ddab0c635a48083；基线v0.4.2/f458d6c8fcef5959b206f5e47d66668fdcb57a42。非docs运行改动已直接导入并修正原生回归；保留原包、展开文件、覆盖前备份及差异于local/incoming-v043。候选旧文档“月华/取消冰雪”不采用，当前用户明确冰魔法要求优先。

当前运行/复审版本v0.4.3，分支codex/mirror-moon；运行固定提交d2f715fc3813e7ad92a65cf592bca48939c15af0；最终EXE SHA写入交付/审查包BASELINE.json与outputs/交付校验_v0.4.3.json。后续仅文档提交记录实际发布结果，运行标签不移动。v0.4.0/172977f、v0.4.1/c3d70f6、v0.4.2/f458d6c及各自包体全部保留。

必须保留：冰魔法名称和三层冰枪/16冰刺/冰雷/三螺旋/三震波/三种雪花及扇外伴生物，隐藏雷霆UI但内部circle/moon/元素索引1保留，前向限幅/胸前门槛/双掌共鸣+搭腕；镜水双手下垂出画连续0.30秒消散，大开合一上一下/一左一右出画保持，纯追踪丢失保持；玄银蓝宝纯净八角镜；水火掌上悬空；水三发射通道、主人锁定、不把OTHER当缩放；火焰有效拳累计/临界拳暂停/0.28秒缺失宽限/左右独立。旧历史“仅拍掌”“双臂放下也永不关闭”“月华/雷霆可选”已被本轮覆盖。

## 实际路径与启动

- 仓库：`C:\Users\hsbsl\Documents\Codex\2026-11-07\https-github-com-hsbslscswda-python-invitations\work\Python-`；当前聊天cwd不是仓库。
- 本机启动：`C:\Users\hsbsl\Documents\Codex\2026-11-07\https-github-com-hsbslscswda-python-invitations\outputs/双击启动镜中取月.lnk`，最终验证后指向v0.4.3；或直接`C:\Users\hsbsl\Documents\Codex\2026-11-07\https-github-com-hsbslscswda-python-invitations\outputs\镜中取月_v0.4.3/启动摄像头.cmd`（调用同目录MirrorMoon.exe）。标题应为v0.4.3，C关闭摄像头，Esc重置，空格暂停，F11全屏。
- Windows完整解压包：`C:\Users\hsbsl\Documents\Codex\2026-11-07\https-github-com-hsbslscswda-python-invitations\outputs/镜中取月_Windows_v0.4.3.zip`；源码包：`C:\Users\hsbsl\Documents\Codex\2026-11-07\https-github-com-hsbslscswda-python-invitations\outputs/镜中取月_源码_v0.4.3.zip`。
- Gemini上传文件：`C:\Users\hsbsl\Documents\Codex\2026-11-07\https-github-com-hsbslscswda-python-invitations\outputs/发给Gemini_v0.4.3/镜中取月_v0.4.3_Gemini审查包.zip`；配套文字：同目录`复制给Gemini.txt`全文。无需用户拆源码/写问题/找日志。
- 实测/失败/构造图：`C:\Users\hsbsl\Documents\Codex\2026-11-07\https-github-com-hsbslscswda-python-invitations\work\Python-\local\incoming-v043`；最终摘要：`C:\Users\hsbsl\Documents\Codex\2026-11-07\https-github-com-hsbslscswda-python-invitations\outputs/验证记录_v0.4.3.md`。
- Python3.12 `.venv`，依赖锁requirements-lock.txt；GLSL资源必须显式UTF-8读取，不能依赖-X utf8掩盖Windows GBK问题。模型和许可在assets/models及包体第三方许可目录。
- 用户诊断：`%LOCALAPPDATA%/MirrorMoon/diagnostics`。测试前点“记录日志”，结束停止；用户只需法术/现象/大致时段，Codex自行定位。审查包无个人录像、原始JSONL、模型权重或EXE。

## 软件验证 / 待真人分开

本轮157 pytest、Ruff/compileall、严格标准/高GL十次缩放全屏和冰/镜/刃构造动作、兼容动作、水火完整事件、摄像头启停重开、最终EXE七项、真实ZIP解压同EXE检查均通过。镜面三尺寸24组合p95=1/255（原八组中位0）；最终EXE SHA `36b56c3c7f3f97dff0a94dccd015e2ae0f7647427db02e01767c3f38bd98526c`。性能与失败证据见VALIDATION顶部，不拿退出0或测试数量当GL成功。识别仍约15Hz，低于20Hz目标；新图形脚本约58次/秒是Qt提交率，非显示FPS保证。

真人动作、主观视觉/亮度、多人碰撞、动作成功率和长时稳定性待验；课程D扩展和最终报告/成员/模板/视频未完成。

## 发布状态

v0.4.3已公开预发行：[GitHub发布页](https://github.com/hsbslscswda/Python-/releases/tag/v0.4.3)，release ID 438178805，draft=false、prerelease=true。运行标签固定 `d2f715fc3813e7ad92a65cf592bca48939c15af0`，三附件均uploaded，服务器字节数/SHA256与本地清单一致，Windows公开下载HEAD200。首次Windows上传在TLS握手时连接重置；复用同一发布ID并保留已验源码/审查附件，只补缺Windows包后完成，没有重复建发布或覆盖旧附件。

本机快捷方式现指向v0.4.3，另有便捷入口`C:/Users/hsbsl/Documents/ChatGPT/镜中取月/启动镜中取月_v0.4.3.lnk`。三ZIP/审查清单/代码提交均已冻结，具体摘要在outputs/交付校验_v0.4.3.json；发布记录在outputs/GitHub下载_v0.4.3.json。包内HANDOFF冻结于发布前，当前仓库HANDOFF由后续文档提交记录最终状态，不为更新文档重建同版或移动标签。

已核验历史v0.4.2公开预发行ID437689890，三个附件完整；v0.4.1 ID437681562、v0.4.0 ID437538423保留。旧发布并无当前缺失工作，不重建/重传。

## 用户下一步：最短自测

1. 打开上述启动入口，确认v0.4.3，点记录日志；坐姿也可用，冰/镜尽量让肩肘入画，水火仅手也可用。双手放腿/桌面几秒，冰魔法不应误召唤；抬至胸/颈前握拳唤阵，另一手开掌前伸。测试副手搭腕与两掌同时打开的过载，观察是否正面稳定、层次和亮度合适。
2. 镜界：双手靠近稍停再拉开，缩放/旋转/折镜；分别大开合出画和双手自然向下出画，前者保持、后者约0.30秒开始消散。遮住低位但仍在画内的手不应关闭。再开后快合碎镜，看图像与方向是否连续；慢合停住可收镜。
3. 水球：握拳→摊开，观察球明显悬空与惯性；双掌夹球保持后拉开（含斜向）；分别试副手从画外直接搭腕、近腕握拳助推、主人手握拳压缩发射。试拍掌结束和下垂出画结束、大开合保持；留意误发射和缩放跳变。
4. 火焰：左右分别张开→握拳累计2秒→张开，再同时点火；半握缩小、短遮挡、全拳/翻掌向下熄灭，观察球形底部、悬空间隙、暗部与火舌是否合意。完成停止记录并按C；只反馈法术/现象/大致时间。

## Gemini进度与工程下一步

已收到并逐项处理原候选，结论见GEMINI_REVIEW_RESPONSE；新固定v0.4.3复审包/提示词已随交付冻结，尚待用户转交，最多三个重点：镜面插值/旋转碎片/出画；水发射缩放与火解锁边界；完整冰系及标准/高画质成本/过曝。未收到集成后v0.4.3复审，不能写成Gemini已验收。

用户：上传唯一新审查ZIP并粘贴配套提示词全文，转回完整回复及候选文件；做上述真实动作并反馈。Codex：本轮冻结、远程发布和审查材料已完成；随后按真实反馈自动分析本机日志、复现修复，按Gemini意见逐项接受/调整/不采用/延期并更新证据。仅真实动作/审美/缺少授权才等待；远程故障不阻止本地运行或审查。
