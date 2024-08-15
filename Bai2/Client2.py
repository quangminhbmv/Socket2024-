import socket
import os
import time
import zipfile
import threading
from collections import deque

HOST = '127.0.0.1'         # Server IP address
PORT = 8888                    # Server port
OUTPUT_FOLDER = 'output2'      # Directory to store downloaded files
INPUT_FILE = 'input2.txt'       # File containing list of downloaded files and priorities

# Define priority delays
PRIORITY_DELAYS = {
    'CRITICAL': 1,   # High priority: Retry delay in seconds
    'HIGH': 4,       # Medium priority: Retry delay in seconds
    'NORMAL': 10     # Normal priority: Retry delay in seconds
}

def parse_input_file():
    """Parse the input file to get file paths and priorities."""
    files = []
    if os.path.exists(INPUT_FILE):
        with open(INPUT_FILE, 'r') as file:
            for line in file:
                parts = line.strip().split(maxsplit=1)  # Split on first space only
                if len(parts) == 2:
                    file_path, priority = parts
                    priority = priority.upper()  # Convert priority to uppercase
                    if priority in PRIORITY_DELAYS:
                        files.append((file_path, priority))
                    else:
                        print(f"Warning: Unknown priority '{priority}' for file {file_path}.")
    return files

def receive_files_list(server_socket):
    try:
        files_list = server_socket.recv(4096).decode('utf-8').strip()
        return files_list.split(',')
    except Exception as e:
        print(f"Error receiving file list from server: {e}")
        return []

def receive_file_size(client_socket, file_path, priority):
    retry_delay = PRIORITY_DELAYS.get(priority, PRIORITY_DELAYS['NORMAL'])
    while True:
        client_socket.send(file_path.encode('utf-8'))
        
        try:
            response = client_socket.recv(1024)
            response_str = response.decode('utf-8').strip()
        except UnicodeDecodeError:
            time.sleep(retry_delay)
            continue
        except Exception as e:
            time.sleep(retry_delay)
            continue
        
        if response == b'error':
            time.sleep(retry_delay)
            continue
        
        if response_str.startswith('begin'):
            file_size_str = response_str[len('begin'):].strip()
        elif response_str.startswith('end'):
            file_size_str = response_str[len('end'):].strip()
        else:
            file_size_str = response_str
        
        if not file_size_str:
            time.sleep(retry_delay)
            continue
        
        if file_size_str.lower() == 'error':
            time.sleep(retry_delay)
            continue
        
        try:
            file_size = int(file_size_str)
            client_socket.send(b'ack')  # Acknowledge receipt of file size
            return file_size
        except ValueError:
            time.sleep(retry_delay)
            continue
        except Exception as e:
            time.sleep(retry_delay)
            continue

def download_file(client_socket, file_path, file_size):
    file_name = os.path.basename(file_path)
    full_path = os.path.join(OUTPUT_FOLDER, file_name)
    received_bytes = 0
    CHUNK_SIZE = 1024  # Size of each data chunk received

    try:
        if not os.path.exists(OUTPUT_FOLDER):
            os.makedirs(OUTPUT_FOLDER)

        with open(full_path, 'wb') as file:
            while received_bytes < file_size:
                client_socket.settimeout(5)  # Set timeout for receiving data
                remaining_bytes = file_size - received_bytes
                if remaining_bytes < CHUNK_SIZE:
                    CHUNK_SIZE = remaining_bytes
                
                try:
                    data = client_socket.recv(CHUNK_SIZE)
                except socket.timeout:
                    print(f"\nError: Timeout occurred while downloading {file_name}.")
                    return
                
                if not data:
                    print(f"\nError: Connection lost while downloading {file_name}.")
                    return

                file.write(data)
                received_bytes += len(data)

                progress = min(100, int(received_bytes / file_size * 100))
                print(f"\rDownloading {file_name}: {progress}% complete", end='', flush=True)

            print()  # Print new line after download completes

        if received_bytes != file_size:
            raise Exception(f"Incomplete download of {file_name}. Expected {file_size} bytes, received {received_bytes} bytes.")

        client_socket.send(b'success')  # Notify server of successful download

    except Exception as e:
        print(f"\nError downloading {file_name}: {e}")
        if os.path.exists(full_path):
            os.remove(full_path)  # Remove any downloaded file on error


def download_thread(client_socket, file_path, priority):
    """Threaded function to handle downloading a file based on its priority."""
    file_size = receive_file_size(client_socket, file_path, priority)
    if file_size is None:
        print(f"Failed to retrieve file size for {file_path}.")
        return

    download_file(client_socket, file_path, file_size)
    print(f"Downloaded {file_path}")

def main():
    try:
        if not os.path.exists(OUTPUT_FOLDER):
            os.makedirs(OUTPUT_FOLDER)

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            client_socket.connect((HOST, PORT))
            print(f"Connected to server at {HOST}:{PORT}")

            file_paths = receive_files_list(client_socket)
            if not file_paths:
                print("No files received from server. Exiting.")
                return

            print(f"Files available for download: {', '.join(file_paths)}")

            # Automatically get file paths and priorities from input.txt
            files_with_priorities = parse_input_file()
            file_queue = deque(sorted(files_with_priorities, key=lambda x: PRIORITY_DELAYS[x[1]]))

            # Download files based on priority
            while file_queue:
                file_path, priority = file_queue.popleft()
                if file_path in file_paths:
                    thread = threading.Thread(target=download_thread, args=(client_socket, file_path, priority))
                    thread.start()
                    thread.join()  # Wait for thread to finish

            print("All files downloaded successfully.")

    except ConnectionRefusedError:
        print(f"Connection to {HOST}:{PORT} refused. Make sure the server is running.")
    except KeyboardInterrupt:
        print("\nClient program interrupted. Closing...")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()