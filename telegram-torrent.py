#!/usr/bin/env python
#-*- coding: utf-8 -*-

import sys
import logging
import json
import telepot

from optparse import OptionParser
from telepot.delegate import per_chat_id, create_open
from agents import TestAgent, DelugeAgent

# Logging configuration constants
LOG_FILE = '/var/log/deluge-telegram.log'
LOG_FORMAT = '[%(levelname)-8s] %(asctime)-15s %(message)s'

# Bot configuration constants
CONFIG_FILE = '/etc/deluge-telegram/default.conf'


class Torrenter(telepot.helper.ChatHandler):
    """
        Main Torrenter class

        Message handler for Telegram Bot
    """
    YES = 'OK'
    NO = 'NO'
    MENU0 = 'Home'
    MENU2 = 'Progress'
    MENU4 = 'Add'

    MENU5 = 'Show all'
    MENU6 = 'Pause item'
    MENU7 = 'Remove item'
    MENU8 = 'Resume item'

    GREETING = "How can I help you?"
    ERROR_PERMISSION_DENIED = "Permission denied"

    mode = ''

    entry_set = {}
    active_set = {}
    completed_set = {}

    def __init__(self, seed_tuple, timeout):
        super(Torrenter, self).__init__(seed_tuple, timeout)
        self.agent = self.create_agent(AGENT_TYPE)

    @staticmethod
    def create_agent(agent_type):
        logger.info("Started with agent of type '{}'".format(agent_type))

        if agent_type == 'deluge':
            return DelugeAgent()
        elif agent_type == 'test':
            return TestAgent()

        raise "Invalid agent type {}".format(agent_type)

    @staticmethod
    def filter_list(item_list):
        logger.info('Filtering list...')

        active_items = {k: v for k, v in item_list.items() if v['status'] in ['Downloading', 'Seeding']}
        completed_items = {k: v for k, v in item_list.items() if v['status'] in ['Seeding', 'Paused']}

        logger.debug('Active set: {}'.format(active_items))
        logger.debug('Completed set: {}'.format(completed_items))

        return active_items, completed_items

    @staticmethod
    def prepare_message(item_list):
        ret = ''

        for item in item_list:
            logger.debug('Item: {}'.format(item))

            ret += 'Title: {title}\nStatus: {status}'.format(**item)

            if item['status'] == 'Downloading':
                ret += ' ({progress})\n'.format(**item)
            else:
                ret += ' ({ratio})\n'.format(**item)

            ret += '\n'

        return ret

    def open(self, initial_msg, seed):
        content_type, chat_type, chat_id = telepot.glance2(initial_msg)
        logger.info("Initial Message (user:{}) (chat:{}) (type:{})".format(chat_id, chat_type, content_type))

    def message_with_keyboard(self, message, action_list):
        keyboard_items = []
        for item in action_list:
            keyboard_items.append([item])

        logger.debug("Keyboard items: {}".format(keyboard_items))

        show_keyboard = {'keyboard': keyboard_items, 'one_time_keyboard': True, 'resize_keyboard': True}
        self.sender.sendMessage(message, reply_markup=show_keyboard)

    def menu(self, message=GREETING):
        self.mode = ''
        self.message_with_keyboard(message, [self.MENU4, self.MENU2])

    def main_menu(self, message):
        self.message_with_keyboard(message, [self.MENU2, self.MENU0])

    def yes_or_no(self, comment):
        show_keyboard = {'keyboard': [[self.YES, self.NO], [self.MENU0]], 'one_time_keyboard': True}
        self.sender.sendMessage(comment, reply_markup=show_keyboard)

    def message_or_cancel(self, message):
        self.message_with_keyboard(message, [self.MENU0])

    def message_with_set(self, message, answer_set):
        item_list = []

        for k, v in answer_set.items():
            item_list.append(v['title'])

        item_list.append(self.MENU0)

        self.message_with_keyboard(message, item_list)

    def tor_ask_for_link(self):
        self.mode = self.MENU4
        self.message_or_cancel('Send me the link please')

    def tor_add_from_link(self, link):
        self.mode = ''
        self.sender.sendMessage('Link received, please wait...')

        response = self.agent.add_item(link)

        self.main_menu(response)

    def tor_show_list(self, active_only):
        self.mode = ''

        self.entry_set = self.agent.list_items()
        if not self.entry_set:
            logger.info('No results...')
            self.menu('Nothing found. Try to add something first')
            return

        self.active_set, self.completed_set = self.filter_list(self.entry_set)

        if active_only:
            out_string = self.prepare_message(self.active_set.values())
        else:
            out_string = self.prepare_message(self.entry_set.values())

        logger.debug('Result message: {}'.format(out_string))

        action_list = []

        if active_only:
            action_list.append(self.MENU5)

        if len(self.active_set) > 0:
            action_list.append(self.MENU6)

        if not active_only and len(self.completed_set) > 0:
            action_list.append(self.MENU8)
            action_list.append(self.MENU7)

        action_list.append(self.MENU0)

        if len(out_string) > 0:
            logger.debug('Sending active item list...')
            self.message_with_keyboard(out_string, action_list)
        else:
            logger.debug('No active items found.')
            self.message_with_keyboard('No active items found.', action_list)

    def show_full_list(self, command):
        if command == self.YES:
            self.tor_show_list(False)
        else:
            self.menu()

    def show_pausable_list(self):
        logger.debug("show_pausable_list called...")
        if len(self.entry_set) > 0:
            logger.debug("Sending list of active items")

            self.mode = self.MENU6
            self.message_with_set('Which item do you want to pause?', self.active_set)
        else:
            logger.debug("Active items list is empty.")
            self.main_menu('All items are already paused')

    def show_resumable_list(self):
        logger.debug("show_resumable_list called...")
        if len(self.completed_set) > 0:
            logger.debug("Sending list of completed items")
            self.mode = self.MENU8
            self.message_with_set('Which item do you want to resume?', self.completed_set)
        else:
            logger.debug("Completed items list is empty.")
            self.main_menu('No item to resume')

    def show_removable_list(self):
        logger.debug("show_removable_list called...")
        if len(self.completed_set) > 0:
            logger.debug("Sending list of completed items")
            self.mode = self.MENU7
            self.message_with_set('Which item do you want to remove?', self.completed_set)
        else:
            logger.debug("Completed items list is empty.")
            self.main_menu('No item to remove')

    @staticmethod
    def find_key_by_title(item_set, title):
        found_key = None

        for k, entry in item_set.items():
            if entry['title'] == title:
                found_key = k

        return found_key

    def tor_pause_item(self, command):
        self.mode = ''

        key_to_pause = self.find_key_by_title(self.active_set, command)

        if key_to_pause is not None:
            res = self.agent.pause_item(key_to_pause)
            logger.info("Command result: {}".format(res))
            self.main_menu('Ok')
        else:
            logger.info("Item not found.")
            self.main_menu('Item not found.')

    def tor_resume_item(self, command):
        self.mode = ''

        key_to_resume = self.find_key_by_title(self.completed_set, command)

        if key_to_resume is not None:
            res = self.agent.resume_item(key_to_resume)
            logger.info("Command result: {}".format(res))
            self.main_menu('Ok')
        else:
            self.main_menu('Item not found.')

    def tor_remove_item(self, command):
        self.mode = ''

        key_to_remove = self.find_key_by_title(self.completed_set, command)

        if key_to_remove is not None:
            res = self.agent.remove_item(key_to_remove)
            logger.info("Command result: {}".format(res))
            self.main_menu('Ok')
        else:
            self.main_menu('Item not found.')

    def auto_manage_torrent_links(self, message):
        logger.debug('Detecting if the message is a Torrent link...')
        if message.startswith('magnet:') or message.endswith('.torrent'):
            logger.debug('Message is a Torrent link and will be auto-managed.')
            self.mode = self.MENU4
            self.tor_add_from_link(message)
            return True

        logger.debug('Message is not a Torrent link.')
        return False

    def handle_command(self, command):
        logger.debug("command: {}, mode: {}".format(command, self.mode))
        self.sender.sendChatAction('typing')

        if command == self.MENU0:
            self.menu()

        elif command == self.MENU2:
            self.tor_show_list(True)

        elif command == self.MENU4:
            self.tor_ask_for_link()

        elif self.mode == self.MENU4:  # Get Link
            self.tor_add_from_link(command)

        elif command == self.MENU5:     # Show All
            self.tor_show_list(False)

        elif command == self.MENU6:     # Pause item
            self.show_pausable_list()

        elif self.mode == self.MENU6:   # Pause the item
            self.tor_pause_item(command)

        elif command == self.MENU8:     # Resume item
            self.show_resumable_list()

        elif self.mode == self.MENU8:
            self.tor_resume_item(command)

        elif command == self.MENU7:     # Remove item
            self.show_removable_list()

        elif self.mode == self.MENU7:
            self.tor_remove_item(command)

        elif not self.auto_manage_torrent_links(command):
            self.menu()

    def on_message(self, msg):
        content_type, chat_type, chat_id = telepot.glance2(msg)

        # Check ID
        if chat_id not in VALID_USERS:
            logger.warning("Permission Denied (user:{}) (chat:{})".format(chat_id, chat_type))
            self.sender.sendMessage(self.ERROR_PERMISSION_DENIED)
            return

        if content_type is 'text':
            cmd = msg['text']
            logger.info("Message received (user:{}) (chat:{}) (type:{}) (text:{})".format(chat_id, chat_type, content_type, cmd))
            self.handle_command(cmd)
            return
        else:
            logger.info("Message received (user:{}) (chat:{}) (type:{})".format(chat_id, chat_type, content_type))

        logger.error("Error: Command '{}' not recognized".format(msg))
        self.sender.sendMessage("I don't know what you mean...")

    def on_close(self, exception):
        pass


def setup_logging(log_level, printtostdout):
    global logger

    logging.basicConfig(filename=LOG_FILE, format=LOG_FORMAT)

    logger = logging.getLogger(__name__)
    logger.setLevel(log_level)

    if printtostdout:
        soh = logging.StreamHandler(sys.stdout)
        soh.setLevel(log_level)
        filelog = logging.getLogger()
        filelog.addHandler(soh)


def parse_config(filename):
    f = open(filename, 'r')
    js = json.loads(f.read())
    f.close()
    return js


def setup(config):
    global TOKEN
    global AGENT_TYPE
    global VALID_USERS

    TOKEN = config['common']['token']
    AGENT_TYPE = config['common']['agent_type']
    VALID_USERS = config['common']['valid_users']


parser = OptionParser('Test logging')
parser.add_option('-d', '--debug', type='string', help='Available levels are CRITICAL (3), ERROR (2), WARNING (1), INFO (0), DEBUG (-1)', default='INFO')
parser.add_option('-p', '--printtostdout', action='store_true', default=False, help='Print all log messages to stdout')
options, args = parser.parse_args()

try:
    loglevel = getattr(logging, options.debug)
except AttributeError:
    loglevel = {3: logging.CRITICAL,
                2: logging.ERROR,
                1: logging.WARNING,
                0: logging.INFO,
                -1: logging.DEBUG,
                }[int(options.debug)]

setup_logging(loglevel, options.printtostdout)

logger.info('Starting up...')

config_json = parse_config(CONFIG_FILE)
if not bool(config_json):
    logger.error("Err: Setting file is not found")
    exit()

setup(config_json)

bot = telepot.DelegatorBot(TOKEN, [
    (per_chat_id(), create_open(Torrenter, timeout=120)),
])

logger.info('Ready to ROCK!')

bot.notifyOnMessage(run_forever=True)