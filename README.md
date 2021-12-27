# SinglePlayer [SundayProjects]
Simple RPi Zero internet stream player.

# Usage
```python single_player.py <audio stream URL>```
```python single_player.py -s <json list file> ```

# JSON List File
```
[
    {
        "name": "Classic Rock Florida HD",
        "uri": "http://us4.internet-radio.com:8258/"
    },
    {
        "name": "Smooth Jazz Florida WSJF-DB",
        "uri": "https://www.internet-radio.com/servers/tools/playlistgenerator/?u=http://us4.internet-radio.com:8266/listen.pls&t=.m3u",
        "type": "m3u"
    } 
  ]
```
# Setup USB Audio Device
```shell
lsusb

Bus 001 Device 002: ID 0d8c:000c C-Media Electronics, Inc. Audio Adapter
Bus 001 Device 001: ID 1d6b:0002 Linux Foundation 2.0 root hub
```

```shell
dmesg | grep C-Media

[    4.193779] usb 1-1: Product: C-Media USB Headphone Set  
[    4.206491] input: C-Media USB Headphone Set   as /devices/platform/soc/20980000.usb/usb1/1-1/1-1:1.3/0003:0D8C:000C.0001/input/input0
[    4.282648] hid-generic 0003:0D8C:000C.0001: input,hidraw0: USB HID v1.00 Device [C-Media USB Headphone Set  ] on usb-20980000.usb-1/input3
```

```shell
aplay -l

card 0: vc4hdmi [vc4-hdmi], device 0: MAI PCM i2s-hifi-0 [MAI PCM i2s-hifi-0]
  Subdevices: 1/1
  Subdevice #0: subdevice #0
card 1: Set [C-Media USB Headphone Set], device 0: USB Audio [USB Audio]
  Subdevices: 1/1
  Subdevice #0: subdevice #0
```

```shell
sudo nano /usr/share/alsa/alsa.conf
```

Set default audio device
```
defaults.ctl.card 1
defaults.pcm.card 1
```

# Setup startup led
I want led indicates system is ready.
```
sudo crontab -e

@reboot bash /home/pi/SinglePlayer/startup_led.sh >/home/pi/startup_led_cronlog 2>&1
```

# First naive plan :D
![plan1](./docs/images/firstNaive.png "First Plan")

# Sources
Cause my memory is horrible and I did not use python for aeons.
## Logging
https://realpython.com/python-logging/
## RPi GPIO
https://raspberrypihq.com/use-a-push-button-with-raspberry-pi-gpio/
## Python VLC
https://www.geeksforgeeks.org/vlc-module-in-python-an-introduction/

https://stackoverflow.com/a/66083570
## USB Audio Device
https://www.raspberrypi-spy.co.uk/2019/06/using-a-usb-audio-device-with-the-raspberry-pi/

## URLLIB
https://www.geeksforgeeks.org/python-urllib-module/

## URL Attachment
https://stackoverflow.com/a/61630166
