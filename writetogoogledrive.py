import maverick
import requests
import time

pushover_token = "[TOKEN HERE]"
pushover_user = "[USER KEY HERE]"
ifttt_key = '[IFTT API HERE]'


def pushtempstoifttt(datatopush):
   datatopush = datatopush[1:-1]
   datatopush = datatopush.split(",")
   r= requests.post('https://maker.ifttt.com/trigger/BBQ_log/with/key/'+ifttt_key, params={"value1":datatopush[0],"value2":datatopush[1],"value3":""})


def pushover_temp(notif):
   import http.client, urllib
   conn = http.client.HTTPSConnection("api.pushover.net:443")
   conn.request("POST", "/1/messages.json",
     urllib.parse.urlencode({
       "token": pushover_token,
       "user": pushover_user,
       "message": notif,
     }), { "Content-type": "application/x-www-form-urlencoded" })
   conn.getresponse()

pushtempstoifttt(str(maverick.worker()))

