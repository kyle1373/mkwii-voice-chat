import sys
import threading
import socket
import pyaudio
import numpy
import signal
from gui import VoiceChatGUI
from PyQt5.QtWidgets import QApplication

class VoiceChatClient:
    def __init__(self, user_id, server_ip='127.0.0.1', server_port=8080):
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

        # Start GUI
        self.app = QApplication(sys.argv)
        users_list = ['User1', 'User2', 'User3']  # For demo purposes
        if self.user_id not in users_list:
            users_list.append(self.user_id)
        self.gui = VoiceChatGUI(self.user_id, users_list)
        self.gui.on_volume_change = self.on_volume_change

        # Start threads
        threading.Thread(target=self.send_audio, daemon=True).start()
        threading.Thread(target=self.receive_audio, daemon=True).start()

        # Signal handling for Ctrl+C
        signal.signal(signal.SIGINT, self.handle_exit)

    def on_volume_change(self, volumes):
        self.volumes.update(volumes)

    def send_audio(self):
        while self.running:
            try:
                print("Sending audio")
                data = self.stream.read(self.chunk, exception_on_overflow=False)
                # Prepare message
                user_id_bytes = self.user_id.encode('utf-8')
                user_id_bytes = user_id_bytes[:20]  # Max 20 bytes
                user_id_bytes = user_id_bytes.ljust(20, b'\0')  # Pad with null bytes
                message_body = user_id_bytes + data
                message_length = len(message_body)
                # Pack the length as 4 bytes big-endian
                message = message_length.to_bytes(4, 'big') + message_body
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

    def receive_audio(self):
        while self.running:
            try:
                # Read the message length
                header = self.recv_all(4)
                if not header:
                    break
                message_length = int.from_bytes(header, 'big')
                # Read the message body
                message_body = self.recv_all(message_length)
                if not message_body:
                    break
                # Extract sender_id and audio data
                user_id_bytes = message_body[:20]
                sender_id = user_id_bytes.rstrip(b'\0').decode('utf-8')
                if sender_id == self.user_id:
                    continue  # Skip own audio
                audio_data = message_body[20:]
                volume = self.gui.get_volume_for_user(sender_id)
                adjusted_audio = self.adjust_volume(audio_data, volume)
                self.play_stream.write(adjusted_audio)
            except Exception as e:
                print(f"Receive audio error: {e}")
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
        sys.exit(0)

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
        try:
            sys.exit(self.app.exec_())
        except KeyboardInterrupt:
            print("Keyboard interrupt caught.")
            self.handle_exit(None, None)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        user_id = sys.argv[1]
    else:
        user_id = 'User1'
    client = VoiceChatClient(user_id)
    client.run()
