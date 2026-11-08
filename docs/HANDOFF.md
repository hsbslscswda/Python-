# 镜中取月 v0.4.4 工程交接

更新2026-11-08。持续职责和交付流程见[WORKFLOW.md](WORKFLOW.md)；需求以[SPEC.md末尾v0.4.4](SPEC.md)优先；候选逐项判断见[GEMINI_REVIEW_RESPONSE.md](GEMINI_REVIEW_RESPONSE.md)。Codex主要实现/默认唯一集成，Gemini独立审查，用户只负责转交材料和真实动作/审美，不组织源码/日志或裁决技术争议。

## 最新需求 / 版本 / 路径

本轮基于固定v0.4.3/d2f715fc3813e7ad92a65cf592bca48939c15af0集成最新v0.4.4 ZIP，SHA168f1617bd400665a4a0a336da6ad53ff0f89cfa3069862a6c0451a06cdea484。当前分支codex/mirror-moon。原包/展开文件/覆盖前备份/差异/证据位于local/incoming-v044；运行固定提交54f709a3c0509b99a0f2fe8768cfaf51a0c4ab50；EXE摘要写入最终BASELINE.json与交付清单。后续文档提交不移动运行标签。

必须保留：完整v043冰系布局和隐藏雷霆/内部索引；镜面/冻结片、镜水向下出画0.30秒消散、大开合或纯丢失保持；水火掌上悬空/独立火和手动切换免垂手。新修正：躯干正面yaw±1.08、仅正身更新参考、cos0.44/双盘视差；用户四冰色；双掌50/50、0.22秒短容错不无限续OTHER，手仅模式亦不吸附；可靠Pose搭腕/水平指向平射/重力0.04和环腰圆锥音爆雾；has_orb、冷却0.65后新FIST→2.2秒内明确OPEN>=0.45重召，不再0.85秒原地回凝。

- 实际仓库：`C:\Users\hsbsl\Documents\Codex\2026-11-07\https-github-com-hsbslscswda-python-invitations\work\Python-`；当前聊天cwd不是代码仓库。
- 本机最终入口：`C:\Users\hsbsl\Documents\Codex\2026-11-07\https-github-com-hsbslscswda-python-invitations\outputs/双击启动镜中取月.lnk`；便捷入口为`C:/Users/hsbsl/Documents/ChatGPT/镜中取月/启动镜中取月_v0.4.4.lnk`；或`C:\Users\hsbsl\Documents\Codex\2026-11-07\https-github-com-hsbslscswda-python-invitations\outputs\镜中取月_v0.4.4/启动摄像头.cmd`（MirrorMoon.exe）。标题v0.4.4，C关摄像头、Esc重置、空格暂停、F11全屏。
- 交付：`C:\Users\hsbsl\Documents\Codex\2026-11-07\https-github-com-hsbslscswda-python-invitations\outputs/镜中取月_Windows_v0.4.4.zip`与`镜中取月_源码_v0.4.4.zip`；校验为`交付校验_v0.4.4.json`。
- Gemini上传：`C:\Users\hsbsl\Documents\Codex\2026-11-07\https-github-com-hsbslscswda-python-invitations\outputs/发给Gemini_v0.4.4/镜中取月_v0.4.4_Gemini审查包.zip`；粘贴同目录`复制给Gemini.txt`全文，最多三个问题。包内无个人录像/原始动作JSONL、模型权重或EXE。
- 本轮证据：`C:\Users\hsbsl\Documents\Codex\2026-11-07\https-github-com-hsbslscswda-python-invitations\work\Python-\local\incoming-v044`；外层短测/验证摘要在outputs/启动与自测_v0.4.4.md、验证记录_v0.4.4.md。
- Python3.12、原requirements-lock与检查配置保留；GLSL显式UTF-8不能回退默认GBK。公开模型及许可证仍随包保留。
- 真人诊断：`%LOCALAPPDATA%/MirrorMoon/diagnostics`。用户点“记录日志”，结束只回报法术/现象/大致时间；Codex自动定位分析，不让用户提取/打包。

## 软件已验证 / 真人待验

本轮原候选161项通过；集成168 pytest、Ruff/compileall、标准/高GL十次缩放全屏及冰/镜/隐藏刃、标准/高/兼容水火、24镜面采样、摄像头启停、最终EXE七项与真实ZIP解压运行全部通过。高/兼容无未请求重生帧。最终EXE SHA `f18f6e309deec2c9780deb38f8141ea74702b75722e1a3cf9b72723571f7044b`。软件测量/首次失败/修正证据见VALIDATION顶部。

真实侧身识别、双掌不同远近、搭腕/掌向成功率、发射方向和冰色/水雾审美、多人命中与长时稳定性待用户；识别约15Hz，未达20Hz目标。程序化视觉与单目估计不冒充精确深度/流体。课程D扩展和最终课程材料未完成。

## 发布 / Gemini进度

v0.4.4已公开预发行：[发布页](https://github.com/hsbslscswda/Python-/releases/tag/v0.4.4)，release ID 438226332，draft=false、prerelease=true。运行标签固定 `54f709a3c0509b99a0f2fe8768cfaf51a0c4ab50`，三个附件均uploaded，服务器大小/SHA256与本地清单一致，Windows公开下载HEAD200。运行/源码/复审基线固定，当前后续文档提交记录实际发布结果，包内HANDOFF冻结于发布前；不因此重建包体或移动标签。

本机主快捷方式与便捷入口`C:/Users/hsbsl/Documents/ChatGPT/镜中取月/启动镜中取月_v0.4.4.lnk`已指向该版最终EXE。源码包、Windows包、Gemini包与提示词均已生成并逐项校验；详情见outputs/交付校验_v0.4.4.json与GitHub下载_v0.4.4.json。沿用既有分支正常推送和独立新预发行，旧版本无覆盖/重复上传。

已核验v0.4.3公开发布ID438178805、d2f715f、三个附件完整；v0.4.0–v0.4.2也保留，不重建/上传一致附件。包内交接在冻结时记录状态，发布后仅后续文档提交更新当前HANDOFF。

已收到并处理本轮原候选，决定见GEMINI_REVIEW_RESPONSE。新v0.4.4复审包已冻结，待用户转交，未收到集成后复审。三个重点：侧身姿态/冰色布局，双掌/发射/重召状态，水材质音爆雾和性能/回归。用户不需要重新组织问题。

## 用户下一步短测 / 工程下一步

1. 打开当前启动入口确认v0.4.4，点记录日志。冰魔法胸前握拳唤阵，另一手开掌；身体左右转动和仅横移分别测试，看法阵是否跟随前胸、层次/颜色是否合意。镜/冰尽量肩肘入画，水火可只手。
2. 水球握拳→明确摊开，双掌夹球保持后慢拉大/收小、两掌一远一近，观察中点是否稳定；短遮副手再回来，不能骤吸回另一手。
3. 分别掌向前、掌向上和侧身搭腕发射，也可副手拳助推/主人拳压缩；看平飞方向、球面高光/焦散及环腰音爆云。发射后保持摊手至少3秒，原位不应出现新球；冷却后重新握拳再明确摊开，应新召小球，OTHER自然放松不召唤。
4. 简短回归：镜/水双手向下出画0.30秒消散、大开合出画保持；独立火各自张开→拳2秒→再张开，半握/翻掌熄灭。完成停日志并按C，只反馈法术/现象/时段。

用户：做真实动作/视觉反馈并将唯一新审查ZIP+提示词全文发给Gemini，转回完整回复和候选。Codex：冻结/发布、启动入口、复审材料与最终交接已完成；随后主动提取本机日志、复现修复，逐项接受/调整/不采用/延期Gemini意见并更新证据；只有真实动作/审美/缺授权才等待，远程故障不阻止本地使用/审查。
