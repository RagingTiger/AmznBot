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
import math
import json
import slackclient
from amazon.api import AmazonAPI, AmazonSearch

# globals
STARTUP_MSG = '*AMZNBOT RESTARTING ... INITIAL PRICES @ {0}:*\n'
PRODUCT_MSG = ('*{0}*: `{1}` {2} | SalesRank: {3} | Availability: {4} '
               '|<{5}|link>\n'
               )
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


def get_config(configfile='.config.json'):
    """
    Read in JSON file, extract configuration values, and return dictionary
    """
    # try reading
    try:
        with open(configfile, 'r') as config:
            configdict = json.loads(config.read())
    except IOError:
        sys.exit('File {0} not found\n'.format(configfile))
    except ValueError:
        sys.exit('Format error in filter config file\n')

    # return dict
    return configdict


class AmznBot(object):
    def __init__(self):
        # create product dictionary
        self._prod = None

        # create slack instance pointer
        self._slk_instance = None

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

        # iterate over resulsts
        for i, product in enumerate(results):
            print '{0} - {1}'.format(i, self._format_msg(product))

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

        # get slack instance
        try:
            # get channel
            self._slk_chnl = self._cfg['channel']

            # get slack instance
            slk_toke = self._tokens['SLACK_API_TOKEN']
            self._slk_instance = slackclient.SlackClient(slk_toke)

        except KeyError:
            sys.exit('Check Slack token and/or config file :(')

        # initialize product dictionary
        self._prod = self._init_prod_dict(reporters)

        # report
        while True:
            try:
                # sleep period minutes
                if debug:
                    print 'Sleeping {0} seconds'.format(sleep_time)
                    self.items()
                else:
                    # post to slack
                    self._update_slack(reporters)

                time.sleep(sleep_time)

            except KeyboardInterrupt:
                sys.exit('\nShutting Down :)')

    def _post_slack(self, msg):
        # send message
        try:
            self._slk_instance.api_call('chat.postMessage',
                                        as_user='true',
                                        channel='#{0}'.format(self._slk_chnl),
                                        text=msg
                                        )
        except AttributeError:
            sys.exit('Slack instance was not initialized')

    def _format_msg(self, product):
        return PRODUCT_MSG.format(
                                   product.asin,
                                   product.formatted_price,
                                   product.title,
                                   product.sales_rank,
                                   product.availability,
                                   product.offer_url,
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
            itemids = self._cfg['itemid']
        except KeyError:
            sys.exit('Make sure config file has \'itemid\'')

        # get number of groups of 10 or less
        num_grp = int(math.ceil(len(itemids)/10.0))

        # now create list of item groups for 10 items or less
        item_ls = []
        for i in range(num_grp):
            item_ls.append(itemids[i*10:(i+1)*10])

        # now get results
        results = []
        for itemid_grp in item_ls:
            # format for request
            item_id_str = ','.join(itemid_grp)

            # get products
            product = self._amazon.lookup(ItemId=item_id_str)

            # make sure its a list
            if type(product) is not list:
                product = [product]

            # add to results
            results += product

        return results

    def _init_prod_dict(self, reporters):
        # local dictionary
        items = {}

        # loop over reporters
        for reporter in reporters:
            # get results
            results = reporter()

            # get iniital prices and format start up message
            starting_msg = STARTUP_MSG.format(time.asctime())
            for product in results:
                # get initial price
                items[product.asin] = product.formatted_price
                # create string for initial price
                starting_msg += self._format_msg(product)

        # post to slack
        self._post_slack(starting_msg)

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
            if type(results) is AmazonSearch or list:
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

    def _update_slack(self, reps):
        # get updates
        updates = [msg for msg in self._gen_update(reps) if msg is not '']

        # any updates, post to slack
        if any(updates):
            for slk_msg in updates:
                # create msg header
                hdr = 'Update: {0}'.format(time.asctime())
                slk_msg = '\n{0} {1} {2}\n{3}'.format('*|', hdr, '|*',
                                                      slk_msg
                                                      )
                # send message
                self._post_slack(slk_msg)


# executable
if __name__ == '__main__':

    # get fire
    import fire

    # pass class
    fire.Fire(AmznBot)
