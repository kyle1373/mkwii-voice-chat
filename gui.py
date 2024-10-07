# gui.py

import sys
import random
import math
from PyQt5.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsEllipseItem, QGraphicsTextItem,
    QPushButton, QWidget, QVBoxLayout, QHBoxLayout, QGraphicsItemGroup
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QGraphicsItem
from PyQt5.QtGui import QBrush, QFont

class UserGraphicsItem(QGraphicsItemGroup):
    def __init__(self, user_id, x, y, color, movable):
        super().__init__()
        self.user_id = user_id
        self.icon_item = QGraphicsEllipseItem(-10, -10, 20, 20)
        self.icon_item.setBrush(QBrush(color))
        self.addToGroup(self.icon_item)

        self.label_item = QGraphicsTextItem(user_id)
        self.label_item.setFont(QFont('Arial', 12))
        self.label_item.setPos(-self.label_item.boundingRect().width()/2, -30)
        self.addToGroup(self.label_item)

        if movable:
            self.setFlag(QGraphicsItem.ItemIsMovable, True)
            self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        else:
            self.setFlag(QGraphicsItem.ItemIsMovable, True)  # Allow moving blue dots

        self.setPos(x, y)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            # No need to do anything, the label moves with the group
            pass
        return super().itemChange(change, value)

class VoiceChatGUI(QGraphicsView):
    mute_state_changed = pyqtSignal(bool)
    deafen_state_changed = pyqtSignal(bool)

    def __init__(self, user_id):
        super().__init__()

        self.user_id = user_id

        # Set up the scene
        self.scene = QGraphicsScene()
        self.setScene(self.scene)

        # Rectangle area dimensions
        self.area_width = 800
        self.area_height = 600
        self.setFixedSize(self.area_width, self.area_height)

        # User items: user_id -> UserGraphicsItem
        self.users = {}

        # Mute and Deafen states
        self.is_muted = False
        self.is_deafened = False

        # UI Elements
        self.init_ui()

    def init_ui(self):
        # Mute and Deafen buttons
        self.mute_button = QPushButton("Mute")
        self.mute_button.setCheckable(True)
        self.mute_button.clicked.connect(self.toggle_mute)

        self.deafen_button = QPushButton("Deafen")
        self.deafen_button.setCheckable(True)
        self.deafen_button.clicked.connect(self.toggle_deafen)

        # Layout
        self.button_widget = QWidget()
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.mute_button)
        button_layout.addWidget(self.deafen_button)
        self.button_widget.setLayout(button_layout)
        self.button_widget.setGeometry(0, 0, 200, 50)
        self.scene.addWidget(self.button_widget)

    def toggle_mute(self):
        self.is_muted = self.mute_button.isChecked()
        self.mute_button.setText("Unmute" if self.is_muted else "Mute")
        if self.is_muted:
            self.mute_button.setStyleSheet("background-color: red")
        else:
            self.mute_button.setStyleSheet("")
        self.mute_state_changed.emit(self.is_muted)

    def toggle_deafen(self):
        self.is_deafened = self.deafen_button.isChecked()
        self.deafen_button.setText("Undeafen" if self.is_deafened else "Deafen")
        if self.is_deafened:
            self.deafen_button.setStyleSheet("background-color: red")
        else:
            self.deafen_button.setStyleSheet("")
        self.deafen_state_changed.emit(self.is_deafened)

    def add_user(self, user_id):
        if user_id in self.users:
            return

        # Random position
        x = random.randint(50, self.area_width - 70)
        y = random.randint(50, self.area_height - 70)

        color = Qt.red if user_id == self.user_id else Qt.blue
        movable = True  # Allow moving blue dots as well

        user_item = UserGraphicsItem(user_id, x, y, color, movable)
        self.scene.addItem(user_item)
        self.users[user_id] = user_item

    def remove_user(self, user_id):
        if user_id in self.users:
            user_item = self.users[user_id]
            self.scene.removeItem(user_item)
            del self.users[user_id]

    def update_user_list(self, user_list):
        existing_users = set(self.users.keys())
        new_users = set(user_list)

        # Add new users
        for user_id in new_users - existing_users:
            self.add_user(user_id)

        # Remove disconnected users
        for user_id in existing_users - new_users:
            self.remove_user(user_id)

    def calculate_proximity(self, hearing_range_factor=.0001):
        if self.user_id not in self.users:
            return {}

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

            # Scale the distance using the hearing_range_factor
            scaled_distance = distance / hearing_range_factor

            # Ensure that max_distance is also scaled accordingly
            scaled_max_distance = max_distance / hearing_range_factor

            # Calculate the volume, with a more rapid falloff based on scaled distance
            volume = max(0.0, 1.0 - (scaled_distance / scaled_max_distance))

            # Assign volume to the corresponding user_id
            volumes[user_id] = volume

        return volumes

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        volumes = self.calculate_proximity()
        # Update volumes in the client code if necessary
        if hasattr(self, 'on_volume_change'):
            self.on_volume_change(volumes)
