import sqlalchemy
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.inspection import inspect
from sqlalchemy.orm.mapper import Mapper
from sqlalchemy.util import symbol
import types

from .exceptions import BadQuery, FieldNotFound, BadSpec


try:
    from sqlalchemy import Table
    from sqlalchemy.sql.selectable import Alias
except ImportError:
    pass


class Field(object):

    def __init__(self, model, field_name):
        self.model = model
        self.field_name = field_name

    def get_sqlalchemy_field(self):
        sqlalchemy_field = get_nested_column(self.model, self.field_name)

        if sqlalchemy_field is None:
            raise FieldNotFound(
                'Model {} has no column `{}`.'.format(
                    self.model, self.field_name
                )
            )

        # If it's a hybrid method, then we call it so that we can work with
        # the result of the execution and not with the method object itself
        if isinstance(sqlalchemy_field, types.MethodType):
            sqlalchemy_field = sqlalchemy_field()

        return sqlalchemy_field


def _is_hybrid_property(orm_descriptor):
    return orm_descriptor.extension_type == symbol('HYBRID_PROPERTY')


def _is_hybrid_method(orm_descriptor):
    return orm_descriptor.extension_type == symbol('HYBRID_METHOD')


def get_relationship_models(model, field):
    parts = field.split(".")

    if len(parts) > 1:
        # Order in which joins are applied to the query matters so use list.
        relationships = list()

        # Find all relationships.
        for i in range(1, len(parts)):
            if (column := find_nested_relationship_model(inspect(model), parts[0:i])) is not None:
                relationships.append(column.class_attribute)

        return relationships

    return list()


def should_outer_join_relationship(operator):
    return operator == 'is_null'


def find_nested_relationship_model(mapper, field):
    parts = field if isinstance(field, list) else field.split(".")

    if (part := parts[0]) in mapper.relationships:
        related_field = mapper.relationships[part]
        return find_nested_relationship_model(related_field.mapper, ".".join(parts[1::])) if len(parts) > 1 else related_field
    else:
        return None


def get_nested_column(model, field):
    """
    Searches through relationships to find the requested field.
    """
    parts = field if isinstance(field, list) else field.split(".")

    mapper = inspect(model)
    orm_descriptors = mapper.all_orm_descriptors
    hybrid_fields = [
        key for key, item in orm_descriptors.items()
        if _is_hybrid_property(item) or _is_hybrid_method(item)
    ]

    # Search in own model fields
    if len(parts) == 1:
        if field in mapper.columns or field in mapper.composites or field in hybrid_fields:
            return getattr(model, field)
        else:
            return None

    # Search in relationships.
    if (part := parts[0]) in mapper.relationships:
        return get_nested_column(getattr(model, part).property.entity.class_, ".".join(parts[1::]))
    else:
        return None

def _get_tables_from_join(orm_join):
    models = []
    if isinstance(orm_join.right, Table):
        models.append(orm_join.right)
    elif isinstance(orm_join.right, Alias):
        pass
    else:
        models.extend(_get_tables_from_join(orm_join.right))
    if isinstance(orm_join.left, Table):
        models.append(orm_join.left)
    elif isinstance(orm_join.right, Alias):
        pass
    else:
        models.extend(_get_tables_from_join(orm_join.left))
    return models


def _get_model_class_by_table_name(registry, tablename):
    """ Return the model class matching `tablename` in the given `registry`.
    """
    for cls in registry.values():
        if hasattr(cls, '__tablename__') and cls.__tablename__ == tablename:
            return cls


def _get_query_models_1_4(query):
    """Get models from query. Works for sqlalchemy 1.4

    :param query:
        A :class:`sqlalchemy.orm.Query` instance.

    :returns:
        A dictionary with all the models included in the query.
    """
    models = [col_desc['entity'] for col_desc in query.column_descriptions]
    if models:
        try:
            registry = models[-1].registry._class_registry
            joined = []
            for f in query.statement.get_final_froms():
                if not f._is_join:
                    continue
                if isinstance(f, Table):
                    joined.append(
                        _get_model_class_by_table_name(registry, f.name)
                    )
                else:
                    joined.extend(
                        _get_model_class_by_table_name(registry, m.name)
                        for m in _get_tables_from_join(f)
                    )

            models.extend([m for m in joined if m not in models])
        except InvalidRequestError:
            pass

    tables = query._from_obj
    select_from_models = [
        t._annotations['entity_namespace']._identity_class for t in tables
    ]
    models.extend([m for m in select_from_models if m not in models])

    tables = query._legacy_setup_joins
    joined = [
        t[0]._annotations['entity_namespace']._identity_class
        for t in tables
    ]
    models.extend([m for m in joined if m not in models])

    return {model.__name__: model for model in models if model}


def _get_query_models(query):
    """Get models from query. Works for sqlalchemy < 1.4

    :param query:
        A :class:`sqlalchemy.orm.Query` instance.

    :returns:
        A dictionary with all the models included in the query.
    """
    models = [col_desc['entity'] for col_desc in query.column_descriptions]
    models.extend(mapper.class_ for mapper in query._join_entities)

    # account also query.select_from entities
    if (
        hasattr(query, '_select_from_entity') and
        (query._select_from_entity is not None)
    ):
        model_class = (
            query._select_from_entity.class_
            if isinstance(query._select_from_entity, Mapper)  # sqlalchemy>=1.1
            else query._select_from_entity  # sqlalchemy==1.0
        )
        if model_class not in models:
            models.append(model_class)

    return {model.__name__: model for model in models}


def get_query_models(query):
    """Get models from query.

    :param query:
        A :class:`sqlalchemy.orm.Query` instance.

    :returns:
        A dictionary with all the models included in the query.
    """
    if sqlalchemy.__version__ > '1.3':
        return _get_query_models_1_4(query)
    return _get_query_models(query)


def get_model_from_spec(spec, query, default_model=None):
    """ Determine the model to which a spec applies on a given query.

    A spec that does not specify a model may be applied to a query that
    contains a single model. Otherwise the spec must specify the model to
    which it applies, and that model must be present in the query.

    :param query:
        A :class:`sqlalchemy.orm.Query` instance.

    :param spec:
        A dictionary that may or may not contain a model name to resolve
        against the query.

    :returns:
        A model instance.

    :raise BadSpec:
        If the spec is ambiguous or refers to a model not in the query.

    :raise BadQuery:
        If the query contains no models.

    """
    models = get_query_models(query)
    if not models:
        raise BadQuery('The query does not contain any models.')

    model_name = spec.get('model')
    if model_name is not None:
        models = [v for (k, v) in models.items() if k == model_name]
        if not models:
            raise BadSpec(
                'The query does not contain model `{}`.'.format(model_name)
            )
        model = models[0]
    else:
        if len(models) == 1:
            model = list(models.values())[0]
        elif default_model is not None:
            return default_model
        else:
            raise BadSpec("Ambiguous spec. Please specify a model.")

    return model


def get_default_model(query):
    """ Return the singular model from `query`, or `None` if `query` contains
    multiple models.
    """
    query_models = get_query_models(query).values()
    if len(query_models) == 1:
        default_model, = iter(query_models)
    else:
        default_model = None
    return default_model


def auto_join(query, inner_join_relationships, outer_join_relationships):
    """ Automatically join models to `query` if they're not already present.
    """
    for relationship in outer_join_relationships:
        query = _join_relationship(query, relationship, True)

    for relationship in inner_join_relationships:
        query = _join_relationship(query, relationship, False)

    return query


def join_relationship_1_3(query, relationship, outer_join=False):
    model = relationship.property.entity.class_
    if model not in get_query_models(query).values():
        try:
            query = query.join(relationship, isouter=outer_join)
        except InvalidRequestError:
            pass  # can't be autojoined

    return query


def get_model_class_by_name(registry, name):
    """ Return the model class matching `name` in the given `registry`.
    """
    for cls in registry.values():
        if getattr(cls, '__name__', None) == name:
            return cls


def join_relationship_1_4(query, relationship, outer_join=False):
    """ Automatically join models to `query` if they're not already present
    and the join can be done implicitly. Works for sqlalchemy 1.4
    """
    # every model has access to the registry, so we can use any from the query
    query_models = get_query_models(query).values()
    model_registry = list(query_models)[-1].registry._class_registry

    model = get_model_class_by_name(model_registry, relationship)
    if model and model not in query_models:
        try:
            tmp_query = query.join(model, isouter=outer_join)
            tmp_query.statement.compile()
            query = tmp_query
        except InvalidRequestError:
            pass  # can't be autojoined
    return query


def _join_relationship(query, relationship, outer_join=False):
    """ Automatically join models to `query` if they're not already present
    and the join can be done implicitly.
    """
    if sqlalchemy.__version__ < '1.4':
        return join_relationship_1_3(query, relationship, outer_join)
    return join_relationship_1_4(query, relationship, outer_join)
