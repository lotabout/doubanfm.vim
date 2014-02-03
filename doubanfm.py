#!/usr/bin/env python

import json
import requests
import subprocess
import multiprocessing
from multiprocessing import Process

class DoubanFM():
    """docstring for DoubanFM"""
    def __init__(self):
        self.logined = False
        self.song_list = []
        self.channel = 1
        self.cur_song = {'sid':''}
        self.proxy = None
        self.debug = True

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
        if self.debug:
            print "self.user_id = ", self.user_id
            print "self.token = ", self.token
            print "self.expire = ", self.expire
            print "self.logined = ", self.logined
        return True

    def changeChannel(self, channel):
        self.channel = channel
        if self.debug:
            print "self.channel = ", self.channel
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
        r = requests.get(url,params=payload,proxies=self.proxy)
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
        self.q_pro_name = multiprocessing.Queue()
        while True:
            cmd = self.queue.get()
            if cmd == 'start':
                song_url = self.douban.endCurSong()
                self.start_a_song(song_url['url'])
            elif cmd == 'end':
                self.stop_a_song()
                song_url = self.douban.endCurSong()
                self.start_a_song(song_url['url'])
            elif cmd == 'skip':
                self.stop_a_song()
                song_url = self.douban.skipCurrentSong()
                self.start_a_song(song_url['url'])
            elif cmd == 'quit':
                self.stop_a_song()
                self.douban.bye()
                break;
            elif cmd == 'pause_toggle':
                if self.pro:
                    self.pro.stdin.write(' ')
            else:
                print "control: Unknown command"


    def start_a_song(self, url):
        self.cur_play_thread = Process(target = self.playing, args=(url,))
        self.cur_play_thread.start()
        self.pro = self.q_pro_name.get()

    def stop_a_song(self):
        if self.pro:
            self.pro.terminate()
        self.cur_play_thread.terminate()
        self.cur_play_thread.join()
        self.cur_play_thread = None

    def playing(self, url):
        cmd = ['mplayer',url]
        pro = subprocess.Popen(cmd,stdin=subprocess.PIPE, stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.q_pro_name.put(pro)
        try:
            pro.communicate()
        except Exception, e:
            pro.terminate()
        self.queue.put('end')

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
