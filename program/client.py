# client.py

import sys
import threading
import socket
import pyaudio
import numpy
import signal
import json
from gui import VoiceChatGUI
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer, QObject, pyqtSignal

class VoiceChatClient(QObject):
    user_list_updated = pyqtSignal(list)

    def __init__(self, user_id, server_ip='127.0.0.1', server_port=8080):
        super().__init__()
        self.user_id = user_id
        self.server_ip = server_ip
        self.server_port = server_port

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.server_ip, self.server_port))

        self.audio = pyaudio.PyAudio()

        # Audio stream parameters
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = 44100
        self.chunk = 1024

        # Input stream for recording
        self.stream = self.audio.open(format=self.format,
                                      channels=self.channels,
                                      rate=self.rate,
                                      input=True,
                                      frames_per_buffer=self.chunk)

        # Output stream for playback
        self.play_stream = self.audio.open(format=self.format,
                                           channels=self.channels,
                                           rate=self.rate,
                                           output=True,
                                           frames_per_buffer=self.chunk)

        self.volumes = {}  # Volumes for each user

        self.running = True

        # Initialize mute/deafen state
        self.is_muted = False
        self.is_deafened = False
        self.state_lock = threading.Lock()

        # Start GUI
        self.app = QApplication(sys.argv)
        self.gui = VoiceChatGUI(self.user_id)
        self.gui.on_volume_change = self.on_volume_change

        # Connect GUI signals
        self.gui.mute_state_changed.connect(self.on_mute_state_changed)
        self.gui.deafen_state_changed.connect(self.on_deafen_state_changed)

        # Connect client signals
        self.user_list_updated.connect(self.gui.update_user_list)

        # Send user ID to server
        self.send_user_id()

        # Start threads
        threading.Thread(target=self.receive_data, daemon=True).start()
        threading.Thread(target=self.send_audio, daemon=True).start()

        # Set up a timer to periodically check for Ctrl+C (SIGINT)
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_signals)
        self.timer.start(100)  # Check every 100ms

        # Signal handling for Ctrl+C
        signal.signal(signal.SIGINT, self.handle_exit)

    def send_user_id(self):
        user_id_bytes = self.user_id.encode('utf-8')
        user_id_length = len(user_id_bytes)
        self.sock.sendall(user_id_length.to_bytes(4, 'big') + user_id_bytes)

    def check_signals(self):
        # This is called periodically to allow handling of Ctrl+C
        pass

    def on_volume_change(self, volumes):
        with self.state_lock:
            self.volumes.update(volumes)

    def on_mute_state_changed(self, is_muted):
        with self.state_lock:
            self.is_muted = is_muted

    def on_deafen_state_changed(self, is_deafened):
        with self.state_lock:
            self.is_deafened = is_deafened

    def send_audio(self):
        while self.running:
            try:
                with self.state_lock:
                    if self.is_muted:
                        continue
                data = self.stream.read(self.chunk, exception_on_overflow=False)
                # Prepare message
                user_id_bytes = self.user_id.encode('utf-8')
                user_id_bytes = user_id_bytes[:20]  # Max 20 bytes
                user_id_bytes = user_id_bytes.ljust(20, b'\0')  # Pad with null bytes
                message_body = user_id_bytes + data
                message_length = len(message_body)
                # Message type 1 for audio data
                message = b'\x01' + message_length.to_bytes(4, 'big') + message_body
                self.sock.sendall(message)
            except Exception as e:
                print(f"Send audio error: {e}")
                self.running = False
                break

    def recv_all(self, size):
        data = b''
        while len(data) < size:
            packet = self.sock.recv(size - len(data))
            if not packet:
                return None
            data += packet
        return data

    def receive_data(self):
        while self.running:
            try:
                # Read the message type
                message_type_bytes = self.recv_all(1)
                if not message_type_bytes:
                    break
                message_type = message_type_bytes[0]

                if message_type == 1:  # Audio data
                    # Read the message length
                    message_length_bytes = self.recv_all(4)
                    if not message_length_bytes:
                        break
                    message_length = int.from_bytes(message_length_bytes, 'big')
                    # Read the message body
                    message_body = self.recv_all(message_length)
                    if not message_body:
                        break
                    # Extract sender_id and audio data
                    user_id_bytes = message_body[:20]
                    sender_id = user_id_bytes.rstrip(b'\0').decode('utf-8')
                    audio_data = message_body[20:]

                    with self.state_lock:
                        is_deafened = self.is_deafened
                        volumes = self.volumes.copy()
                    if is_deafened:
                        continue  # Skip playback if deafened

                    volume = volumes.get(sender_id, 0.0)
                    print(volume)
                    adjusted_audio = self.adjust_volume(audio_data, volume)
                    self.play_stream.write(adjusted_audio)
                elif message_type == 3:  # User list update
                    # Read the message length
                    message_length_bytes = self.recv_all(4)
                    if not message_length_bytes:
                        break
                    message_length = int.from_bytes(message_length_bytes, 'big')
                    # Read the message body
                    message_body = self.recv_all(message_length)
                    if not message_body:
                        break
                    user_list = json.loads(message_body.decode('utf-8'))['users']
                    # Emit a signal to update the user list in the GUI
                    self.user_list_updated.emit(user_list)
            except Exception as e:
                print(f"Receive data error: {e}")
                self.running = False
                break

    def adjust_volume(self, audio_data, volume):
        # Simple volume adjustment
        audio_samples = numpy.frombuffer(audio_data, dtype=numpy.int16)
        adjusted_samples = (audio_samples * volume).astype(numpy.int16)
        return adjusted_samples.tobytes()

    def handle_exit(self, signum, frame):
        print("Exiting...")
        self.running = False
        self.cleanup()
        self.app.quit()  # Quit the PyQt application

    def cleanup(self):
        """Clean up resources when exiting."""
        try:
            self.sock.close()
            self.stream.stop_stream()
            self.stream.close()
            self.play_stream.stop_stream()
            self.play_stream.close()
            self.audio.terminate()
        except Exception as e:
            print(f"Error during cleanup: {e}")

    def run(self):
        self.gui.show()
        sys.exit(self.app.exec_())

if __name__ == '__main__':
    if len(sys.argv) > 1:
        user_id = sys.argv[1]
    else:
        user_id = 'User1'
    client = VoiceChatClient(user_id)
    client.run()
