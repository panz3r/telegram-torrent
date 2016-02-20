#!/usr/bin/env python2
#-*- coding: utf-8 -*-

import sys
import os
import logging
import telepot
import json
from optparse import OptionParser
from telepot.delegate import per_chat_id, create_open


# Logging configuration constants
LOG_FILE = '/var/log/deluge-telegram.log'
LOG_FORMAT = '[%(levelname)-8s] %(asctime)-15s %(message)s'

# Bot configuration constants
CONFIG_FILE = '/etc/deluge-telegram/setting.json'


class DelugeAgent:
    """ Deluge Agent

        Torrent management functions for Deluge daemon
    """
    def deluge_cmd(self, command, target=""):
        logger.info('Command {} launched with target {}...'.format(command, target))
        return os.popen("deluge-console {} {}".format(command, target)).read()

    def filterCompletedList(self, result, active_only=False):
        outString = ''
        resultlist = result.split('\n \n')

        entry_dict = {}
        completed_dict = {}

        for entry in resultlist:
            title = entry[entry.index('Name:')+6:entry.index('ID:')-1]

            logger.debug('Entry title: {}'.format(title))

            if 'State: Paused' in entry:
                status = 'Paused'
            elif 'State: Downloading' in entry:
                status = 'Downloading'
            elif 'State: Seeding' in entry:
                status = 'Seeding'
            else:
                status = 'Unknown'

            entry_id = entry[entry.index('ID:')+4:entry.index('State:')-1]

            progress = ''
            ratio = ''
            if status == 'Seeding' or status == 'Paused':
                completed_dict[title] = entry_id
                ratio = entry[entry.index('Ratio:')+7:entry.index('Ratio:')+12]
            elif status == 'Downloading':
                progress = entry[entry.index('Progress:')+10:entry.index('% [')+1]

            if status != 'Paused':
                entry_dict[title] = entry_id

            if active_only and status not in ['Seeding', 'Downloading']:
                logger.debug('Entry skipped because of Active filter')
            else:
                outString += 'Title: '+title+'\n' + 'Status: ' + status

                if progress:
                    outString += ' ({}%)\n'.format(progress)
                elif ratio:
                    outString += ' ({})\n'.format(ratio)

                outString += '\n'

        logger.debug("Active Entry set: {}".format(entry_dict))
        logger.debug("Complete Entry set: {}".format(completed_dict))

        return outString, entry_dict, completed_dict

    def list_items(self):
        return self.deluge_cmd("info")

    def add_item(self, link):
        return self.deluge_cmd('add', link)

    def pause_item(self, item_id):
        return self.deluge_cmd('pause', item_id)

    def resume_item(self, item_id):
        return self.deluge_cmd('resume', item_id)

    def remove_item(self, item_id):
        return self.deluge_cmd('del', item_id)


################################################################################
#
# Main Torrenter
#
#  Messange Handler for Telegram Bot
#
class Torrenter(telepot.helper.ChatHandler):
    YES = 'OK'
    NO = 'NO'
    MENU0 = 'Home'
    MENU2 = 'Progress'
    MENU4 = 'Add'

    MENU5 = 'Show all'
    MENU6 = 'Pause item'
    MENU7 = 'Remove item'
    MENU8 = 'Resume item'

    MENU2_0 = 'Show all (Active and Inactive)'
    MENU2_1 = 'Clear Completed'

    GREETING = "How can I help you?"
    ERROR_PERMISSION_DENIED = "Permission denied"

    mode = ''
    entry_set = {}
    completed_set = {}

    def __init__(self, seed_tuple, timeout):
        super(Torrenter, self).__init__(seed_tuple, timeout)
        self.agent = self.create_agent(AGENT_TYPE)

    @staticmethod
    def create_agent(agent_type):
        logger.info("Started with agent of type '{}'".format(agent_type))

        if agent_type == 'deluge':
            return DelugeAgent()

        raise "Invalid agent type {}".format(agent_type)

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

    def menu(self):
        self.mode = ''
        self.message_with_keyboard(self.GREETING, [self.MENU4, self.MENU2])

    def main_menu(self, message):
        self.message_with_keyboard(message, [self.MENU2, self.MENU0])

    def yes_or_no(self, comment):
        show_keyboard = {'keyboard': [[self.YES, self.NO], [self.MENU0]], 'one_time_keyboard': True}
        self.sender.sendMessage(comment, reply_markup=show_keyboard)

    def message_or_cancel(self, message):
        self.message_with_keyboard(message, [self.MENU0])

    def message_with_set(self, message, answer_set):
        answer_set.append(self.MENU0)
        self.message_with_keyboard(message, answer_set)

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

        result = self.agent.list_items()
        if not result:
            logger.info('No results...')
            self.sender.sendMessage('Nothing found.')
            self.menu()
            return

        outString, entry_set, completed_set = self.agent.filterCompletedList(result, active_only)

        self.entry_set = entry_set
        self.completed_set = completed_set

        action_list = []

        if active_only:
            action_list.append(self.MENU5)

        if len(self.entry_set) > 0:
            action_list.append(self.MENU6)

        if not active_only and len(self.completed_set) > 0:
            action_list.append(self.MENU8)
            action_list.append(self.MENU7)

        if not outString == '':
            logger.debug('Sending active item list...')
            self.message_with_set(outString, action_list)
        else:
            logger.debug('No active items found.')
            self.message_with_set('No active items found.', action_list)

        # if not active_only:
        #     self.mode = self.MENU2_1
        #     self.yes_or_no('Would you like to remove the completed items from the list?')
        # else:
        #     self.mode = self.MENU2_0
        #     self.yes_or_no('Would you like to see all items, even the inactive ones?')

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
            self.message_with_set('Which item do you want to pause?', self.entry_set.keys())
        else:
            logger.debug("Active items list is empty.")
            self.main_menu('All items are already paused')

    def show_resumable_list(self):
        logger.debug("show_resumable_list called...")
        if len(self.completed_set) > 0:
            logger.debug("Sending list of completed items")
            self.mode = self.MENU8
            self.message_with_set('Which item do you want to resume?', self.completed_set.keys())
        else:
            logger.debug("Completed items list is empty.")
            self.main_menu('No item to resume')

    def show_removable_list(self):
        logger.debug("show_removable_list called...")
        if len(self.completed_set) > 0:
            logger.debug("Sending list of completed items")
            self.mode = self.MENU7
            self.message_with_set('Which item do you want to remove?', self.completed_set.keys())
        else:
            logger.debug("Completed items list is empty.")
            self.main_menu('No item to remove')

    def tor_pause_item(self, command):
        self.mode = ''

        if command in self.entry_set:
            res = self.agent.pause_item(self.entry_set[command])
            logger.info("Command result: {}".format(res))
            self.main_menu('Ok')
        else:
            logger.info("Item not found.")
            self.main_menu('Item not found.')

    def tor_resume_item(self, command):
        self.mode = ''

        if command in self.completed_set:
            res = self.agent.resume_item(self.completed_set[command])
            logger.info("Command result: {}".format(res))
            self.main_menu('Ok')
        else:
            self.main_menu('Item not found.')

    def tor_remove_item(self, command):
        self.mode = ''

        if command in self.completed_set:
            res = self.agent.remove_item(self.completed_set[command])
            logger.info("Command result: {}".format(res))
            self.main_menu('Ok')
        else:
            self.main_menu('Item not found.')

    def tor_del_list(self, command):
        self.mode = ''
        if command == self.YES:
            self.sender.sendMessage('Cleaning up...')

            for id in self.completedlist:
                logger.info('Removing item with id={}'.format(id))
                self.agent.removeFromList(id)

            self.sender.sendMessage('Done')

        self.menu()

    def handle_command(self, command):
        logger.debug("command: {}, mode: {}".format(command, self.mode))
        self.sender.sendChatAction('typing')

        if command == self.MENU0:
            self.menu()

        elif command == self.MENU2:
            self.tor_show_list(True)

        elif self.mode == self.MENU2_0:
            self.show_full_list(command)

        elif self.mode == self.MENU2_1:  # Del Torrents
            self.tor_del_list(command)

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

        else:
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