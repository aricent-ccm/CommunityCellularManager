

class SubscriberReportView(BaseReport):
    """View Subscriber reports on basis of Network or tower level."""

    def __init__(self, **kwargs):
        template = "dashboard/report/subscriber.html"
        url_namespace = "subscriber-report"
        reports = {'Subscriber': ['Subscriber Activity',
                                  'Subscriber Status']}
        super(SubscriberReportView, self).__init__(reports, template,
                                                   url_namespace, **kwargs)

    def get(self, request):
        return self.handle_request(request)

    def post(self, request):
        return self.handle_request(request)


class HealthReportView(BaseReport):
    """View System health reports."""

    def __init__(self, **kwargs):
        template = "dashboard/report/health.html"
        url_namespace = "health-report"
        reports = {'Health': ['BTS Health']}
        super(HealthReportView, self).__init__(reports, template,
                                               url_namespace, **kwargs)

    def get(self, request):
        return self.handle_request(request)

    def post(self, request):
        return self.handle_request(request)



