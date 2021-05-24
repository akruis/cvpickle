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
Testsuite for cvpickle
'''
import unittest
import contextvars
import cvpickle
import pickle
import io

cvar1 = contextvars.ContextVar("cvar1")
cvar1.set('cvar1-value')
cvar2 = contextvars.ContextVar("cvar2")
cvar2.set('cvar2-value')

MODULE_NAME = __name__

class Test(unittest.TestCase):
    cvar3 = contextvars.ContextVar("cvar3")
    cvar3.set('cvar3-value')

    def test_contextreducer(self):
        context_reducer = cvpickle.ContextReducer()
        context_reducer.register_contextvar(cvar1, __name__)
        context_reducer.register_contextvar(self.cvar3, __name__, type(self).__name__ + '.cvar3')
        ctx = contextvars.copy_context()
        reduced = context_reducer(ctx)
        
        self.assertIsInstance(reduced, tuple)
        self.assertEqual(len(reduced), 2)
        self.assertIs(reduced[0], cvpickle._context_factory)
        args = reduced[1]
        self.assertIsInstance(args, tuple)
        self.assertEqual(len(args), 2)
        self.assertIs(args[0], None)
        self.assertDictEqual(args[1], {
            (MODULE_NAME, 'Test.cvar3'): 'cvar3-value',
            (MODULE_NAME, 'cvar1'): 'cvar1-value'})

    def test_context_factory(self):
        ctx = cvpickle._context_factory(contextvars.Context, {
            (MODULE_NAME, 'Test.cvar3'): 'cvar3-new-value',
            (MODULE_NAME, 'cvar1'): 'cvar1-new-value'})
        self.assertIsInstance(ctx, contextvars.Context)
        self.assertEqual(len(ctx), 2)
        self.assertEqual(ctx[cvar1], 'cvar1-new-value')
        self.assertEqual(ctx[self.cvar3], 'cvar3-new-value')

    def _test_pickle(self, factory_is_copy_context, protocol=None):
        context_reducer = cvpickle.ContextReducer(factory_is_copy_context=factory_is_copy_context)
        context_reducer.register_contextvar(cvar1, __name__)
        context_reducer.register_contextvar(self.cvar3, __name__, type(self).__name__ + '.cvar3')
        ctx = contextvars.copy_context()

        f = io.BytesIO()
        pickler = pickle.Pickler(f, protocol=protocol)
        pickler.dispatch_table = {contextvars.Context: context_reducer}
        pickler.dump(ctx)
        p = f.getvalue()

        # import pickletools; p = pickletools.optimize(p) ; pickletools.dis(p)
        ctx2 = pickle.loads(p)
        self.assertIsNot(ctx2, ctx)
        self.assertIsInstance(ctx2, contextvars.Context)
        if not factory_is_copy_context:
            self.assertEqual(len(ctx2), 2)
        self.assertEqual(ctx2[cvar1], 'cvar1-value')
        self.assertEqual(ctx2[self.cvar3], 'cvar3-value')

    def test_pickle_default(self):
        self._test_pickle(False)

    def test_pickle_copy_context(self):
        self._test_pickle(True)

    def test_pickle_proto_0(self):
        self._test_pickle(False, 0)

    def test_pickle_proto_highest(self):
        self._test_pickle(False, -1)

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()