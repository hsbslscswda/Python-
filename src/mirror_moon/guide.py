"""Small animated pose guide. Demonstration only, separate from observed yellow skeleton."""

import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget


class PoseGuide(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.mode = "circle"
        self.started = time.perf_counter()
        self.setFixedWidth(260)
        self.setMinimumHeight(360)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#101f2c"))
        phase = int((time.perf_counter() - self.started) / 3.0) % 3
        titles = {
            "circle": ("① 一手松握拳，放在胸前", "② 另一手张开，朝前弯伸", "③ 召唤手搭住施法前臂"),
            "blade": ("① 手收到另一侧肩膀前", "② 停一下，再快速向外挥", "③ 出刃后，反向挥可连斩"),
            "mirror": ("① 双手开掌，胸前靠近", "② 向两边拉开，展开镜面", "③ 慢合关闭，快合碎镜"),
        }
        notes = {
            "circle": "手肘角度不限。\n施法后召唤手可自由活动。\n握拳停法；放下施法手收阵。\n搭臂增强可超过100%。",
            "blade": "可用任意一只手。\n先收手停留，再向外挥。\n提示“已蓄势”还没有出刃。",
            "mirror": "先开掌靠近，稍停后再拉开。\n碎镜只需快速合到一拳距离，\n不必拍掌，也不必双手重叠。",
        }
        p.setPen(QColor("#d9e8ef"))
        p.setFont(QFont("Microsoft YaHei UI", 12, QFont.Weight.Bold))
        p.drawText(QRectF(14, 12, 232, 32), "动作示范 · 自动轮播")
        p.setFont(QFont("Microsoft YaHei UI", 11))
        p.drawText(QRectF(14, 44, 232, 52), Qt.TextFlag.TextWordWrap, titles[self.mode][phase])
        p.save()
        p.translate(0, 88)
        p.setPen(QPen(QColor("#f2cd65"), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(130, 33), 20, 20)
        body = [
            ((130, 54), (130, 150)),
            ((80, 78), (180, 78)),
            ((130, 150), (98, 205)),
            ((130, 150), (163, 205)),
        ]
        left = [(80, 78), (62, 118), (122, 110)]
        right = [(180, 78), (198, 125), (208, 175)]
        if self.mode == "circle":
            if phase >= 1:
                right = [(180, 78), (205, 100), (220, 60)]
            if phase == 2:
                left = [(80, 78), (124, 125), (213, 83)]
        elif self.mode == "blade":
            right = [(180, 78), (153, 125), (85, 78)] if phase == 0 else [(180, 78), (210, 85), (242, 55)]
            if phase == 2:
                right = [(180, 78), (145, 115), (85, 95)]
            left = [(80, 78), (62, 135), (60, 175)]
        else:
            gap = 15 if phase == 0 else 83 if phase == 1 else 45 + 28 * math.sin(time.perf_counter() * 2)
            left = [(80, 78), (65, 118), (130 - gap, 112)]
            right = [(180, 78), (195, 118), (130 + gap, 112)]
        for chain in (left, right):
            body += list(zip(chain, chain[1:]))
        for a, b in body:
            p.drawLine(QPointF(*a), QPointF(*b))
        for index, chain in enumerate((left, right)):
            x, y = chain[-1]
            fist = self.mode == "circle" and index == 0
            p.setBrush(QColor("#f2cd65") if fist else QColor("#101f2c"))
            p.drawEllipse(QPointF(x, y), 8 if fist else 12, 8 if fist else 12)
        p.restore()
        p.setPen(QColor("#d9e8ef"))
        p.setFont(QFont("Microsoft YaHei UI", 10))
        p.drawText(
            QRectF(14, 307, 232, max(110, self.height() - 330)), Qt.TextFlag.TextWordWrap, notes[self.mode]
        )
        p.end()
