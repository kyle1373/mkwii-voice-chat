# server.py

import socket
import threading

class VoiceChatServer:
    def __init__(self, host='0.0.0.0', port=8080):
        self.clients = []
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind((host, port))
        self.sock.listen(5)
        print(f"Server started on {host}:{port}. Waiting for clients...")
        threading.Thread(target=self.accept_clients, daemon=True).start()

    def accept_clients(self):
        while True:
            conn, addr = self.sock.accept()
            self.clients.append(conn)
            print(f"Client connected from {addr}")
            threading.Thread(target=self.client_handler, args=(conn,), daemon=True).start()

    def client_handler(self, conn):
        while True:
            try:
                # Read the message length
                header = self.recv_all(conn, 4)
                if not header:
                    break
                message_length = int.from_bytes(header, 'big')
                # Read the message body
                message_body = self.recv_all(conn, message_length)
                if not message_body:
                    break
                # Broadcast the message to other clients
                self.broadcast(header + message_body, conn)
            except:
                break
        conn.close()
        self.clients.remove(conn)
        print(f"Client disconnected")

    def recv_all(self, conn, size):
        data = b''
        while len(data) < size:
            packet = conn.recv(size - len(data))
            if not packet:
                return None
            data += packet
        return data

    def broadcast(self, data, sender_conn):
        for client in self.clients:
            if client != sender_conn:
                try:
                    client.sendall(data)
                except:
                    pass

if __name__ == '__main__':
    server = VoiceChatServer()
    try:
        while True:
            pass  # Keep the main thread alive
    except KeyboardInterrupt:
        print("Server shutting down.")
