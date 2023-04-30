import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import webrtcvad
import pyaudio
import wave
import os
import time
import threading
import subprocess
import re
from collections import deque

#Dependencies
#pip3 install webrtcvad
#sudo apt install portaudio19-dev
#pip3 install pyaudio

#ros2 topic pub /chatgpt/prompt std_msgs/msg/String "data: 'Greetings!'" -1

# Parameters
DEVICE_INDEX=0
FORMAT = "pyaudio.paInt16"
CHANNELS = 1
RATE = 16000  # 16 kHz
MODEL = "models/ggml-base.en.bin"
NUM_THREADS = 8
NUM_PROCESSORS = 2

CHUNK = 320  # 20 ms frame duration for 16,000 Hz sample rate
RECORD_SECONDS = 5
WAV_OUTPUT_FOLDER = "recordings"

class WhisperTranscriber(Node):
    def __init__(self):
        super().__init__('whisper_transcriber')
        self.text_pub = self.create_publisher(String, '/chatgpt/prompt', 10)
        
        if not os.path.exists(WAV_OUTPUT_FOLDER):
            os.makedirs(WAV_OUTPUT_FOLDER)

        #self.detect_thread = threading.Thread(target=self.detect_speech)
        #self.detect_thread.start()
        print('Recording Audio')
        self.record_audio("test.wav")

        print('Beginning Detect Speech')
        self.detect_speech()

    def record_audio(self, filename):
        vad = webrtcvad.Vad()
        vad.set_mode(3)  # Set the VAD sensitivity. 3 is the highest sensitivity.

        audio = pyaudio.PyAudio()
        frames = []

        # Start recording
        #stream = audio.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, input_device_index=1, frames_per_buffer=1024)
        stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, input_device_index=DEVICE_INDEX, frames_per_buffer=1024)

        print("Recording...")

        silence_duration = 0
        MAX_SILENCE_DURATION = 1  # Maximum silence duration in seconds

        while True:
            data = stream.read(CHUNK)
            frames.append(data)
            is_speech = vad.is_speech(data, RATE)

            if not is_speech:
                silence_duration += CHUNK / RATE
                if silence_duration >= MAX_SILENCE_DURATION:
                    break
            else:
                silence_duration = 0

        # Stop recording
        stream.stop_stream()
        stream.close()
        
        print("Finished recording.")

        audio.terminate()

        # Save as WAV file
        wave_file = wave.open(filename, 'wb')
        wave_file.setnchannels(CHANNELS)
        wave_file.setsampwidth(audio.get_sample_size(FORMAT))
        wave_file.setframerate(RATE)
        wave_file.writeframes(b''.join(frames))
        wave_file.close()

    def extract_transcribed_text(self, output):
        # Use regex to extract the transcribed text between the timestamp brackets
        pattern = r'\[\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}\]\s*(.+)\s*'
        matches = re.findall(pattern, output)
        transcribed_text = ' '.join(matches)
        return transcribed_text

    def detect_speech(self):
        print("Waiting for speech...")
        surpress = True #False
        while True:
            filename = f"{WAV_OUTPUT_FOLDER}/output_{int(time.time())}.wav"
             
	    # Suppress ALSA and JACK error messages
            if surpress:
                with open(os.devnull, 'w') as devnull:
                    old_stderr = os.dup(2)
                    os.dup2(devnull.fileno(), 2)
            
                    record_audio(filename)
            
                    # Restore stderr
                    os.dup2(old_stderr, 2)
            else:
                record_audio(filename)
        
            # Replace 'my_avr_program' with the name of your AVR program
            # and 'filename' with the path to the recorded WAV file
            #print("running avr");
            command = f"./avr -m {MODEL} -f {filename}"
        
            #print(command)

            # Execute the command and pipe the output
            result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print("done")

            # Extract transcribed text from the avr program's output
            output = result.stdout.decode('utf-8')
            transcribed_text = extract_transcribed_text(output)
        
            # Print the transcribed text
            print(transcribed_text)

            clarified_text = transcribed_text.replace(',', '').replace('.', '').upper()

            if 'SCRAPPY QUIT' in clarified_text:
                exit()

            if transcribed_text != '':
                if transcribed_text[0] != '(' and transcribed_text[0] != '[':
                    print('Outputting to /whisper/transcribed_text')
                    text_pub.publish(transcribed_text)

            # Delete the recording after processing
            os.remove(filename)

if __name__ == "__main__":
    print('Starting')
    rclpy.init()
    WhisperTranscriber()
    #WhisperTranscriber.detect_speech(self)
#    while True:
#      print("looping")
#      rclpy.spin()
