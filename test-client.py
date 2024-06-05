import socket
import subprocess
import time
import wave
import numpy as np
import struct
from datetime import datetime

SERVER_IP = '192.168.8.210'
UDP_PORT = 8080
TCP_PORT = 9090

client_socket_udp = None
client_socket_tcp = None


start_time_tx = None

def initialize_sockets():
	global client_socket_udp, client_socket_tcp
	client_socket_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	client_socket_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	client_socket_tcp.connect((SERVER_IP, TCP_PORT))
	
def close_sockets():
	global client_socket_udp, client_socket_tcp
	if client_socket_tcp:
		client_socket_tcp.close()
		client_socket_tcp = None
	if client_socket_udp:
		client_socket_udp.close()
		client_socket_udp = None	

def calculate_energy(channel):
	energy = np.mean(channel ** 2) #calculates energy summing the square of each sample
	return np.sqrt(energy)	

def send_command(command):
	global start_time_tx
	try:
		client_socket_tcp.sendall(command.encode())		
		if command == 'streaming':
			start_time_tx = time.time()	
			record_audio()
			
		elif command == 'exit':
			stop_time_tx = time.time()		
			convert_raw_to_wav()
			channel_1, channel_2 = separate_channels()
		
			if channel_1 is not None and channel_2 is not None:
				#Average energy for channel 1
				start_time_energy = time.time()
				total_average_energy_1 = calculate_energy(channel_1)
				total_average_energy_1_db = 20 * np.log10(total_average_energy_1)
						
				#Average energy for channel 2
				total_average_energy_2 = calculate_energy(channel_2)
				total_average_energy_2_db = 20 * np.log10(total_average_energy_2)
				stop_time_energy = time.time()
				data = struct.pack('!dddddd', total_average_energy_1_db, total_average_energy_2_db, start_time_tx, stop_time_tx, start_time_energy, stop_time_energy) #we use struct because we are dealing with numbers (time)		
				client_socket_tcp.sendall(data)
						
				print('Average energy in the CLIENT: ')
				print('Channel 1 [db]: ', total_average_energy_1_db)
				print('Channel 2 [db]: ', total_average_energy_2_db)

				print('start:', datetime.fromtimestamp(start_time_energy).strftime('%d-%m-%Y %H:%M:%S.%f'))
				print('end:', datetime.fromtimestamp(stop_time_energy).strftime('%d-%m-%Y %H:%M:%S.%f'))
			
			
			message_from_server = client_socket_tcp.recv(1024).decode('utf-8')
			stop_time_response = time.time()
					
			print(message_from_server)
			print('stop:', datetime.fromtimestamp(stop_time_response).strftime('%d-%m-%Y %H:%M:%S.%f'))
			response_data = struct.pack('!d', stop_time_response)
			client_socket_tcp.sendall(response_data)		
			print('Exit')	
			client_socket_tcp.shutdown(socket.SHUT_RDWR)
			close_sockets()
	except Exception as e:
		print("Error: ", e)

def record_audio():
	try:
		arecord_process = subprocess.Popen(['arecord', '-f', 'S16_LE', '-r', '44100', '-c', '2', '-t', 'raw', '-d', '11'], stdout=subprocess.PIPE, bufsize=32768)	
		
		while (time.time() - start_time_tx) <= 11:	
			audio_data = arecord_process.stdout.read(32768)

			with open('recorded_audio.bin', 'ab') as f: #saves the audio locally as raw data in a .bin file
				f.write(audio_data)
			client_socket_udp.sendto(audio_data, (SERVER_IP, UDP_PORT))
		arecord_process.terminate()
	except Exception as e:
		print("Recording error: ", e)
		if arecord_process:
			arecord_process.terminate()
	
def convert_raw_to_wav():
	try:
		with open('recorded_audio.bin', 'rb') as raw_file:
			raw_data = raw_file.read()
		
		wav_file = wave.open('recorded_audio.wav', 'wb')
		wav_file.setnchannels(2)
		wav_file.setsampwidth(2)
		wav_file.setframerate(44100)
		wav_file.writeframes(raw_data)
		wav_file.close()
	except Exception as e:
		print("Conversion error: ", e)

def separate_channels():
	try:		
		wf = wave.open('recorded_audio.wav', 'rb')
		channels = wf.getnchannels()
		bytes_per_frame = wf.getsampwidth() #sample width
		sample_rate = wf.getframerate()
			
		frames_data = wf.readframes(wf.getnframes())
		audio = np.frombuffer(frames_data, dtype=np.int16) #converts frames into a numpy array 
		channel_1 = audio[::2]
		channel_2 = audio[1::2]
		wf.close()
		print('Channels: ', channels)
		print('Bytes per frame: ', bytes_per_frame)
		print('Sample rate: ', sample_rate)
		return channel_1, channel_2
	except Exception as e:
		print("Separation error: ", e)
		return None, None

if __name__ == "__main__":
	for i in range(100):
		print("Execution: ", i+1)
		initialize_sockets()
		send_command("streaming")
		send_command("exit")
		time.sleep(3)