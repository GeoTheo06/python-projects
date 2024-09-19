import pyaudio
import wave
import speech_recognition as sr
from googletrans import Translator
import os

#type "change system sounds" in search bar go to "recording" set "cable ouput" device as the 
# default device. Right click "cable output" device, go to "listen" tab. Enable "listen to 
# this device" option. select the device to which you want to listen the computer output to.

i = 1

file_path = "captured_text.txt"

# Function to record audio using PyAudio
def record_audio(filename, duration=30):  # Listen for x seconds
	audio = pyaudio.PyAudio()
	stream = audio.open(format=pyaudio.paInt16, channels=1, rate=44100, input=True, frames_per_buffer=1024)
	frames = []

	print("Listening...")

	for i in range(0, int(44100 / 1024 * duration)):
		data = stream.read(1024)
		frames.append(data)

	print("Finished recording.")
	stream.stop_stream()
	stream.close()
	audio.terminate()

	with wave.open(filename, 'wb') as wf:
		wf.setnchannels(1)
		wf.setsampwidth(audio.get_sample_size(pyaudio.paInt16))
		wf.setframerate(44100)
		wf.writeframes(b''.join(frames))

# play audio on Windows
def play_audio(filename):
	os.system("start wmplayer /play /close " + filename)

def recognize_speech():
    while True:
        with sr.Microphone() as source:
            print("Listening for Russian speech...")
            audio = recognizer.listen(source)

        try:
            text = recognizer.recognize_google(audio, language="ru-RU")
            print(f"Recognized: {text}")
            # Put the recognized text in a shared queue for translation thread
            translation_queue.put(text)
        except sr.UnknownValueError:
            print("Could not understand audio")
        except sr.RequestError as e:
            print(f"Error when recognizing audio: {e}")

# Function for translating speech
def translate_speech():
    while True:
        text = translation_queue.get()
        translation = translator.translate(text, src="ru", dest="en")
        print(f"Translation: {translation.text}")

# Infinite loop for continuous translation and playback
while True:
	# Record audio for x seconds
	record_audio("captured_voice.wav", duration=30)

	# Perform speech recognition
	recognized_text = recognize_speech()

	if recognized_text:
		# Translate recognized text to English
		translated_text = translate_text(recognized_text, dest_language='en')
		print(f"\nTranslated text {i}: {translated_text}\n")
	i=i+1

	if recognized_text
	translated_text = translate_text 	