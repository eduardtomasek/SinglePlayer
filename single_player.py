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
import textwrap

import vlc
import requests

# DISPLAY
import board
import adafruit_ssd1306 # this sets GPIO mode 11 (bcm)
from PIL import Image, ImageDraw, ImageFont # https://pillow.readthedocs.io/en/stable/

DISPLAY_WIDTH = 128
DISPLAY_HEIGHT = 64
DISPLAY_BORDER = 3
DISPLAY_INNER_BORDER = 2
DISPLAY_ADDRESS = 0x3c
DISPLAY_TEXT_MAX_LENGTH = 18
DISPLAY_TEXT_MAX_LINES = 4
DISPLAY_YELLOW_AREA_OFFSET = 10
DISPLAY_TIMEOUT = 300

_displayON = True
_displayTimeout = 0

i2c = board.I2C()
oled = adafruit_ssd1306.SSD1306_I2C(DISPLAY_WIDTH, DISPLAY_HEIGHT, i2c, addr=DISPLAY_ADDRESS)

# GPIO SETTINGS
GPIO.setwarnings(False)
# GPIO.setmode(GPIO.BOARD)
# GPIO.setup(10, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
# GPIO.setup(12, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(15, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(18, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

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
		# Media list player method "next" appears to be not reliable. (https://www.olivieraubert.net/vlc/python-ctypes/doc/vlc-pysrc.html#MediaListPlayer.next)
		# I decided mirror playlist in code and just play specific item by index.
		# It looks like more reliable.
		
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
		display_text('Paused', player.getCurrentStationName())
	else:
		logging.info('%s resumed', player.getCurrentStationName())
		display_text('Playing', player.getCurrentStationName())

def changestation_callback(channel):
	player.next()
	logging.info("next [%s] %s", player.getCurrentStationIndex(), player.getCurrentStationName())
	display_text('Playing', player.getCurrentStationName())

# FUNCTIONS
def load_stations(path):
	f = open(path)
	data = json.load(f)
	f.close()

	return data

# DISPLAY FUNCTIONS
def display_turn_off():
	global _displayON

	oled.poweroff()

	_displayON = False

def display_turn_on():
	global _displayON

	oled.poweron()

	_displayON = True

def display_timeout():
	global _displayTimeout

	if _displayTimeout > DISPLAY_TIMEOUT:
		_displayTimeout = 0
		display_turn_off()


def display_text(status = 'Playing', text='Default text'):
	if _displayON == False:
		display_turn_on()

	oled.fill(0)
	oled.show()

	image = Image.new('1', (oled.width, oled.height))
	draw = ImageDraw.Draw(image)

	font = ImageFont.load_default()

	# YELLOW AREA
	(statusWidth, statusHeight) = font.getsize(status)
	# RIGHT YELLOW TEXT
	draw.text((oled.width - (statusWidth + DISPLAY_BORDER + DISPLAY_INNER_BORDER), DISPLAY_BORDER + 1), status, font=font, fill=255)

	# LEFT YELLOW TEXT
	draw.text((DISPLAY_BORDER + DISPLAY_INNER_BORDER, DISPLAY_BORDER + 1), 'OnLine', font=font, fill=255)

	# BLUE AREA
	(textWidth, textHeight) = font.getsize(text)

	# wrap text with maximum characters per line a and maximum amount of lines
	textSegments = textwrap.wrap(text, width=DISPLAY_TEXT_MAX_LENGTH)[:DISPLAY_TEXT_MAX_LINES]
	textSegmentsLength = len(textSegments)

	# we are starting drawing text from the center of screen (with yellow area offset, see display info https://www.aliexpress.com/item/32896971385.html)
	lines = textSegmentsLength // 2

	# for vertical text centering we need to know if number of lines are odd or even
	even = True if textSegmentsLength % 2 == 0 else False

	for line in textSegments:
		(lineWidth, lineHeight) = font.getsize(line)

		# horizontal center is easy
		lineX = oled.width//2 - lineWidth//2

		if even == False:
			# for even number of lines we have to shift vertical center up by half line height
			centerY = (oled.height//2 - lineHeight//2) + DISPLAY_YELLOW_AREA_OFFSET
		else:
			# for ood number of lines we just start in our vertical center
			centerY = (oled.height//2) + DISPLAY_YELLOW_AREA_OFFSET
		
		# cause our origin is in vertical center we need to divide lines count by two (half text is in upper half of screen and second half in lower screen part)
		# with this number in loop we can start draw text from upper half and 
		# continue to bottom half of given area
		lineY = centerY - (lines * lineHeight)

		draw.text((lineX, lineY), line, font=font, fill=255)

		lines = lines - 1

	oled.image(image)
	oled.show()

def main(argv):
	global player
	global _displayTimeout

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

	logging.info('GPIO mode: %s', GPIO.getmode())

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
	#GPIO.add_event_detect(10, GPIO.RISING, callback = playpause_callback, bouncetime=500)
	#GPIO.add_event_detect(12, GPIO.RISING, callback = changestation_callback, bouncetime=500)
	GPIO.add_event_detect(15, GPIO.RISING, callback = playpause_callback, bouncetime=500)
	GPIO.add_event_detect(18, GPIO.RISING, callback = changestation_callback, bouncetime=500)

	# PLAYER INIT
	player = VLC()
	#player.addPlaylist(stations_preprocessing(stations))
	player.addPlaylist(sl.preprocessing(stations))
	player.play()
	display_text('Playing', player.getCurrentStationName())

	# WAITING FOR STREAM
	while player.isPlaying() == 0:
		time.sleep(0.5)

	while True:
		time.sleep(0.5)
		if (_displayON == True):
			_displayTimeout = _displayTimeout + 0.5

		display_timeout()


if __name__ == "__main__":
	try:
		main(sys.argv[1:])
	except Exception as e:
		logging.error('Exception ocurred', exc_info=True)