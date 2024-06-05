import socket
import time
import wave
import numpy as np
import threading
from datetime import datetime
import struct

SERVER_IP = '192.168.8.210'
UDP_PORT = 8080
TCP_PORT = 9090

server_socket_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server_socket_udp.bind((SERVER_IP, UDP_PORT))

server_socket_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket_tcp.bind((SERVER_IP, TCP_PORT))

server_running = True
client_files = {}
client_lock = threading.Lock()
file_name = None
stop_time = time.time()

def calculate_energy(audio_channel):
    energy = np.mean(audio_channel ** 2)
    return np.sqrt(energy)

def separate_channels(file_name, client_id):
    # Read raw data and add WAV header
    with open(file_name, 'rb') as raw_file:
        raw_data = raw_file.read()

    #file_name_wav = f'wav_file_{client_id}.wav'
    file_name_wav = file_name.replace('.bin', '.wav') #####################################
    with wave.open(file_name_wav, 'wb') as wav_file:
        wav_file.setnchannels(2)
        wav_file.setsampwidth(2)
        wav_file.setframerate(44100)
        wav_file.writeframes(raw_data)

    # Separate channels
    with wave.open(file_name_wav, 'rb') as wav_file:
        channels = wav_file.getnchannels()
        bytes_per_frame = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        frames_data = wav_file.readframes(wav_file.getnframes())
        audio = np.frombuffer(frames_data, dtype=np.int16)
        channel_1 = audio[::2]
        channel_2 = audio[1::2]

    return channel_1, channel_2

def udp_server():
    global file_name
    current_time = datetime.now().strftime("%Y%m%d%H%M%S")

    print("UDP Server initiated. Waiting for actions...")
    while server_running:
        try:
            data, client_address = server_socket_udp.recvfrom(32768)
            client_id = f"{client_address[0]}"          
            new_format_stop_time = datetime.fromtimestamp(stop_time).strftime('%d-%m-%Y %H-%M-%S-%f')
            file_name = f'raw_data_{client_id}_{new_format_stop_time}.bin'
            with client_lock:
                if client_id not in client_files:
                    client_files[client_id] = open(file_name, 'ab')  #####################  CAN NOT BE 'wb' mode because it has to APPEND audio bytes
                client_files[client_id].write(data)
                print(f"Receiving audio from {client_address}...")
        except Exception as e:
            print(f"UDP Server error: {e}")

def handle_tcp_client(connection, client_address):
    client_id = f"{client_address[0]}"
    global new_transmission
    global stop_time
    print(f"Handling TCP client: {client_address}")
    try:
        while True:
            data = connection.recv(1024)
            if not data:
                break
            if data.decode('utf-8') == "streaming":
                print(f"Audio streaming started for {client_address}...")
            elif data.decode('utf-8') == "exit":
                print(f"Client {client_address} requested to stop streaming.")
                #file_name = f'raw_data_{client_id}.bin'
                channel_1, channel_2 = separate_channels(file_name, client_id)
                start_time_energy_server = time.time()
                average_energy_1 = calculate_energy(channel_1)
                average_energy_1_db = 20 * np.log10(average_energy_1)
              
                average_energy_2 = calculate_energy(channel_2)
                average_energy_2_db = 20 * np.log10(average_energy_2)
                stop_time_energy_server = time.time()
                print(f'Average energy for Channel 1 [db] for {client_address}: {average_energy_1_db}')
                print(f'Average energy for Channel 2 [db] for {client_address}: {average_energy_2_db}')

                client_data = connection.recv(1024)
                client_average_energy_1_db, client_average_energy_2_db, start_time__tx_client, stop_time_tx_client,start_time_energy_client, stop_time_energy_client = struct.unpack('!dddddd', client_data)
                if stop_time_tx_client != stop_time:
                    stop_time = stop_time_tx_client

                start_time__tx_client = datetime.fromtimestamp(start_time__tx_client).strftime('%d-%m-%Y %H:%M:%S.%f')
                stop_time_tx_client = datetime.fromtimestamp(stop_time_tx_client).strftime('%d-%m-%Y %H:%M:%S.%f')
                start_time_energy_client =  datetime.fromtimestamp(start_time_energy_client).strftime('%d-%m-%Y %H:%M:%S.%f')
                stop_time_energy_client = datetime.fromtimestamp(stop_time_energy_client).strftime('%d-%m-%Y %H:%M:%S.%f')
                start_time_energy_server = datetime.fromtimestamp(start_time_energy_server).strftime('%d-%m-%Y %H:%M:%S.%f')
                stop_time_energy_server = datetime.fromtimestamp(stop_time_energy_server).strftime('%d-%m-%Y %H:%M:%S.%f')

                response_from_server = f'Average energy in the SERVER: \n Channel 1 [db]: {average_energy_1_db} \n Channel 2 [db]: {average_energy_2_db}'
                start_time_response_from_server = time.time() #Contains the time at which THE SERVER start sending a response to the client               
                connection.sendall(response_from_server.encode('utf-8'))

                response_data = connection.recv(8) 
                stop_time_response_from_server = struct.unpack('!d', response_data)[0] #Contains the time at which THE CLIENT receives the response from server
                stop_time_response_from_server = datetime.fromtimestamp(stop_time_response_from_server).strftime('%d-%m-%Y %H:%M:%S.%f')
                start_time_response_from_server = datetime.fromtimestamp(start_time_response_from_server).strftime('%d-%m-%Y %H:%M:%S.%f')

                # Saves the information in a file locally
                with open(f'information_{client_address[0]}.txt', 'a+') as info: #the mode is set to append and read, just in case we need to use the info again
                    info.writelines(f"{client_address, average_energy_1_db, average_energy_2_db, client_average_energy_1_db, client_average_energy_2_db, start_time__tx_client, stop_time_tx_client, start_time_energy_client, 
                                       stop_time_energy_client, start_time_energy_server, stop_time_energy_server, start_time_response_from_server, stop_time_response_from_server}\n")
                break
    except Exception as e:
        print(f'TCP Client handling error for {client_address}: {e}')
    finally:
        connection.close()
        with client_lock:
            if client_id in client_files:
                client_files[client_id].close()
                del client_files[client_id]

def tcp_server():
    server_socket_tcp.listen(5)
    print("TCP Server initiated. Waiting for connections...")
    while server_running:
        try:
            connection, addr = server_socket_tcp.accept()
            print("Connected to:", addr)
            client_thread = threading.Thread(target=handle_tcp_client, args=(connection, addr))
            client_thread.start()
        except Exception as e:
            print(f'TCP Server error: {e}')

if __name__ == "__main__":
    udp_thread = threading.Thread(target=udp_server)
    tcp_thread = threading.Thread(target=tcp_server)

    udp_thread.start()
    tcp_thread.start()

    udp_thread.join()
    tcp_thread.join()

    server_socket_udp.close()
    server_socket_tcp.close()
