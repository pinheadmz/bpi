import requests
import pyqrcode
import json

import os, sys

import curses
import atexit
import time

### default endpoints, not using any API key
# testnet
nodeurl = "http://127.0.0.1:18332/"
wallurl = "http://127.0.0.1:18334/wallet/primary/"
# main
#nodeurl = "http://127.0.0.1:8332/"
#wallurl = "http://127.0.0.1:8334/wallet/primary/"

### set up some functions to get data from bcoin node & wallet servers
### these functions are equivalent to using cURL from the command line
### the Python requests package makes this super easy for us
def getInfo():
  return requests.get(nodeurl).json()

def getAddress():
  params = {"account":"default"}
  return requests.post(wallurl + 'address', json=params).json()

def getBalance():
  return requests.get(wallurl + 'balance?account=default').json()

### read the JSON files from disk and keep the last 20 in memory
# should be the same directory used in the Javascript program (~/blocks on Raspberry Pi)
BLOCKS_DIR = os.path.expanduser('~') + '/blocks/'
TXS_DIR = os.path.expanduser('~') + '/txs/'
# global variable to store all the block and tx details
BLOCKS = {}
# generic function to load any directory of JSON files into any object passed in
def readFiles(dict, dir):
  files = [files for (dirpath, dirnames, files) in os.walk(dir)][0]
  for index in files:
    try:
      with open (dir + str(index)) as file:
        dict[index] = json.load(file)
    except:
      return False
    # sort list by index (file name)
    sortedDictKeys = sorted(dict)
    # only keep last 20 in memory
    if len(sortedDictKeys) > 20:
      del dict[sortedDictKeys[0]]

# check for new txs
def checkTXs():
  txs = {}
  try:
    readFiles(txs, TXS_DIR)
  except:
    return False
  for hash, tx in txs.items():
    # flash notification in top right corner for 5 seconds (or left corner if window is too narrow)
    col = MAXYX[1] - 50 if MAXYX[1] > 50 else 0
    stdscr.addstr(0, col, "  ***  New Transaction!  *** ", curses.A_REVERSE)
    # display receiving addresses and their amounts
    line = 1
    total = 0
    for detail in tx['details']:
      amt = detail['value'] / 100000000.0
      total += amt
      stdscr.addstr(line, col, str(amt) + " " + str(detail['address']), curses.A_REVERSE)
      line += 1
    stdscr.addstr(line, col, "TOTAL: " + str(total), curses.A_REVERSE)
    hideCursor()
    stdscr.refresh()
    # remove tx file so we only notify once
    os.remove(TXS_DIR + hash)
    time.sleep(5)

### calculate cycle progress as % and countdown integer given current blockchain height
def getDiff(height):
  return {"percent": (height % 2016 / 2016.0) * 100, "countdown": 2016 - (height % 2016)}
def getHalf(height):
  return {"percent": (height % 210000 / 210000.0 ) * 100, "countdown": 210000 - (height % 210000)}

### print the text info display
def printInfo(info, balance):
  if MAXYX[0] < 9:
    stdscr.erase()
    stdscr.addstr(0, 0, "Window too small!")
    stdscr.refresh()
    return False

  # pull the relevant bits from the data
  progress = info['chain']['progress']
  latestHeight = info['chain']['height']
  latestHash = info['chain']['tip']
  confbal = balance['confirmed']
  unconfbal = balance['unconfirmed']
  # print it to the screen
  stdscr.erase()
  stdscr.addstr(0, 0, "Progress: " + str(int(progress*100000000)/1000000.0) + "%")
  stdscr.addstr(1, 0, "Height: " + str(latestHeight))
  stdscr.addstr(2, 0, "Hash: " + str(latestHash))
  stdscr.addstr(3, 0, "Confirmed balance: " + str(confbal / 100000000.0))
  stdscr.addstr(4, 0, "Unconfirmed balance: " + str(unconfbal / 100000000.0))
  stdscr.addstr(5, 0, "Window size: " + str(WINDOW / 60) + " min")

  edge = drawBlockchain()
  drawMeters(latestHeight, edge)

  # print menu on bottom
  menu = "[Q]uit   [D]eposit [+/-]Zoom"
  stdscr.addstr(MAXYX[0]-1, 0, menu)
  stdscr.refresh()

### draw the recent blockchain and return the last row used in the display
WINDOW = 30 * 60 # total seconds across width of screen
def drawBlockchain():
  if MAXYX[0] < 40:
    axis = 6
    altUpDown = False
  else:
    axis = 20
    altUpDown = True

  secondsPerCol = WINDOW/MAXYX[1]
  stdscr.addstr(axis, 0, "[" + "-" * (MAXYX[1]-2) + "]")
  now = int(time.time())
  down = True  
  edge = axis + 1
  for index, block in BLOCKS.items():
    secondsAgo = now - block['time']
    
    if secondsAgo < WINDOW:
      top = axis if down else axis-15
      col = MAXYX[1] - (secondsAgo / secondsPerCol) - 9
      if col > 0:
        stdscr.addstr(axis, col, "|")
        stdscr.addstr(top+1, col, "#" + str(index))
        if MAXYX[0] > 21:
          stdscr.addstr(top+2, col, "Hash:")
          for i in range(8):
            stdscr.addstr(top+3+i, col+1, block['hash'][i*8:i*8+8])
          stdscr.addstr(top+11, col, "TXs:")
          stdscr.addstr(top+12, col+1, str("{:,}".format(block['totalTX'])))
          stdscr.addstr(top+13, col, "Age:")
          stdscr.addstr(top+14, col+1, str(secondsAgo/60) + ":" + str(secondsAgo%60).zfill(2))
          if altUpDown:
            down = not down
          edge = axis+14
  return edge

### draw progress bars
def drawMeters(height, top):
  colsPerPercent = (MAXYX[1]-2)/100
  if MAXYX[0] > (top + 4):
    diff = getDiff(height)
    stdscr.addstr(top+2, 0, "Next difficulty adjustment: " + str(diff['countdown']) + " blocks" )
    stdscr.addstr(top+3, 0, "[" + "-" * (MAXYX[1]-2) + "]")
    for i in range(int(colsPerPercent * diff['percent'])):
      stdscr.addch(top+3, i+1, curses.ACS_CKBOARD)
  if MAXYX[0] > (top + 7):
    half = getHalf(height)
    stdscr.addstr(top+5, 0, "Next subsidy halvening: " + str(half['countdown']) + " blocks" )
    stdscr.addstr(top+6, 0, "[" + "-" * (MAXYX[1]-2) + "]")
    for i in range(int(colsPerPercent * half['percent'])):
      stdscr.addch(top+6, i+1, curses.ACS_CKBOARD)

### display address and QR code
def displayAddr():
  addr = getAddress()['address']
  code = pyqrcode.create(addr, 'M', version=3).terminal(quiet_zone=1)
  
  # switch back to terminal
  endCurses()
  # display QR code
  os.system('clear')
  print addr
  print
  print code
  print
  raw_input("Press Enter to continue...")
  # switch back to our curses UI
  startCurses()

### start the curses text-based terminal interface
REFRESH = 1 # refresh rate in seconds
MAXYX = None
stdscr = None
def startCurses():
  global stdscr, MAXYX
  stdscr = curses.initscr()
  #curses.noecho()
  curses.halfdelay(REFRESH * 10) # blocking value is x 0.1 seconds
  MAXYX = stdscr.getmaxyx() # store window dimensions
startCurses()
def endCurses():
  curses.echo()
  curses.nocbreak()
  curses.endwin()

### automatically cleanup curses settings on exit
def cleanup():
  endCurses()
  os.system('clear')
  print "bye!"
atexit.register(cleanup)

### stash cursor in the bottom right corner
def hideCursor():
  stdscr.addstr(MAXYX[0]-1, MAXYX[1]-1, "")

### check for keyboard input -- also serves as the pause between REFRESH cycles
def checkKeyIn():
  global WINDOW, MAXYX
  keyNum = stdscr.getch()
  if keyNum == curses.KEY_RESIZE:
    MAXYX = stdscr.getmaxyx()
    return False

  if keyNum == -1:
    return False
  else:
    key = chr(keyNum)
  if key in ("q", "Q"):
    sys.exit()
  if key in ("d", "D"):
    displayAddr()
  if key in ("-"):
    WINDOW += 10 * 60
  if key in ("+"):
    WINDOW -= 10 * 60
    if WINDOW < 10 * 60:
      WINDOW = 10 * 60

### the main loop!
os.system('clear')
while True:
  # read block headers from files
  readFiles(BLOCKS, BLOCKS_DIR)
  checkTXs()
  # get data from servers
  info = getInfo()
  balance = getBalance()
  # draw!
  printInfo(info, balance)
  hideCursor()
  checkKeyIn()
