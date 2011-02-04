from sentry import conf

_client = (None, None)

def get_client():
    global _client
    if _client[0] != conf.CLIENT:
        module, class_name = conf.CLIENT.rsplit('.', 1)
        _client = (conf.CLIENT, getattr(__import__(module, {}, {}, class_name), class_name)())
    return _client[1]

client = get_client()

