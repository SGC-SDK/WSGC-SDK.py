# WSGC-SDK for Python
Implements of WebSocket SGC Client

# How to Setup

`pip install git+https://github.com/SGC-SDK/WSGC-SDK.py.git`

# Example

```py
import discord
from discord.ext import commands
import logging

from wsgc_sdk import WSGCClient

logging.basicConfig(level=logging.DEBUG)
bot = commands.Bot(command_prefix='ts!')

@bot.event
async def on_ready():
    print('OK READY')
    bot.wsgc_client = WSGCClient(bot)
    await bot.wsgc_client.connect()

@bot.event
async def on_wsgc_message(m):
    # ...

@bot.event
async def on_wsgc_event(m):
    # ...

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    # ...

bot.run('zuoruhiwwwwww.Anz00f.jaggj')
```