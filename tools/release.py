"""Stage the deliverable, then freeze a tested commit and an explicit Gemini upload kit."""

import argparse
import hashlib
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.2.0"
OUTPUTS = ROOT.parents[1] / "outputs"
PORTABLE = OUTPUTS / f"镜中取月_v{VERSION}"


def git(*arguments):
    return subprocess.check_output(["git", *arguments], cwd=ROOT).decode("utf-8").strip()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def archive_directory(directory, target, prefix=None):
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=3) as archive:
        for file in sorted(directory.rglob("*")):
            if file.is_file():
                archive.write(file, Path(prefix or directory.name) / file.relative_to(directory))
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None


def stage():
    OUTPUTS.mkdir(exist_ok=True)
    if PORTABLE.exists():
        raise RuntimeError(f"交付目录已存在，不自动覆盖：{PORTABLE}")
    shutil.copytree(ROOT / "dist" / "MirrorMoon", PORTABLE)
    for name, args in (
        ("启动摄像头.cmd", "--autostart --diagnostics"),
        ("构造动作演示.cmd", "--demo"),
        ("兼容画质.cmd", "--compat --autostart --diagnostics"),
    ):
        (PORTABLE / name).write_bytes(
            ('@echo off\r\nstart "" "%~dp0MirrorMoon.exe" ' + args + "\r\n").encode("ascii")
        )
    print(PORTABLE, flush=True)


def finalize():
    assert not git("status", "--porcelain"), "先提交固定基线，再生成审查包"
    head = git("rev-parse", "HEAD")
    paired = json.loads((ROOT / "local/package-smoke.json").read_text("utf-8"))
    camera = next(x for x in paired if x["case"] == "camera")
    assert camera["application_path_contains_chinese"] and camera["metrics"]["pipeline_error"] is None
    assert camera["metrics"]["paired_inference_hz"] > 0 and camera["metrics"]["paint_count"] > 0
    assert digest(PORTABLE / "MirrorMoon.exe") == digest(ROOT / "dist/MirrorMoon/MirrorMoon.exe")
    remote = git("ls-remote", "--heads", "origin", "refs/heads/codex/mirror-moon")
    pushed = remote.split()[0] == head if remote else False
    baseline = {
        "version": VERSION,
        "commit": head,
        "base_commit": git("rev-parse", "79cddf2"),
        "branch": "codex/mirror-moon",
        "repository": git("remote", "get-url", "origin"),
        "pushed": pushed,
        "branch_url": "https://github.com/hsbslscswda/Python-/tree/codex/mirror-moon" if pushed else None,
        "exe_sha256": digest(PORTABLE / "MirrorMoon.exe"),
        "human_acceptance": "pending",
        "models": json.loads((ROOT / "assets/models/manifest.json").read_text("utf-8")),
    }
    for filename in ("README.md", "THIRD_PARTY_NOTICES.md"):
        shutil.copy2(ROOT / filename, PORTABLE / filename)
    shutil.copytree(ROOT / "docs", PORTABLE / "docs", dirs_exist_ok=True)
    (PORTABLE / "BASELINE.json").write_text(json.dumps(baseline, ensure_ascii=False, indent=2), "utf-8")
    tracked = git("ls-files").splitlines()
    review = ROOT / "local" / f"review-{VERSION}"
    review.mkdir(exist_ok=True)
    for filename in tracked:
        target = review / "source" / filename
        target.parent.mkdir(exist_ok=True, parents=True)
        shutil.copy2(ROOT / filename, target)
    (review / "BASELINE.json").write_text(json.dumps(baseline, ensure_ascii=False, indent=2), "utf-8")
    (review / "changes.patch").write_bytes(
        subprocess.check_output(["git", "diff", "79cddf2", head, "--"], cwd=ROOT)
    )
    evidence = review / "evidence"
    evidence.mkdir(exist_ok=True)
    for filename in (
        "pytest-results.txt",
        "pytest-results.xml",
        "ruff-results.txt",
        "model-path-smoke.json",
        "package-smoke.json",
        "missing-model-smoke.json",
        "missing-model-repeated.json",
        "extracted-package-smoke.json",
        "ui-smoke-demo.json",
        "ui-smoke-camera.json",
    ):
        shutil.copy2(ROOT / "local" / filename, evidence / filename)
    for folder in ("graphics", "graphics-compat"):
        target = evidence / folder
        target.mkdir(exist_ok=True)
        for filename in ("results.json", "metrics.json"):
            shutil.copy2(ROOT / "local" / folder / filename, target / filename)
    for filename in ("ui-guide-synthetic.png",):
        shutil.copy2(ROOT / "local" / filename, evidence / filename)
    for filename in ("circle-overdrive.png", "blade.png", "mirror-fold.png", "mirror-shatter.png"):
        shutil.copy2(ROOT / "local/graphics" / filename, evidence / "graphics" / filename)
    (review / "先读我.md").write_text(
        f"""# 固定基线 v{VERSION} / {head[:7]}

先读 source/docs/VALIDATION.md 的 v0.2.0 记录，再读 source/docs/DECISIONS.md 与 GEMINI_REVIEW_RESPONSE.md。完整源码、配置、着色器、测试、依赖锁和模型来源均在 source；差异在 changes.patch。原用户反馈已经证明 v0.1.1 真人体验失败，旧构造测试不能覆盖这一结论。

本包没有用户摄像头照片、视频、个人关键点，也没有模型权重。evidence 中有当前 pytest、真实模型中文路径测试、最终中文交付路径EXE检查与明确标注的构造画面。v0.2.0 真人动作与视觉体验尚未复验，不能把修复后的模拟测试当作人体通过。

请审查：1. 新的 Hands/Pose 关联、肘角滤波、按臂校准是否仍会引入身份交换或抖动/迟滞；2. 召唤手自由后，握臂进入/失去/恢复的证据和退出是否安全，包含正面透视缩短；3. 月刃/镜面在10Hz附近及遮挡重获时是否存在误触或漏触。每项给具体文件、复现和验收；未运行请明示。不要另起工程。
""",
        "utf-8",
    )
    manifest = {
        str(p.relative_to(review)).replace("\\", "/"): digest(p)
        for p in sorted(review.rglob("*"))
        if p.is_file() and p.name != "FILES_SHA256.json"
    }
    (review / "FILES_SHA256.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), "utf-8")
    kit = OUTPUTS / f"发给Gemini_v{VERSION}"
    kit.mkdir(exist_ok=True)
    review_zip = kit / f"镜中取月_v{VERSION}_Gemini审查包.zip"
    archive_directory(review, review_zip, "MirrorMoon_Review")
    prompt = f"""这是《镜中取月》当前代码的固定基线审查包，版本 v{VERSION}，commit {head}。
请先解压阅读“先读我.md”、source/docs/VALIDATION.md 的 v0.2.0 记录、GEMINI_REVIEW_RESPONSE.md 及相关源码/测试。上一版已有真人反馈：强度抖动、双手接近失效、握臂未成功、月刃/镜面无法实际释放；本次修复尚待真人复验。
请只审查三个问题：Hands/Pose 关联、肘角滤波与按臂校准的身份/稳定性；召唤手自由后握臂进入退出（含透视缩短）；10Hz和遮挡重获时月刃/镜面误触漏触边界。
每项给严重程度、文件位置、最小复现、影响、最小修正和验收方法。没有运行就明确说未运行。不要重新起工程，不把构造输入、模型连通或旧版测试当成真人动作通过。真人动作与审美由我反馈，技术实现与验证由 Codex 负责。
"""
    (kit / "复制给Gemini.txt").write_text(prompt, "utf-8")
    (kit / "怎么发.md").write_text(
        f"上传本文件夹中的 **{review_zip.name}**，再把 **复制给Gemini.txt** 的全文粘贴到同一条消息。不需要上传Windows运行包、旧审查包或个人影像。\n",
        "utf-8",
    )
    app_zip = OUTPUTS / f"镜中取月_Windows_v{VERSION}.zip"
    archive_directory(PORTABLE, app_zip)
    source_zip = OUTPUTS / f"镜中取月_源码_v{VERSION}.zip"
    with zipfile.ZipFile(source_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=3) as archive:
        for filename in tracked:
            archive.write(ROOT / filename, Path("MirrorMoon_Source") / filename)
        for p in (ROOT / "assets/models").glob("*.task"):
            archive.write(p, Path("MirrorMoon_Source/assets/models") / p.name)
        for p in (PORTABLE / "THIRD_PARTY_LICENSES/mediapipe").rglob("*"):
            if p.is_file():
                archive.write(
                    p,
                    Path("MirrorMoon_Source/THIRD_PARTY_LICENSES/mediapipe")
                    / p.relative_to(PORTABLE / "THIRD_PARTY_LICENSES/mediapipe"),
                )
        archive.writestr(
            "MirrorMoon_Source/BASELINE.json", json.dumps(baseline, ensure_ascii=False, indent=2)
        )
    for original, target in (
        ("VALIDATION.md", f"验证记录_v{VERSION}.md"),
        ("HANDOFF.md", f"启动与自测_v{VERSION}.md"),
    ):
        shutil.copy2(ROOT / "docs" / original, OUTPUTS / target)
    (OUTPUTS / "先读我.md").write_text(
        f"""# 请使用修复版 v{VERSION}

双击同目录的「双击启动镜中取月.lnk」，窗口标题须为 v{VERSION}。也可打开「{PORTABLE.name}」中的「启动摄像头.cmd」。旧包不自动更新。关闭摄像头点按钮或按 C。

给 Gemini：进入「{kit.name}」，上传其中唯一的ZIP，再粘贴「复制给Gemini.txt」全文。

代码基线 {head}。GitHub 开发分支已同步：{pushed}。{baseline["branch_url"] or ""}

日志可在程序中点击「打开日志文件夹」。修复版的真人动作与视觉体验仍待本人复验。队友可从 GitHub Releases 下载 Windows ZIP： https://github.com/hsbslscswda/Python-/releases/tag/v{VERSION} 。详见「验证记录_v{VERSION}.md」。
""",
        "utf-8",
    )
    files = [app_zip, source_zip, review_zip, kit / "复制给Gemini.txt"]
    (OUTPUTS / f"交付校验_v{VERSION}.json").write_text(
        json.dumps(
            {
                "baseline": baseline,
                "files": {
                    str(p.relative_to(OUTPUTS)): {"bytes": p.stat().st_size, "sha256": digest(p)}
                    for p in files
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        "utf-8",
    )
    print(
        json.dumps(
            {"version": VERSION, "commit": head, "pushed": pushed, "review_zip": str(review_zip)},
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("stage", "finalize"))
    arguments = parser.parse_args()
    stage() if arguments.action == "stage" else finalize()
