# minqlx - A Quake Live server administrator bot.
# Copyright (C) 2015 Mino <mino@minomino.org>

# This file is part of minqlx.

# minqlx is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# minqlx is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with minqlx. If not, see <http://www.gnu.org/licenses/>.

# news plugin by Joe Winett (abighairyspider)
#
# This plugin broadcasts messages generated on another
# server to the players on this server.  This is similar
# to the IRC plugin, but no IRC daemon required.
#
# This plugin doesn't use a secret so you'll need to make
# sure bad actors aren't sending UDP to you on this
# designated port, or it'll get sent to your players.
#
# OR OR OR, you might want that, I donno.
#
# This isn't supported.  Duh.
#
# cvars                   
#
# qlx_newsListenAddress   default(0.0.0.0:30960)
# qlx_newsNickname        default(cvar sv_hostname)  Display name of this server
# qlx_newsSecret          ** NOT USED **  You gotta firewall the port
# qlx_newsNetwork         other servers list - no default (<IPaddr:port>[,<IPaddr:port>])
# qlx_newsFormatMap       Format for Map Loaded - default("^1Loaded map ^7{}^1 on Server {}")
# qlx_newsFormatPlayerConnect       default( "^1Player ^7{}^1 connected to Server {}" )
# qlx_newsFormatPlayerDisconnect    default( "^1Player ^7{} ^1{} from Server {}" )
# qlx_newsFormatPlayerWonFFA        default( "^1Player ^7{}^1 won ^7{}^1 on Server {}" )
# Note: End game message for modes other than FFA munged together sloppily YMMV
# qlx_newsSkipBots        No broadcasts about bots connecting or disconnecting default(1)

import minqlx
import datetime
import time
import re
import pprint
import socket
import threading
import asyncio


class news(minqlx.Plugin):
    def __init__(self):
        super().__init__()

        self.set_cvar_once("qlx_newsListenAddress", "0.0.0.0:30960")
        self.set_cvar_once("qlx_newsNickname", self.get_cvar("sv_hostname"))        

        self.listen_address  = self.get_cvar("qlx_newsListenAddress")
        #self.secret          = self.get_cvar("qlx_newsSecret")
        self.nickname        = self.get_cvar("qlx_newsNickname")
        self.network         = self.parse_network( self.get_cvar("qlx_newsNetwork"))

        self.format_map      = self.get_cvar("qlx_newsFormatMap") or "^1Loaded map ^7{}^1 on Server {}"
        self.format_player_connect = self.get_cvar("qlx_newsFormatPlayerConnect") or  "^1Player ^7{}^1 connected to Server {}"
        self.format_player_disconnect = self.get_cvar("qlx_newsFormatPlayerDisconnect") or  "^1Player ^7{} ^1{} from Server {}"
        self.format_player_won_ffa = self.get_cvar("qlx_newsFormatPlayerWonFFA") or "^1Player ^7{}^1 won ^7{}^1 on Server {}"
        self.format_skip_bots = self.get_cvar("qlx_newsSkipBots") or True       
        
        #if not self.secret:
        #   self.logger.warning("qlx_newsSecret is required to send and receive broadcasts")

        if not self.network:
            self.logger.warning("qlx_newsNetwork is empty, no broadcasts will be sent")

        if not self.listen_address:
            self.logger.warning("qlx_newsListenAddress is empty or malformed, no broadcasts will be received")
        else:
            self.async_listener = SimpleAsyncListener( self.nickname, self.listen_address, self.handle_msg )
            self.async_listener.run()
        
        self.add_hook("game_end", self.handle_game_end)
        self.add_hook("unload", self.handle_unload)
        self.add_hook("map", self.handle_map)
        self.add_hook("player_connect", self.handle_player_connect, priority=minqlx.PRI_LOWEST)
        self.add_hook("player_disconnect", self.handle_player_disconnect, priority=minqlx.PRI_LOWEST)

    # parse a list like this 127.0.0.1:30961, 192.168.1.2, 192.168.1.2:30961
    def parse_network(self, network_string):
        network_members = []        
        for x in [y.strip() for y in network_string.split(',')]:
            match = re.search( "([^:]*)(:([0-9]*))?", x )
            if match:
                member = ( match.group(1), int(match.group(3)) or 30960 )
                network_members.append(member)
        return network_members
    
    def broadcast_msg( self, message_str ):
        sock = socket.socket( socket.AF_INET, socket.SOCK_DGRAM )   
        for udp_ip_port in self.network:
            sock.sendto( str.encode(message_str), udp_ip_port )

    def handle_msg(self, async_listener, msg_tuple ):
        if not msg_tuple:
            return
        
        msg = msg_tuple[0].decode()
        addr = msg_tuple[1]

        self.logger.info( "Msg [%s] from [%s]" % ( msg, addr[0] ) )
        minqlx.CHAT_CHANNEL.reply(msg)


# data members on handle game end
# {'ABORTED': False,
# 'CAPTURE_LIMIT': 8,
# 'EXIT_MSG': 'Fraglimit hit.',
# 'FACTORY': 'ffa',
# 'FACTORY_TITLE': 'Free For All',
# 'FIRST_SCORER': 'abighairyspider',
# 'FRAG_LIMIT': 1,
# 'GAME_LENGTH': 8,
# 'GAME_TYPE': 'FFA',
# 'INFECTED': 0,
# 'INSTAGIB': 0,
# 'LAST_LEAD_CHANGE_TIME': 8525,
# 'LAST_SCORER': 'abighairyspider',
# 'LAST_TEAMSCORER': 'none',
# 'MAP': 'hellsgate',
# 'MATCH_GUID': '30920e79-385b-401e-b570-78ac4e6e4400',
# 'MERCY_LIMIT': 0,
# 'QUADHOG': 0,
# 'RESTARTED': 0,
# 'ROUND_LIMIT': 10,
# 'SCORE_LIMIT': 150,
# 'SERVER_TITLE': 'My Quake Live Server',
# 'TIME_LIMIT': 15,
# 'TRAINING': 0,
# 'TSCORE0': 0,
# 'TSCORE1': 0}

    def handle_game_end(self, data):
       
        if data["ABORTED"]:
            return       
        
        if data["GAME_TYPE"] == "FFA":
            text = self.format_player_won_ffa.format(data['LAST_SCORER'],data['MAP'],self.nickname)
        else:                   
            text = "^1Player ^7" + data['LAST_SCORER']        

            if data['LAST_TEAMSCORER'] != "none":
                text += "^1 scored last for ^7" + data['LAST_TEAMSCORER'] + "^1 to win "
            else:
                text += "^1 won "

            text += "^7" + data['MAP'] + "^1 on " + self.nickname

        self.broadcast_msg(text)

    def handle_unload(self, plugin):
        if plugin == self.__class__.__name__ and self.async_listener:
            self.async_listener.stop()

    def handle_map(self, map, factory):
        self.broadcast_msg( self.format_map.format(map,self.nickname))

    def player_is_bot(self, player):
        return( str(player.steam_id)[0] == "9") #bot steam id's start with a 9 

    def handle_player_connect(self, player):
        if( self.format_skip_bots and self.player_is_bot(player)):
            return
        
        self.broadcast_msg( self.format_player_connect.format(player.name,self.nickname) )
 
    def handle_player_disconnect(self, player, reason):
        if( self.format_skip_bots and self.player_is_bot(player)):
            return
        
        if reason and reason[-1] not in ("?", "!", "."):
            reason = reason + "."
    
        self.broadcast_msg( self.format_player_disconnect.format(player.name, reason, self.nickname) )


# ====================================================================
#                        SIMPLE ASYNC LISTENER
#                  based on SimpleAsyncIrc in ./irc.py
# ====================================================================
class SimpleAsyncListener(threading.Thread):
    def __init__(self, nickname, listen_address, msg_handler, stop_event=threading.Event()):

        split_addr = listen_address.split(":")

        self.host = split_addr[0]
        self.port = int(split_addr[1]) if len(split_addr) > 1 else 30960
        self.nickname = nickname
        self.msg_handler = msg_handler
        self.stop_event = stop_event

        super().__init__()

        self._lock = threading.Lock()          
        
   
    def listener(self):
        logger = minqlx.get_logger("news")   
        
        while not self.stop_event.is_set():
            try:
                sock = socket.socket( socket.AF_INET, socket.SOCK_DGRAM )   
                sock.bind( (self.host, self.port)  )   
                logger.info( "Listening on %s:%s" % sock.getsockname() )     
                while not self.stop_event.is_set():
                    msg_tuple = sock.recvfrom(1024) 
                    if msg_tuple[0]:
                        self.msg_handler( self, msg_tuple )
                sock.close()
                logger.info( "Listener Stopped" )     

            except Exception:
                minqlx.log_exception()

    def run(self):    
        logger = minqlx.get_logger("news")   
        logger.debug("listener thread starting")

        self.news_thread = threading.Thread(target=self.listener)
        self.news_thread.name = "newsListener"
        self.news_thread.daemon = True
        self.news_thread.start()



    def stop(self):
        self.stop_event.set()

