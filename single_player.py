import vlc
import time
import sys
import logging
import getopt
import RPi.GPIO as GPIO

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BOARD)
GPIO.setup(10, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

# GLOBALS
LOG_FORMAT = '%(asctime)s %(process)d %(levelname)s %(message)s'
LOG_FILE = 'single_player.log'

pause = False
player = False

def playpause_callback(channel):
        global pause

        pause = not pause

        if pause == True:
                player.pause()
                logging.info('Paused')
        else:
                player.play()
                logging.info('Resumed')

def main(argv):
        global player

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
                opts, args = getopt.getopt(argv, '')
                uri = args[0]
        except getopt.GetoptError as e:
                logging.error("%s: %s\n" % (args[0], e.msg))
                sys.exit(2)

        # GPIO EVENTS
        GPIO.add_event_detect(10, GPIO.RISING, callback = playpause_callback, bouncetime=500)

        # PLAYER INIT
        player = vlc.MediaPlayer(uri)
        player.play()

        # WAITING FOR STREAM
        while player.is_playing() == 0:
                time.sleep(0.5)

        while True:
                time.sleep(0.5)

if __name__ == "__main__":
        try:
                main(sys.argv[1:])
        except Exception as e:
                logging.error('Exception ocurred', exc_info=True)