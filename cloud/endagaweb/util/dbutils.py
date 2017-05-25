"""utlity methods running on the underlying database.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""
import uuid
import django


def get_db_time(connection):
    cursor = connection.cursor()
    cursor.execute("SELECT statement_timestamp();")
    return cursor.fetchone()[0]


def format_transaction(transaction, negative=False):
    # Generating new transaction id using old transaction and date
    tr = str(uuid.uuid4().hex[:4])
    dt = str(django.utils.timezone.now().date()).replace('-', '')
    transaction_id = '{0}id{1}{2}'.format(dt, tr, str(transaction)[:8])
    if negative:
        return '-%s' % (transaction_id, )
    else:
        return transaction_id
