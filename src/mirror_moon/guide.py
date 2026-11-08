"""Custom QPainter Filigree & Astrolabe Engraving Engine for PoseGuide and Ornamental UI Panels."""

import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QWidget


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _lerp_pt(p1: tuple[float, float], p2: tuple[float, float], t: float) -> tuple[float, float]:
    return (_lerp(p1[0], p2[0], t), _lerp(p1[1], p2[1], t))


def draw_filigree_corner(p: QPainter, x: float, y: float, dx: float, dy: float, size: float, color: QColor):
    """Draws an intricate European classical acanthus/astrolabe corner ornament at (x, y) oriented by (dx, dy)."""
    p.save()
    p.translate(x, y)
    p.scale(dx, dy)
    pen_main = QPen(color, 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    pen_fine = QPen(QColor(color.red(), color.green(), color.blue(), int(color.alpha() * 0.65)), 0.95)

    # Outer & inner stepped corner brackets + Baroque scroll curves
    path = QPainterPath()
    path.moveTo(0, size * 1.15)
    path.lineTo(0, 6)
    path.quadTo(0, 0, 6, 0)
    path.lineTo(size * 1.15, 0)

    path.moveTo(4.5, size * 0.85)
    path.lineTo(4.5, 9.5)
    path.quadTo(4.5, 4.5, 9.5, 4.5)
    path.lineTo(size * 0.85, 4.5)

    # Double Acanthus S-scroll spirals
    path.moveTo(4.5, size * 0.58)
    path.cubicTo(size * 0.36, size * 0.56, size * 0.42, size * 0.25, size * 0.20, size * 0.20)
    path.moveTo(size * 0.58, 4.5)
    path.cubicTo(size * 0.56, size * 0.36, size * 0.25, size * 0.42, size * 0.20, size * 0.20)

    # Secondary outer leaf curl
    path.moveTo(0, size * 0.72)
    path.quadTo(size * 0.24, size * 0.68, size * 0.26, size * 0.45)
    path.moveTo(size * 0.72, 0)
    path.quadTo(size * 0.68, size * 0.24, size * 0.45, size * 0.26)

    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(pen_main)
    p.drawPath(path)

    # Corner astrolabe sun-diamond & quarter-ring
    p.setPen(pen_fine)
    p.drawArc(QRectF(-size * 0.38, -size * 0.38, size * 0.76, size * 0.76), 270 * 16, 90 * 16)
    p.drawArc(QRectF(-size * 0.52, -size * 0.52, size * 1.04, size * 1.04), 270 * 16, 90 * 16)
    diamond = QPainterPath()
    d = 4.4
    cx, cy = 9.0, 9.0
    diamond.moveTo(cx, cy - d)
    diamond.lineTo(cx + d, cy)
    diamond.lineTo(cx, cy + d)
    diamond.lineTo(cx - d, cy)
    diamond.closeSubpath()
    p.setBrush(color)
    p.drawPath(diamond)
    p.restore()


def draw_edge_medallion(p: QPainter, cx: float, cy: float, horizontal: bool, span: float, color: QColor):
    """Draws a classical central crest / astrolabe cartouche along a panel edge."""
    p.save()
    p.translate(cx, cy)
    if not horizontal:
        p.rotate(90)
    pen = QPen(color, 1.15)
    p.setPen(pen)
    p.setBrush(QColor(16, 14, 26, 230))
    # Central diamond + flanking scrolls
    cartouche = QPainterPath()
    cartouche.moveTo(-span * 0.5, 0)
    cartouche.quadTo(-span * 0.25, -4.5, -6.0, 0)
    cartouche.lineTo(0, -5.0)
    cartouche.lineTo(6.0, 0)
    cartouche.quadTo(span * 0.25, -4.5, span * 0.5, 0)
    cartouche.quadTo(span * 0.25, 4.5, 6.0, 0)
    cartouche.lineTo(0, 5.0)
    cartouche.lineTo(-6.0, 0)
    cartouche.quadTo(-span * 0.25, 4.5, -span * 0.5, 0)
    p.drawPath(cartouche)
    p.setBrush(color)
    p.drawEllipse(QPointF(0, 0), 2.2, 2.2)
    p.restore()


def draw_engraved_tablet(
    p: QPainter,
    rect: QRectF,
    bg_top: str = "#13111c",
    bg_mid: str = "#0d0b14",
    bg_bot: str = "#09070e",
    corner_size: float = 22.0,
    with_celestial_watermark: bool = False,
    phase_angle: float = 0.0,
):
    """Renders a dark midnight-velvet tablet with brushed silver-champagne double borders, corner filigree, and edge crests."""
    r = rect.adjusted(2, 2, -2, -2)
    grad = QLinearGradient(r.left(), r.top(), r.left(), r.bottom())
    grad.setColorAt(0.0, QColor(bg_top))
    grad.setColorAt(0.5, QColor(bg_mid))
    grad.setColorAt(1.0, QColor(bg_bot))
    p.setBrush(QBrush(grad))
    p.setPen(QPen(QColor(198, 180, 142, 175), 1.4))
    p.drawRoundedRect(r, 6, 6)

    # Inner hairline border with guilloche micro-dots at intervals
    inner = r.adjusted(4.5, 4.5, -4.5, -4.5)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor(148, 163, 184, 72), 0.95))
    p.drawRoundedRect(inner, 4, 4)

    if with_celestial_watermark:
        p.save()
        p.setClipRect(inner)
        cx, cy = r.center().x(), r.center().y()
        rad = min(r.width(), r.height()) * 0.45
        p.setPen(QPen(QColor(198, 180, 142, 28), 0.9))
        p.drawEllipse(QPointF(cx, cy), rad, rad)
        p.drawEllipse(QPointF(cx, cy), rad * 0.78, rad * 0.78)
        p.drawEllipse(QPointF(cx, cy), rad * 0.52, rad * 0.52)
        for i in range(12):
            ang = i * math.pi / 6.0 + phase_angle * 0.15
            p.drawLine(
                QPointF(cx + rad * 0.52 * math.cos(ang), cy + rad * 0.52 * math.sin(ang)),
                QPointF(cx + rad * math.cos(ang), cy + rad * math.sin(ang)),
            )
        p.restore()

    filigree_col = QColor(214, 195, 156, 215)
    draw_filigree_corner(p, r.left() + 2, r.top() + 2, 1, 1, corner_size, filigree_col)
    draw_filigree_corner(p, r.right() - 2, r.top() + 2, -1, 1, corner_size, filigree_col)
    draw_filigree_corner(p, r.left() + 2, r.bottom() - 2, 1, -1, corner_size, filigree_col)
    draw_filigree_corner(p, r.right() - 2, r.bottom() - 2, -1, -1, corner_size, filigree_col)

    if r.width() > 220:
        crest_col = QColor(198, 180, 142, 155)
        draw_edge_medallion(p, r.center().x(), r.top() + 2.2, True, 36.0, crest_col)
        draw_edge_medallion(p, r.center().x(), r.bottom() - 2.2, True, 36.0, crest_col)
    if r.height() > 260:
        crest_col = QColor(198, 180, 142, 145)
        draw_edge_medallion(p, r.left() + 2.2, r.center().y(), False, 34.0, crest_col)
        draw_edge_medallion(p, r.right() - 2.2, r.center().y(), False, 34.0, crest_col)


class FiligreePanel(QFrame):
    """Reusable QFrame with custom-painted European classical astrolabe filigree borders & corners."""

    def __init__(self, corner_size: float = 18.0, watermark: bool = False, parent=None):
        super().__init__(parent)
        self.corner_size = corner_size
        self.watermark = watermark

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        draw_engraved_tablet(
            p,
            QRectF(self.rect()),
            corner_size=self.corner_size,
            with_celestial_watermark=self.watermark,
        )
        p.end()


def _pose(mode, phase, sub_t):
    mode = "mirror" if mode == "water" else "circle" if mode == "fire" else mode
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


def _draw_mini_astrolabe(p: QPainter, cx: float, cy: float, rad: float, t: float):
    """Draws an intricate miniature multi-ring astrolabe on the PoseGuide canvas."""
    p.save()
    p.translate(cx, cy)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor(214, 195, 156, 220), 1.6))
    p.drawEllipse(QPointF(0, 0), rad, rad)
    p.setPen(QPen(QColor(125, 211, 252, 195), 1.15))
    p.drawEllipse(QPointF(0, 0), rad * 0.84, rad * 0.84)
    p.drawEllipse(QPointF(0, 0), rad * 0.56, rad * 0.56)

    # 12-pointed dodecagram star & cardinal moon crescents
    for k in range(4):
        ang0 = k * math.pi / 6.0 + t * 0.4
        poly = QPainterPath()
        for i in range(4):
            a = ang0 + i * math.tau / 3.0
            pt = QPointF(rad * 0.82 * math.cos(a), rad * 0.82 * math.sin(a))
            if i == 0:
                poly.moveTo(pt)
            else:
                poly.lineTo(pt)
        p.setPen(QPen(QColor(186, 230, 253, 165), 0.95))
        p.drawPath(poly)

    for m in range(8):
        ma = m * math.pi / 4.0 - t * 0.3
        p.setPen(QPen(QColor(214, 195, 156, 185), 1.1))
        p.drawEllipse(QPointF(rad * 0.68 * math.cos(ma), rad * 0.68 * math.sin(ma)), 3.2, 3.2)
    p.restore()


class PoseGuide(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.mode = "circle"
        self.started = time.perf_counter()
        self.setFixedWidth(296)
        self.setMinimumHeight(445)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        elapsed = time.perf_counter() - self.started
        draw_engraved_tablet(
            p,
            QRectF(self.rect()),
            bg_top="#141220",
            bg_mid="#0d0b16",
            bg_bot="#08070d",
            corner_size=24.0,
            with_celestial_watermark=True,
            phase_angle=elapsed,
        )

        cycle_dur = 2.6
        phase = int(elapsed / cycle_dur) % 3
        sub_t = (elapsed % cycle_dur) / cycle_dur
        wave = 0.5 - 0.5 * math.cos(sub_t * math.tau)

        titles = {
            "circle": ("Ⅰ · 胸前握拳唤阵", "Ⅱ · 伸臂轰出冰棱寒雾", "Ⅲ · 双掌共鸣暴风雪"),
            "blade": ("Ⅰ · 收手蓄势", "Ⅱ · 破空挥斩", "Ⅲ · 回锋十字"),
            "mirror": ("Ⅰ · 胸前合手凝镜", "Ⅱ · 展臂旋天控镜", "Ⅲ · 折镜万象与崩碎"),
        }
        titles.update(
            water=("握拳后摊开召唤", "双手夹住并拉大", "搭腕发射，拍掌结束"),
            fire=("张开后握拳2秒", "张开掌心点火", "翻掌或握拳熄灭"),
        )
        subtitles = {
            "circle": (
                "任意一手握拳置于胸前片刻，展开冰魄奥术法阵",
                "另一手张开前伸释放极寒冰雾与破空冰枪；握拳暂停输出",
                "副手搭在施法腕/前臂上，或将副手同样张开抬起（双掌无遮挡共鸣），触发过载",
            ),
            "blade": (
                "将施法手收至对侧肩前停留蓄势",
                "向身体外侧快速挥斩释放月刃",
                "稍停后反向挥回触发连斩",
            ),
            "mirror": (
                "双手在胸前靠近停留片刻，唤出太虚镜缝",
                "向两侧拉开双手展开魔镜，上下倾斜双臂可 360° 旋转镜界",
                "旋转镜面开启万花筒；向内快合双手触发碎镜定格",
            ),
        }
        subtitles.update(
            water=(
                "任意角度握拳再摊开，水球悬浮掌上；无需身体入画",
                "双掌夹住水球，拉开可变大。移动时有惯性",
                "搭腕/握拳发射；冷却后重新握拳再摊开召唤，拍掌或双臂向下出画收起",
            ),
            fire=(
                "先张开，再握拳满2秒解锁该手",
                "再次张开点火，左右手可各有一团火焰",
                "握拳时火焰收缩熄灭；翻掌朝下熄灭，张开可重燃",
            ),
        )
        tips = {
            "circle": "✦ 只要施法手不放下，移动身体不会中断冰魔法\n✦ 金青奥术法阵正对躯干，释放翻涌冰雾与破空冰棱\n✦ 放下施法手即可收阵归隐",
            "blade": "✦ 挥刀动作连贯即可\n✦ 切换法术时请先自然垂手半秒",
            "mirror": "✦ 双臂一上一下大角度旋转也不会中断\n✦ 自由缩放不关镜；合拢停住 0.3 秒平静收镜",
        }

        tips.update(
            water="水球持续保留，丢手不会消失。\n坐着可用；掌前距离与人物碰撞为单目近似。",
            fire="只需识别手，不需要肩膀和站姿。\n短时掉点保持位置，不会被当作握拳。",
        )

        # Engraved Chapter Ribbon
        p.setPen(QPen(QColor(214, 195, 156, 165), 1.15))
        p.setBrush(QColor(28, 25, 44, 215))
        p.drawRoundedRect(QRectF(18, 16, 260, 30), 4, 4)
        p.setPen(QColor("#f1e6d0"))
        p.setFont(QFont("Georgia", 11, QFont.Weight.Bold))
        p.drawText(QRectF(26, 16, 244, 30), Qt.AlignmentFlag.AlignVCenter, titles[self.mode][phase])

        # Step description
        p.setPen(QColor("#cbd5e1"))
        p.setFont(QFont("Microsoft YaHei UI", 10))
        p.drawText(QRectF(20, 52, 256, 52), Qt.TextFlag.TextWordWrap, subtitles[self.mode][phase])

        # Inner Astrolabe Stage Viewport
        p.save()
        p.translate(18, 106)
        p.setBrush(QColor(9, 8, 16, 235))
        p.setPen(QPen(QColor(198, 180, 142, 135), 1.2))
        p.drawRoundedRect(QRectF(0, 0, 260, 196), 6, 6)

        # Intricate celestial armillary background inside the stage
        p.setPen(QPen(QColor(148, 163, 184, 36), 0.9))
        p.drawEllipse(QPointF(130, 98), 82, 82)
        p.drawEllipse(QPointF(130, 98), 62, 62)
        p.drawEllipse(QPointF(130, 98), 82, 34)
        p.drawEllipse(QPointF(130, 98), 34, 82)

        # Ethereal caster bust silhouette
        torso_path = QPainterPath()
        torso_path.moveTo(85, 68)
        torso_path.quadTo(130, 60, 175, 68)
        torso_path.lineTo(164, 168)
        torso_path.quadTo(130, 175, 96, 168)
        torso_path.closeSubpath()
        p.setBrush(QColor(30, 36, 58, 165))
        p.setPen(QPen(QColor(198, 180, 142, 175), 1.5))
        p.drawPath(torso_path)

        p.setBrush(QColor(30, 36, 58, 190))
        p.drawEllipse(QPointF(130, 34), 18, 21)

        l_sh, r_sh = (88.0, 72.0), (172.0, 72.0)
        current = _pose(self.mode, phase, sub_t)
        previous = _pose(self.mode, (phase - 1) % 3, 1.0)
        blend = min(1.0, sub_t / 0.12)
        blend = blend * blend * (3.0 - 2.0 * blend)
        l_el, l_wr, r_el, r_wr = tuple(_lerp_pt(a, b, blend) for a, b in zip(previous[:4], current[:4]))
        l_fist, r_fist = current[4:] if blend > 0.5 else previous[4:]

        arm_pen = QPen(QColor("#cbd5e1"), 6.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        for sh_pt, el_pt, wr_pt, is_fist in ((l_sh, l_el, l_wr, l_fist), (r_sh, r_el, r_wr, r_fist)):
            p.setPen(arm_pen)
            p.drawLine(QPointF(*sh_pt), QPointF(*el_pt))
            p.drawLine(QPointF(*el_pt), QPointF(*wr_pt))
            p.setPen(QPen(QColor("#f8fafc"), 1.6))
            p.setBrush(QColor("#e2c07d") if is_fist else QColor("#38bdf8"))
            p.drawEllipse(QPointF(*wr_pt), 7 if is_fist else 9, 7 if is_fist else 9)

        if self.mode == "circle":
            cx, cy = _lerp_pt((130.0, 104.0), r_wr, min(1.0, sub_t * 2.0) if phase == 2 else 0.0)
            rad = (38.0 + 14.0 * wave) if phase == 1 else (50.0 if phase == 2 else 40.0)
            _draw_mini_astrolabe(p, cx, cy, rad, elapsed)
        elif self.mode == "water":
            p.setBrush(QColor(25, 130, 200, 145))
            p.setPen(QPen(QColor("#80d4ec"), 2))
            p.drawEllipse(QPointF(r_wr[0], r_wr[1] - 28), 22 + wave * 8, 23)
        elif self.mode == "fire":
            p.setBrush(QColor(255, 105, 20, 200))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(r_wr[0], r_wr[1] - 28), 12, 25 + wave * 10)
        elif self.mode == "mirror":
            mw = math.hypot(r_wr[0] - l_wr[0], r_wr[1] - l_wr[1])
            if mw > 24:
                p.save()
                p.translate((l_wr[0] + r_wr[0]) / 2, (l_wr[1] + r_wr[1]) / 2)
                angle_deg = math.degrees(math.atan2(r_wr[1] - l_wr[1], r_wr[0] - l_wr[0]))
                p.rotate(angle_deg)
                p.setBrush(QColor(56, 189, 248, 45))
                p.setPen(QPen(QColor(214, 195, 156, 220), 2.0))
                p.drawRoundedRect(QRectF(-mw / 2, -mw * 0.34, mw, mw * 0.68), 4, 4)
                p.restore()

        p.restore()

        p.setPen(QColor("#94a3b8"))
        p.setFont(QFont("Microsoft YaHei UI", 9))
        p.drawText(QRectF(20, 310, 256, 92), Qt.TextFlag.TextWordWrap, tips[self.mode])
        p.setFont(QFont("Georgia", 9, QFont.Weight.Bold))
        p.setPen(QColor("#d6c39c"))
        p.drawText(QRectF(20, 408, 256, 22), "✦ 星盘人像为法典示范 · 镜中为实景舞台")
        p.end()
