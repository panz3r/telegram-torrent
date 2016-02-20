# Deluge Telegram

A simple Telegram Bot (https://telegram.org/blog/bot-revolution) written in Python that allows remote control over a locally installed Deluge server (http://deluge-torrent.org)

Inspired by telegram-control-torrent (https://github.com/seungjuchoi/telegram-control-deluge)

## Dependencies
- Telepot (https://pypi.python.org/pypi/telepot)

## Configuration
The setting.json file contains all the required settings

- common
  - **token**: The Bot API token supplied by the BotFather after creating your Bot
  - **valid_users**: A list of the Telegram UserID allowed to interact with the Bot
  - **agent_type**:  The type of the agent that manages torrent

- for_transmission
  - **transmission_user**: The User that manages Transmission daemon
  - **transmission_password**: The Password to login User to Transmission daemon
  - **transmission_port**: The Port to communicate with Transmission daemon
