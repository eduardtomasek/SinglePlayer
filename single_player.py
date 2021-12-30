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

player = False

# CLASSES
class VLC:
	def __init__(self):
		self.Player = vlc.Instance('--loop')
		self.listPlayer = None
		self.mediaList = None
		self.stationsList = None
		self.stationIndex = 0
		self.statePause = False

	def play(self):
		self.listPlayer.play()

	def next(self):
		#nextDone = self.listPlayer.next()
		#logging.info('next: %s', nextDone)

		#if nextDone == -1:
			#nextDone = self.listPlayer.next()

		#if nextDone != -1:
			#self.setStationIndex()
		
		self.setStationIndex()
		self.playItemOnIndex(self.stationIndex)

	def pause(self):
		self.listPlayer.pause()

	def togglePause(self):
		self.statePause = not self.statePause

		if self.statePause == True:
			self.stop()
		else:
			self.playItemOnIndex(self.stationIndex)

		return self.statePause

	def previous(self):
		self.listPlayer.previous()

	def playItemOnIndex(self, index):
		return self.listPlayer.play_item_at_index(index)

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

	def getCurrentStationIndex(self):
		return self.stationIndex

	def getCurrentStationName(self):
		return self.stationsList[self.stationIndex]['name']

	def setStationIndex(self):
		if self.stationIndex + 1 >= len(self.stationsList):
			self.stationIndex = -1

		self.stationIndex = self.stationIndex + 1

class StationsList:
	def __init__(self, options):
		self.MEDIA_TYPE_M3U = 'm3u'
		self.MEDIA_TYPE_STREAM = 'direct_stream'
		self.TMP_FOLDER = options['tmpFolder']

	def _check_stream(self, url):
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

	def _sanitize_file_name(self, filename):
		return re.sub('[ ,.]', '_', filename)

	def _mkdir(self, path):
		if not os.path.exists(path):
			os.mkdir(path)

	def _is_attachment(self, url):
		headers = requests.get(url, stream=True).headers
		return 'attachment' in headers.get('Content-Disposition', '')

	def _is_text_plain(self, url):
		headers = requests.get(url, stream=True).headers

		return 'text/plain' in headers.get('Content-Type', '')
	
	def _download_file(self, url, path):
		data = requests.get(url)

		with open(path, 'wb') as file:
			file.write(data.content)
	
	def _absolute_path(self, path):
		p = urlparse(path)
		return os.path.abspath(os.path.join(p.netloc, p.path))

	def preprocessing(self, stations):
		newStations = []

		for s in stations:
			uri = s['uri']
			name = s['name']
			mediaType =  s['type'] if 'type' in s else ''
			passTest = False

			if os.path.isfile(uri):
				uri = self._absolute_path(uri)
				passTest = True

			if passTest == False and uri[:4] == 'file':
				uri = self._absolute_path(uri)
				if os.path.isfile(uri):
					passTest = True

			if passTest == False and uri[:4] == 'http':
				if mediaType == self.MEDIA_TYPE_STREAM:
					passTest = self._check_stream(uri)
				elif mediaType == self.MEDIA_TYPE_M3U:
					if self._is_attachment(uri) or self._is_text_plain(uri):
						self._mkdir(self.TMP_FOLDER)
						sanitizedName = self._sanitize_file_name(name)
						filePath = os.path.join(self.TMP_FOLDER, sanitizedName + '.m3u')
						self._download_file(uri, filePath)
						uri = self._absolute_path(filePath)
					
					passTest = True
				else:
					passTest = self._check_stream(uri)
			
			if passTest == True:
				newStations.append({
					"name": s['name'],
					"uri": uri
				})
		
		return newStations
	
# CALLBACKS
def playpause_callback(channel):
	if player.togglePause() == True:
		logging.info('%s paused', player.getCurrentStationName())
	else:
		logging.info('%s resumed', player.getCurrentStationName())

def changestation_callback(channel):
	player.next()
	logging.info("next [%s] %s", player.getCurrentStationIndex(), player.getCurrentStationName())

# FUNCTIONS
def load_stations(path):
	f = open(path)
	data = json.load(f)
	f.close()

	return data

def main(argv):
	global player
	stations = []
	sl = StationsList({ 'tmpFolder': TMP_FOLDER })

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
	#player.addPlaylist(stations_preprocessing(stations))
	player.addPlaylist(sl.preprocessing(stations))
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