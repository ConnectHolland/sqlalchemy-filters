SQLAlchemy filters
==================

> Filter, sort and paginate SQLAlchemy query objects. Ideal for exposing
> these actions over a REST API.

![image](https://img.shields.io/pypi/v/sqlalchemy-filters.svg%0A%20:target:%20https://pypi.org/project/sqlalchemy-filters/)

![image](https://img.shields.io/pypi/pyversions/sqlalchemy-filters.svg%0A%20:target:%20https://pypi.org/project/sqlalchemy-filters/)

![image](https://img.shields.io/pypi/format/sqlalchemy-filters.svg%0A%20:target:%20https://pypi.org/project/sqlalchemy-filters/)

![image](https://travis-ci.org/juliotrigo/sqlalchemy-filters.svg?branch=master%0A%20:target:%20https://travis-ci.org/juliotrigo/sqlalchemy-filters)


# Installation
Add the following to your `pyproject.toml` file:
```
[[tool.poetry.source]]
name = "connectholland"
url = "https://pypi.packages.connectholland.nl/simple/"
``` 
To add the repository credentials: `poetry config http-basic.connectholland connectholland <read_secret>`.

The <read_secret> can be found in the CH_Secrets AWS account > Systems Manager > Parameter Store as the `/ch/pypi/read-secret` parameter (eu-west-1 region)

This package supports SQLite, MySQL and PostgreSQL, depending on which engine you use you have to install this package with either the `mysql` or `postgresql` extra: `poetry add sqlalchemy-filters --extras "mysql"`.

Filtering
---------

Assuming that we have a [SQLAlchemy](https://www.sqlalchemy.org/)
`query` object:

``` {.sourceCode .python}
from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base


class Base(object):
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    count = Column(Integer, nullable=True)

    @hybrid_property
    def count_square(self):
        return self.count * self.count

    @hybrid_method
    def three_times_count(self):
        return self.count * 3


Base = declarative_base(cls=Base)


class Foo(Base):

    __tablename__ = 'foo'

# ...

query = session.query(Foo)
```

Then we can apply filters to that `query` object (multiple times):

``` {.sourceCode .python}
from sqlalchemy_filters import apply_filters


# `query` should be a SQLAlchemy query object

filter_spec = [{'field': 'name', 'op': '==', 'value': 'name_1'}]
filtered_query = apply_filters(Foo, query, filter_spec)

more_filters = [{'field': 'foo_id', 'op': 'is_not_null'}]
filtered_query = apply_filters(Foo, filtered_query, more_filters)

result = filtered_query.all()
```

It is also possible to filter queries that contain multiple models,
including joins:

``` {.sourceCode .python}
class Bar(Base):

    __tablename__ = 'bar'

    foo_id = Column(Integer, ForeignKey('foo.id'))
```

``` {.sourceCode .python}
query = session.query(Foo).join(Bar)

filter_spec = [
    {'field': 'bar.name', 'op': '==', 'value': 'name_1'},
    {'field': 'count', 'op': '>=', 'value': 5},
]
filtered_query = apply_filters(Foo, query, filter_spec)

result = filtered_query.all()
```

`apply_filters` will attempt to automatically join models to `query` if
they're not already present and a model-specific filter is supplied. For
example, the value of `filtered_query` in the following two code blocks
is identical:

``` {.sourceCode .python}
query = session.query(Foo).join(Bar)  # join pre-applied to query

filter_spec = [
    {'field': 'name', 'op': '==', 'value': 'name_1'},
    {'field': 'bar.count', 'op': '>=', 'value': 5},
]
filtered_query = apply_filters(Foo, query, filter_spec)
```

``` {.sourceCode .python}
query = session.query(Foo)  # join to Bar will be automatically applied

filter_spec = [
    {field': 'name', 'op': '==', 'value': 'name_1'},
    {'field': 'bar.count', 'op': '>=', 'value': 5},
]
filtered_query = apply_filters(Foo, query, filter_spec)
```

The automatic join is only possible if
[SQLAlchemy](https://www.sqlalchemy.org/) can implictly determine the
condition for the join, for example because of a foreign key
relationship.

Automatic joins allow flexibility for clients to filter and sort by
related objects without specifying all possible joins on the server
beforehand. Feature can be explicitly disabled by passing
`do_auto_join=False` argument to the `apply_filters` call.

It is also possible to apply filters to queries defined by fields,
functions or `select_from` clause:

``` {.sourceCode .python}
query_alt_1 = session.query(Foo.id, Foo.name)
query_alt_2 = session.query(func.count(Foo.id))
query_alt_3 = session.query().select_from(Foo).add_column(Foo.id)
```

The automatic join will inner join relationships by default, to
outer join a relationship add the `outer_join` property to yur spec:

``` {.sourceCode .python}
filter_spec = [
    {'field': 'bar.count', 'op': 'is_null', 'outer_join': True},
]
```

### Hybrid attributes

You can filter by a [hybrid
attribute](https://docs.sqlalchemy.org/en/13/orm/extensions/hybrid.html):
a [hybrid
property](https://docs.sqlalchemy.org/en/13/orm/extensions/hybrid.html#sqlalchemy.ext.hybrid.hybrid_property)
or a [hybrid
method](https://docs.sqlalchemy.org/en/13/orm/extensions/hybrid.html#sqlalchemy.ext.hybrid.hybrid_method).

``` {.sourceCode .python}
query = session.query(Foo)

filter_spec = [{'field': 'count_square', 'op': '>=', 'value': 25}]
filter_spec = [{'field': 'three_times_count', 'op': '>=', 'value': 15}]

filtered_query = apply_filters(Foo, query, filter_spec)
result = filtered_query.all()
```

Sort
----

``` {.sourceCode .python}
from sqlalchemy_filters import apply_sort


# `query` should be a SQLAlchemy query object

sort_spec = [
    {'field': 'name', 'direction': 'asc'},
    {'field': 'bar.id', 'direction': 'desc'},
]
sorted_query = apply_sort(Foo, query, sort_spec)

result = sorted_query.all()
```

`apply_sort` will attempt to automatically join models to `query` if
they're not already present and a model-specific sort is supplied. The
behaviour is the same as in `apply_filters`.

This allows flexibility for clients to sort by fields on related objects
without specifying all possible joins on the server beforehand.

### Hybrid attributes

You can sort by a [hybrid
attribute](https://docs.sqlalchemy.org/en/13/orm/extensions/hybrid.html):
a [hybrid
property](https://docs.sqlalchemy.org/en/13/orm/extensions/hybrid.html#sqlalchemy.ext.hybrid.hybrid_property)
or a [hybrid
method](https://docs.sqlalchemy.org/en/13/orm/extensions/hybrid.html#sqlalchemy.ext.hybrid.hybrid_method).

Pagination
----------

``` {.sourceCode .python}
from sqlalchemy_filters import apply_pagination


# `query` should be a SQLAlchemy query object

query, pagination = apply_pagination(query, page_number=1, page_size=10)

page_size, page_number, num_pages, total_results = pagination

assert 10 == len(query)
assert 10 == page_size == pagination.page_size
assert 1 == page_number == pagination.page_number
assert 3 == num_pages == pagination.num_pages
assert 22 == total_results == pagination.total_results
```

Filters format
--------------

Filters must be provided in a list and will be applied sequentially.
Each filter will be a dictionary element in that list, using the
following format:

``` {.sourceCode .python}
filter_spec = [
    {'field': 'field_name', 'op': '==', 'value': 'field_value'},
    {'field': 'relation_field.field_2_name', 'op': '!=', 'value': 'field_2_value'},
    # ...
]
```

Where `field` is the name of the field that will be filtered using the
operator provided in `op` (optional, defaults to `==`) and the provided
`value` (optional, depending on the operator).

This is the list of operators that can be used:

-   `is_null`
-   `is_not_null`
-   `==`, `eq`
-   `!=`, `ne`
-   `>`, `gt`
-   `<`, `lt`
-   `>=`, `ge`
-   `<=`, `le`
-   `like`
-   `ilike`
-   `not_ilike`
-   `in`
-   `not_in`
-   `any`
-   `not_any`

### any / not\_any

PostgreSQL specific operators allow to filter queries on columns of type
`ARRAY`. Use `any` to filter if a value is present in an array and
`not_any` if it's not.

### Boolean Functions

`and`, `or`, and `not` functions can be used and nested within the
filter specification:

``` {.sourceCode .python}
filter_spec = [
    {
        'or': [
            {
                'and': [
                    {'field': 'field_name', 'op': '==', 'value': 'field_value'},
                    {'field': 'field_2_name', 'op': '!=', 'value': 'field_2_value'},
                ]
            },
            {
                'not': [
                    {'field': 'field_3_name', 'op': '==', 'value': 'field_3_value'}
                ]
            },
        ],
    }
]
```

Note: `or` and `and` must reference a list of at least one element.
`not` must reference a list of exactly one element.

Sort format
-----------

Sort elements must be provided as dictionaries in a list and will be
applied sequentially:

``` {.sourceCode .python}
sort_spec = [
    {'field': 'name', 'direction': 'asc'},
    {'field': 'bar.id', 'direction': 'desc'},
    # ...
]
```

Where `field` is the name of the field that will be sorted using the
provided `direction`.

The `model` key is optional if the original query being sorted only
applies to one model.

### nullsfirst / nullslast

``` {.sourceCode .python}
sort_spec = [
    {'field': 'count', 'direction': 'asc', 'nullsfirst': True},
    # ...
]
```

`nullsfirst` is an optional attribute that will place `NULL` values
first if set to `True`, according to the [SQLAlchemy
documentation](https://docs.sqlalchemy.org/en/latest/core/sqlelement.html#sqlalchemy.sql.expression.nullsfirst).

`nullslast` is an optional attribute that will place `NULL` values last
if set to `True`, according to the [SQLAlchemy
documentation](https://docs.sqlalchemy.org/en/latest/core/sqlelement.html#sqlalchemy.sql.expression.nullslast).

If none of them are provided, then `NULL` values will be sorted
according to the RDBMS being used. SQL defines that `NULL` values should
be placed together when sorting, but it does not specify whether they
should be placed first or last.

Even though both `nullsfirst` and `nullslast` are part of
[SQLAlchemy](https://www.sqlalchemy.org/), they will raise an unexpected
exception if the RDBMS that is being used does not support them.

At the moment they are [supported by
PostgreSQL](https://www.postgresql.org/docs/current/queries-order.html),
but they are **not** supported by SQLite and MySQL.

# Development

## Running tests
The default configuration uses **SQLite**, **MySQL** (if the driver is
installed) and **PostgreSQL** (if the driver is installed) to run
the tests, with the following URIs:

``` {.sourceCode .shell}
sqlite+pysqlite:///test_sqlalchemy_filters.db
mysql+mysqlconnector://root:@localhost:3306/test_sqlalchemy_filters
postgresql+psycopg2://postgres:@localhost:5432/test_sqlalchemy_filters?client_encoding=utf8'
```

A test database will be created, used during the tests and destroyed
afterwards for each RDBMS configured.

In order to run tests you need to create a MySQL and PostgreSQL database using the default ports and configuration:
```
docker run -d --rm --name postgres-sqlalchemy-filters -p 5432:5432 \
    -e POSTGRES_USER=postgres \
    -e POSTGRES_HOST_AUTH_METHOD=trust \
    -e POSTGRES_DB=test_sqlalchemy_filters \
    -e POSTGRES_INITDB_ARGS="--encoding=UTF8 --lc-collate=en_US.utf8 --lc-ctype=en_US.utf8" \
    postgres:9.6

docker run -d --rm --name mysql-sqlalchemy-filters -p 3306:3306 \
    -e MYSQL_ALLOW_EMPTY_PASSWORD=yes \
    mysql:5.7
```

Make sure to run `poetry install --extras "mysql postgresql"` to install all db connectors. To run the tests locally: `poetry run pytest test`.

Database management systems
---------------------------

The following RDBMS are supported (tested):

-   SQLite
-   MySQL
-   PostgreSQL

SQLAlchemy support
------------------

The following [SQLAlchemy](https://www.sqlalchemy.org/) versions are
supported: `1.0`, `1.1`, `1.2`, `1.3`.

Changelog
---------

Consult the
[CHANGELOG](https://github.com/juliotrigo/sqlalchemy-filters/blob/master/CHANGELOG.rst)
document for fixes and enhancements of each version.

License
-------

Apache 2.0. See
[LICENSE](https://github.com/juliotrigo/sqlalchemy-filters/blob/master/LICENSE)
for details.
