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

import datetime as datetime2
import json
import uuid
from datetime import datetime
from random import randrange

import pytz
from django import test
from django.test import TestCase

from ccm.common import crdt
from endagaweb import models
from endagaweb import tasks


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
                balance=0, state='active'):
        sub = models.Subscriber.objects.create(
            imsi=imsi, network=cls.network, balance=balance, state=state)
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
        return 'IMSI0%014d' % (randrange(1, 1e10),)

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
                           'Provisioned %s' % (imsi,),
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


class SubscriberValidityTests(TestBase):
    """
    We can change subscriber state depending on its validity and can deactivate
    after completion of threshold 
    """

    def setup_the_env(self, days=7):
        imsi = self.gen_imsi()
        self.subscriber = self.add_sub(imsi, balance=100, state='active')
        # Set expired validity for the number
        validity = datetime.now(pytz.utc) - datetime2.timedelta(days=days)
        self.bts = models.BTS(uuid="133222", nickname="test-bts-name!",
                              inbound_url="http://localhost/133222/test",
                              network=self.network)
        self.bts.save()
        self.number = models.Number(
            number='5559234', state="inuse", network=self.bts.network,
            kind="number.nexmo.monthly", subscriber=self.subscriber,
            valid_through=validity)
        net = models.Network.objects.get(id=self.bts.network.id)
        net.sub_vacuum_enabled = True
        net.sub_vacuum_inactive_days = 180
        net.sub_vacuum_grace_days = 30
        self.number.save()
        net.save()

    def test_subscriber_inactive(self):
        # Set subscriber's validity 7 days earlier then current date
        self.setup_the_env(days=7)
        tasks.subscriber_validity_state()
        subscriber = models.Subscriber.objects.get(id=self.subscriber.id)
        self.assertEqual(subscriber.state, 'inactive')

    def test_subscriber_expired(self):
        # Set subscriber's validity more than threshold days
        days = self.network.sub_vacuum_inactive_days
        self.setup_the_env(days=days + 1)
        tasks.subscriber_validity_state()
        subscriber = models.Subscriber.objects.get(id=self.subscriber.id)
        self.assertEqual(subscriber.state, 'first_expire')

    def test_subscriber_recycle(self):
        # Set subscriber's validity days more than grace period and
        # threshold days
        days = self.network.sub_vacuum_inactive_days + self.network.sub_vacuum_grace_days
        self.setup_the_env(days=days + 1)
        tasks.subscriber_validity_state()
        subscriber = models.Subscriber.objects.get(id=self.subscriber.id)
        self.assertEqual(subscriber.state, 'recycle')


class BlockUnblockSubscriberTests(TestBase):
    """
    We can block subscriber on three consecutive invalid activities
    """
    def setup_the_env(self):
        imsi = self.gen_imsi()
        self.subscriber = self.add_sub(imsi, balance=100, state='active')
        self.number = models.Number(
            number='5559234', state="inuse", network=self.subscriber.network,
            kind="number.nexmo.monthly", subscriber=self.subscriber)
        net = models.Network.objects.get(id=self.subscriber.network.id)
        self.number.save()
        net.save()

    def test_generate_an_event(self, subscriber_id=None,
                                    kind='error_call'):
        now = datetime.now(pytz.utc)
        self.setup_the_env()
        if subscriber_id is None:
            subscriber_id = self.subscriber.id

        event = models.UsageEvent.objects.create(
            subscriber_id=subscriber_id, date=now, kind=kind,
            reason='some reason (''error_call)')
        event.save()

    def test_subscriber_is_block(self):
        """
        Set subscriber to Block state if 'consecutive' 3 error_call/sms UEs
        :return: 
        """

        # First invalid UE
        self.test_generate_an_event(kind='error_sms')
        subscriber = models.Subscriber.objects.get(id=self.subscriber.id)
        self.assertEqual(subscriber.is_blocked, False)

        # Interrupted consecutive count with valid UE
        self.test_generate_an_event(subscriber_id=subscriber.id,
                                         kind='sms')
        subscriber = models.Subscriber.objects.get(id=subscriber.id)
        self.assertEqual(subscriber.is_blocked, False)
        # Removed if it exists
        invalid_event = models.SubscriberInvalidEvents.objects.filter(
            subscriber=subscriber).exists()
        self.assertEqual(invalid_event, False)

        # First invalid UE again
        self.test_generate_an_event(subscriber_id=subscriber.id,
                                         kind='error_sms')
        subscriber = models.Subscriber.objects.get(id=subscriber.id)
        self.assertEqual(subscriber.is_blocked, False)

        # Second invalid UE
        self.test_generate_an_event(subscriber_id=subscriber.id,
                                         kind='error_call')
        subscriber = models.Subscriber.objects.get(id=subscriber.id)
        self.assertEqual(subscriber.is_blocked, False)

        # Third consecutive invalid UE again
        self.test_generate_an_event(subscriber_id=subscriber.id,
                                         kind='error_sms')
        subscriber = models.Subscriber.objects.get(id=subscriber.id)
        self.assertEqual(subscriber.is_blocked, True)


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
            'category': "Subscriber",
            'imsi_val[]': self.gen_imsi()
        }
        response = self.client.post('/dashboard/subscriber_management/categoryupdate', data)
        # Anonymous User can not see this page so returning  permission denied.
        self.assertEqual(302, response.status_code)

    def test_post_subscriber_auth(self):
        self.login()
        data = {
            'category': "Subscriber",
            'imsi_val[]': self.gen_imsi()
        }
        response = self.client.post('/dashboard/subscriber_management/categoryupdate', data)
        self.assertEqual(200, response.status_code)

    def test_successful_post_subscriber_auth(self):
        """When subscriber update succeeds, we send a 'message' """
        self.login()
        imsi = self.gen_imsi()
        bal = randrange(1, 1000)
        self.add_sub(imsi, balance=bal)
        data = {
            'category': "Subscriber",
            'imsi_val[]': imsi
        }
        response = self.client.post('/dashboard/subscriber_management/categoryupdate', data)
        # We'll get back JSON (the page reload will be triggered in js).
        expected_response = {
            'message':"IMSI category updated successfully"
        }
        self.assertEqual(expected_response, json.loads(response.content))
        self.assertEqual(200, response.status_code)

    def test_fail_post_subscriber_auth(self):
        """When subscriber update succeeds, we send a 'message' """
        self.login()
        data = {
            'category': "Subscriber",
            'imsi_val[]': self.gen_imsi()
        }
        response = self.client.post('/dashboard/subscriber_management/categoryupdate', data)
        # We'll get back JSON (the page reload will be triggered in js).
        expected_response = {
            'message':"IMSI category update cannot happen"
        }
        self.assertEqual(expected_response, json.loads(response.content))
        self.assertEqual(200, response.status_code)
