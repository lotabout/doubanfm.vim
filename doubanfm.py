#!/usr/bin/env python

import requests
import subprocess
import multiprocessing
from multiprocessing import Process
import logging
import sys

class DoubanFM():
    """docstring for DoubanFM"""
    def __init__(self):
        self.logined = False
        self.song_list = []
        self.channel = 1
        self.cur_song = {'sid':''}
        self.proxy = None
        self.logger = logging.getLogger('DoubanFM')
        self.logger.addHandler(logging.StreamHandler(sys.stdout))
        self.logger.setLevel(logging.DEBUG)

    def login(self, email, passwd):
        url = 'http://www.douban.com/j/app/login'
        payload={'email':email,'password':passwd,'app_name':'radio_desktop_win','version':100}
        r = requests.post(url, data=payload, proxies = self.proxy)
        data = r.json()
        
        if data['err'] != 'ok':
            print 'login failed.'
            if self.debug:
                print 'in login(): request got \'err\''
            return False
        self.user_id = data['user_id']
        self.token = data['token']
        self.expire = data['expire']
        self.logined = True
        self.logger.debug("self.user_id = %s", self.user_id)
        self.logger.debug("self.token = %s", self.token)
        self.logger.debug("self.expire = %s", self.expire)
        self.logger.debug("self.logined = %s", self.logined)
        return True

    def changeChannel(self, channel):
        self.channel = channel
        self.logger.debug("self.channel = %s", self.channel)
        self.song_list = []

    def getChannels(self):
        url = "http://www.douban.com/j/app/radio/channels"
        self.r = requests.get(url, proxies = self.proxy)
        return self.r.json()['channels']
    
    def printChannels(self):
        self.channels = ''
        if not self.channels:
            self.channels = self.getChannels()
        for channel in self.channels:
            print '%s\t%s\t%s' % (channel['channel_id'], 
                    channel['name'],channel['name_en'])

    def getParams(self):
        """Generate parameter needed for report according to private memeber"""
        try:
            type = self.cur_song['type']
        except:
            type = 'n'
        if self.logined:
            params = {'app_name':'radio_desktop_win', 'version':100,
                    'user_id':self.user_id, 'expire':self.expire,
                    'token':self.token, 'type':type,
                    'sid':self.cur_song['sid'], 'channel':self.channel}
        else:
            params = {'app_name':'radio_desktop_win', 'version':100,
                    'type':type, 'sid':self.cur_song['sid'], 
                    'channel':self.channel}
        return params

    def sendMsg(self):
        url = 'http://www.douban.com/j/app/radio/people'
        payload = self.getParams()
        try: r = requests.get(url,params=payload,proxies=self.proxy)
        except: r = {}
        return r

    def getSongList(self):
        if self.cur_song['type'] in ['n', 'p']:
            r = self.sendMsg()
            return r.json()['song']
        else:
            return []

    def playNext(self):
        if len(self.song_list) == 0:
            self.cur_song['type'] = 'n'
            self.song_list.extend(self.getSongList())
        elif len(self.song_list) < 2:
            self.cur_song['type'] = 'p'
            self.song_list.extend(self.getSongList())
        else:
            self.sendMsg()
        song = self.song_list.pop(0)
        self.cur_song = song
        self.cur_song['type'] = 's'
        print('%s %s'%(song['artist'],song['title']))
        return song

    def skipCurrentSong(self):
        self.cur_song['type'] = 's'
        return self.playNext()

    def rateCurSong(self):
        self.cur_song['type'] = 'r'
        self.sendMsg()

    def unrateCurSong(self):
        self.cur_song['type'] = 'u'
        self.sendMsg()

    def endCurSong(self):
        self.cur_song['type'] = 'e'
        return self.playNext()

    def bye(self):
        self.cur_song['type'] = 'b'
        self.sendMsg()

class MusicPlayer():
    def __init__(self):
        self.queue = multiprocessing.Queue()
        self.douban = DoubanFM();
        self.logger = logging.getLogger('Music Player')
        self.logger.addHandler(logging.StreamHandler(sys.stdout))
        self.logger.setLevel(logging.DEBUG)
        #c = raw_input('channel:')
        c = 2
        self.douban.changeChannel(int(c))
        if c=='0':
            email = raw_input("email:") 
            import getpass
            password = getpass.getpass("password:") 
            if not DoubanFM.login(email,password):
                self.douban.changeChannel(1)

    def control(self):
        self.pro = None
        self.paused = False
        timeout = 0.25
        while True:
            try: cmd = self.queue.get(True, timeout)
            except: cmd = "no cmd"
            #print "control: get cmd: ", cmd
            if self.pro and self.pro.poll() is not None:
                # not Running
                self.logger.info("Not running")
                self.stop_a_song()
                song_url = self.douban.endCurSong()
                self.start_a_song(song_url['url'])

            if cmd == 'start':
                self.logger.debug('control: get cmd: %s', cmd)
                song_url = self.douban.endCurSong()
                self.start_a_song(song_url['url'])
            elif cmd == 'skip':
                self.logger.debug("control: get cmd: %s", cmd)
                self.stop_a_song()
                song_url = self.douban.skipCurrentSong()
                self.start_a_song(song_url['url'])
            elif cmd == 'quit':
                self.logger.debug("control: get cmd: %s", cmd)
                self.stop_a_song()
                self.douban.bye()
                break;
            elif cmd == 'pause_toggle':
                self.logger.debug("control: get cmd: %s", cmd)
                if self.pro:
                    self.logger.debug("pause_toggle: self.pro exists.")
                    self.pro.stdin.write(' ')
                    self.paused = not self.paused
            elif cmd == "no cmd":
                pass
            elif cmd == "stop":
                self.stop_a_song()
            else:
                self.logger.debug("control: Unknown command")


    def start_a_song(self, url):
        cmd = ['mplayer',url]
        self.pro = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                stdout=open('/dev/null'), stderr=open('/dev/null'))
        self.logger.debug("start_a_song: end")
        self.paused = False

    def stop_a_song(self):
        self.logger.debug("in: stop_a_song.")
        if self.pro and self.pro.poll() is None:
            self.logger.debug("stop_a_song: mplayer is running")
            try: 
                self.pro.stdin.write('q')
            except Exception, e: 
                self.pro.terminate()
            self.pro.wait()
        self.pro = None
        self.paused = False
        self.logger.debug("stop_a_song: end")

    def player_start(self):
        self.queue.put('start')
        self.ctrl = Process(target = self.control)
        self.ctrl.start()

    def player_stop(self):
        self.queue.put('quit')
        self.ctrl.join()

    def player_rate(self):
        self.douban.rateCurSong()

    def player_unrate(self):
        self.douban.unrateCurSong()

    def player_skip(self):
        self.queue.put('skip')

    def player_pause_toggle(self):
        self.queue.put('pause_toggle')

mc = MusicPlayer()
