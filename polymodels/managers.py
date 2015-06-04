from __future__ import unicode_literals

import warnings

import django
from django.core.exceptions import ImproperlyConfigured
from django.db import models


class PolymorphicQuerySet(models.query.QuerySet):
    def select_subclasses(self, *models):
        self.type_cast = True
        relateds = set()
        opts = self.model._meta
        accessors = opts._subclass_accessors
        if models:
            subclasses = set()
            for model in models:
                if not issubclass(model, self.model):
                    raise TypeError(
                        "%r is not a subclass of %r" % (model, self.model)
                    )
                subclasses.update(model._meta._subclass_accessors.keys())
            # Collect all `select_related` required lookups
            for subclass in subclasses:
                # Avoid collecting ourself and proxy subclasses
                related = accessors[subclass][2]
                if related:
                    relateds.add(related)
            queryset = self.filter(
                **self.model.content_type_lookup(*tuple(subclasses))
            )
        else:
            # Collect all `select_related` required relateds
            for accessor in accessors.values():
                # Avoid collecting ourself and proxy subclasses
                related = accessor[2]
                if accessor[2]:
                    relateds.add(related)
            queryset = self
        if relateds:
            queryset = queryset.select_related(*relateds)
        return queryset

    def exclude_subclasses(self):
        return self.filter(**self.model.content_type_lookup())

    def _clone(self, *args, **kwargs):
        kwargs.update(type_cast=getattr(self, 'type_cast', False))
        return super(PolymorphicQuerySet, self)._clone(*args, **kwargs)

    def iterator(self):
        iterator = super(PolymorphicQuerySet, self).iterator()
        if getattr(self, 'type_cast', False):
            for obj in iterator:
                yield obj.type_cast()
        else:
            # yield from iterator
            for obj in iterator:
                yield obj


class PolymorphicManager(models.Manager.from_queryset(PolymorphicQuerySet)):
    use_for_related_fields = True

    def contribute_to_class(self, model, name):
        # Avoid circular reference
        from .models import BasePolymorphicModel
        if not issubclass(model, BasePolymorphicModel):
            raise ImproperlyConfigured(
                '`%s` can only be used on '
                '`BasePolymorphicModel` subclasses.' % self.__class__.__name__
            )
        return super(PolymorphicManager, self).contribute_to_class(model, name)

    def get_queryset(self):
        queryset = super(PolymorphicManager, self).get_queryset()
        model = self.model
        opts = model._meta
        if opts.proxy:
            # Select only associated model and its subclasses.
            queryset = queryset.filter(**self.model.subclasses_lookup())
        return queryset

    # TODO: Remove when dropping support for Django 1.7
    if django.VERSION < (1, 8):
        def get_query_set(self):
            warnings.warn(
                "`PolymorphicManager.get_query_set` is deprecated, use `get_queryset` instead",
                DeprecationWarning,
                stacklevel=2
            )
            return PolymorphicManager.get_queryset(self)
