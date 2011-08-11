import sentry.models
from sentry.db import models

from sqlalchemy import Table, Column, Integer, Float, String, Text, \
                       DateTime, MetaData

__all__ = ('metadata', 'model_map', 'model_meta')

column_map = {
    models.String: lambda x: String(255, default=x.default, nullable=True),
    models.Text: lambda x: Text(default=x.default, nullable=True),
    models.Integer: lambda x: Integer(default=x.default, nullable=True),
    models.Float: lambda x: Float(default=x.default, nullable=True),
    models.DateTime: lambda x: DateTime(default=x.default, nullable=True),
    models.List: lambda x: Text(default=x.default, nullable=True),
}

model_map = {}
model_meta = {}

def create_sqlalchemy_def(metadata, model):
    columns = [
        Column('id', String(32), primary_key=True),
    ]
    for name, field in model._meta.fields: 
        columns.append(Column(name, column_map[field](field), nullable=True))

    table = Table(model.__name__.lower(), metadata, *columns)
    
    return table

def create_sqlalchemy_metadata_def(metadata, model):
    columns = [
        Column('id', String(32), primary_key=True),
        Column('key', String(255), primary_key=True),
        Column('value', Text(nullable=True), primary_key=True),
    ]

    table = Table('%s_metadata' % (model.__name__.lower(),), metadata, *columns)
    
    return table

metadata = MetaData()
# metadata.create_all(engine) 

for var in dir(sentry.models):
    if isinstance(var, models.Model):
        model_map[var] = create_sqlalchemy_def(metadata, var)
        model_meta[var] = create_sqlalchemy_metadata_def(metadata, var)
