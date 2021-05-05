# Pickling support for contextvars.Context objects
# Copyright (c) 2021  Anselm Kruis
#
# This library is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# This library is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this library; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Suite 500, Boston, MA  02110-1335  USA.

'''
cvpickle --- make contextvar.Context picklable

A minimal example:
>>> import cvpickle
>>> import contextvars
...
>>> my_context_var = contextvars.ContextVar("my_context_var")
>>> cvpickle.register_contextvar(my_context_var, __name__)

Pickling of context objects is not possible by default for two reasons, given in
https://www.python.org/dev/peps/pep-0567/#making-context-objects-picklable:

   1. ContextVar objects do not have __module__ and __qualname__ attributes,
      making straightforward pickling of Context objects impossible.
   2. Not all context variables refer to picklable objects. Making a ContextVar
      picklable must be an opt-in.

The module "cvpickle" provides a reducer (class ContextReducer) for context objects.
You have to register a ContextVar with the reducer to get it pickled.

For convenience, the module provides a global ContextReducer object in
cvpickle.default_context_reducer and ContextVar (un-)registration functions
cvpickle.register_contextvar() and cvpickle.unregister_contextvar()
'''

import contextvars
import types
import importlib
from pickle import _getattribute
import copyreg


class _ContextVarProxy:
    def __init__(self, module_name, qualname):
        self.module_name = module_name
        self.qualname = qualname


def _context_factory(cls, mapping):
    if cls is None:
        context = contextvars.Context()
    else:
        context = cls()

    def set_vars():
        for (modulename, qualname), value in mapping.items():
            module = importlib.import_module(modulename)
            cv = _getattribute(module, qualname)[0]
            cv.set(value)
            
    context.run(set_vars)
    return context


class ContextReducer:
    """A ContestReducer is a reduction function for a contextvars.Context object.
    """

    def __init__(self, *, auto_register=False, factory_is_copy_context=False):
        # contextvars.ContextVar is hashable, but it is not possible to create a weak reference
        # to a ContextVar (as of Python 3.7.1). Therefore we use a regular dictionary instead of
        # weakref.WeakKeyDictionary(). That's no problem, because deleting a ContextVar always leaks
        # references 
        self.picklable_contextvars = {}
        self.auto_register = auto_register
        self.factory_is_copy_context = factory_is_copy_context
    
    def __call__(self, context):
        """Reduce a contextvars.Context object
        """
        if not isinstance(context, contextvars.Context):
            raise TypeError('Argument must be a Context object not {}'.format(type(context).__name__))
        cvars = {}
        for cv, value in context.items():
            mod_and_name = self.picklable_contextvars.get(cv)
            if mod_and_name is not None:
                cvars[mod_and_name] = value

        if self.factory_is_copy_context:
            cls = contextvars.copy_context
        else:
            cls = type(context)
            if cls is contextvars.Context:
                # class contextvars.Context can't be pickled, because its __module__ is 'builtins' (Python 3.7.5)
                cls = None
        return _context_factory, (cls, cvars)

    def register_contextvar(self, contextvar, module, qualname=None, *, validate=True):
        """Register a context variable
        """
        if not isinstance(contextvar, contextvars.ContextVar):
            raise TypeError('Argument 1 must be a ContextVar object not {}'.format(type(contextvar).__name__))
        
        modulename = module
        is_module = isinstance(module, types.ModuleType)
        if is_module:
            modulename = module.__name__
        if qualname is None:
            qualname = contextvar.name
        if validate:
            if not is_module:
                module = importlib.import_module(modulename)
            v = _getattribute(module, qualname)[0]  # raises AttributeError
            if v is not contextvar:
                raise ValueError('Not the same object: ContextVar {} and global {}.{}'.format(contextvar.name, modulename, qualname))
        self.picklable_contextvars[contextvar] = (modulename, qualname)
        if self.auto_register:
            self.auto_register = False
            copyreg.pickle(contextvars.Context, self)
            # in case of stackless python enable context pickling
            try:
                from stackless import PICKLEFLAGS_PICKLE_CONTEXT, pickle_flags, pickle_flags_default
            except ImportError:
                pass
            else:
                pickle_flags(PICKLEFLAGS_PICKLE_CONTEXT, PICKLEFLAGS_PICKLE_CONTEXT)
                pickle_flags_default(PICKLEFLAGS_PICKLE_CONTEXT, PICKLEFLAGS_PICKLE_CONTEXT)
    
    def unregister_contextvar(self, contextvar):
        """Unregister a context variable
        """
        del self.picklable_contextvars[contextvar]
        
default_context_reducer = ContextReducer(auto_register=True, factory_is_copy_context=True)

def register_contextvar(contextvar, module, qualname=None, *, validate=True):
    return default_context_reducer.register_contextvar(contextvar, module, qualname, validate=validate)

def unregister_contextvar(contextvar):
    return default_context_reducer.unregister_contextvar(contextvar)
