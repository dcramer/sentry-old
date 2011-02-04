# Inspired by Django's models

import datetime

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

    def _map(self, values):
        for k, v in values.iteritems():
            field = self.model._fields.get(k)
            if field:
                values[k] = field.to_db(v)
        return values

    def get(self, pk):
        data = backend.get(self.model, pk)
        return self.model(pk, **self._map(data))

    def create(self, **values):
        pk = backend.add(self.model, **self._map(values))
        return self.model(pk, **values)

    def update(self, pk, **values):
        return backend.set(self.model, pk, **self._map(values))

    def add_to_index(self, pk, index, score):
        return backend.add_to_index(self.model, pk, index, score)

    def get_or_create(self, defaults={}, **index):
        # return (instance, created)

        pk = backend.get_by_cindex(self.model, **self._map(index))
        if pk:
            return self.get(pk), False

        defaults.update(index)
        inst = self.create(**defaults)
        backend.add_to_cindex(self.model, inst.pk, **self._map(index))
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

        setattr(new_class, '_fields', dict(fields))

        return new_class

class Model(object):
    __metaclass__ = ModelDescriptor

    def __init__(self, pk=None, **kwargs):
        self.pk = pk
        for attname, field in self._fields.iteritems():
            try:
                val = field.to_python(kwargs.pop(attname))
            except KeyError:
                # This is done with an exception rather than the
                # default argument on pop because we don't want
                # get_default() to be evaluated, and then not used.
                # Refs #12057.
                val = field.get_default()
            setattr(self, attname, val)

    def __setattr__(self, key, value):
        # XXX: is this the best approach for validating attributes
        field = self._fields.get(key)
        if field:
            value = field.to_python(value)
        object.__setattr__(self, key, value)

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

    def to_db(self, value=None):
        return value

    def to_python(self, value=None):
        return value

class String(Field):
    def to_python(self, value=None):
        if value:
            value = unicode(value)
        return value

class Integer(Field):
    def to_python(self, value=None):
        if value:
            value = int(value)
        return value

class DateTime(Field):
    def to_db(self, value=None):
        if value:
            # TODO: coerce this to UTC
            value = value.strftime('%s')
        return value

    def to_python(self, value=None):
        if value:
            if not isinstance(value, datetime.datetime):
                # TODO: coerce this to a UTC datetime object
                value = datetime.datetime.fromtimestamp(float(int(value)))
            value = value.replace(microsecond=0)
        return value