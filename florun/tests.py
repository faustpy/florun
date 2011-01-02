#!/usr/bin/python
# -*- coding: utf8 -*-

import unittest

from flow import Flow, Node, Interface, FlowError, NodeNotFoundError


class INode(Node):
    def __init__(self, *args, **kwargs):
        Node.__init__(self, *args, **kwargs)
        self.i1 = Interface(self, 'i1', type=Interface.INPUT)
        self.i2 = Interface(self, 'i2', type=Interface.OUTPUT)
        self.i3 = Interface(self, 'i3', type=Interface.PARAMETER)
        self.i4 = Interface(self, 'i4', type=Interface.RESULT)


class TestFlow(unittest.TestCase):

    def setUp(self):
        self.flow = Flow()
        self.n1 = INode()
        self.n2 = INode()
        self.f1 = Flow()
        self.f1.addNode(self.n1)
        self.f1.addNode(self.n2)

    def test_addNode(self):
        self.assertEqual(self.flow.nodes, [])
        n = Node()
        self.flow.addNode(n)
        self.assertEqual(self.flow.nodes, [n])
        self.assertEqual(n.flow, self.flow)
        self.assertTrue(n in self.flow.nodes)
        self.assertTrue(n in self.flow.startNodes)
        # Add it twice
        self.flow.addNode(Node(id='foo'))
        self.assertRaises(FlowError, self.flow.addNode, Node(id='foo'))
        # Add it twice without name
        self.flow.addNode(Node())
        self.flow.addNode(Node())  # Not raising

    def test_removeNode(self):
        self.assertEqual(self.flow.nodes, [])
        self.assertRaises(FlowError, self.flow.removeNode, Node())
        n = Node()
        self.flow.addNode(n)
        self.flow.removeNode(n)
        self.assertFalse(n in self.flow.nodes)
        self.assertEqual(n.flow, None)

    def test_findNode(self):
        self.assertRaises(NodeNotFoundError, self.flow.findNode, 'foo')
        n = Node()
        self.flow.addNode(n)
        self.assertEqual(n, self.flow.findNode(''))
        n = Node(id='bar')
        self.flow.addNode(n)
        self.assertNotEqual(n, self.flow.findNode(''))
        self.assertEqual(n, self.flow.findNode('bar'))

    def test_randomId(self):
        class FooNode(Node):
            label = 'foo'
        self.flow.addNode(FooNode())
        self.assertEqual('foo', self.flow.randomId(FooNode()))
        self.flow.addNode(FooNode())
        self.assertEqual('foo-2', self.flow.randomId(FooNode()))
        self.flow.addNode(FooNode())
        self.assertEqual('foo-3', self.flow.randomId(FooNode()))
        self.flow.addNode(FooNode())
        self.assertEqual('foo-4', self.flow.randomId(FooNode()))

    def test_addConnector(self):
        i1 = self.n2.findInterface('i1')
        i2 = self.n1.findInterface('i2')
        self.f1.addConnector(i2, i1)
        self.assertEqual(1, len(self.n1.successors))
        self.assertEqual(0, len(self.n2.successors))
        self.assertEqual(0, len(self.n1.predecessors))
        self.assertEqual(1, len(self.n2.predecessors))
        self.assertTrue(self.n1 in self.f1.startNodes)
        self.assertFalse(self.n2 in self.f1.startNodes)
        self.assertRaises(FlowError, self.f1.addConnector, i1, i2)

    def test_removeConnector(self):
        i1 = self.n1.findInterface('i1')
        i2 = self.n2.findInterface('i2')
        self.f1.addConnector(i2, i1)
        self.assertRaises(FlowError, self.f1.removeConnector, i1, i2)
        self.flow.removeConnector(i2, i1)
        self.assertTrue(self.n1 in self.f1.startNodes)
        self.assertTrue(self.n2 in self.f1.startNodes)
        self.assertEqual(0, len(self.n1.successors))
        self.assertEqual(0, len(self.n2.successors))
        self.assertEqual(0, len(self.n1.predecessors))
        self.assertEqual(0, len(self.n2.predecessors))
        self.assertRaises(FlowError, self.f1.removeConnector, i2, i1)


class TestInterface(unittest.TestCase):

    def setUp(self):
        self.n1 = INode()
        self.n2 = INode()
        self.f1 = Flow()
        self.f1.addNode(self.n1)
        self.f1.addNode(self.n2)
        self.i1 = self.n2.findInterface('i1')
        self.i2 = self.n1.findInterface('i2')
        self.i3 = self.n2.findInterface('i3')
        self.i4 = self.n1.findInterface('i4')

    def test_repr(self):
        n = INode(id='foo')
        i = n.findInterface('i1')
        self.assertEqual("INode(foo)::Interface(i1)", unicode(i))

    def test_isInput(self):
        self.assertTrue(self.i1.isInput())
        self.assertTrue(self.i3.isInput())
        self.assertFalse(self.i2.isInput())
        self.assertFalse(self.i4.isInput())

    def test_isCompatible(self):
        self.assertFalse(self.i1.isCompatible(self.i1))  # Same interface
        self.assertFalse(self.i1.isCompatible(self.i3))  # Same node

        self.assertEqual(self.i1.type, Interface.INPUT)
        self.assertEqual(self.i2.type, Interface.OUTPUT)
        self.assertEqual(self.i3.type, Interface.PARAMETER)
        self.assertEqual(self.i4.type, Interface.RESULT)
        
        self.assertTrue(self.i1.isCompatible(self.i2))
        self.assertTrue(self.i1.isCompatible(self.i4))
        self.assertTrue(self.i3.isCompatible(self.i2))
        self.assertTrue(self.i3.isCompatible(self.i4))
        
        self.assertFalse(self.i2.isCompatible(self.i1))
        self.assertFalse(self.i2.isCompatible(self.i3))
        self.assertFalse(self.i4.isCompatible(self.i1))
        self.assertFalse(self.i4.isCompatible(self.i3))

    def test_addSuccessor(self):
        self.assertFalse(self.i2 in self.i1.successors)
        self.assertFalse(self.i1 in self.i2.predecessors)
        self.i2.addSuccessor(self.i1)
        self.assertTrue(self.i1 in self.i2.successors)
        self.assertTrue(self.i2 in self.i1.predecessors)
        self.assertRaises(FlowError, self.i1.addSuccessor, self.i2)

    def test_removeSuccessor(self):
        self.assertFalse(self.i2 in self.i1.successors)
        self.assertFalse(self.i1 in self.i2.predecessors)
        self.assertRaises(FlowError, self.i1.removeSuccessor, self.i2)
        self.i2.addSuccessor(self.i1)
        self.assertRaises(FlowError, self.i1.removeSuccessor, self.i2)
        self.i2.removeSuccessor(self.i1)
        self.assertFalse(self.i2 in self.i1.successors)
        self.assertFalse(self.i1 in self.i2.predecessors)


class TestNode(unittest.TestCase):

    def setUp(self):
        self.n1 = INode()
        self.f1 = Flow()
        self.f1.addNode(self.n1)

    def test_findInterface(self):
        self.assertTrue(self.n1.findInterface('i1'))
        self.assertRaises(FlowError, self.n1.findInterface, 'foo')

    def test_applyAttributes(self):
        pass


if __name__ == '__main__':
    unittest.main()
