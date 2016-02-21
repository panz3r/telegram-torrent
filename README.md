# Telegram Torrent

A simple Telegram Bot (https://telegram.org/blog/bot-revolution) written in Python that allows remote control over a 
locally installed BitTorrent client


Inspired by telegram-control-torrent (https://github.com/seungjuchoi/telegram-control-deluge)

## Supported BitTorrent client
-  Deluge (http://deluge-torrent.org)

## Dependencies
- Telepot (https://pypi.python.org/pypi/telepot)

## Configuration
The default.conf file contains all the required settings

- common
  - **token**: The Bot API token supplied by the BotFather after creating your Bot
  - **valid_users**: A list of the Telegram UserID allowed to interact with the Bot
  - **agent_type**:  The type of the agent that manages torrent