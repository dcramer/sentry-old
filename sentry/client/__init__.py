def get_client(app):
    setting = app.config['CLIENT']
    module, class_name = setting.rsplit('.', 1)
    return getattr(__import__(module, {}, {}, class_name), class_name)()

