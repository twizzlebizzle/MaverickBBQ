UPDATED:
Forked the original to allow the original to just output 2 temperatures only into the terminal (or import and pass them into another program)  I also didn't require any of the SQL/logging/etc

I also added a second program thats very basic that just allows me to log my temperatures to google drive.  (I run this every 1-5 mins via crontab)




# MaverickBBQ
Receives Wireless BBQ Thermometer Telegrams via RF-Receiver attached to Raspberry Pi

For further development, see:
https://github.com/WLANThermo/WLANThermo_v2/blob/master/software/usr/bin/maverick.py

Needs pigpiod (http://abyz.co.uk/rpi/pigpio/pigpiod.html) running to work
start with: pigpiod -x -1


usage: maverick.py [-h] [--html [HTML]] [--json [JSON]] [--sqlite [SQLITE]]
                   [--debug] [--pin PIN] [--nosync] [--fahrenheit] [--verbose]

Receives Wireless BBQ Thermometer Telegrams via RF-Receiver

optional arguments:
  -h, --help         show this help message and exit
  --html [HTML]      Writes a HTML file
  --json [JSON]      Writes a JSON file
  --sqlite [SQLITE]  Writes to an SQLite Database
  --debug            Generates additional debugging Output
  --pin PIN          Sets the Pin number
  --nosync           Always register new IDs
  --fahrenheit       Sets the Output to Fahrenheit
  --verbose          Print more Information to stdout

  Attach an 433,92MHz (different Receiver needed in the US, I think) receiver to a free GPIO (default=18 (BCM Numbering) and you are ready to go.
