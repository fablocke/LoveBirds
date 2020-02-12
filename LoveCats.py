##!/usr/bin/python3
import asyncio
import time
import os
import sys
import signal
from telethon import TelegramClient, events, sync
from telethon.tl.types import InputMessagesFilterVoice
import RPi.GPIO as GPIO
from gpiozero import Servo
from time import sleep
from neopixel import *
from random import randrange


phone = '' #change this: This is your phone number
peer = '@' #and this: This is the username that you want to talk with

"""
initialisation of GPIOs
"""
global recLED      #led recording (mic+)
global recBUT      #button recording (mic+)
global playLED     #led you have a voicemail
global p


global toPlay      # number of voicemail waiting
global recD        # duration of recording (in half second)
global playOK      # autorisation to play messages (boolean)
global playOKD     # timeout(en 1/2 secondes) de l'autorisation
global motorON     # motor command
global previousMotorON #was the motor on before?
global heartBeatLed #heartbeat effect on led
global motor

# LED strip configuration:
global LED_COUNT    # = 16 # Number of LED pixels.
global LED_PIN      #= 18 # GPIO pin connected to the pixels (18 uses PWM!).
global LED_FREQ_HZ # LED signal frequency in hertz (usually 800khz)
global LED_DMA # DMA channel to use for generating signal (try 10)
global LED_BRIGHTNESS # Set to 0 for darkest and 255 for brightest
global LED_INVERT # True to invert the signal (when using NPN transistor level shift)
global LED_CHANNEL# se
global statusSTRIP


heartBeatLed = False
previousMotorON = False
motorON = False
playOK = False
recD = 0
playOKD = 0

toPlay = -1
playLED = 22
recLED = 25
recBUT = 23
motor = 17

LED_COUNT = 5 # Number of LED pixels.
LED_PIN = 12 # GPIO pin connected to the pixels (18 uses PWM!).
#LED_PIN = 10 # GPIO pin connected to the pixels (10 uses SPI /dev/spidev0.0).
LED_FREQ_HZ = 800000 # LED signal frequency in hertz (usually 800khz)
LED_DMA = 10 # DMA channel to use for generating signal (try 10)
LED_BRIGHTNESS = 40 # Set to 0 for darkest and 255 for brightest
LED_INVERT = False # True to invert the signal (when using NPN transistor level shift)
LED_CHANNEL = 0 # set to '1' for GPIOs 13, 19, 41, 45 or 
statusStrip = False

"""
initialisation of GPIO leds and switch and motor
"""
GPIO.setmode(GPIO.BCM)
GPIO.setup(recLED, GPIO.OUT)
GPIO.setup(recBUT, GPIO.IN)
GPIO.setup(playLED, GPIO.OUT)
GPIO.setup(motor, GPIO.OUT)
GPIO.output(recLED, GPIO.LOW)


async def timeC():
    """
    time management : duration of recording and timeout for autorization to play
    """
    global playOK
    global playOKD
    global recD
    global motorON
    global statusStrip

    while True :
        await asyncio.sleep(0.5)
        recD = recD + 1
        if playOK == True:
            playOKD = playOKD - 1
            if playOKD <= 0:
                playOK = False



async def recTG():
    """
    Send a message 'voice'
    initialisation of gpio led and button
    when button is pushed: recording in a separate process
    that is killed when the button is released
    conversion to .oga by sox
    """
    global recD
    global playOK
    global playOKD
    delay = 0.2 
    while True:    
        await asyncio.sleep(delay)
        if GPIO.input(recBUT) == GPIO.LOW:
            heartBeatLed = False
            p.ChangeDutyCycle(100) #turns ON the REC LED
            recD = 0
            pid = os.fork()
            if pid == 0 :
                #os.execl('/usr/bin/arecord','arecord','-D','plughw:1,0','--rate=44000','/home/pi/rec.wav')
                os.execl('/usr/bin/sox','sox','-t','alsa','default','/home/pi/rec.wav')
                #os.system('sox -t alsa default /home/pi/rec.wav')
            else:
                while GPIO.input(recBUT) == GPIO.LOW :
                    await asyncio.sleep(delay)
                os.kill(pid, signal.SIGKILL)
                heartBeatLed = False
                #GPIO.output(recLED, GPIO.LOW)
                p.ChangeDutyCycle(0) #turns OFF the REC LED
                playOK = True
                playOKD = 30
                if recD > 1:
                    os.system('sudo killall sox')
                    os.system('ffmpeg -i /home/pi/rec.wav -acodec mp3 /home/pi/rec.mp3 -y')
                    #os.system('/usr/bin/sox /home/pi/rec.wav /home/pi/rec.ogg')
                    #os.rename('/home/pi/rec.ogg', '/home/pi/rec.oga')
                    await client.send_file(peer, '/home/pi/rec.mp3',voice_note=True)
        else:
            #heartBeatLed = False
            #GPIO.output(recLED, GPIO.LOW)
            p.ChangeDutyCycle(0)

#motor uses global to turn ON the motor
async def motor():
   global motorON
   global motor
   global previousMotorON
   # Adjust the pulse values to set rotation range
   min_pulse = 0.000544    # Library default = 1/1000
   max_pulse = 0.0024              # Library default = 2/1000
   # Initial servo position
   pos =  1
   test = 0
   servo = Servo(17, pos, min_pulse, max_pulse, 20/1000, None)
   

   while True:
      await asyncio.sleep(0.2)
      if motorON == True:
         pos=pos*(-1)
         servo.value=pos
         await asyncio.sleep(2)
      else :
                        #put back in original position
                        servo.value=0
                        #detach the motor to avoid glitches and save energy
                        servo.detach()
                        previousMotorON = False


async def LEDStripe():
   global statusStrip
   while True:
      if statusStrip:
         strip = Adafruit_NeoPixel(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
         strip.begin()
         i = 255
         while(i>=0):
            #print('1')

            for j in range(strip.numPixels()):
               strip.setPixelColor(j, Color(0,i,0))
               strip.show()
               asyncio.sleep(0.008)
            i=i-1
         print('FlaSH!')
         await asyncio.sleep(0.3)
      else:
         await asyncio.sleep(0.1)

#this is the les that mimic heartbeat when you have a voicemail waiting
async def heartBeat():
   global heartBeatLed
   global p


   p = GPIO.PWM(recLED, 500)     # set Frequece to 500Hz
   p.start(100)                     # Start PWM output, Duty Cycle = 0
   while True:
      if heartBeatLed == True :
         for dc in range(0, 20, 2):   # Increase duty cycle: 0~100
            p.ChangeDutyCycle(dc)
            await asyncio.sleep(0.01)
         for dc in range(20, -1, -2): # Decrease duty cycle: 100~0
            p.ChangeDutyCycle(dc)
            await asyncio.sleep(0.005)
         time.sleep(0.05)
   
         for dc in range(0, 101, 2):   # Increase duty cycle: 0~100
            p.ChangeDutyCycle(dc)     # Change duty cycle
            await asyncio.sleep(0.01)
         for dc in range(100, -1, -2): # Decrease duty cycle: 100~0
            p.ChangeDutyCycle(dc)
            await asyncio.sleep(0.01)

         await asyncio.sleep(0.06)
   
         for dc in range(0,8, 2):   # Increase duty cycle: 0~100
            p.ChangeDutyCycle(dc)     # Change duty cycle
            await asyncio.sleep(0.01)
         for dc in range(7, -1, -1): # Decrease duty cycle: 100~0
            p.ChangeDutyCycle(dc)
            await asyncio.sleep(0.01)
         await asyncio.sleep(1)
         
      else :
            await asyncio.sleep(0.1)



async def playTG():
    """
    when authorized to play (playOK == True)
    play one or several messages waiting (file .ogg) playLED on
    message playing => playing
    last message waiting => toPlay
    """
    global toPlay
    global playOK
    global motorON
    global heartBeatLed
    global servo
    global statusStrip

    playing = 0
    while True:
        if toPlay >= 0:
            GPIO.output(playLED, GPIO.HIGH)
            motorON = True
            heartBeatLed = True
            statusStrip = True
            
        else:
            GPIO.output(playLED, GPIO.LOW)
            motorON = False
            heartBeatLed = False
            statusStrip = False

            
        if (toPlay >= 0) and (playOK == True):
            while playing <= toPlay:
                name = '/home/pi/play' + str(playing) + '.ogg'
                os.system('sudo killall vlc')

                pid = os.fork()
                if pid == 0 :
                    os.execl('/usr/bin/cvlc', 'cvlc', name,  '--play-and-exit')
                    #os.execl('/usr/bin/cvlc', 'cvlc',  name, ' vlc://quit')

                os.wait()         
                playing = playing + 1
                if playing <= toPlay :
                    await asyncio.sleep(1)
            playing = 0
            toPlay = -1  
            playOk = True
            playOKD = 30     
        await asyncio.sleep(0.2)




"""
initialization of the application and user for telegram
init of the name of the correspondant with the file /boot/PEER.txt
declaration of the handler for the messages arrival
filtering of message coming from the correspondant
download of file .oga renamed .ogg

"""
GPIO.output(playLED, GPIO.HIGH)
motorON=True
api_id = 1105416
api_hash = '2bc41ff3e4672dd00f1efef7f52e0d87'
client =  TelegramClient('LoveCats', api_id, api_hash)
time.sleep(2)
client.connect()
if not  client.is_user_authorized():
    time.sleep(2)
    client.send_code_request(phone,force_sms=True)
    key = input('Enter key: ')
    print (key)
    asyncio.sleep(2)
    me = client.sign_in(phone=phone, code=key)
GPIO.output(playLED, GPIO.LOW)        
motorON=False
 

#print(peer)
#print(len(peer))
@client.on(events.NewMessage)
async def receiveTG(event):
    global toPlay
    #print(event.stringify())
    fromName = '@' + event.sender.username
    
    #only plays messages sent by your correpondant, if you want to play messages from everybody comment next line and uncomment the next next line
    if (event.media.document.mime_type  == 'audio/ogg') and (peer == fromName) :
    #if (event.media.document.mime_type == 'audio/ogg'): 
            ad = await client.download_media(event.media)
            #print('ok')
            toPlay =   toPlay + 1
            #print(toPlay)
            if toPlay == 0:
                #os.system('/usr/bin/cvlc --play-and-exit /home/pi/LB/lovebird.wav')
                sounds =  os.listdir('./sounds/')
                print(sounds)
                os.system('/usr/bin/cvlc --play-and-exit ./sounds/'+sounds[randrange(len(sounds))])
            name = '/home/pi/play' + str(toPlay) +  '.ogg'
            #print(name)
            os.rename(ad,name)
            await asyncio.sleep(0.2)
            #os.system('/usr/bin/cvlc --play-and-exit ' +  name)
           
"""
Main sequence (handler receiveTG), playTG, timeC, recTG, motor et heartBeat are excuted in parallel

"""
#os.system('/usr/bin/cvlc /home/pi/LB/lovebird.wav vlc://quit')
os.system('/usr/bin/cvlc --play-and-exit ./sounds/cat_purr.wav')

loop = asyncio.get_event_loop()
loop.create_task(recTG())
loop.create_task(playTG())
loop.create_task(timeC())
loop.create_task(motor())
loop.create_task(heartBeat())
loop.create_task(LEDStripe())
loop.run_forever()
client.run_until_disconnected()



