from sentry import conf

def main():
    import haystack
    from haystack.indexes import SearchIndex, RealTimeSearchIndex, CharField, DateTimeField
    from haystack.sites import SearchSite

    from sentry.models import GroupedMessage

    if conf.SEARCH_UPDATES == 'realtime':
        base_class = RealTimeSearchIndex
    elif conf.SEARCH_UPDATES == 'manual':
        base_class = SearchIndex
    else:
        raise ValueError('SEARCH_UPDATES must be `realtime` or `manual`')

    backend = haystack.load_backend(conf.SEARCH_ENGINE)

    class SentrySearchSite(SearchSite): pass

    site = SentrySearchSite()
    site.backend = backend.SearchBackend(site, **conf.SEARCH_OPTIONS)

    class GroupedMessageIndex(base_class):
        text = CharField(document=True, stored=False)
        status = CharField(stored=False, null=True)
        first_seen = DateTimeField(model_attr='first_seen', stored=False)
        last_seen = DateTimeField(model_attr='last_seen', stored=False)

        # def get_queryset(self):
        #     """Used when the entire index for model is updated."""
        #     return GroupedMessage.objects.all()

        def prepare_text(self, instance):
            return '\n'.join(filter(None, [instance.message, instance.class_name, instance.traceback, instance.view]))

    site.register(GroupedMessage, GroupedMessageIndex)
    
# Ensure we stop here if we havent configured Sentry to work under haystack
if conf.SEARCH_ENGINE:
    main()