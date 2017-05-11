"""Tests for models.Subscriber.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from datetime import datetime
from random import randrange
import uuid

from django import test
from django.test import TestCase
import json
import pytz
from ccm.common import crdt
from endagaweb import models


class TestBase(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.user = models.User(username="km", email="k@m.com")
        cls.user.set_password('pw')
        cls.user.save()
        cls.user_profile = models.UserProfile.objects.get(user=cls.user)
        cls.network = cls.user_profile.network

        # Create a test client.
        cls.client = test.Client()

    @classmethod
    def tearDownClass(cls):
        cls.user.delete()
        cls.user_profile.delete()

    def tearDown(self):
        self.logout()

    @classmethod
    def add_sub(cls, imsi,
                ev_kind=None, ev_reason=None, ev_date=None,
                balance=0):
        sub = models.Subscriber.objects.create(
            imsi=imsi, network=cls.network, balance=balance)
        if ev_kind:
            if ev_date is None:
                ev_date = datetime.now(pytz.utc)
            ev = models.UsageEvent(
                subscriber=sub, network=cls.network, date=ev_date,
                kind=ev_kind, reason=ev_reason)
            ev.save()
        return sub

    @staticmethod
    def gen_crdt(delta):
        # CRDT updates with the same UUID are merged - the max values of
        # the P and N counters are taken - so we need to ensure the UUID
        # of each update is distinct.
        c = crdt.PNCounter(str(uuid.uuid4()))
        if delta > 0:
            c.increment(delta)
        elif delta < 0:
            c.decrement(-delta)
        return c

    @staticmethod
    def gen_imsi():
        return 'IMSI0%014d' % (randrange(1, 1e10), )

    @staticmethod
    def get_sub(imsi):
        return models.Subscriber.objects.get(imsi=imsi)

    def login(self):
        """Log the client in."""
        data = {
            'email': 'km',
            'password': 'pw'
        }
        self.client.post('/auth/', data)

    def logout(self):
        """Log the client out."""
        self.client.get('/logout')


class SubscriberBalanceTests(TestBase):
    """
    We can manage subscriber balances.
    """
    def test_sub_get_balance(self):
        """ Test the balance property. """
        bal = randrange(1, 1000)
        sub = self.add_sub(self.gen_imsi(),
                           balance=bal)
        self.assertEqual(sub.balance, bal)

    def test_sub_update_balance(self):
        """ Test that we can add credit to a subscriber. """
        bal = randrange(1, 1000)
        imsi = self.gen_imsi()
        self.add_sub(imsi, balance=bal)
        delta = randrange(1, 1000)
        c = self.gen_crdt(delta)
        models.Subscriber.update_balance(imsi, c)
        self.assertEqual(self.get_sub(imsi).balance, bal + delta)

    def test_sub_update_balance_negative(self):
        """ Test that we can subtract credit from a subscriber. """
        bal = randrange(1, 1000)
        imsi = self.gen_imsi()
        self.add_sub(imsi, balance=bal)
        delta = randrange(0, bal)
        c = self.gen_crdt(-delta)
        models.Subscriber.update_balance(imsi, c)
        self.assertEqual(self.get_sub(imsi).balance, bal - delta)

    def test_sub_change_balance(self):
        """ Test the change_balance class method. """
        bal = randrange(1, 1000)
        sub = self.add_sub(self.gen_imsi(),
                           balance=bal)
        delta = randrange(1, 1000)
        sub.change_balance(delta)
        self.assertEqual(sub.balance, bal + delta)

    def test_sub_balance_setting(self):
        """ Test the balance update fails if balance already set. """
        # works if balance is not yet used
        sub = self.add_sub(self.gen_imsi())
        bal = randrange(1, 1000)
        sub.balance = bal  # works since it's currently zero
        self.assertEqual(sub.balance, bal)
        # throws exception if balance already set
        with self.assertRaises(ValueError):
            sub.balance = randrange(1, 1000)


class ActiveSubscriberTests(TestBase):
    """
    We can identify outbound (in)active Subcribers.
    """
    def test_sub_sans_outbound_activity(self):
        """Use registration data if a sub has no outbound activity."""
        days = 90
        the_past = datetime(year=2014, month=8, day=10, tzinfo=pytz.utc)
        imsi = self.gen_imsi()
        sub = self.add_sub(imsi,
                           'Provisioned',
                           'Provisioned %s' % (imsi, ),
                           ev_date=the_past)
        outbound_inactives = self.network.get_outbound_inactive_subscribers(
            days)
        self.assertItemsEqual([sub], outbound_inactives)

    def test_sub_with_activity(self):
        """Active subs don't appear in inactive list."""
        days = 90
        imsi = self.gen_imsi()
        sub = self.add_sub(imsi,
                           'outside_sms', 'sms sent')
        outbound_inactives = self.network.get_outbound_inactive_subscribers(
            days)
        self.assertFalse(sub in outbound_inactives)


class SubscriberUITest(TestBase):
    """Testing that we can add User in the UI."""

    def test_subscriber(self):
        """Subscriber management page without login """
        self.logout()
        response = self.client.get('/dashboard/subscriber_management/subscriber')
        # Anonymous User can not see this page so returning  permission denied.
        self.assertEqual(302, response.status_code)

    def test_subscriber_auth(self):
        """Subscriber management page with valid logged in user """
        self.login()
        response = self.client.get('/dashboard/subscriber_management/subscriber')
        self.assertEqual(200, response.status_code)

    def test_post_subscriber(self):
        self.logout()
        data = {
            'category': "TestSim",
            'imsi_val[]': "IMSI19999000000000"
        }
        response = self.client.post('/dashboard/subscriber_management/categoryupdate', data)
        # Anonymous User can not see this page so returning  permission denied.
        self.assertEqual(302, response.status_code)

    def test_post_subscriber_auth(self):
        self.login()
        data = {
            'category': "TestSim",
            'imsi_val[]': "IMSI19999000000000"
        }
        response = self.client.post('/dashboard/subscriber_management/categoryupdate', data)
        self.assertEqual(200, response.status_code)

    def test_successful_post_subscriber_auth(self):
        """When subscriber update succeeds, we send a 'message' """
        self.login()
        data = {
            'category': "TestSim",
            'imsi_val[]': "IMSI19999000000000"
        }
        response = self.client.post('/dashboard/subscriber_management/categoryupdate', data)
        # We'll get back JSON (the page reload will be triggered in js).
        expected_response = {
            'message':"IMSI category update cannot happen"
        }
        self.assertEqual(expected_response, json.loads(response.content))