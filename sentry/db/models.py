"""
sentry.db.models
~~~~~~~~~~~~~~~~

:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

# Inspired by Django's models

import datetime
import simplejson

try:
    import cPickle as pickle
except ImportError:
    import pickle

from sentry import app

def to_db(model, values):
    result = {}
    for k, v in values.iteritems():
        field = model._meta.fields.get(k)
        if field:
            v = field.to_db(v)
            if v is None:
                v = ''
        else:
            v = simplejson.dumps(v)
        result[k] = v
    return result

class DoesNotExist(Exception):
    pass

class DuplicateKeyError(Exception):
    pass

class ManagerDescriptor(object):
    def __init__(self, manager):
        self.manager = manager

    def __get__(self, instance, type=None):
        if instance != None:
            raise AttributeError("Manager isn't accessible via %s instances" % type.__name__)
        return self.manager

class QuerySet(object):
    def __init__(self, model, order_by=None, filter_by=None):
        assert not (order_by and filter_by)
        self.model = model
        self.index = order_by or self.model._meta.ordering
        self.filter = filter_by
    
    def __repr__(self):
        return u'<%s: %s>' % (self.__class__.__name__, list(self))

    def __getitem__(self, key):
        is_slice = isinstance(key, slice)
        if is_slice:
            assert key.step == 1 or key.step is None
            start = key.start or 0
            stop = key.stop
        else:
            start = key
            stop = key + 1

        if stop == -1:
            num = stop
        else:
            num = stop - start
        
        if self.index.startswith('-'):
            desc = True
            index = self.index[1:]
        else:
            desc = False
            index = self.index

        results = self._get_results(start, num, index, desc)
        
        if is_slice:
            return results
        return results[0]

    def __len__(self):
        if self.index.startswith('-'):
            index = self.index[1:]
        else:
            index = self.index
        
        return app.db.count(self.model, index)

    def __iter__(self):
        for r in self[0:-1]:
            yield r

    def _get_results(self, start, num, index, desc=False):
        if self.filter:
            data = [(pk, app.db.get_data(self.model, pk)) for pk in app.db.list_by_cindex(self.model, **to_db(self.model, self.filter))]
        else:
            data = app.db.list(self.model, index, start, num, desc)

        return [self.model(pk, **data) for pk, data in data]

    def order_by(self, index):
        assert not self.filter
        self.index = index
        return self
    
class Manager(object):
    def __init__(self, model):
        self.model = model

    def count(self):
        return app.db.count(self.model, self.model._meta.ordering)

    def get_query_set(self):
        return QuerySet(self.model)

    def filter(self, **kwargs):
        assert len(kwargs) == 1
        return QuerySet(self.model, filter_by=kwargs)

    def all(self):
        return self.get_query_set()

    def order_by(self, index):
        return self.get_query_set().order_by(index)

    def get(self, pk):
        data = app.db.get(self.model, pk)
        if data == {}:
            raise self.model.DoesNotExist
        return self.model(pk, **data)

    def create(self, **values):
        instance = self.model(**values)
        instance.save()

        return instance

    def set_meta(self, pk, **values):
        if not values:
            return
        app.db.set_meta(self.model, pk, **to_db(self.model, values))

    def get_meta(self, pk):
        return dict((k, simplejson.loads(v)) for k, v in app.db.get_meta(self.model, pk).iteritems())

    def remove_from_index(self, pk, index):
        return app.db.remove_from_index(self.model, pk, index)

    def add_to_index(self, pk, index, score):
        return app.db.add_to_index(self.model, pk, index, score)

    def get_or_create(self, defaults=None, **index):
        # return (instance, created)

        pk_set = app.db.list_by_cindex(self.model, **to_db(self.model, index))
        if len(pk_set) == 1:
            return self.get(pk_set[0]), False
        elif pk_set:
            raise self.model.MultipleObjectsReturned

        if defaults is None:
            defaults = {}
        else:
            defaults = defaults.copy()
        defaults.update(index)

        inst = self.create(**defaults)

        return inst, True

class Options(object):
    def __init__(self, meta, attrs):
        # Grab fields
        fkeys = []
        fields = []
        for obj_name, obj in attrs.iteritems():
            if isinstance(obj, ForeignKey):
                fkeys.append((obj_name, obj))
            elif isinstance(obj, Field):
                fields.append((obj_name, obj))
        
        self.relations = fkeys
        self.fields = dict(fields)

        default_order = meta.__dict__.get('ordering')

        self.ordering = default_order or 'default'

        self.sortables = list(meta.__dict__.get('sortables', []))

        self.indexes = list(meta.__dict__.get('indexes', []))

        if self.ordering != 'default':
            self.sortables.append(self.ordering)

        # If we've specified ordering, and ordering is not already defined
        # as a sort index, we must register it
        if default_order and default_order not in self.sortables:
            self.sortables.append(default_order)

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

    DoesNotExist = DoesNotExist
    DuplicateKeyError = DuplicateKeyError

    def __init__(self, pk=None, **kwargs):
        self.pk = pk
        for attname, field in self._meta.fields.iteritems():
            try:
                val = field.to_python(kwargs.pop(attname))
            except KeyError:
                val = field.get_default()
            setattr(self, attname, val)
        if kwargs:
            raise ValueError('%s are not part of the schema for %s' % (', '.join(kwargs.keys()), self.__class__.__name__))

    def __eq__(self, other):
        return type(other) == type(self) and other.pk == self.pk

    def __setattr__(self, key, value):
        # XXX: is this the best approach for validating attributes
        field = self._meta.fields.get(key)
        if field and value:
            value = field.to_python(value)
        object.__setattr__(self, key, value)

    def __repr__(self):
        return u'<%s: %s>' % (self.__class__.__name__, unicode(self))

    def __unicode__(self):
        return self.pk or u'None'

    def decr(self, key, amount=1):
        result = app.db.decr(self.__class__, self.pk, key, amount)
        if key in self._meta.sortables:
            self.objects.add_to_index(self.pk, key, result)
        setattr(self, key, result)
        return result

    def incr(self, key, amount=1):
        result = app.db.incr(self.__class__, self.pk, key, amount)
        if key in self._meta.sortables:
            self.objects.add_to_index(self.pk, key, result)
        setattr(self, key, result)
        return result

    def save(self):
        model = self.__class__
        
        values = dict((name, getattr(self, name)) for name in self._meta.fields.iterkeys())

        # Ensure we've grabbed a primary key
        # XXX: API might need some work here yet
        created = not self.pk
        if created:
            self.pk = app.db.add(model)

        self.update(**values)
        
        if created:
            # Ensure we save our default index (this only happens
            # on instance creation)
            ordering = model._meta.ordering
            if ordering == 'default':
                value = datetime.datetime.now()
                self.objects.add_to_index(self.pk, 'default', value)

    def update(self, **values):
        assert self.pk
        
        model = self.__class__

        result = app.db.set(model, self.pk, **to_db(model, values))

        for index in self._meta.sortables:
            if index in values:
                self.objects.add_to_index(self.pk, index, getattr(self, index) or 0.0)

        # TODO: we need to deal w/ unsetting the previous keys
        for index in self._meta.indexes:
            index_values = dict((name, getattr(self, name)) for name in index)
            app.db.add_to_cindex(model, self.pk, **to_db(model, index_values))

        for k, v in values.iteritems():
            setattr(self, k, v)

        return result

    def delete(self):
        assert self.pk

        model = self.__class__
        
        # remove indexes
        for index in self._meta.sortables:
            self.objects.remove_from_index(self.pk, index)

        for index in self._meta.indexes:
            index_values = dict((name, getattr(self, name)) for name in index)
            app.db.remove_from_cindex(model, self.pk, **to_db(model, index_values))

        ordering = self._meta.ordering
        if ordering == 'default':
            self.objects.remove_from_index(self.pk, 'default')

        # remove relation keys
        for name, field in self._meta.relations:
            app.db.remove_relation(model, self.pk)
            # TODO: clean up remaining relation

        # remove instance
        app.db.delete(model, self.pk)

    def set_meta(self, **values):
        self.objects.set_meta(self.pk, **values)

    def get_meta(self):
        return self.objects.get_meta(self.pk)

    def add_relation(self, instance, score):
        # add child relation
        app.db.add_relation(self.__class__, self.pk, instance.__class__, instance.pk, score)
        # add parent relation
        app.db.add_relation(instance.__class__, instance.pk, self.__class__, self.pk, score)

    def get_relations(self, model, offset=0, limit=100, desc=True):
        return [model(pk, **data) for pk, data in app.db.list_relations(self.__class__, self.pk, model, offset, limit, desc)]

    def _get_data(self):
        return self.get_meta() or {}
    data = property(_get_data)

class Field(object):
    def __init__(self, default=None, **kwargs):
        self.default = default

    def get_default(self):
        if not self.default:
            value = self.to_python(None)
        elif callable(self.default):
            value = self.default()
        else:
            value = self.default
        return value

    def to_db(self, value=None):
        if value is None:
            value = ''
        return value

    def to_python(self, value=None):
        return value

class ForeignKey(object):
    def __init__(self, to_model):
        self.to_model = to_model

class String(Field):
    def to_python(self, value=None):
        if value:
            value = unicode(value)
        else:
            value = u''
        return value

class Text(String):
    pass

class Integer(Field):
    def to_python(self, value=None):
        if value:
            value = int(value)
        else:
            value = 0
        return value

class Float(Field):
    def to_python(self, value=None):
        if value:
            value = float(value)
        else:
            value = 0.0
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
            if '.' in value:
                value = datetime.datetime.strptime(value, '%Y-%m-%dT%H:%M:%S.%f')
            else:
                value = datetime.datetime.strptime(value, '%Y-%m-%dT%H:%M:%S')
        return value

class List(Field):
    def to_db(self, value=None):
        if isinstance(value, (tuple, list)):
            value = pickle.dumps(value)
        return value

    def to_python(self, value=None):
        if not value:
            value = []
        elif isinstance(value, basestring):
            value = pickle.loads(value)
        return value