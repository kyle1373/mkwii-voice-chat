# server.py

import socket
import threading
import json

class VoiceChatServer:
    def __init__(self, host='0.0.0.0', port=8080):
        self.clients = {}  # Maps connection to user_id
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind((host, port))
        self.sock.listen(5)
        print(f"Server started on {host}:{port}. Waiting for clients...")
        threading.Thread(target=self.accept_clients, daemon=True).start()

    def accept_clients(self):
        while True:
            conn, addr = self.sock.accept()
            threading.Thread(target=self.client_handler, args=(conn,), daemon=True).start()

    def client_handler(self, conn):
        try:
            # Receive user ID from the client
            user_id_length_bytes = self.recv_all(conn, 4)
            if not user_id_length_bytes:
                conn.close()
                return
            user_id_length = int.from_bytes(user_id_length_bytes, 'big')
            user_id_bytes = self.recv_all(conn, user_id_length)
            if not user_id_bytes:
                conn.close()
                return
            user_id = user_id_bytes.decode('utf-8')
            self.clients[conn] = user_id
            print(f"User '{user_id}' connected.")
            self.broadcast_user_list()

            while True:
                # Read the message type
                message_type_bytes = self.recv_all(conn, 1)
                if not message_type_bytes:
                    break
                message_type = message_type_bytes[0]

                if message_type == 1:  # Audio data
                    # Read the message length
                    message_length_bytes = self.recv_all(conn, 4)
                    if not message_length_bytes:
                        break
                    message_length = int.from_bytes(message_length_bytes, 'big')
                    # Read the message body
                    message_body = self.recv_all(conn, message_length)
                    if not message_body:
                        break
                    # Broadcast the audio data to other clients
                    self.broadcast_audio(message_type_bytes + message_length_bytes + message_body, conn)
                elif message_type == 2:  # Control messages (e.g., mute, deafen)
                    # Handle control messages if needed
                    pass
        except Exception as e:
            print(f"Error: {e}")
        finally:
            user_id = self.clients.get(conn, 'Unknown')
            print(f"User '{user_id}' disconnected.")
            conn.close()
            del self.clients[conn]
            self.broadcast_user_list()

    def recv_all(self, conn, size):
        data = b''
        while len(data) < size:
            packet = conn.recv(size - len(data))
            if not packet:
                return None
            data += packet
        return data

    def broadcast_audio(self, data, sender_conn):
        for client_conn in self.clients.keys():
            if client_conn != sender_conn:
                try:
                    client_conn.sendall(data)
                except:
                    pass

    def broadcast_user_list(self):
        user_list = list(self.clients.values())
        message_body = json.dumps({'users': user_list}).encode('utf-8')
        message_length = len(message_body)
        message = b'\x03' + message_length.to_bytes(4, 'big') + message_body  # Message type 3 for user list
        for client_conn in self.clients.keys():
            try:
                client_conn.sendall(message)
            except:
                pass

if __name__ == '__main__':
    server = VoiceChatServer()
    try:
        while True:
            pass  # Keep the main thread alive
    except KeyboardInterrupt:
        print("Server shutting down.")
