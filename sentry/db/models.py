# Inspired by Django's models

from sentry.db import backend

class ManagerDescriptor(object):
    def __init__(self, manager):
        self.manager = manager

    def __get__(self, instance, type=None):
        if instance != None:
            raise AttributeError("Manager isn't accessible via %s instances" % type.__name__)
        return self.manager

class Manager(object):
    def __init__(self, model):
        self.model = model

    def get(self, pk):
        data = backend.get(self.model, pk)
        return self.model(pk, **data)

    def create(self, **values):
        pk = backend.add(self.model, **values)
        return self.model(pk, **values)

    def update(self, pk, **values):
        return backend.set(self.model, pk, **values)

    def add_to_index(self, pk, index, score):
        return backend.add_to_index(self.model, pk, index, score)

    def get_or_create(self, defaults={}, **index):
        # return (instance, created)

        pk = backend.get_by_cindex(self.model, **index)
        if pk:
            return self.get(pk), False

        defaults.update(index)
        inst = self.create(**defaults)
        backend.add_to_cindex(self.model, inst.pk, **index)
        return inst, True

class ModelDescriptor(type):
    def __new__(cls, name, bases, attrs):
        super_new = super(ModelDescriptor, cls).__new__
        parents = [b for b in bases if isinstance(b, ModelDescriptor)]
        if not parents:
            # If this isn't a subclass of Model, don't do anything special.
            return super_new(cls, name, bases, attrs)

        module = attrs.pop('__module__')
        new_class = super_new(cls, name, bases, {'__module__': module})

        # Setup default manager
        setattr(new_class, 'objects', Manager(new_class))

        fields = []

        # Add all attributes to the class.
        for obj_name, obj in attrs.iteritems():
            if isinstance(obj, Field):
                fields.append((obj_name, obj))
            setattr(new_class, obj_name, obj)

        setattr(new_class, '_fields', fields)

        return new_class

class Model(object):
    __metaclass__ = ModelDescriptor

    def __init__(self, pk=None, **kwargs):
        self.pk = pk
        for attname, field in self._fields:
            try:
                val = kwargs.pop(attname)
            except KeyError:
                # This is done with an exception rather than the
                # default argument on pop because we don't want
                # get_default() to be evaluated, and then not used.
                # Refs #12057.
                val = field.get_default()
            setattr(self, attname, val)

    def incr(self, key, amount=1):
        result = backend.incr(self.__class__, self.pk, key, amount)
        setattr(self, key, result)
        return result

    def update(self, **values):
        backend.set(self.__class__, self.pk, **values)
        for k, v in values.iteritems():
            setattr(self, k, v)

    def add_relation(self, instance, score):
        return backend.add_relation(self.__class__, self.pk, instance.__class__, instance.pk, score)

    def get_relations(self, model, offset=0, limit=100):
        return [model(pk, **data) for pk, data in backend.list_relations(self.__class__, self.pk, model, offset, limit)]

class Field(object):
    def __init__(self, default=None, **kwargs):
        self.default = default

    def get_default(self):
        if not self.default:
            value = None
        elif callable(self.default):
            value = self.default()
        else:
            value = self.default
        return value

    def save(self, value=None):
        if not value:
            value= self.get_default()
        return value

    def to_python(self, value=None):
        return value

class String(Field):
    def save(self, value=None):
        return unicode(super(Integer, self).save(value))

class Integer(Field):
    def save(self, value=None):
        return int(super(Integer, self).save(value))

class DateTime(Field):
    def save(self, value=None):
        # XXX: coerce to UTC
        value = super(Integer, self).save(value)
        assert isinstance(value, datetime)
        return value.strftime('%s')
