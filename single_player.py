import time
import os
import sys
import logging
import getopt
import json
import urllib.request
from urllib.parse import urlparse
import re
import RPi.GPIO as GPIO

import vlc
import requests

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BOARD)
GPIO.setup(10, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(12, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

# GLOBALS
LOG_FORMAT = '%(asctime)s %(process)d %(levelname)s %(message)s'
LOG_FILE = 'single_player.log'
TMP_FOLDER = os.path.join('.', 'tmp')

MEDIA_TYPE_STREAM = 'direct_stream'
MEDIA_TYPE_M3U = 'm3u'

CONTENT_TYPE_TEXT = 'text/plain'

player = False

# CLASSES
class VLC:
	def __init__(self):
		self.Player = vlc.Instance('--loop')
		self.stationIndex = 0
		self.statePause = False

	def play(self):
		self.listPlayer.play()

	def next(self):
		if self.listPlayer.next() == -1:
			self.listPlayer.next()

		self.setStationIndex()

	def pause(self):
		self.listPlayer.pause()

	def togglePause(self):
		self.statePause = not self.statePause

		if self.statePause == True:
			self.pause()
		else:
			self.play()

		return self.statePause

	def previous(self):
		self.listPlayer.previous()

	def stop(self):
		self.listPlayer.stop()

	def addPlaylist(self, list):
		self.stationsList = list
		self.mediaList = self.Player.media_list_new()

		for item in list:
			self.mediaList.add_media(item['uri'])

		self.listPlayer = self.Player.media_list_player_new()
		self.listPlayer.set_media_list(self.mediaList)

	def isPlaying(self):
		return self.listPlayer.is_playing()

	def getCurrentStationInfo(self):
		return self.stationsList[self.stationIndex]

	def getCurrentStationName(self):
		return self.stationsList[self.stationIndex]['name']

	def setStationIndex(self):
		if self.stationIndex + 1 >= len(self.stationsList):
			self.stationIndex = -1

		self.stationIndex = self.stationIndex + 1

# FUNCTIONS
def playpause_callback(channel):
	if (player.togglePause() == True):
		logging.info('Paused')
	else:
		logging.info('Resumed')

def changestation_callback(channel):
	player.next()
	logging.info("next %s", player.getCurrentStationName())

def load_stations(path):
	f = open(path)
	data = json.load(f)
	f.close()

	return data

def check_stream(url):
	code = 0

	try:
		code = urllib.request.urlopen(url).getcode()
	except Exception as e:
		code = e.code
		logging.error('Exception ocurred', exc_info=True)
	
	stringCode = str(code)

	if stringCode.startswith('2') or stringCode.startswith('3'):
		return True
	
	return False

def sanitize_file_name(filename):
	return re.sub('[ ,.]', '_', filename)

def mkdir(path):
	if not os.path.exists(path):
		os.mkdir(path)

def is_attachment(url):
	headers = requests.get(url, stream=True).headers
	return 'attachment' in headers.get('Content-Disposition', '')

def is_text_plain(url):
	headers = requests.get(url, stream=True).headers

	return CONTENT_TYPE_TEXT in headers.get('Content-Type', '')

def download_file(url, path):
	data = requests.get(url)

	with open(path, 'wb') as file:
		file.write(data.content)

def absolute_path(path):
	p = urlparse(path)
	return os.path.abspath(os.path.join(p.netloc, p.path))

def stations_preprocessing(stations):
	newStations = []

	for s in stations:
		uri = s['uri']
		name = s['name']
		mediaType =  s['type'] if 'type' in s else ''
		passTest = False

		if os.path.isfile(uri):
			uri = absolute_path(uri)
			passTest = True

		if uri[:4] == 'file':
			uri = absolute_path(uri)
			if os.path.isfile(uri):
				passTest = True

		if passTest == False and uri[:4] == 'http':
			if mediaType == MEDIA_TYPE_STREAM:
				passTest = check_stream(uri)
			elif mediaType == MEDIA_TYPE_M3U:
				if is_attachment(uri) or is_text_plain(uri):
					mkdir(TMP_FOLDER)
					sanitizedName = sanitize_file_name(name)
					filePath = os.path.join(TMP_FOLDER, sanitizedName + '.m3u')
					download_file(uri, filePath)
					uri = absolute_path(filePath)
				
				passTest = True
			else:
				passTest = check_stream(uri)
		
		if (passTest == True):
			newStations.append({
				"name": s['name'],
				"uri": uri
			})
	
	return newStations

def main(argv):
	global player
	stations = []

	# LOGGING SETUP
	logging.basicConfig(filename=LOG_FILE, filemode='a', format=LOG_FORMAT, level=logging.DEBUG)
	root = logging.getLogger()
	handler = logging.StreamHandler(sys.stdout)
	handler.setLevel(logging.DEBUG)
	formater = logging.Formatter(LOG_FORMAT)
	handler.setFormatter(formater)
	root.addHandler(handler)

	# PROCESS ARGUMENTS
	try:
		opts, args = getopt.getopt(argv, 's:', ['stations='])
		for opt, arg in opts:
			if opt in ['-s', '--stations']:
				stations = load_stations(arg)

		if not stations:
			stations = [{
				"name": "Radio Stream",
				"uri": args[0]
			}]
	except getopt.GetoptError as e:
		logging.error("%s: %s\n" % (args[0], e.msg))
		sys.exit(2)

	# GPIO EVENTS
	GPIO.add_event_detect(10, GPIO.RISING, callback = playpause_callback, bouncetime=500)
	GPIO.add_event_detect(12, GPIO.RISING, callback = changestation_callback, bouncetime=500)

	# PLAYER INIT
	player = VLC()
	player.addPlaylist(stations_preprocessing(stations))
	player.play()

	# WAITING FOR STREAM
	while player.isPlaying() == 0:
		time.sleep(0.5)

	while True:
		time.sleep(0.5)

if __name__ == "__main__":
	try:
		main(sys.argv[1:])
	except Exception as e:
		logging.error('Exception ocurred', exc_info=True)