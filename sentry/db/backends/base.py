class SQLAlchemyBackend(object):
    # TODO: this would use sql alchemy syntax

    def incr(self, schema, lookup, key='count', amount=1):
        inst, created = schema.objects.get_or_create(lookup)
        # Maintain counts
        if not created:
            inst.count += 1
            schema.objects.filter(pk=inst.pk).update(**{key: F(key) + amount})
        return inst.count

    def add(self, schema, lookup, **values):
        inst, created = schema.objects.get_or_create(lookup, defaults=values)
        return created

    def set(self, schema, lookup, **values):
        inst, created = schema.objects.get_or_create(lookup, defaults=values)
        if not created:
            schema.objects.filter(pk=inst.pk).update(values)
        return True