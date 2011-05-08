from sentry import app

_client = (None, None)

def get_client():
    global _client
    if _client[0] != app.config['CLIENT']:
        module, class_name = app.config['CLIENT'].rsplit('.', 1)
        _client = (app.config['CLIENT'], getattr(__import__(module, {}, {}, class_name), class_name)())
    return _client[1]

client = get_client()

