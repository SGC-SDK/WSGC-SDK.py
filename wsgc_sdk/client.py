import traceback
from typing import Type
import aiohttp
import asyncio
import ssl, pathlib
import os
import datetime
import discord
import json
import time
from discord.ext import commands

basedir = os.path.dirname(os.path.abspath(__file__))

ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
ca_bundle = f'{basedir}/cacert.pem'
ssl_context.load_verify_locations(ca_bundle)

class VirtualGuild:
    def __init__(self, bot, data):
        self.id = 0
        if 'SGC' in data['t']:
            self.id = 706905953320304772

class VirtualChannel:
    def __init__(self, bot, ws, data):
        self.id = 0
        if data['t'] == 'SGC_MESSAGE':
            self.id = 707158257818664991
        elif data['t'] == 'SGC_EVENT':
            self.id = 799184205316751391
        self.name = 'virtual-channel-object'
        self.guild = VirtualGuild(bot, data)
        self.msgtype = 0 if data['t']=='SGC_MESSAGE' else 1
        self.ws = ws
    
    async def send(self, d):
        await self.ws.send_json({
            't': 'SGC_MESSAGE' if self.msgtype==0 else 'SGC_EVENT',
            'd': json.loads(d)
        })

class VirtualMessage:
    def __init__(self, bot, ws, data, author):
        msg = data['d']
        self.content = msg
        self.author = author
        self.channel = VirtualChannel(bot, ws, data)
        self.guild = VirtualGuild(bot, data)

class VirtualContext:
    def __init__(self, bot, ws, data):
        fromData = data.get('f', {})
        author = None
        if fromData.get('id'):
            author = bot.get_user(int(fromData.get('id')))
        self.msgtype = 0 if data['t']=='SGC_MESSAGE' else 1
        self.ws = ws
        self.message = VirtualMessage(bot, ws, data, author)
        self.author = author
        self.created_at = datetime.datetime.utcnow()
        self.edited_at = None
        self.reference = None
        self.guild = VirtualGuild(bot, data)
        self.channel = VirtualChannel(bot, ws, data)
        self.content = data
    
    async def send(self, d):
        await self.ws.send_json({
            't': 'SGC_MESSAGE' if self.msgtype==0 else 'SGC_EVENT',
            'd': json.loads(d)
        })

class WSGCClient:

    def __is_bot__(self, a):
        return isinstance(a, discord.Client) or isinstance(a, commands.Bot) or isinstance(a, discord.AutoShardedClient) or isinstance(a, commands.AutoShardedBot)

    def __init__(self, bot):
        if not self.__is_bot__(bot):
            raise TypeError('bot is not Discord client')
        self.bot = bot
        self.ws = None
        self._session = aiohttp.ClientSession()
        self.latency = None
        self.gateway_url = 'wss://wsgc-gw1.cyberrex.jp/v1'
        self.bot_id:str = str(bot.user.id)

        self._listen_process_task = None
    
    @property
    def opened(self):
        if not self.ws:
            return False
        return not self.ws.closed
    
    @property
    def closed(self):
        if not self.ws:
            return True
        return self.ws.closed

    async def connect(self):
        if self.opened:
            raise ConnectionError('Already connected to WSGC Gateway.')
        self.ws = await self._session.ws_connect(self.gateway_url)
        await self.ws.send_json({
            't': 'REGISTER',
            'd': {
                'id': str(self.bot.user.id)
            }
        })
        self._listen_process_task = asyncio.create_task(self._listen_process())
        self.bot.dispatch('wsgc_ready')

    async def _listen_process(self):
        async for msg in self.ws:
            try:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    payload = msg.json()
                    self.bot.dispatch('wsgc_raw_response', payload)

                    if payload['t'] == 'HEARTBEAT':
                        d = payload['d']
                        remote_ts = d['ts']
                        cur_ts = time.time()
                        self.latency = cur_ts - remote_ts

                    if payload['t'] == 'SGC_MESSAGE':
                        ctx = VirtualContext(self.bot, self.ws, payload)
                        self.bot.dispatch('wsgc_message', ctx)
                    
                    if payload['t'] == 'SGC_EVENT':
                        ctx = VirtualContext(self.bot, self.ws, payload)
                        self.bot.dispatch('wsgc_event', ctx)
                    
                if msg.type == aiohttp.WSMsgType.ERROR:
                    # Reconnect
                    self.bot.dispatch('wsgc_disconnect')
                    asyncio.create_task(self._restart_listen_process())
                    return
                
            except Exception as e:
                print(traceback.format_exc())
    
    async def _restart_listen_process(self):
        if self._listen_process_task:
            # Stop current listening task
            self._listen_process_task.cancel()
            await asyncio.sleep(1)
            # Reconnect
            await self.connect()
            self.bot.dispatch('wsgc_resume')
    
    async def close(self):
        if self.opened:
            if self._listen_process_task:
                # Stop current listening task
                self._listen_process_task.cancel()
            await self.ws.send_json({
                't': 'CLOSE'
            })
            self.bot.dispatch('wsgc_disconnect')

    async def disconnect(self):
        await self.close()