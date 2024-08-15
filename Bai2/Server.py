import socket
import os
import threading

HOST = '127.0.0.1'         # Server IP address
PORT = 8888                    # Server port
FILES_DIRECTORY = 'list'       # Directory containing files to send

def get_file_paths(directory):
    """Get a list of file paths in the specified directory."""
    file_paths = []
    for root, _, files in os.walk(directory):
        for file in files:
            file_path = os.path.relpath(os.path.join(root, file), FILES_DIRECTORY)
            file_paths.append(file_path.replace('\\', '/'))  # Convert to forward slashes for uniformity
    return file_paths

def send_files_list(client_socket):
    """Send the list of files available for download to the client."""
    file_paths = get_file_paths(FILES_DIRECTORY)
    files_data = ','.join(file_paths)
    client_socket.send(files_data.encode())

def send_file(client_socket, file_path):
    """Send the requested file to the client."""
    full_path = os.path.join(FILES_DIRECTORY, file_path)
    
    # Check if the file exists and is a regular file
    if os.path.exists(full_path) and os.path.isfile(full_path):
        try:
            # Notify client that file transfer is starting and send file size
            file_size = os.path.getsize(full_path)
            client_socket.send(b'begin')
            client_socket.send(str(file_size).encode())

            # Wait for client to acknowledge receipt of file size
            client_socket.recv(1024)

            # Send file data in chunks
            with open(full_path, 'rb') as file:
                while True:
                    file_data = file.read(2048)
                    if not file_data:
                        break
                    client_socket.sendall(file_data)
            
            # Notify client that file transfer is complete
            client_socket.send(b'end')

            # Receive response from client
            response = client_socket.recv(1024).decode()
            if response.lower() == 'success':
                print(f"File {file_path} successfully downloaded by client.")
            else:
                print(f"Client failed to download file {file_path}.")
        
        except IOError:
            print(f"Error reading or sending file {file_path}.")
        except Exception as e:
            print(f"Error sending {file_path}: {e}")

    else:
        print(f"File {file_path} does not exist on server.")

def handle_client_connection(client_socket):
    """Handle a single client connection."""
    try:
        send_files_list(client_socket)

        while True:
            file_path = client_socket.recv(1024).decode('utf-8').strip()
            if not file_path:
                break

            send_file(client_socket, file_path)
    except ConnectionResetError:
        print("Connection reset by client.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client_socket.close()

def main():
    """Main server function to accept and handle client connections."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.bind((HOST, PORT))
        server_socket.listen(5)  # Allow up to 5 clients to wait for connection
        print(f"Server is listening on {HOST}:{PORT}...")

        while True:
            client_socket, client_addr = server_socket.accept()
            print(f"Accepted connection from {client_addr}")

            # Start a new thread to handle the client connection
            client_thread = threading.Thread(target=handle_client_connection, args=(client_socket,))
            client_thread.start()

if __name__ == "__main__":
    main()
