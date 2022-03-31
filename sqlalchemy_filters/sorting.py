# -*- coding: utf-8 -*-

from .exceptions import BadSortFormat
from .models import Field, auto_join, get_model_from_spec, get_default_model, get_relationship_models, \
    should_outer_join_relationship

SORT_ASCENDING = 'asc'
SORT_DESCENDING = 'desc'


class Sort(object):

    def __init__(self, sort_spec):
        self.sort_spec = sort_spec

        try:
            field_name = sort_spec['field']
            direction = sort_spec['direction']
        except KeyError:
            raise BadSortFormat(
                '`field` and `direction` are mandatory attributes.'
            )
        except TypeError:
            raise BadSortFormat(
                'Sort spec `{}` should be a dictionary.'.format(sort_spec)
            )

        if direction not in [SORT_ASCENDING, SORT_DESCENDING]:
            raise BadSortFormat('Direction `{}` not valid.'.format(direction))

        self.field_name = field_name
        self.direction = direction
        self.nullsfirst = sort_spec.get('nullsfirst')
        self.nullslast = sort_spec.get('nullslast')

    def get_named_models(self, model):
        field = self.sort_spec['field']
        operator = self.sort_spec['op'] if 'op' in self.sort_spec else None

        models = get_relationship_models(model, field)

        return list(), models if should_outer_join_relationship(operator) else models, list()

    def format_for_sqlalchemy(self, query, default_model):
        sort_spec = self.sort_spec
        direction = self.direction
        field_name = self.field_name

        model = get_model_from_spec(sort_spec, query, default_model)

        field = Field(model, field_name)
        sqlalchemy_field = field.get_sqlalchemy_field()

        if direction == SORT_ASCENDING:
            sort_fnc = sqlalchemy_field.asc
        elif direction == SORT_DESCENDING:
            sort_fnc = sqlalchemy_field.desc

        if self.nullsfirst:
            return sort_fnc().nullsfirst()
        elif self.nullslast:
            return sort_fnc().nullslast()
        else:
            return sort_fnc()


def get_named_models(base_model, sorts):
    inner_join_models = list()
    outer_join_models = list()

    for sort in sorts:
        inner_join, outer_join = sort.get_named_models(base_model)
        inner_join_models.extend(inner_join)
        outer_join_models.extend(outer_join)

    return inner_join_models, outer_join_models


def apply_sort(model, query, sort_spec):
    """Apply sorting to a :class:`sqlalchemy.orm.Query` instance.

    :param model:
        A :class:`sqlalchemy.ext.declarative.DeclarativeMeta` from the model to apply the sorting on.

    :param sort_spec:
        A list of dictionaries, where each one of them includes
        the necesary information to order the elements of the query.

        Example::

            sort_spec = [
                {'model': 'Foo', 'field': 'name', 'direction': 'asc'},
                {'model': 'Bar', 'field': 'id', 'direction': 'desc'},
                {
                    'model': 'Qux',
                    'field': 'surname',
                    'direction': 'desc',
                    'nullslast': True,
                },
                {
                    'model': 'Baz',
                    'field': 'count',
                    'direction': 'asc',
                    'nullsfirst': True,
                },
            ]

        If the query being modified refers to a single model, the `model` key
        may be omitted from the sort spec.

    :returns:
        The :class:`sqlalchemy.orm.Query` instance after the provided
        sorting has been applied.
    """
    if isinstance(sort_spec, dict):
        sort_spec = [sort_spec]

    sorts = [Sort(item) for item in sort_spec]

    inner_join_models, outer_join_models = get_named_models(model, sorts)
    query = auto_join(query, inner_join_models, outer_join_models)

    sqlalchemy_sorts = [
        sort.format_for_sqlalchemy(query, model) for sort in sorts
    ]

    if sqlalchemy_sorts:
        query = query.order_by(*sqlalchemy_sorts)

    return query
