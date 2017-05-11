"""Tests for models.Users.

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
import json

import pytz

from django.test import TestCase

from ccm.common import crdt
from endagaweb import models


class TestBase(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.username = 'y'
        cls.password = 'pw'
        cls.user = models.User(username=cls.username, email='y@l.com')
        cls.user.set_password(cls.password)
        cls.user.save()
        cls.user_profile = models.UserProfile.objects.get(user=cls.user)
        
        cls.uuid = "59216199-d664-4b7a-a2db-6f26e9a5d208"
        
        # Create a test client.
        cls.client = test.Client()

    @classmethod
    def tearDownClass(cls):
        cls.user.delete()
        cls.user_profile.delete()

    def tearDown(self):
        self.logout()

    def login(self):
        """Log the client in."""
        data = {
            'email': self.username,
            'password': self.password,
        }
        self.client.post('/auth/', data)

    def logout(self):
        """Log the client out."""
        self.client.get('/logout')


class UserTests(TestBase):
    """
    We can manage subscriber balances.
    """
    def test_assert(self):
        """ sample test """
        self.assertEqual(1, 1)

    def test_assert(self):
        """ sample test """
        self.assertEqual(1, 1)


class UserUITest(TestBase):
    """Testing that we can add User in the UI."""

    def test_add_user(self):
        self.logout()
        response = self.client.get('/dashboard/user/management')
        # Anonymous User can not see this page so returning  permission denied.
        self.assertEqual(302, response.status_code)

    def test_add_user_auth(self):
        self.login()
        response = self.client.get('/dashboard/user/management')
        self.assertEqual(200, response.status_code)

    def test_delete_user(self):
        self.logout()
        response = self.client.get('/dashboard/user/management/delete')
        # Anonymous User can not see this page so returning  permission denied.
        self.assertEqual(302, response.status_code)

    def test_delete_user_auth(self):
        self.login()
        response = self.client.get('/dashboard/user/management/delete')
        self.assertEqual(200, response.status_code)

    def test_block_user(self):
        self.logout()
        response = self.client.get('/dashboard/user/management/blocking')
        # Anonymous User can not see this page so returning  permission denied.
        self.assertEqual(302, response.status_code)

    def test_block_user_auth(self):
        self.login()
        response = self.client.get('/dashboard/user/management/blocking')
        self.assertEqual(200, response.status_code)

    def test_post_add_user(self):
        self.logout()
        data = {
            'email': "a@b.com",
            'password':"pw",
            'username':"a@b.com",
            'role': "Network Admin",
            'networks': '1,2',
            'permissions':"44,45,46"
        }
        response = self.client.post('/dashboard/user/management', data)
        # Anonymous User can not see this page so returning  permission denied.
        self.assertEqual(302, response.status_code)

    def test_post_add_user_auth(self):
        self.login()
        data = {
            'email': "a@b.com",
            'password':"pw",
            'username':"a@b.com",
            'role': "Loader",
            'networks': '1,2',
            'permissions':"44,45,46"
        }
        response = self.client.post('/dashboard/user/management', data)
        self.assertEqual(200, response.status_code)

    def test_check_email_exists(self):
        self.login()
        email = "test@domain.com"
        response = self.client.get('/dashboard/user/management/checkuser?email='+email)
        expected_response = {
            'email_available':True
        }
        self.assertEqual(expected_response, json.loads(response.content))
        self.assertEqual(200, response.status_code)

    """def test_get_permissions(self):
        self.login()
        data = {
            'category': "Subscriber",
        }
        resqponse = self.client.post('/dashboard/user/management', data)
        self.assertEqual(200, response.status_code)\
    """