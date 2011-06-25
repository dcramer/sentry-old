class ClientProxy(object):
    def __init__(self, app):
        self.__app = app
        self.__client = (None, None)

    def __getattr__(self, attr):
        return getattr(self.__get_client(), attr)

    def __call__(self, *args, **kwargs):
        return self.__get_client()(*args, **kwargs)

    def __eq__(self, other):
        return self.__get_client() == other

    def __get_client(self):
        setting, client = self.__client
        if setting != self.__app.config['CLIENT']:
            setting = self.__app.config['CLIENT']
            client = get_client(setting)
            self.__client = (setting, client)
        return client
    
    def capture(self, *args, **kwargs):
        return self.__get_client().capture(*args, **kwargs)

def get_client(path):
    module, class_name = path.rsplit('.', 1)
    return getattr(__import__(module, {}, {}, class_name), class_name)()

