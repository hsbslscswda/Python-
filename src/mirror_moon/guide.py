"""Classical Greco-Roman / Hermetic Astrolabe Grimoire Pose Coach."""

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
        self.setFixedWidth(290)
        self.setMinimumHeight(440)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Classical Roman Grimoire / Astrolabe Tablet Background
        rect = self.rect().adjusted(3, 3, -3, -3)
        grad = QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0.0, QColor("#1e1815"))
        grad.setColorAt(0.5, QColor("#151110"))
        grad.setColorAt(1.0, QColor("#0e0b0a"))
        p.setBrush(QBrush(grad))
        p.setPen(QPen(QColor("#b8924a"), 2.0))
        p.drawRoundedRect(rect, 6, 6)

        # Inner ornate double brass frame
        inner = rect.adjusted(5, 5, -5, -5)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(184, 146, 74, 110), 1.0))
        p.drawRoundedRect(inner, 4, 4)

        elapsed = time.perf_counter() - self.started
        cycle_dur = 2.6
        phase = int(elapsed / cycle_dur) % 3
        sub_t = (elapsed % cycle_dur) / cycle_dur
        wave = 0.5 - 0.5 * math.cos(sub_t * math.tau)

        titles = {
            "circle": ("Ⅰ · 胸前握拳唤阵", "Ⅱ · 伸臂导引星流", "Ⅲ · 双手共鸣过载"),
            "blade": ("Ⅰ · 收手蓄势", "Ⅱ · 破空挥斩", "Ⅲ · 回锋十字"),
            "mirror": ("Ⅰ · 胸前合手凝镜", "Ⅱ · 展臂旋天控镜", "Ⅲ · 折镜万象与崩碎"),
        }
        subtitles = {
            "circle": (
                "任意一手握拳置于胸前片刻，展开古星盘法阵",
                "另一手张开前伸增强能量、收回减弱；握拳暂停输出",
                "将召唤手搭在施法手腕或前臂上（伸直或弯曲皆可），触发过载",
            ),
            "blade": (
                "将施法手收至对侧肩前停留蓄势",
                "向身体外侧快速挥斩释放月刃",
                "稍停后反向挥回触发连斩",
            ),
            "mirror": (
                "双手在胸前靠近停留片刻，唤出太虚镜缝",
                "向两侧拉开双手展开古镜，上下倾斜双臂可 360° 旋转镜界",
                "旋转镜面开启万花筒；向内快合双手触发碎镜定格",
            ),
        }
        tips = {
            "circle": "✦ 只要施法手不放下，移动身体不会中断施法\n✦ 金色星盘为法阵本体，青/紫光流为释放魔力\n✦ 放下施法手即可收阵归隐",
            "blade": "✦ 挥刀动作连贯即可\n✦ 切换法术时请先自然垂手半秒",
            "mirror": "✦ 双臂一上一下大角度旋转也不会中断\n✦ 自由缩放不关镜；合拢停住 0.3 秒平静收镜",
        }

        # Roman Chapter Banner
        p.setPen(QPen(QColor("#c8a256"), 1.2))
        p.setBrush(QColor("#2a2019"))
        p.drawRoundedRect(QRectF(16, 16, 258, 30), 4, 4)
        p.setPen(QColor("#f3dfb2"))
        p.setFont(QFont("Georgia", 11, QFont.Weight.Bold))
        p.drawText(QRectF(24, 16, 242, 30), Qt.AlignmentFlag.AlignVCenter, titles[self.mode][phase])

        # Step description in warm parchment ivory
        p.setPen(QColor("#e8dcc4"))
        p.setFont(QFont("Microsoft YaHei UI", 10, QFont.Weight.Medium))
        p.drawText(QRectF(18, 52, 254, 54), Qt.TextFlag.TextWordWrap, subtitles[self.mode][phase])

        # Astrolabe Stage Viewport
        p.save()
        p.translate(15, 108)
        p.setBrush(QColor("#0d0b0e"))
        p.setPen(QPen(QColor("#6e552c"), 1.5))
        p.drawRoundedRect(QRectF(0, 0, 260, 196), 6, 6)

        # Subtle background astrolabe meridian rings
        p.setPen(QPen(QColor(184, 146, 74, 38), 1.0, Qt.PenStyle.DotLine))
        p.drawEllipse(QPointF(130, 98), 78, 78)
        p.drawLine(QPointF(130, 10), QPointF(130, 186))
        p.drawLine(QPointF(20, 98), QPointF(240, 98))

        # Classical bust / robed caster silhouette
        torso_path = QPainterPath()
        torso_path.moveTo(85, 68)
        torso_path.quadTo(130, 60, 175, 68)
        torso_path.lineTo(164, 168)
        torso_path.quadTo(130, 175, 96, 168)
        torso_path.closeSubpath()
        p.setBrush(QColor(62, 48, 36, 165))
        p.setPen(QPen(QColor("#c8a256"), 1.8))
        p.drawPath(torso_path)

        # Head
        p.setBrush(QColor(62, 48, 36, 190))
        p.drawEllipse(QPointF(130, 34), 18, 21)

        l_sh, r_sh = (88.0, 72.0), (172.0, 72.0)
        current = _pose(self.mode, phase, sub_t)
        previous = _pose(self.mode, (phase - 1) % 3, 1.0)
        blend = min(1.0, sub_t / 0.12)
        blend = blend * blend * (3.0 - 2.0 * blend)
        l_el, l_wr, r_el, r_wr = tuple(_lerp_pt(a, b, blend) for a, b in zip(previous[:4], current[:4]))
        l_fist, r_fist = current[4:] if blend > 0.5 else previous[4:]

        arm_pen = QPen(QColor("#e2c07d"), 6.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        for sh_pt, el_pt, wr_pt, is_fist in ((l_sh, l_el, l_wr, l_fist), (r_sh, r_el, r_wr, r_fist)):
            p.setPen(arm_pen)
            p.drawLine(QPointF(*sh_pt), QPointF(*el_pt))
            p.drawLine(QPointF(*el_pt), QPointF(*wr_pt))
            p.setPen(QPen(QColor("#fff3d1"), 1.8))
            p.setBrush(QColor("#d97706") if is_fist else QColor("#38bdf8"))
            p.drawEllipse(QPointF(*wr_pt), 7 if is_fist else 9, 7 if is_fist else 9)

        # Spell preview overlay
        if self.mode == "circle":
            cx, cy = _lerp_pt((130.0, 104.0), r_wr, min(1.0, sub_t * 2.0) if phase == 2 else 0.0)
            rad = (36.0 + 14.0 * wave) if phase == 1 else (50.0 if phase == 2 else 38.0)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(234, 179, 8, 220), 2.2))
            p.drawEllipse(QPointF(cx, cy), rad, rad)
            p.setPen(QPen(QColor(56, 189, 248, 200), 1.8, Qt.PenStyle.DashLine))
            p.drawEllipse(QPointF(cx, cy), rad * 0.72, rad * 0.72)
        elif self.mode == "mirror":
            mw = math.hypot(r_wr[0] - l_wr[0], r_wr[1] - l_wr[1])
            if mw > 24:
                p.save()
                p.translate((l_wr[0] + r_wr[0]) / 2, (l_wr[1] + r_wr[1]) / 2)
                angle_deg = math.degrees(math.atan2(r_wr[1] - l_wr[1], r_wr[0] - l_wr[0]))
                p.rotate(angle_deg)
                p.setBrush(QColor(56, 189, 248, 45))
                p.setPen(QPen(QColor("#eab308"), 2.2))
                p.drawRoundedRect(QRectF(-mw / 2, -mw * 0.34, mw, mw * 0.68), 4, 4)
                p.restore()

        p.restore()

        # Grimoire footnotes
        p.setPen(QColor("#c7b698"))
        p.setFont(QFont("Microsoft YaHei UI", 9))
        p.drawText(QRectF(18, 312, 254, 92), Qt.TextFlag.TextWordWrap, tips[self.mode])
        p.setFont(QFont("Microsoft YaHei UI", 9))
        p.setPen(QColor("#d4af37"))
        p.drawText(QRectF(18, 408, 254, 22), "✦ 鎏金人像为法典示范 · 镜中为实景舞台")
        p.end()
