import os
import logging


class BaseAgent:
    """ Base Agent

        Torrent management functions definition
    """
    def list_items(self):
        return {}

    def add_item(self, link):
        return ''

    def pause_item(self, item_id):
        return ''

    def resume_item(self, item_id):
        return ''

    def remove_item(self, item_id):
        return ''


class TestAgent(BaseAgent):
    """ Test Agent

        A mock implementation of Torrent management functions
    """
    def __init__(self):
        self.items = {}

    def list_items(self):
        return self.items

    def add_item(self, link):
        self.items[hash(link)] = {'title': link, 'status': 'Downloading', 'progress': '0.00', 'ratio': '0.333'}
        return 'Added.'

    def pause_item(self, item_id):
        self.items[item_id]['status'] = 'Paused'
        return 'Paused.'

    def resume_item(self, item_id):
        self.items[item_id]['status'] = 'Seeding'
        return 'Resumed.'

    def remove_item(self, item_id):
        self.items.pop(item_id)
        return 'Removed.'


class DelugeAgent(BaseAgent):
    """ Deluge Agent

        Torrent management functions for Deluge daemon
    """
    @staticmethod
    def deluge_cmd(command, target=""):
        logging.info('Command {} launched with target {}...'.format(command, target))
        return os.popen("deluge-console {} {}".format(command, target)).read()

    @staticmethod
    def parse_result(result):
        result_list = result.split('\n \n')

        entry_dict = {}

        for entry in result_list:
            logging.debug('Parsing Entry: {}'.format(entry))

            title = entry[entry.index('Name:')+6:entry.index('ID:')-1]
            entry_id = entry[entry.index('ID:')+4:entry.index('State:')-1]

            if 'State: Paused' in entry:
                status = 'Paused'
            elif 'State: Downloading' in entry:
                status = 'Downloading'
            elif 'State: Seeding' in entry:
                status = 'Seeding'
            else:
                status = 'Unknown'

            progress = ''
            ratio = ''
            if status in ['Seeding', 'Paused']:
                ratio = entry[entry.index('Ratio:')+7:entry.index('Ratio:')+12]
            elif status == 'Downloading':
                progress = entry[entry.index('Progress:')+10:entry.index('% [')+1]

            entry_dict[entry_id] = {'title': title, 'status': status, 'progress': progress, 'ratio': ratio}

        logging.debug("Entry set: {}".format(entry_dict))

        return entry_dict

    def list_items(self):
        result = self.deluge_cmd("info")

        if not result:
            logging.info('No results.')
            return {}

        return self.parse_result(result)

    def add_item(self, link):
        return self.deluge_cmd('add', link)

    def pause_item(self, item_id):
        return self.deluge_cmd('pause', item_id)

    def resume_item(self, item_id):
        return self.deluge_cmd('resume', item_id)

    def remove_item(self, item_id):
        return self.deluge_cmd('del', item_id)