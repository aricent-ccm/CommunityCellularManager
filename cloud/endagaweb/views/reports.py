

class BillingReportView(ProtectedView):
    def __init__(self, **kwargs):
        super(BillingReportView, self).__init__(**kwargs)
        self.template = "dashboard/report/billing.html"
        self.url_namespace = 'billing-report'
        self.reports = REPORTS_DICT

    def get(self, request):
        return self.handle_request(request)

    def post(self, request):
        return self.handle_request(request)

    def handle_request(self, request):
        user_profile = UserProfile.objects.get(user=request.user)
        network = user_profile.network
        report_list = list({x for v in self.reports.itervalues() for x in v})
        if request.method == "POST":
            request.session['topup_percent'] = request.POST.get(
                'top_percent') or 100
            request.session['level_id'] = request.POST.get('level_id') or 0
            if request.session['level_id']:
                request.session['level'] = 'tower'
            else:
                request.session['level'] = "network"
                request.session['level_id'] = network.id
            request.session['reports'] = request.POST.getlist('reports', None)
            return redirect(
                urlresolvers.reverse(self.url_namespace) + '?filter=1')
        elif request.method == "GET":
            if 'filter' not in request.GET:
                # Reset filtering params.
                request.session['level'] = 'network'
                if self.url_namespace == 'subscriber-report':
                    request.session['level'] = 'network'
                request.session['level_id'] = network.id
                request.session['reports'] = report_list
                request.session['topup_percent'] = 100
        else:
            return HttpResponseBadRequest()

        # For top top-up percentage
        denom_list = []
        denom_list2 = []
        # Get denominatations available for that network
        denomination = NetworkDenomination.objects.filter(
            network_id=network.id)

        for denom in denomination:
            start_amount = humanize_credits(
                denom.start_amount, currency=CURRENCIES[network.currency])
            end_amount = humanize_credits(
                denom.end_amount, currency=CURRENCIES[network.currency])
            denom_list.append(
                (start_amount.amount_raw, end_amount.amount_raw))
        formatted_denomnation = []
        for denom in denom_list:
            # Now format to set them as stat-types
            formatted_denomnation.append(
                str(humanize_credits(
                    denom[0],
                    CURRENCIES[network.subscriber_currency])).replace(',', '')
                + ' - ' +
                str(humanize_credits(
                    denom[1],
                    CURRENCIES[network.subscriber_currency])).replace(',', ''))
            denom_list2.append(
                str(denom[0])
                + '-' +
                str(denom[1]))
        currency = CURRENCIES[network.subscriber_currency].symbol
        timezone_offset = pytz.timezone(user_profile.timezone).utcoffset(
            datetime.datetime.now()).total_seconds()
        level = request.session['level']
        level_id = int(request.session['level_id'])
        reports = request.session['reports']
        topup_percent = float(request.session['topup_percent'])

        towers = models.BTS.objects.filter(
            network=user_profile.network).values('nickname', 'uuid', 'id')
        network_has_activity = UsageEvent.objects.filter(
            network=network).exists()
        context = {
            'networks': get_objects_for_user(request.user, 'view_network',
                                             klass=Network),
            'towers': towers,
            'level': level,
            'level_id': level_id,
            'reports': reports,
            'report_list': self.reports,
            'user_profile': user_profile,
            'current_time_epoch': int(time.time()),
            'timezone_offset': timezone_offset,
            'network_has_activity': network_has_activity,
            'kinds': ','.join(formatted_denomnation),
            'extra_param': ','.join(denom_list2),
            'topup_percent': topup_percent,
            'value_type': currency,
        }
        template = get_template(self.template)
        html = template.render(context, request)
        return HttpResponse(html)

