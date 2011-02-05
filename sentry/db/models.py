# Inspired by Django's models

import datetime

try:
    import cPickle as pickle
except ImportError:
    import pickle

from sentry.db import backend

def map_field_values(model, values):
    result = {}
    for k, v in values.iteritems():
        field = model._meta.fields.get(k)
        if field:
            v = field.to_db(v)
        result[k] = v
    return result

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

    def all(self, offset=0, limit=100):
        return self.sort_by(self.model._meta.ordering, offset, limit)

    def sort_by(self, index, offset=0, limit=100):
        if index.startswith('-'):
            desc = True
            index = index[1:]
        else:
            desc = False
        return [self.model(pk, **data) for pk, data in backend.list(self.model, index, offset, limit, desc)]

    def get(self, pk):
        data = backend.get(self.model, pk)
        return self.model(pk, **data)

    def create(self, **values):
        pk = values.pop('pk', None)
        if pk:
            backend.set(self.model, pk, **map_field_values(self.model, values))
        else:
            pk = backend.add(self.model, **map_field_values(self.model, values))

        instance = self.model(pk, **values)

        for index in self.model._meta.indexes:
            if index in values:
                value = getattr(instance, index)
                self.add_to_index(pk, index, value)

        ordering = self.model._meta.ordering
        if ordering == 'default':
            value = datetime.datetime.now()
            self.add_to_index(pk, 'default', value)

        return instance

    def update(self, pk, **values):
        result = backend.set(self.model, pk, **map_field_values(self.model, values))

        for index in self.model._meta.indexes:
            if index in values:
                value = values[index]
                self.add_to_index(pk, index, value)

        return result

    def set_meta(self, pk, **values):
        if not values:
            return
        backend.set_meta(self.model, pk, **map_field_values(self.model, values))

    def get_meta(self, pk):
        return backend.get_meta(self.model, pk)

    def add_to_index(self, pk, index, score):
        return backend.add_to_index(self.model, pk, index, score)

    def get_or_create(self, defaults={}, **index):
        # return (instance, created)

        pk = backend.get_by_cindex(self.model, **map_field_values(self.model, index))
        if pk:
            return self.get(pk), False

        defaults = defaults.copy()
        defaults.update(index)

        inst = self.create(**defaults)

        backend.add_to_cindex(self.model, inst.pk, **map_field_values(self.model, index))

        return inst, True

class Options(object):
    def __init__(self, meta, attrs):
        # Grab fields
        fields = []
        for obj_name, obj in attrs.iteritems():
            if isinstance(obj, Field):
                fields.append((obj_name, obj))

        self.fields = dict(fields)

        default_order = meta.__dict__.get('ordering')
        self.ordering = default_order or 'default'
        self.indexes = list(meta.__dict__.get('indexes', []))
        if default_order:
            self.indexes.append(default_order)

class ModelDescriptor(type):
    def __new__(cls, name, bases, attrs):
        super_new = super(ModelDescriptor, cls).__new__
        parents = [b for b in bases if isinstance(b, ModelDescriptor)]
        if not parents:
            # If this isn't a subclass of Model, don't do anything special.
            return super_new(cls, name, bases, attrs)

        module = attrs.pop('__module__')
        new_class = super_new(cls, name, bases, {'__module__': module})
        attr_meta = attrs.pop('Meta', None)
        if not attr_meta:
            meta = getattr(new_class, 'Meta', None)
        else:
            meta = attr_meta
        setattr(new_class, '_meta', Options(meta, attrs))

        # Setup default manager
        setattr(new_class, 'objects', Manager(new_class))

        # Add all attributes to the class.
        for obj_name, obj in attrs.iteritems():
            setattr(new_class, obj_name, obj)

        return new_class

class Model(object):
    __metaclass__ = ModelDescriptor

    def __init__(self, pk=None, **kwargs):
        self.pk = pk
        for attname, field in self._meta.fields.iteritems():
            try:
                val = field.to_python(kwargs.pop(attname))
            except KeyError:
                # This is done with an exception rather than the
                # default argument on pop because we don't want
                # get_default() to be evaluated, and then not used.
                # Refs #12057.
                val = field.get_default()
            setattr(self, attname, val)
        if kwargs:
            raise ValueError('%s are not part of the schema for %s' % (', '.join(kwargs.keys()), self.__class__.__name__))

    def __setattr__(self, key, value):
        # XXX: is this the best approach for validating attributes
        field = self._meta.fields.get(key)
        if field:
            value = field.to_python(value)
        object.__setattr__(self, key, value)

    def __repr__(self):
        return u'<%s: %s>' % (self.__class__.__name__, unicode(self))

    def __unicode__(self):
        return self.pk

    def incr(self, key, amount=1):
        result = backend.incr(self.__class__, self.pk, key, amount)
        setattr(self, key, result)
        return result

    def update(self, **values):
        self.objects.update(self.pk, **values)
        for k, v in values.iteritems():
            setattr(self, k, v)

    def set_meta(self, **values):
        self.objects.set_meta(self.pk, **values)

    def get_meta(self):
        return self.objects.get_meta(self.pk)

    def add_relation(self, instance, score):
        return backend.add_relation(self.__class__, self.pk, instance.__class__, instance.pk, score)

    def get_relations(self, model, offset=0, limit=100):
        return [model(pk, **data) for pk, data in backend.list_relations(self.__class__, self.pk, model, offset, limit)]

    def _get_data(self):
        return self.get_meta() or {}
    data = property(_get_data)


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
        if isinstance(value, datetime.datetime):
            # TODO: coerce this to UTC
            value = value.isoformat()
        return value

    def to_python(self, value=None):
        if value and not isinstance(value, datetime.datetime):
            # TODO: coerce this to a UTC datetime object
            value = datetime.datetime.strptime(value, '%Y-%m-%dT%H:%M:%S.%f')
        return value

class List(Field):
    def to_db(self, value=None):
        if isinstance(value, (tuple, list)):
            value = pickle.dumps(value)
        return value

    def to_python(self, value=None):
        if isinstance(value, basestring):
            value = pickle.loads(value)
        return value