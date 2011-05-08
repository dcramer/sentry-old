def get_backend(app):
    setting = app.config['DATASTORE']
    engine = setting['ENGINE']
    module, class_name = engine.rsplit('.', 1)
    return getattr(__import__(module, {}, {}, class_name), class_name)(**setting.get('OPTIONS', {}))
