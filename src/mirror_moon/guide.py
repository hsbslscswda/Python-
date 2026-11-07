"""User-supplied Gemini pose coach, adapted to the implemented rules; demonstration only."""

import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _lerp_pt(p1: tuple[float, float], p2: tuple[float, float], t: float) -> tuple[float, float]:
    return (_lerp(p1[0], p2[0], t), _lerp(p1[1], p2[1], t))


def _pose(mode, phase, sub_t):
    wave = 0.5 - 0.5 * math.cos(sub_t * math.tau)
    # Compute smooth arm joint positions (shoulder, elbow, wrist, is_fist)
    if mode == "circle":
        if phase == 0:
            l_el, l_wr, l_fist = (
                (70.0, 118.0),
                _lerp_pt((78.0, 150.0), (118.0, 102.0), min(1.0, sub_t * 2.2)),
                True,
            )
            r_el, r_wr, r_fist = (188.0, 122.0), (195.0, 162.0), False
        elif phase == 1:
            l_el, l_wr, l_fist = (72.0, 115.0), (116.0, 104.0), True
            r_el = _lerp_pt((186.0, 115.0), (198.0, 92.0), wave)
            r_wr = _lerp_pt((175.0, 96.0), (218.0, 64.0), wave)
            r_fist = False
        else:
            r_el, r_wr, r_fist = (196.0, 94.0), (216.0, 68.0), False
            l_el = _lerp_pt((72.0, 115.0), (140.0, 108.0), min(1.0, sub_t * 2.0))
            l_wr = _lerp_pt((116.0, 104.0), (202.0, 78.0), min(1.0, sub_t * 2.0))
            l_fist = True
    elif mode == "blade":
        l_el, l_wr, l_fist = (70.0, 124.0), (64.0, 166.0), False
        r_fist = False
        if phase == 0:
            r_el = _lerp_pt((188.0, 118.0), (150.0, 112.0), min(1.0, sub_t * 2.0))
            r_wr = _lerp_pt((195.0, 150.0), (102.0, 78.0), min(1.0, sub_t * 2.0))
        elif phase == 1:
            t_slash = min(1.0, max(0.0, (sub_t - 0.22) * 10.0))
            r_el = _lerp_pt((150.0, 112.0), (204.0, 88.0), t_slash)
            r_wr = _lerp_pt((102.0, 78.0), (236.0, 56.0), t_slash)
        else:
            t_back = min(1.0, max(0.0, (sub_t - 0.22) * 10.0))
            r_el = _lerp_pt((204.0, 88.0), (148.0, 116.0), t_back)
            r_wr = _lerp_pt((236.0, 56.0), (96.0, 108.0), t_back)
    else:
        l_fist = r_fist = False
        if phase == 0:
            gap = _lerp(36.0, 14.0, min(1.0, sub_t * 2.0))
            l_el, l_wr = (74.0, 118.0), (130.0 - gap, 105.0)
            r_el, r_wr = (186.0, 118.0), (130.0 + gap, 105.0)
        elif phase == 1:
            gap = _lerp(18.0, 74.0, min(1.0, sub_t * 1.8))
            tilt_y = 55.0 * math.sin(sub_t * math.tau)
            l_el, l_wr = (68.0, 116.0), (130.0 - gap, 105.0 - tilt_y)
            r_el, r_wr = (192.0, 116.0), (130.0 + gap, 105.0 + tilt_y)
        else:
            gap = _lerp(72.0, 16.0, min(1.0, max(0.0, (sub_t - 0.35) * 12.0)))
            l_el, l_wr = (72.0, 116.0), (130.0 - gap, 105.0)
            r_el, r_wr = (188.0, 116.0), (130.0 + gap, 105.0)

    return l_el, l_wr, r_el, r_wr, l_fist, r_fist


class PoseGuide(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.mode = "circle"
        self.started = time.perf_counter()
        self.setFixedWidth(280)
        self.setMinimumHeight(430)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Card background with subtle border
        rect = self.rect().adjusted(2, 2, -2, -2)
        grad = QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0.0, QColor("#112233"))
        grad.setColorAt(1.0, QColor("#0a1520"))
        p.setBrush(QBrush(grad))
        p.setPen(QPen(QColor("#244660"), 1.5))
        p.drawRoundedRect(rect, 10, 10)

        elapsed = time.perf_counter() - self.started
        cycle_dur = 2.6
        phase = int(elapsed / cycle_dur) % 3
        sub_t = (elapsed % cycle_dur) / cycle_dur
        wave = 0.5 - 0.5 * math.cos(sub_t * math.tau)

        titles = {
            "circle": ("步骤 1/3 · 胸前握拳召唤", "步骤 2/3 · 单手前推控强弱", "步骤 3/3 · 搭手触发过载"),
            "blade": ("步骤 1/3 · 收手至对侧肩前", "步骤 2/3 · 向外快速挥斩", "步骤 3/3 · 反手回斩连击"),
            "mirror": (
                "步骤 1/3 · 双掌错开唤醒",
                "步骤 2/3 · 拉开旋转控镜",
                "步骤 3/3 · 快合碎镜 / 拧转折镜",
            ),
        }
        subtitles = {
            "circle": (
                "任意一手握拳放在胸前约 0.2 秒，展开身前星环",
                "另一手张开朝镜头前推增强、收回减弱；握拳暂停",
                "把召唤手搭在施法手腕附近或前臂上，星环移至掌前增强至 110–150%",
            ),
            "blade": (
                "将右手收到左肩前（或左手收至右肩前）停留蓄势",
                "手腕浮现月牙后，向身体外侧快速横挥或斜挥出刀",
                "出刀后稍停再反向挥回；两条轨迹相交才有十字裂空",
            ),
            "mirror": (
                "双手在胸前靠近（开掌或侧掌，别重叠）停留片刻唤出镜缝",
                "向两侧拉开双手展开魔镜，双手上下转动，可连续旋转镜面",
                "转动镜面后稍停进入折镜；快合至一拳距离碎镜",
            ),
        }
        tips = {
            "circle": "• 放下施法手 = 结束收阵\n• 施法手握拳 = 停止输出但保留法阵\n• 校准当前手臂可让 100% 强度更轻松",
            "blade": "• 挥刀无需猛甩，动作连贯即可\n• 切换系统后请先自然放下双手半秒",
            "mirror": "• 缩小后可再拉开；极近保持会收镜\n• 双手合拢并停住 0.3 秒 = 平静收镜",
        }

        # Header badge
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#1b3b52"))
        p.drawRoundedRect(QRectF(14, 14, 252, 28), 6, 6)
        p.setPen(QColor("#7dd3fc"))
        p.setFont(QFont("Microsoft YaHei UI", 11, QFont.Weight.Bold))
        p.drawText(QRectF(22, 14, 236, 28), Qt.AlignmentFlag.AlignVCenter, titles[self.mode][phase])

        # Step description (large, readable)
        p.setPen(QColor("#f0f9ff"))
        p.setFont(QFont("Microsoft YaHei UI", 11))
        p.drawText(QRectF(16, 48, 248, 52), Qt.TextFlag.TextWordWrap, subtitles[self.mode][phase])

        # Stage viewport for animated mannequin
        p.save()
        p.translate(10, 102)
        p.setBrush(QColor("#08111a"))
        p.setPen(QPen(QColor("#1c3548"), 1))
        p.drawRoundedRect(QRectF(4, 0, 252, 195), 8, 8)

        # Draw soft torso silhouette
        torso_path = QPainterPath()
        torso_path.moveTo(85, 68)
        torso_path.quadTo(130, 62, 175, 68)
        torso_path.lineTo(162, 165)
        torso_path.quadTo(130, 172, 98, 165)
        torso_path.closeSubpath()
        p.setBrush(QColor(30, 58, 82, 140))
        p.setPen(QPen(QColor("#38bdf8"), 1.8))
        p.drawPath(torso_path)

        # Head
        p.setBrush(QColor(30, 58, 82, 180))
        p.drawEllipse(QPointF(130, 34), 18, 21)

        l_sh, r_sh = (88.0, 72.0), (172.0, 72.0)
        current = _pose(self.mode, phase, sub_t)
        previous = _pose(self.mode, (phase - 1) % 3, 1.0)
        blend = min(1.0, sub_t / 0.12)
        blend = blend * blend * (3.0 - 2.0 * blend)
        l_el, l_wr, r_el, r_wr = tuple(_lerp_pt(a, b, blend) for a, b in zip(previous[:4], current[:4]))
        l_fist, r_fist = current[4:] if blend > 0.5 else previous[4:]

        # Draw limb segments with distinct cyan/sky colors (not diagnostic yellow)
        arm_pen = QPen(QColor("#7dd3fc"), 7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        for sh_pt, el_pt, wr_pt, is_fist in ((l_sh, l_el, l_wr, l_fist), (r_sh, r_el, r_wr, r_fist)):
            p.setPen(arm_pen)
            p.drawLine(QPointF(*sh_pt), QPointF(*el_pt))
            p.drawLine(QPointF(*el_pt), QPointF(*wr_pt))
            p.setPen(QPen(QColor("#e0f2fe"), 2))
            p.setBrush(QColor("#f59e0b") if is_fist else QColor("#38bdf8"))
            p.drawEllipse(QPointF(*wr_pt), 7 if is_fist else 9, 7 if is_fist else 9)

        # Draw mini spell visual preview on top of the mannequin
        if self.mode == "circle":
            cx, cy = _lerp_pt((130.0, 104.0), r_wr, min(1.0, sub_t * 2.0) if phase == 2 else 0.0)
            rad = (36.0 + 14.0 * wave) if phase == 1 else (48.0 if phase == 2 else 38.0)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(56, 189, 248, 210), 2.2))
            p.drawEllipse(QPointF(cx, cy), rad, rad)
            p.setPen(QPen(QColor(186, 230, 253, 160), 1.2, Qt.PenStyle.DashLine))
            p.drawEllipse(QPointF(cx, cy), rad * 0.72, rad * 0.72)
        elif self.mode == "blade":
            p.setBrush(Qt.BrushStyle.NoBrush)
            if phase == 0:
                p.setPen(QPen(QColor("#38bdf8"), 2.5))
                p.drawArc(QRectF(r_wr[0] - 18, r_wr[1] - 18, 36, 36), 30 * 16, 180 * 16)
            else:
                arc_pen = QPen(QColor("#e0f2fe"), 3.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
                p.setPen(arc_pen)
                p.drawLine(QPointF(102, 78 if phase == 1 else 108), QPointF(*r_wr))
        else:
            mw = abs(r_wr[0] - l_wr[0])
            if mw > 24:
                p.save()
                p.translate((l_wr[0] + r_wr[0]) / 2, (l_wr[1] + r_wr[1]) / 2)
                angle_deg = math.degrees(math.atan2(r_wr[1] - l_wr[1], r_wr[0] - l_wr[0]))
                p.rotate(angle_deg)
                p.setBrush(QColor(56, 189, 248, 45))
                p.setPen(QPen(QColor("#7dd3fc"), 2.0))
                p.drawRoundedRect(QRectF(-mw / 2, -mw * 0.34, mw, mw * 0.68), 4, 4)
                p.restore()

        p.restore()

        # Bottom concise tips
        p.setPen(QColor("#94a3b8"))
        p.setFont(QFont("Microsoft YaHei UI", 10))
        p.drawText(QRectF(16, 306, 248, 108), Qt.TextFlag.TextWordWrap, tips[self.mode])
        p.setFont(QFont("Microsoft YaHei UI", 9))
        p.setPen(QColor("#7dd3fc"))
        p.drawText(QRectF(16, 409, 248, 22), "青色为动作示范；黄线才是实际追踪")
        p.end()
