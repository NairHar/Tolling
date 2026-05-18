
import sys
from abc import ABCMeta, abstractmethod
import numpy as np
from datetime import datetime

class ValidatingProperty(metaclass=ABCMeta):
    def __init__(self, name, docstring=''):
        self.name=str(name)
        self.__doc__=str(docstring)
        self._mangled = '_{}'.format(name)

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return getattr(obj, self._mangled)
    
    def __set__(self, obj, value):
        try:
            value = self.validate_data(obj, value)
        except Exception:
            (etype, err, tb) = sys.exc_info()
            raise ValueError()
        setattr(obj, self._mangled, value)

    @classmethod
    def validate(cls, value, *args, **kwargs):
        if not args:
            kwargs=kwargs.copy()
            kwargs.setdefault('name', '__auto')
        isinstance = cls(*args, **kwargs)
        try:
            return isinstance.validate_date(None, value)
        except Exception:
            raise ValueError
        
    @abstractmethod
    def validate_data(self, obj, value):
        return value



class NullableProperty(ValidatingProperty):
    def __init__(self, name, nullable=True, docstring=''):
        super(NullableProperty, self).__init__(name, docstring)
        self.nullable=bool(nullable)

    @abstractmethod
    def _validate(self, obj, value):
        return value
    
    def validate_data(self, obj, value):
        if value is None:
            if self.nullable:
                return value
            else:
                raise ValueError("Value cannot be None")
        return self._validate(obj, value)
    


class DatetimeIndexProperty(NullableProperty):
    def __init__(self, name, nullable=False, docstring=''):
        def __init__(self, name, nullable=False, docstring=''):
            super(DatetimeIndexProperty, self).__init__(name, nullable, docstring)

    def _validate(self, obj, value):
        try:
            return (value)
        except Exception:
            raise ValueError    




class ArrayProperty(NullableProperty):
    def __init__(self, name, dtype=None, nullable=False, positive=False,
                 allow_scalar=False, ndim=None, shape=None, readonly=False,
                 copy=True, docstring='',additional_validation=None):
        super(ArrayProperty, self).__init__(name, nullable, docstring)
        self.positive = bool(positive)
        self.allow_scalar = bool(allow_scalar)
        self.dtype = dtype
        self.ndim = ndim
        self.shape = shape
        self.readonly = readonly
        self.copy = copy
        self.additional_validation = additional_validation

    def _validate(self, obj, value):
        from collections.abc import Iterable
        from numpy.lib.stride_tricks import as_strided

        shape = self.shape(obj) if callable(self.shape) else self.shape
        ndim = self.ndim(obj) if callable(self.ndim) else self.ndim

        if (isinstance(value, (str, np.generic)) or not isinstance(value, Iterable)):
            if not self.allow_scalar:
                raise TypeError('Cannot cast scalar to array when allow_scalr is False')
            elif ndim is None and shape is None:
                raise ValueError('At least one of ndim and shape must be set if casting scalar')
            elif shape is not None:
                value = as_strided(np.asarray(value), shape=shape, strides=[0]*len(shape))
            else:
                value = np.array([value], ndim=ndim)

        value = np.asarray(value)

        if shape is not None and shape != value.shape:
            raise ValueError("Expected array of shape {exp}, got {got} instead""".format(exp=shape,got=value.shape))
        
        elif ndim is not None and ndim!=len(value.shape):
            raise ValueError(f"Expected array of {ndim:value.shape} dimensions, got shape={shape} ({len(value.shape):d} dims)")
        
        if self.dtype is not None:
            value = value.astype(self.dtype)

        if self.positive:
            neg = value<0
            if neg.any():
                raise ValueError()
            
        if self.readonly:
            if self.copy:
                value = value.copy()
            value.setflags(write=False)

        if self.additional_validation:
            value = self.additional_validation(value)
        return value
            

        
        

class CallableProperty(NullableProperty):
    def __init__(self, name, nullable=False, allow_scalar=False, docstring=''):
        super(CallableProperty, self).__init__(name, nullable, docstring)
        self.allow_scalar = allow_scalar

    def _validate(self, obj, value):
        if callable(value):
            return value
        if self.allow_scalar:
            return lambda *args, **kwargs:value
        

class FloatProperty(NullableProperty):
    def __init__(self, name, nullable=False, positive=False, docstring=''):
        super(FloatProperty, self).__init__(name, nullable, docstring)
        self.positive = bool(positive)

    def _validate(self, obj, value):
        try:
            value = float(value)
        except (TypeError, ValueError):
            raise ValueError
        if self.positive and value<0:
            raise ValueError
        return value
    
class DateTimeProperty(NullableProperty):
    def __init__(self, name, nullable=False, docstring=''):
        super(DateTimeProperty,self).__init__(name, nullable, docstring)

    def _validate(self, obj, value):
        try:
            if isinstance(value, datetime):
                return value
        except Exception:
            raise ValueError
        
class EnumProperty(NullableProperty):
    def __init__(self, name, enum_values, nullable=False, transform=None, docstring=''):
        super(EnumProperty, self).__init__(name, nullable, docstring)
        try:
            self.enum_values=set(enum_values)
        except TypeError:
            self.enum_values=tuple(enum_values)
        if transform is not None:
            assert callable(transform)
        self.transform = transform

    def _validate(self, obj, value):
        if self.transform is not None:
            value = self.trasnform(value)
        if value not in self.enum_values:
            raise ValueError
        return value
    

class TypedProperty(NullableProperty):
    def __init__(self, name, obj_type, nullable=False, docstring=''):
        super(TypedProperty, self).__init__(name, nullable, docstring)
        self.obj_type = obj_type

    def _validate(self, obj, value):
        if not isinstance(value,self.obj_type):
            raise ValueError
        return value