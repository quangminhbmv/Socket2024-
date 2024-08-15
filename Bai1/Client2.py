import socket
import os
import time
import zipfile

HOST = '127.0.0.1'         # Server IP address
PORT = 8888                    # Server port
OUTPUT_FOLDER = 'output2'       # Directory to store downloaded files
INPUT_FILE = 'input2.txt'       # File containing list of downloaded files

def receive_files_list(server_socket):
    try:
        files_list = server_socket.recv(4096).decode('utf-8').strip()
        return files_list.split(',')
    except Exception as e:
        print(f"Error receiving file list from server: {e}")
        return []

def receive_file_size(client_socket, file_path, retry_delay=5):
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
    CHUNK_SIZE = 4096  # Size of each data chunk received

    try:
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

            if not os.path.exists(INPUT_FILE):
                print(f"{INPUT_FILE} not found. Exiting.")
                return

            with open(INPUT_FILE, 'r') as file:
                files_to_download = [line.strip() for line in file if line.strip()]

            # Validate the files to download
            invalid_files = [file for file in files_to_download if file not in file_paths]
            if invalid_files:
                print(f"Invalid file(s) listed in {INPUT_FILE}: {', '.join(invalid_files)}")
                return

            for file_path in files_to_download:
                file_size_response = receive_file_size(client_socket, file_path)
                if file_size_response is None:
                    print(f"Failed to retrieve file size for {file_path}.")
                    continue

                download_file(client_socket, file_path, file_size_response)
                print(f"Downloaded {file_path}")

            print("All selected files downloaded successfully.")

    except ConnectionRefusedError:
        print(f"Connection to {HOST}:{PORT} refused. Make sure the server is running.")
    except KeyboardInterrupt:
        print("\nClient program interrupted. Closing...")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
