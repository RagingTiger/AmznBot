#!/usr/bin/env python

""""
Author: John D. Anderson
Email: jander43@vols.utk.edu
Description: Bot for using Amazon Product API
Usage:
    amznbot.py
    amznbot.py items
    amznbot.py report
    amznbot.py search
"""

# libs
import os
import sys
import time
import slackclient
from amazon.api import AmazonAPI, AmazonSearch

# globals
TOKENS = ['AWSAccessKeyId', 'AWSSecretKey', 'AWSAssociateTag',
          'SLACK_API_TOKEN']


# funcs
def get_toke(tokens='.tokens'):
    # create token dict
    tdict = {}

    # read in file and split
    try:
        with open(tokens, 'r') as toke_file:
            for line in toke_file:
                key, val = line.split('=')
                tdict[key] = val.strip()
    except IOError:
        for token in TOKENS:
            tdict[token] = os.environ.get(token)

    # return dict
    return tdict


def get_config(configfile='.config'):
    # config dict
    configdict = {}

    # open
    with open(configfile, 'r') as config:
        for line in config:
            key, val = line.split('=')
            configdict[key] = val.strip()

    # return dict
    return configdict


class AmznBot(object):
    def __init__(self):
        # create product dictionary
        self._prod = None

        # get config
        self._cfg = get_config()

        # get token and amazon API instanc
        self._tokens = get_toke()
        try:
            self._amazon = AmazonAPI(self._tokens['AWSAccessKeyId'],
                                     self._tokens['AWSSecretKey'],
                                     self._tokens['AWSAssociateTag'])
        except KeyError:
            sys.exit('Check Amazon tokens and try again :(')

    def search(self):
        results = self._get_search()

        for i, product in enumerate(results):
            print '{0}: \'{1}\''.format(product.formatted_price,
                                        product.title)

    def items(self):
        # get results
        results = self._get_items()

        # print or return
        for product in results:
            print '{0}: \'{1}\''.format(product.formatted_price,
                                        product.title)

    def report(self, items=None, search=None, period=1200, debug=None):
        # check period
        try:
            sleep_time = int(period)
        except ValueError:
            sys.exit('--period argument must be a number')

        # check args
        if not items and not search:
            sys.exit('Must provide at least one argument: items | search')

        # reporter list
        reporters = []

        if items:
            # append item reporter
            reporters.append(self._get_items)

        if search:
            # append search reporter
            reporters.append(self._get_search)

        # initialize product dictionary
        self._prod = self._init_prod_dict(reporters)

        # report
        while True:
            try:
                # post to slack
                self._post_slack(reporters)

                # sleep period minutes
                if debug:
                    print 'Sleeping {0} minutes'.format(sleep_time/60.0)
                time.sleep(sleep_time)

            except KeyboardInterrupt:
                sys.exit('\nShutting Down :)')

    def _format_msg(self, product):
        return '`{0}` {1} | <{2}|link>'.format(
                               product.formatted_price,
                               product.title,
                               product.offer_url
                               )

    def _get_search(self):
        # search items
        try:
            return self._amazon.search(Keywords=self._cfg['keywords'],
                                       SearchIndex=self._cfg['searchindex'])
        except KeyError:
            sys.exit('Make sure config file has \'keywords\' and \
                     \'searchindex\'')

    def _get_items(self):
        # check items
        try:
            return self._amazon.lookup(ItemId=self._cfg['itemid'])
        except KeyError:
            sys.exit('Make sure config file has \'itemid\'')

    def _init_prod_dict(self, reporters):
        # local dictionary
        items = {}

        # loop over reporters
        for reporter in reporters:
            # get results
            results = reporter()

            # format msg
            if type(results) is AmazonSearch:
                for product in results:
                    items[product.asin] = '$0.00'

            else:
                items[results.asin] = '$0.00'

        # leave
        return items

    def _gen_update(self, reporters):
        # loop over reporters
        for reporter in reporters:
            # get results
            results = reporter()

            # init slack message string
            slk_msg = ''

            # format msg
            if type(results) is AmazonSearch:
                for product in results:
                    if self._prod[product.asin] != product.formatted_price:
                        # create string for slack message
                        slk_msg += self._format_msg(product)

                        # update product dictionary
                        self._prod[product.asin] = product.formatted_price

            else:
                if self._prod[results.asin] != results.formatted_price:
                    # create string for slack message
                    slk_msg += self._format_msg(results)

                    # update product dictionary
                    self._prod[results.asin] = results.formatted_price

            yield slk_msg

    def _post_slack(self, reps):
        # get updates
        updates = [msg for msg in self._gen_update(reps) if msg is not '']

        # any updates
        if any(updates):
            # get slack object
            try:
                # get channel and token
                slk_chnl = self._cfg['channel']
                slk_toke = self._tokens['SLACK_API_TOKEN']

                # get slack instance
                slk_instance = slackclient.SlackClient(slk_toke)

            except KeyError:
                sys.exit('Check Slack token and/or config file :(')

            # post updates to slack
            for slk_msg in updates:
                # create msg header
                hdr = 'Update: {0}'.format(time.asctime())
                slk_msg = '\n{0} {1} {2}\n{3}'.format('*|', hdr, '|*',
                                                      slk_msg
                                                      )
                # send message
                slk_instance.api_call('chat.postMessage',
                                      as_user='true',
                                      channel='#{0}'.format(slk_chnl),
                                      text=slk_msg
                                      )


# executable
if __name__ == '__main__':

    # get fire
    import fire

    # pass class
    fire.Fire(AmznBot)
