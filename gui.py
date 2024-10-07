# gui.py

import sys
import random
import math
from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsEllipseItem
from PyQt5.QtGui import QBrush
from PyQt5.QtCore import Qt

class VoiceChatGUI(QGraphicsView):
    def __init__(self, user_id, users_list):
        super().__init__()

        self.user_id = user_id

        # Set up the scene
        self.scene = QGraphicsScene()
        self.setScene(self.scene)

        # Rectangle area dimensions
        self.area_width = 800
        self.area_height = 600
        self.setFixedSize(self.area_width, self.area_height)

        # Add users
        self.users = {}  # Dictionary of user_id to QGraphicsEllipseItem
        for uid in users_list:
            is_self = (uid == self.user_id)
            self.add_user(uid, is_self=is_self)

    def add_user(self, user_id, is_self=False):
        # Random position
        x = random.randint(0, self.area_width - 20)
        y = random.randint(0, self.area_height - 20)

        # Create a circle to represent the user
        user_item = QGraphicsEllipseItem(0, 0, 20, 20)
        user_item.setBrush(QBrush(Qt.blue if not is_self else Qt.red))
        if is_self:
            user_item.setFlag(QGraphicsEllipseItem.ItemIsMovable, True)
            user_item.setFlag(QGraphicsEllipseItem.ItemIsSelectable, True)
        else:
            user_item.setFlag(QGraphicsEllipseItem.ItemIsMovable, False)
        user_item.setPos(x, y)

        self.scene.addItem(user_item)
        self.users[user_id] = user_item

    def calculate_proximity(self):
        self_pos = self.users[self.user_id].pos()
        volumes = {}
        for user_id, user_item in self.users.items():
            if user_id == self.user_id:
                continue
            other_pos = user_item.pos()
            dx = self_pos.x() - other_pos.x()
            dy = self_pos.y() - other_pos.y()
            distance = math.hypot(dx, dy)
            max_distance = math.hypot(self.area_width, self.area_height)
            volume = max(0.0, 1.0 - (distance / max_distance))
            volumes[user_id] = volume
        return volumes

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        volumes = self.calculate_proximity()
        # Update volumes in the client code if necessary
        if hasattr(self, 'on_volume_change'):
            self.on_volume_change(volumes)

    def get_volume_for_user(self, user_id):
        volumes = self.calculate_proximity()
        return volumes.get(user_id, 0.0)
