import logging
import sys
import RPi.GPIO as GPIO

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BOARD)
GPIO.setup(16, GPIO.OUT)

# GLOBALS
LOG_FORMAT = '%(asctime)s %(process)d %(levelname)s %(message)s'
LOG_FILE = 'led_indicator.log'

def main():
        # LOGGING SETUP
        logging.basicConfig(filename=LOG_FILE, filemode='a', format=LOG_FORMAT, level=logging.DEBUG)
        root = logging.getLogger()
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
        formater = logging.Formatter(LOG_FORMAT)
        handler.setFormatter(formater)
        root.addHandler(handler)

        GPIO.output(16,GPIO.HIGH)

if __name__ == "__main__":
        try:
                main()
        except Exception as e:
                logging.error('Exception ocurred', exc_info=True)