# -*- coding: utf-8 -*-
"""
    jinja2.runtime
    ~~~~~~~~~~~~~~

    Runtime helpers.

    :copyright: Copyright 2008 by Armin Ronacher.
    :license: BSD.
"""
import sys
from itertools import chain, imap
from jinja2.utils import Markup, partial, soft_unicode, escape, missing, \
     concat, MethodType, FunctionType
from jinja2.exceptions import UndefinedError, TemplateRuntimeError


# these variables are exported to the template runtime
__all__ = ['LoopContext', 'Context', 'TemplateReference', 'Macro', 'Markup',
           'TemplateRuntimeError', 'missing', 'concat', 'escape',
           'markup_join', 'unicode_join']


#: the types we support for context functions
_context_function_types = (FunctionType, MethodType)


def markup_join(seq):
    """Concatenation that escapes if necessary and converts to unicode."""
    buf = []
    iterator = imap(soft_unicode, seq)
    for arg in iterator:
        buf.append(arg)
        if hasattr(arg, '__html__'):
            return Markup(u'').join(chain(buf, iterator))
    return concat(buf)


def unicode_join(seq):
    """Simple args to unicode conversion and concatenation."""
    return concat(imap(unicode, seq))


class Context(object):
    """The template context holds the variables of a template.  It stores the
    values passed to the template and also the names the template exports.
    Creating instances is neither supported nor useful as it's created
    automatically at various stages of the template evaluation and should not
    be created by hand.

    The context is immutable.  Modifications on :attr:`parent` **must not**
    happen and modifications on :attr:`vars` are allowed from generated
    template code only.  Template filters and global functions marked as
    :func:`contextfunction`\s get the active context passed as first argument
    and are allowed to access the context read-only.

    The template context supports read only dict operations (`get`,
    `keys`, `values`, `items`, `iterkeys`, `itervalues`, `iteritems`,
    `__getitem__`, `__contains__`).  Additionally there is a :meth:`resolve`
    method that doesn't fail with a `KeyError` but returns an
    :class:`Undefined` object for missing variables.
    """
    __slots__ = ('parent', 'vars', 'environment', 'exported_vars', 'name',
                 'blocks', '__weakref__')

    def __init__(self, environment, parent, name, blocks):
        self.parent = parent
        self.vars = vars = {}
        self.environment = environment
        self.exported_vars = set()
        self.name = name

        # create the initial mapping of blocks.  Whenever template inheritance
        # takes place the runtime will update this mapping with the new blocks
        # from the template.
        self.blocks = {k: [v] for k, v in blocks.iteritems()}

    def super(self, name, current):
        """Render a parent block."""
        try:
            blocks = self.blocks[name]
            index = blocks.index(current) + 1
            blocks[index]
        except LookupError:
            return self.environment.undefined('there is no parent block '
                                              'called %r.' % name,
                                              name='super')
        return BlockReference(name, self, blocks, index)

    def get(self, key, default=None):
        """Returns an item from the template context, if it doesn't exist
        `default` is returned.
        """
        try:
            return self[key]
        except KeyError:
            return default

    def resolve(self, key):
        """Looks up a variable like `__getitem__` or `get` but returns an
        :class:`Undefined` object with the name of the name looked up.
        """
        if key in self.vars:
            return self.vars[key]
        if key in self.parent:
            return self.parent[key]
        return self.environment.undefined(name=key)

    def get_exported(self):
        """Get a new dict with the exported variables."""
        return {k: self.vars[k] for k in self.exported_vars}

    def get_all(self):
        """Return a copy of the complete context as dict including the
        exported variables.
        """
        return dict(self.parent, **self.vars)

    def call(__self, __obj, *args, **kwargs):
        """Call the callable with the arguments and keyword arguments
        provided but inject the active context or environment as first
        argument if the callable is a :func:`contextfunction` or
        :func:`environmentfunction`.
        """
        if __debug__:
            __traceback_hide__ = True
        if isinstance(__obj, _context_function_types):
            if getattr(__obj, 'contextfunction', 0):
                args = (__self,) + args
            elif getattr(__obj, 'environmentfunction', 0):
                args = (__self.environment,) + args
        return __obj(*args, **kwargs)

    def _all(meth):
        proxy = lambda self: getattr(self.get_all(), meth)()
        proxy.__doc__ = getattr(dict, meth).__doc__
        proxy.__name__ = meth
        return proxy

    keys = _all('keys')
    values = _all('values')
    items = _all('items')
    iterkeys = _all('iterkeys')
    itervalues = _all('itervalues')
    iteritems = _all('iteritems')
    del _all

    def __contains__(self, name):
        return name in self.vars or name in self.parent

    def __getitem__(self, key):
        """Lookup a variable or raise `KeyError` if the variable is
        undefined.
        """
        item = self.resolve(key)
        if isinstance(item, Undefined):
            raise KeyError(key)
        return item

    def __repr__(self):
        return '<%s %s of %r>' % (
            self.__class__.__name__,
            repr(self.get_all()),
            self.name
        )


# register the context as mapping if possible
try:
    from collections import Mapping
    Mapping.register(Context)
except ImportError:
    pass


class TemplateReference(object):
    """The `self` in templates."""

    def __init__(self, context):
        self.__context = context

    def __getitem__(self, name):
        blocks = self.__context.blocks[name]
        wrap = self.__context.environment.autoescape and \
               Markup or (lambda x: x)
        return BlockReference(name, self.__context, blocks, 0)

    def __repr__(self):
        return '<%s %r>' % (
            self.__class__.__name__,
            self.__context.name
        )


class BlockReference(object):
    """One block on a template reference."""

    def __init__(self, name, context, stack, depth):
        self.name = name
        self._context = context
        self._stack = stack
        self._depth = depth

    @property
    def super(self):
        """Super the block."""
        if self._depth + 1 >= len(self._stack):
            return self._context.environment. \
                undefined('there is no parent block called %r.' %
                          self.name, name='super')
        return BlockReference(self.name, self._context, self._stack,
                              self._depth + 1)

    def __call__(self):
        rv = concat(self._stack[self._depth](self._context))
        if self._context.environment.autoescape:
            rv = Markup(rv)
        return rv


class LoopContext(object):
    """A loop context for dynamic iteration."""

    def __init__(self, iterable, recurse=None):
        self._iterator = iter(iterable)
        self._recurse = recurse
        self.index0 = -1

        # try to get the length of the iterable early.  This must be done
        # here because there are some broken iterators around where there
        # __len__ is the number of iterations left (i'm looking at your
        # listreverseiterator!).
        try:
            self._length = len(iterable)
        except (TypeError, AttributeError):
            self._length = None

    def cycle(self, *args):
        """Cycles among the arguments with the current loop index."""
        if not args:
            raise TypeError('no items for cycling given')
        return args[self.index0 % len(args)]

    first = property(lambda x: x.index0 == 0)
    last = property(lambda x: x.index0 + 1 == x.length)
    index = property(lambda x: x.index0 + 1)
    revindex = property(lambda x: x.length - x.index0)
    revindex0 = property(lambda x: x.length - x.index)

    def __len__(self):
        return self.length

    def __iter__(self):
        return LoopContextIterator(self)

    def loop(self, iterable):
        if self._recurse is None:
            raise TypeError('Tried to call non recursive loop.  Maybe you '
                            "forgot the 'recursive' modifier.")
        return self._recurse(iterable, self._recurse)

    # a nifty trick to enhance the error message if someone tried to call
    # the the loop without or with too many arguments.
    __call__ = loop; del loop

    @property
    def length(self):
        if self._length is None:
            # if was not possible to get the length of the iterator when
            # the loop context was created (ie: iterating over a generator)
            # we have to convert the iterable into a sequence and use the
            # length of that.
            iterable = tuple(self._iterator)
            self._iterator = iter(iterable)
            self._length = len(iterable) + self.index0 + 1
        return self._length

    def __repr__(self):
        return '<%s %r/%r>' % (
            self.__class__.__name__,
            self.index,
            self.length
        )


class LoopContextIterator(object):
    """The iterator for a loop context."""
    __slots__ = ('context',)

    def __init__(self, context):
        self.context = context

    def __iter__(self):
        return self

    def next(self):
        ctx = self.context
        ctx.index0 += 1
        return ctx._iterator.next(), ctx


class Macro(object):
    """Wraps a macro."""

    def __init__(self, environment, func, name, arguments, defaults,
                 catch_kwargs, catch_varargs, caller):
        self._environment = environment
        self._func = func
        self._argument_count = len(arguments)
        self.name = name
        self.arguments = arguments
        self.defaults = defaults
        self.catch_kwargs = catch_kwargs
        self.catch_varargs = catch_varargs
        self.caller = caller

    def __call__(self, *args, **kwargs):
        arguments = []
        for idx, name in enumerate(self.arguments):
            try:
                value = args[idx]
            except:
                try:
                    value = kwargs.pop(name)
                except:
                    try:
                        value = self.defaults[idx - self._argument_count]
                    except:
                        value = self._environment.undefined(
                            'parameter %r was not provided' % name, name=name)
            arguments.append(value)

        # it's important that the order of these arguments does not change
        # if not also changed in the compiler's `function_scoping` method.
        # the order is caller, keyword arguments, positional arguments!
        if self.caller:
            caller = kwargs.pop('caller', None)
            if caller is None:
                caller = self._environment.undefined('No caller defined',
                                                     name='caller')
            arguments.append(caller)
        if self.catch_kwargs:
            arguments.append(kwargs)
        elif kwargs:
            raise TypeError('macro %r takes no keyword argument %r' %
                            (self.name, iter(kwargs).next()))
        if self.catch_varargs:
            arguments.append(args[self._argument_count:])
        elif len(args) > self._argument_count:
            raise TypeError('macro %r takes not more than %d argument(s)' %
                            (self.name, len(self.arguments)))
        return self._func(*arguments)

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.name is None and 'anonymous' or repr(self.name)}>"


class Undefined(object):
    """The default undefined type.  This undefined type can be printed and
    iterated over, but every other access will raise an :exc:`UndefinedError`:

    >>> foo = Undefined(name='foo')
    >>> str(foo)
    ''
    >>> not foo
    True
    >>> foo + 42
    Traceback (most recent call last):
      ...
    UndefinedError: 'foo' is undefined
    """
    __slots__ = ('_undefined_hint', '_undefined_obj', '_undefined_name',
                 '_undefined_exception')

    def __init__(self, hint=None, obj=None, name=None, exc=UndefinedError):
        self._undefined_hint = hint
        self._undefined_obj = obj
        self._undefined_name = name
        self._undefined_exception = exc

    def _fail_with_undefined_error(self, *args, **kwargs):
        """Regular callback function for undefined objects that raises an
        `UndefinedError` on call.
        """
        if self._undefined_hint is None:
            if self._undefined_obj is None:
                hint = '%r is undefined' % self._undefined_name
            elif not isinstance(self._undefined_name, basestring):
                hint = '%r object has no element %r' % (
                    self._undefined_obj.__class__.__name__,
                    self._undefined_name
                )
            else:
                hint = '%r object has no attribute %r' % (
                    self._undefined_obj.__class__.__name__,
                    self._undefined_name
                )
        else:
            hint = self._undefined_hint
        raise self._undefined_exception(hint)

    __add__ = __radd__ = __mul__ = __rmul__ = __div__ = __rdiv__ = \
    __truediv__ = __rtruediv__ = __floordiv__ = __rfloordiv__ = \
    __mod__ = __rmod__ = __pos__ = __neg__ = __call__ = \
    __getattr__ = __getitem__ = __lt__ = __le__ = __gt__ = __ge__ = \
    __int__ = __float__ = __complex__ = __pow__ = __rpow__ = \
        _fail_with_undefined_error

    def __str__(self):
        return unicode(self).encode('utf-8')

    def __unicode__(self):
        return u''

    def __len__(self):
        return 0

    def __iter__(self):
        pass

    def __nonzero__(self):
        return False

    def __repr__(self):
        return 'Undefined'


class DebugUndefined(Undefined):
    """An undefined that returns the debug info when printed.

    >>> foo = DebugUndefined(name='foo')
    >>> str(foo)
    '{{ foo }}'
    >>> not foo
    True
    >>> foo + 42
    Traceback (most recent call last):
      ...
    UndefinedError: 'foo' is undefined
    """
    __slots__ = ()

    def __unicode__(self):
        if self._undefined_hint is None:
            if self._undefined_obj is None:
                return u'{{ %s }}' % self._undefined_name
            return '{{ no such element: %s[%r] }}' % (
                self._undefined_obj.__class__.__name__,
                self._undefined_name
            )
        return u'{{ undefined value printed: %s }}' % self._undefined_hint


class StrictUndefined(Undefined):
    """An undefined that barks on print and iteration as well as boolean
    tests and all kinds of comparisons.  In other words: you can do nothing
    with it except checking if it's defined using the `defined` test.

    >>> foo = StrictUndefined(name='foo')
    >>> str(foo)
    Traceback (most recent call last):
      ...
    UndefinedError: 'foo' is undefined
    >>> not foo
    Traceback (most recent call last):
      ...
    UndefinedError: 'foo' is undefined
    >>> foo + 42
    Traceback (most recent call last):
      ...
    UndefinedError: 'foo' is undefined
    """
    __slots__ = ()
    __iter__ = __unicode__ = __len__ = __nonzero__ = __eq__ = __ne__ = \
        Undefined._fail_with_undefined_error


# remove remaining slots attributes, after the metaclass did the magic they
# are unneeded and irritating as they contain wrong data for the subclasses.
del Undefined.__slots__, DebugUndefined.__slots__, StrictUndefined.__slots__
