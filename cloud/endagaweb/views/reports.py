"""Network views.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""


class CallReportView(BaseReport):
    """View Call and SMS reports on basis of Network or tower level."""

    def __init__(self, **kwargs):
        template = "dashboard/report/call-sms.html"
        url_namespace = "call-report"
        reports = {'Call': ['Number of Calls', 'Minutes of Call'],
                   'SMS': ['Number of SMS']}
        super(CallReportView, self).__init__(reports, template,
                                             url_namespace, **kwargs)

    def get(self, request):
        return self.handle_request(request)

    def post(self, request):
        return self.handle_request(request)