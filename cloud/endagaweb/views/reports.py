
class DashboardView(ProtectedView):
    """Main dashboard page with graph of network activity.

    The js on the template itself gets the data for the graph using the stats
    API.  We also load the server's notion of the current time so that we don't
    have to rely on the user's clock.
    """
    # view_network is default (minimum permission assigned)
    permission_required = 'view_network'

    def __init__(self, **kwargs):
        super(DashboardView, self).__init__(**kwargs)
        self.template = "dashboard/index.html"
        self.url_namespace = 'Call_Sms_Data_Usage'
        self.reports = {'call and SMS Data Usage': [' call and SMS Data Usage ']}


    def get(self, request):
        return self.handle_request(request)

    def post(self, request):
        return self.handle_request(request)

    def handle_request(self, request):
        """Process request.

        We want filters to persist even when someone changes pages without
        re-submitting the form. Page changes will always come over a GET
        request, not a POST.
         - If it's a GET, we should try to pull settings from the session.
         - If it's a POST, we should replace whatever is in the session.
         - If it's a GET with no page, we should blank out the session.
         """
        user_profile = UserProfile.objects.get(user=request.user)
        network = user_profile.network
        report_list = list({x for v in self.reports.itervalues() for x in v})
        # Process parameters.
        # We want filters to persist even when someone changes pages without
        # re-submitting the form. Page changes will always come over a GET
        # request, not a POST.
        # - If it's a GET, we should try to pull settings from the session.
        # - If it's a POST, we should replace whatever is in the session.
        # - If it's a GET with no page variable, we should blank out the
        #   session.

        if request.method == "POST":
            request.session['level_id'] = request.POST.get('level_id') or 0
            if request.session['level_id']:
                request.session['level'] = 'tower'
            else:
                request.session['level'] = "network"
                request.session['level_id'] = network.id
            request.session['reports'] = request.POST.getlist('reports', None)
            filter = request.POST.get('filter')
            request.session['filter'] = filter

            return redirect(urlresolvers.reverse(
                    self.url_namespace) )


        elif request.method == "GET":
            if 'level_id' not in request.session:
                request.session['level_id'] = request.GET.get('level_id')
                request.session['reports'] = report_list
                request.session['filter'] = None
                request.session['level'] = request.GET.get('level', 'network')

            else:
                request.session['level_id'] = request.session['level_id']
                request.session['level'] = request.session['level']
            request.session['level_id'] = request.session['level_id']
        else:
            return HttpResponseBadRequest()
        timezone_offset = pytz.timezone(user_profile.timezone).utcoffset(
            datetime.datetime.now()).total_seconds()
        level = request.session['level']
        if request.session['level_id'] != None:
            level_id = int(request.session['level_id'])
        else:
            level_id = network.id
            level = 'network'
        if request.session['level'] != None:
            request.session['level'] = request.session['level']
        else:
            request.session['level'] = request.GET.get('level', 'network')
        reports = request.GET.get('reports')
        filter = request.GET.get('filter')
        towers = models.BTS.objects.filter(network=user_profile.network). \
            order_by('id').values('nickname', 'uuid', 'id')
        network_has_activity = UsageEvent.objects.filter(
            network=network).exists()
        context = {
            'networks': get_objects_for_user(request.user, 'view_network',
                                             klass=Network),
            'network': network,
            'towers': towers,
            'level': level,
            'level_id': level_id,
            'reports': reports,
            'report_list': self.reports,
            'user_profile': user_profile,
            'current_time_epoch': int(time.time()),
            'timezone_offset': timezone_offset,
            'network_has_activity': network_has_activity,
            'value_type': '',
            'filter': filter
        }
        template = get_template(self.template)
        html = template.render(context, request)
        return HttpResponse(html)

