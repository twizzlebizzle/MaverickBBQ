#!/usr/bin/env python3
# coding=utf-8

# maverick.py
# Receives Wireless BBQ Thermometer Telegrams via RF-Receiver
#
# (c) Martin Raatz, 2016
# Changed from fix offset to calculating the min and max length of the pulses based on Header AA99
# the pulswidth changes with every transmission on my ET733
# Checksum is same on ET732 and 733
#
# (c) Björn Schrader, 2015
# Code based on
# https://github.com/martinr63/OregonPi
# https://forums.adafruit.com/viewtopic.php?f=8&t=25414
# http://www.grillsportverein.de/forum/threads/wlan-maverick-bbq-thermometer-raspberry-pi-edition.232283/
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the "Software"), to deal in the Software without restriction, including without
# limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so, subject to the following
# conditions:

# The above copyright notice and this permission notice shall be included in all copies or substantial
# portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
# LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import time
import pigpio
import argparse
import copy
import queue
import threading
import math
import random
import string
import os

parser = argparse.ArgumentParser(description='Receives Wireless BBQ Thermometer Telegrams via RF-Receiver')
parser.add_argument('--debug', action='store_true', help='Generates additional debugging Output')
parser.add_argument('--pin', default=27, type=int, help='Sets the Pin number')
parser.add_argument('--nosync', action='store_true', help='Always register new IDs')
parser.add_argument('--noappend', action='store_true', help='Don´t append to file')

options = parser.parse_args()

#pintouse = 27

if options.debug:
   print(options)

# Globals für die Pinchange-Routine
oldtick = 0
oldlevel = None
state = 'wait'
packet = []
bit = 0
preamblecount = 0
traincount = 0
long_high = 0
long_low = 0
short_high = 0
short_low = 0
long_high_min = 0
long_low_min = 0
short_high_min = 0
short_low_min = 0
long_high_max = 0
long_low_max = 0
short_high_max = 0
short_low_max = 0

# Queue für fertige Pakete
packet_queue = queue.Queue()

# Liste der Sender für die Synchronisierung
unit_list = {}

def get_state (bitlist):
   # Wertet das Statusbye aus
   state = quart(bitlist[6*4:6*4+4]) << 2
   state |= quart(bitlist[7*4:7*4+4])
   if options.debug:
      print('state ', state)
   if state == 7:
      return 'init'
   elif state == 2:
      return 'default'
   else:
      print('Unknown state:', state)
      return 'unknown ' + str(state)

def bitlist_to_int (bitlist):
   out = 0
   for bit in bitlist:
      out = (out << 1) | bit
   return out

def bitlist_to_hexlist (bitlist):
   # Gibt eine Bitliste als Hex aus
   # nützlich zum debuggen
   out = []
   max = int(len(bitlist)/8)
   for i in range(max):
      out.append(hex(bitlist_to_int(bitlist[i*8:i*8+8])))
   return out

def quart (raw):
   # 4 zu 2 Umwandlung
   if raw == [0,1,0,1]:
      return 0
   elif raw == [0,1,1,0]:
      return 1
   elif raw == [1,0,0,1]:
      return 2
   elif raw == [1,0,1,0]:
      return 3
   else:
      print('Error in Quart conversion', raw)
      return -1

def calc_chksum(bitlist):
   # Berechnet die Checksumme anhand der Daten
   chksum_data = 0
   for i in range(12):
      chksum_data |= quart(bitlist[(6+i)*4:(6+i)*4+4]) << 22-2*i

   mask = 0x3331;
   chksum = 0x0;
   for i in range(24):
      if (chksum_data >> i) & 0x01:
         chksum ^= mask;
      msb = (mask >> 15) & 0x01
      mask = (mask << 1) & 0xFFFF
      if msb == 1:
         mask ^= 0x1021

   return chksum

def chksum(bitlist):
   # prüft die errechnete Checksumme gegen die übertragene
   # gibt das Ergebniss zurück, da es gleichzeitig die
   # zufällige ID des Senders ist

   chksum_data = calc_chksum(bitlist)

   chksum = 0
   for i in range(6):
      chksum |= quart(bitlist[(18+i)*4:((18+i)*4)+4]) << 14-i*2

#    if bitlist[24*4:(24*4)+4] == [0,0,0,1] or  bitlist[24*4:(24*4)+4] == [0,0,1,0]:
#       # to be verified, our ET-733 use the ET-732 code below
#       type = 'et733'
#       chksum  |= 0xFFFF & (quart(bitlist[25*4:(25*4)+4])&1) << 3
#       chksum  |= 0xFFFF & (quart(bitlist[25*4:(25*4)+4])&2) << 1
#       if  bitlist[24*4:(24*4)+4] == [0,0,1,0]:
#          chksum |= 0x02
#    else:
   type = 'et732'
   chksum  |= 0xFFFF & quart(bitlist[24*4:(24*4)+4]) << 2
   chksum  |= 0xFFFF & quart(bitlist[25*4:(25*4)+4])

   chksum = (chksum_data & 0xffff) ^ chksum
   return type, chksum

def get_data (bitlist):
   # Liest die Sensordaten aus dem Datenpaket aus
   sensor1 = 0
   sensor2 = 0

   for i in range(5):
      startbit = (4-i)*4
      sensor1 += quart(bitlist[startbit+32:startbit+32+4]) * ( 1 << (2*i))
      sensor2 += quart(bitlist[startbit+52:startbit+52+4]) * ( 1 << (2*i))

   if sensor1 == 0:
      sensor1 = ''
   else:
      sensor1 -= 532

   if sensor2 == 0:
      sensor2 = ''
   else:
      sensor2 -= 532

   return [sensor1, sensor2]

def pinchange(gpio, level, tick):
   # Interruptroutine
   # wertet das Funksignal aus
   global oldtick
   global oldlevel
   global state
   global packet
   global bit
   global packet_queue
   global preamblecount
   global traincount
   global long_high
   global long_low
   global short_high
   global short_low
   global long_high_min
   global long_low_min
   global short_high_min
   global short_low_min
   global long_high_max
   global long_low_max
   global short_high_max
   global short_low_max

   if oldlevel is None:
      oldlevel = level
   elif oldlevel == level:
      print('\nLost_Tick!')
   oldlevel = level
   duration = tick - oldtick
   oldtick = tick
   if duration >= 70:
       if options.debug and preamblecount > 0:
          print(duration, ":", level, " ",sep="", end="", flush=False)

       # wait ist der Wartestatus
       if state == 'wait' and level == 1:
          # lange Ruhe = vermutlich Preamble
          if 4000 < duration < 5500:
             state = 'preamble'
             preamblecount = 1
             if options.debug :
                 print('\npreamble', flush=True)
       elif state == 'preamble':
          if (380 < duration < 650):
             if preamblecount > 6:
                 state = 'train'
                 traincount = 1
                 if options.debug :
                     print('train', flush=True)
                 bit = 1
                 packet[:] = []
                 packet.append(1)
                 packet.append(0)
                 packet.append(1)
                 packet.append(0)
                 packet.append(1)
                 packet.append(0)
                 packet.append(1)
                 packet.append(0)

                 packet.append(1)
                 packet.append(0)
                 packet.append(0)
                 packet.append(1)
                 packet.append(1)
                 packet.append(0)
                 packet.append(0)
                 packet.append(1)

                 long_high = 0
                 long_low = duration
                 short_high = 0
                 short_low = 0
                 long_high_min = 0
                 long_low_min = duration
                 short_high_min = 0
                 short_low_min = 0
                 long_high_max = 0
                 long_low_max = duration
                 short_high_max = 0
                 short_low_max = 0
             else:
                 state = 'wait'
                 preamblecount = 0
                 if options.debug :
                     print('not enough long pulses', flush=True)
          elif (100 < duration < 350):
             state = 'preamble'
          elif 4000 < duration < 5500:
             preamblecount += 1
             if options.debug :
                 print('preamble',preamblecount, flush=True)
          else:
             state = 'wait'
             if options.debug :
                 print('wait', flush=True)
             preamblecount = 0
       elif state == 'train':
             traincount += 1
             if options.debug :
                 print('train',traincount, flush=True)
             #L h   L l   L h   L l   L h   L l   L h   L l   S h   S l   L h   S l   S h   L l   S h   S l   L h
             # 2     3     4     5     6     7     8     9     10    11    12    13    14    15    16    17    18
             if traincount in (2, 4, 6, 8, 12, 18):
                # Long high
                 long_high += duration
                 if long_high_min > duration :
                     long_high_min = duration
                 if long_high_max < duration :
                     long_high_min = duration
             elif traincount in (3, 5, 7, 9, 15):
                 long_low += duration
                 if long_low_min > duration :
                     long_low_min = duration
                 if long_low_max < duration :
                     long_low_min = duration
             elif traincount in (10, 14, 16) :
                 short_high += duration
                 if short_high_min > duration :
                     short_high_min = duration
                 if short_high_max < duration :
                     short_high_min = duration
             elif traincount in (11, 13, 17):
                 short_low += duration
                 if short_low_min > duration :
                     short_low_min = duration
                 if short_low_max < duration :
                     short_low_min = duration
                     
             if traincount == 18:
                 long_high /= 6
                 long_low /= 6
                 short_high /= 3
                 short_low /= 3
                 state = 'data'
                 
                 if long_high_min > long_high*0.75 :
                     long_high_min = long_high*0.75
                 if long_low_min > long_low*0.75 :
                     long_low_min = long_low*0.75
                 if short_high_min > short_high*0.2 :
                     short_high_min = short_high*0.2
                 if short_low_min > short_low*0.2 :
                     short_low_min = short_low*0.2

                 if long_high_max < long_high*1.4 :
                     long_high_max = long_high*1.4
                 if long_low_max < long_low*1.4 :
                     long_low_max = long_low*1.4
                 if short_high_max < short_high*1.25 :
                     short_high_max = short_high*1.25
                 if short_low_max < short_low*1.25 :
                     short_low_max = short_low*1.25

                 long_high_max = math.floor(long_high_max)
                 long_low_max = math.floor(long_low_max)
                 short_high_max = math.floor(short_high_max)
                 short_low_max = math.floor(short_low_max)

                 long_high_min = math.ceil(long_high_min)
                 long_low_min = math.ceil(long_low_min)
                 short_high_min = math.ceil(short_high_min)
                 short_low_min = math.ceil(short_low_min)

                 if options.debug :
                     print('long_high',round(long_high),"min",long_high_min,"max",long_high_max, flush=False)
                     print('short_high',round(short_high),"min",short_high_min,"max",short_high_max, flush=False)
                     print('long_low',round(long_low),"min",long_low_min,"max",long_low_max, flush=False)
                     print('short_low',round(short_low),"min",short_low_min,"max",short_low_max, flush=False)
                     print('data', flush=True)
                     
       elif state == 'data':
          if level == 0:
          # level == 0 heisst, es wurde ein HIGH-Impuls ausgewertet
             if (short_low_min <= duration <= short_low_max ):
                # kurzer LOW = 0 wiederholt
                if options.debug :
                    print ("SL    ",end="", flush=False)
                if bit == 0:
                   packet.append(0)
             elif (long_low_min <= duration <= long_low_max):
                # langes LOW = 0
                if options.debug :
                    print ("LL    ",end="", flush=False)
                packet.append(0)
                bit = 0
             else:
                # ungueltige Zeit
                state = 'wait'
                if options.debug :
                    print('wait ungueltig 0 bei ',len(packet), flush=True)
                preamblecount = 0
          else:
             if (short_high_min <= duration <= short_high_max):
                # kurzer HIGH = 1 wiederholt
                if options.debug :
                    print ("SH    ",end="", flush=False)
                if bit == 1:
                   packet.append(1)
             elif (long_high_min <= duration <= long_high_max):
                # langes HIGH = 1
                if options.debug :
                    print ("LH    ",end="", flush=False)
                packet.append(1)
                bit = 1
             else:
                # ungueltige Zeit
                state = 'wait'
                if options.debug :
                    print('wait ungueltig 1 bei ',len(packet), flush=True)
                preamblecount = 0
       if len(packet) == 104:
          # komplettes Paket empfangen
          if options.debug :
              print('wait - ready', flush=True)
          state = 'wait'
          preamblecount = 0
          packet_queue.put((time.time(),list(packet)))
          packet[:] = []

def updated(id, state, timestamp):
   # Prüft ob in den letzten 5s ein Paket vom gleichen Sender empfangen wurde
   global unit_list
   if id in unit_list:
      if (unit_list[id] + 5) < timestamp:
         unit_list[id] = timestamp
         if options.debug:
            print('units:', unit_list)
         return True
      else:
         return False
   else:
      if state == 'init' or options.nosync:
      # trägt neue Sender nur ein, wenn diese im Sync-Status sind, oder --nosync aktiv ist
         unit_list[id] = timestamp
         if options.debug:
            print('units:', unit_list)
         return True
      else:
         return False

def get_random_filename(filename):
    return filename + '_' + ''.join(random.choice(string.ascii_uppercase + string.digits) for x in range(12))
    
def worker():
   # Hauptthread, wertet empfangene Pakete aus und verteilt an die anderen Queues
   global unit_list
   unit = '°C'
   #while True: ADD 3 spaces
   item_time, item = packet_queue.get()
   type, chksum_is = chksum(item)
   temp1, temp2 = get_data(item)
   state = get_state(item)
   if updated(chksum_is, state, item_time):
      #print((temp1))
      #print(str(temp2))
      #print(time.strftime('%c:',time.localtime(item_time)), '-', chksum_is, '- Temperature 1:', temp1, unit, 'Temperature 2:', temp2, unit)
      if options.debug:
         print('raw:', item)
         print('hex', bitlist_to_hexlist(item))
   packet_queue.task_done()
   return(temp1,temp2)


pi = pigpio.pi() # connect to local Pi
oldtick = pi.get_current_tick()
pi.set_mode(options.pin, pigpio.INPUT)
pi.set_noise_filter(options.pin, 4500, 400000)
callback1 = pi.callback(options.pin, pigpio.EITHER_EDGE, pinchange)
start = time.time()


#def worker2():
 #worker1 = threading.Thread(target=worker)
 #worker1.daemon = True
 #worker1.start()

worker()
#while (1):
#   time.sleep(0.2)
#pi.stop()
