#!/usr/bin/python

import sys
import threading
from utils import logcore, empty, atoi
from xml.dom.minidom import Document, parseString
import tempfile
from gettext import gettext as _



class FlowException(Exception):
    pass



class Flow(object):
    """
    Represents a work-flow, in which each L{Node} executes operations. 
    """
    def __init__(self, **kwargs):
        self.modified = False
        self.filename = None
        self.nodes = []

    def addConnector(self, start, end):
        """
        @type start : {Interface}
        @type end   : {Interface}
        """
        self.modified = True
        start.addSuccessor(end)

    def addNode(self, node):
        """
        @param node : L{Node}
        """
        self.modified = True
        self.nodes.append(node)

    def removeConnector(self, start, end):
        """
        @type start : {Interface}
        @type end   : {Interface}
        """
        self.modified = True
        start.removeSuccessor(end)

    def removeNode(self, node):
        """
        @type node : L{Node}
        """
        self.modified = True
        self.nodes.remove(node)
    
    def randomId(self, node):
        """
        Generates a non-existing node id
        @rtype: string
        """
        id = "%s" % node.label
        i = 2
        while id in [n.id for n in self.nodes]:
            id = "%s-%s" % (node.label, i)
            i = i + 1
        return id
    
    def findNode(self, id):
        """
        Find node by its id
        @rtype: L{Node}
        """
        for n in self.nodes:
            if n.id == id:
                return n
        raise Exception(_(u"Node with id '%s' not found.") % id)
    
    @staticmethod
    def load(filename):
        """
        @type filename : string
        @rtype : L{Flow}
        """
        logcore.info(_("Load flow from file '%s'") % filename)
        fd = open(filename)
        content = fd.read()
        fd.close()
        f = Flow.importXml(content)
        f.filename = filename
        f.modified = False
        return f
    
    def save(self, filename=None):
        if filename is None:
            filename = self.filename
        xml = self.exportXml()
        logcore.info(_("Save flow to file '%s'") % filename)
        fd = open(filename, 'w')
        fd.write(xml)
        fd.close()
        self.modified = False

    @property
    def inputNodes(self):
        return [n for n in self.nodes if issubclass(n.__class__, InputNode)]
    
    def CLIParameterNodes(self):
        return [n for n in self.nodes 
                  if issubclass(n.__class__, CommandLineParameterInputNode)]
    
    @classmethod
    def importXml(cls, xmlcontent):
        """
        @type xmlcontent: string
        @rtype: L{Flow}
        """
        flow = Flow()
        dom = parseString(xmlcontent)
     
        for xmlnode in dom.getElementsByTagName('node'):
            id        = xmlnode.getAttribute('id')
            classname = xmlnode.getAttribute('type')
            logcore.debug(_(u"XML node type %s with id '%s'") % (classname, id))

            # Dynamic instanciation of node type
            try:
                classobj = eval(classname)
            except:
                raise Exception(_(u"Unknown node type '%s'") % classname)
            
            node = classobj(flow=flow, id=id)
            
            # Load graphical attributes
            for prop in xmlnode.getElementsByTagName('graphproperty'):
                name  = prop.getAttribute('name')
                value = atoi(prop.getAttribute('value'))
                logcore.debug(_(u"XML node property : %s = %s") % (name, value))
                node.graphicalprops[name] = value
            flow.addNode(node)
        
        # Once all nodes have been loaded, load links :
        for xmlnode in dom.getElementsByTagName('node'):
            id = xmlnode.getAttribute('id')
            node = flow.findNode(id)
            for xmlinterface in xmlnode.getElementsByTagName('interface'):
                name = xmlinterface.getAttribute('name')
                src  = node.findInterface(name)
                src.slot = True
                if src.isInput() and src.isValue():
                    src.slot = xmlinterface.getAttribute('slot').lower() == 'true'
                    if not src.slot:
                        src.value = xmlinterface.getAttribute('value')
                for xmlsuccessor in xmlinterface.getElementsByTagName('successor'):
                    id    = xmlsuccessor.getAttribute('node')
                    dnode = flow.findNode(id)
                    dname = xmlsuccessor.getAttribute('interface')
                    dest  = dnode.findInterface(dname)
                    dest.slot = True
                    src.addSuccessor(dest)
        return flow
    
    def exportXml(self):
        """
        @rtype: string
        """
        # Document root
        grxml = Document()
        grxmlr = grxml.createElement('flow')
        grxml.appendChild(grxmlr)
        # Each node...
        for node in self.nodes:
            xmlnode = grxml.createElement('node')
            xmlnode.setAttribute('id', unicode(node.id))
            xmlnode.setAttribute('type', unicode(node.classname))
            grxmlr.appendChild(xmlnode)
            
            # Graphical properties
            if not empty(node.graphicalprops):
                for graphprop in node.graphicalprops:
                    prop = grxml.createElement('graphproperty')
                    prop.setAttribute('name', graphprop)
                    prop.setAttribute('value', unicode(node.graphicalprops[graphprop]))
                    xmlnode.appendChild(prop)
            
            # Interfaces and successors
            for interface in node.interfaces:
                xmlinterface = grxml.createElement('interface')
                xmlinterface.setAttribute('name', interface.name)
                if interface.isInput() and interface.isValue():
                    xmlinterface.setAttribute('slot', "%s" % interface.slot)
                    if not interface.slot:
                        val = ''
                        if interface.value is not None:
                            val = interface.value
                        xmlinterface.setAttribute('value', "%s" % val)
                if not empty(interface.successors):
                    for successor in interface.successors:
                        xmlsuccessor = grxml.createElement('successor')
                        xmlsuccessor.setAttribute('node', successor.node.id)
                        xmlsuccessor.setAttribute('interface', successor.name)
                        xmlinterface.appendChild(xmlsuccessor)
                xmlnode.appendChild(xmlinterface)
                
        return grxml.toprettyxml()


class NodeRunner(threading.Thread):
    def __init__(self, node):
        threading.Thread.__init__(self)
        self.node = node
    def run(self):
        self.node.start()
    def stop(self):
        pass

class Runner(object):
    def __init__(self, flow):
        self.flow = flow
        self.threads = []
        
    def start(self):
        logcore.info(_("Start execution of flow..."))
        for node in self.flow.nodes:
            th = NodeRunner(node)
            self.threads.append(th)
            th.start()
        logcore.debug(_("All node instantiated, waiting for their input interfaces to be ready."))
        for node in self.flow.inputNodes:
            # Start nodes without predecessors
            if empty(node.predecessors):
                node.canRun.set()
        logcore.debug(_("All input node started. Wait for each node to finish."))
        for th in self.threads:
            th.join()
        logcore.info(_("Done."))
        
    def stop(self):
        for th in self.threads:
            th.stop()

class Interface(object):
    PARAMETER, INPUT, RESULT, OUTPUT = range(4)

    def __init__(self, node, name, **kwargs):
        self.node = node
        self.name = name
        self.successors = []
        self.predecessors = []
        self.type    = kwargs.get('type', self.PARAMETER)
        self.slot    = kwargs.get('slot', True)
        self.default = kwargs.get('default', None)
        self.value   = kwargs.get('value', self.default)
        self.doc     = kwargs.get('doc', '')
        
        self.__readypredecessors = {}

    def isValue(self):
        return False
    
    def isInput(self):
        return self.type == self.INPUT or self.type == self.PARAMETER
    
    def canConnectTo(self, other):
        """if (self.type == self.OUTPUT and other.type = self.INPUT) or
        check here output --> input, parameter -- result ???
        # He can check mimetype etc.
        """
        if self == other or self.node == other.node:
            return False
        
        for iclass in [InterfaceStream, InterfaceValue, InterfaceList]:
            # Same ancestor
            if issubclass(self.__class__, iclass) and issubclass(other.__class__, iclass):
                return True
        return False

    def addSuccessor(self, interface):
        if not self.canConnectTo(interface):
            raise Exception(_("Cannot connect slots"))
        self.successors.append(interface)
        interface.predecessors.append(self)
        logcore.debug(_("%s has following successors : %s") % (self, self.successors))
        
    def removeSuccessor(self, interface):
        self.successors.remove(interface)
        interface.predecessors.remove(self)

    def load(self, other):
        """
        Method to be overridden by subclasses in order to connect content of nodes interfaces
        @type other : {Interface}
        """
        if other not in self.successors and other not in self.predecessors:
            raise Exception(_("Should not load interface that is not connected."))
    
    def onContentReady(self, interface):
        """
        Receives notifications of predecessors readiness, if all were received, this 
        interface is ready. Notify node.
        @type interface: interface whose content is ready.
        """
        self.load(interface)
        self.__readypredecessors[interface] = True
        if len(self.__readypredecessors.keys()) >= len(self.predecessors):
            self.node.debug("All predecessors of %s are ready." % self.fullname)
            self.node.onInterfaceReady(self)
    
    @property
    def fullname(self):
        return u"%s(%s)" % (self.classname, self.name)
        
    @property
    def classname(self):
        return self.__class__.__name__
    
    def __str__(self):
        return repr(self)
    def __repr__(self):
        return str(unicode(self))
    def __unicode__(self):
        return u"%s::%s" % (self.node, self.fullname)



class Node (object):
    category    = _(u"")
    label       = _(u"")
    description = _(u"")
    
    def __init__(self, **kwargs):
        self.flow = kwargs.get('flow', None)
        self.id = kwargs.get('id', '')
        if self.id == '' and self.flow is not None:
            self.id = self.flow.randomId(self)
        self._interfaces = []
        self.graphicalprops = {}
        
        self.__readyinterfaces = {}
        self.canRun  = threading.Event()
        self.running = False
    
    @property
    def classname(self):
        return self.__class__.__name__

    @property
    def interfaces(self):
        """
        Dynamically list class attributes that are Interfaces.
        @rtype : list of L{Interface}
        """
        if len(self._interfaces) == 0:
            for attr in self.__dict__.values():
                if issubclass(attr.__class__, Interface):
                    self._interfaces.append(attr)
        return self._interfaces

    @property
    def inputInterfaces(self):
        return [i for i in self.interfaces if i.isInput()]

    @property
    def inputSlotInterfaces(self):
        return [i for i in self.inputInterfaces if i.slot]
    
    @property
    def outputInterfaces(self):
        return [i for i in self.interfaces if not i.isInput()]
    
    @property
    def successors(self):
        """
        @rtype: list of L{Node}
        """
        successors = []
        for interface in self.interfaces:
            for successor in interface.successors:
                if successor.node not in successors:
                    successors.append(successor.node)
        return successors
    
    @property
    def predecessors(self):
        """
        @rtype: list of L{Node}
        """
        predecessors = []
        for interface in self.interfaces:
            for predecessor in interface.predecessors:
                if predecessor.node not in predecessors:
                    predecessors.append(predecessor.node)
        return predecessors
    
    def findInterface(self, name):
        for i in self.interfaces:
            if i.name == name:
                return i
        raise Exception(_("Interface with name '%s' not found on node %s.") % (name, self))         

    def onInterfaceReady(self, interface):
        self.__readyinterfaces[interface] = True
        if len(self.__readyinterfaces.keys()) >= len(self.inputSlotInterfaces):
            # Node has all its input interfaces ready
            self.debug("All interfaces are ready, can start.")
            self.canRun.set()

    def run(self):
        pass

    def start(self):
        self.debug(_("Waiting..."))
        self.canRun.wait()
        self.debug(_("Start !"))
        self.running = True
        self.run()
        self.running = False
        self.debug(_("Done."))
        self.canRun.clear()
        self.debug(_("Consider all output interfaces ready."))
        for i in self.outputInterfaces:
            for interface in i.successors:
                self.debug(_("Notify %s") % interface)
                interface.onContentReady(i)
        
    def __str__(self):
        return repr(self)

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, self.id)

    def __unicode__(self):
        return repr(self)

    def debug(self, msg):
        logcore.debug(self._logstr(msg))

    def info(self, msg):
        logcore.info(self._logstr(msg))

    def error(self, msg):
        logcore.error(self._logstr(msg))

    def warning(self, msg):
        logcore.warning(self._logstr(msg))

    def _logstr(self, msg):
        return u"%s: %s" % (self, msg)




class InterfaceValue(Interface):
    def __init__(self, node, name, **kwargs):
        Interface.__init__(self, node, name, **kwargs)
        self._value = None
    @property
    def value(self):
        return self._value
    @value.setter
    def value(self, val):
        self._value = val
    def isValue(self):
        return True
    def load(self, other):
        Interface.load(self, other)
        self.value = other.value

class InterfaceStream(Interface):
    def __init__(self, node, name, **kwargs):
        Interface.__init__(self, node, name, **kwargs)
        self.stream = tempfile.NamedTemporaryFile('w+b')
    
    def __iter__(self):
        return iter(self.stream)
    
    def write(self, data):
        self.stream.write(data)

    def flush(self):
        self.stream.flush()
    
    def load(self, other):
        Interface.load(self, other)
        #self.stream = copy.copy(other.stream)
        self.stream = open(other.stream.name, 'rb')
        #self.stream.seek(0)


class InterfaceList(Interface):
    pass





class ProcessNode (Node):
    category = _(u"Basic Nodes")
    label    = _(u"Process")
    description = _(u"Execute a shell command")
    
    def __init__(self, **kwargs):
        Node.__init__(self, **kwargs)
        self.stdin   = InterfaceStream(self, 'stdin',  default='EOF', type=Interface.INPUT,  doc="standard input")
        self.stdout  = InterfaceStream(self, 'stdout', default='EOF', type=Interface.OUTPUT, doc="standard output")
        self.stderr  = InterfaceStream(self, 'stderr', default='EOF', type=Interface.OUTPUT, doc="standard error output")
        self.command = InterfaceValue(self,  'cmd',    default='',    type=Interface.PARAMETER, slot=False, doc="command to run")
        self.result  = InterfaceValue(self,  'result', default=0,     type=Interface.RESULT, doc="execution code return")

    def run(self):
        # Run cmd with input from stdin, and send output to stdout/stderr, result code
        cmd = self.command.value
        import subprocess
        self.info("Run command '%s'" % cmd)
        proc = subprocess.Popen(cmd, stdin=self.stdin.stream, stdout=self.stdout.stream, stderr=self.stderr.stream)
        proc.wait()
        self.result.value = proc.returncode


class InputNode (Node):
    category = _(u"Input Nodes")
    label    = _(u"")


class FileInputNode (InputNode):
    label       = _(u"File")
    description = _(u"Read the content of a file")

    def __init__(self, **kwargs):
        InputNode.__init__(self, **kwargs)
        self.filepath = InterfaceValue(self,  'filepath', default='',    type=Interface.PARAMETER, slot=False, doc="file to read")
        self.output   = InterfaceStream(self, 'output',   default='EOF', type=Interface.OUTPUT,    doc="file content")

    def run(self):
        # Read file content and pass to output interface
        if empty(self.filepath.value):
            raise FlowException(_("Filepath empty, cannot read file."))
        self.info(_("Read content of file '%s'") % self.filepath.value)
        f = open(self.filepath.value, 'rb')
        for line in f:
            self.output.write(line)
        self.output.flush()
        f.close()


class ValueInputNode (InputNode):
    label    = _(u"Value")
    description = _(u"A string or number")

    def __init__(self, **kwargs):
        InputNode.__init__(self, **kwargs)
        self.input  = InterfaceValue(self, 'value', default='', type=Interface.PARAMETER, slot=False, doc="Manual value")
        self.output = InterfaceValue(self, 'out', default='',   type=Interface.OUTPUT, doc="value")

    def run(self):
        self.output.value = self.input.value


class CommandLineParameterInputNode (InputNode):
    label    = _(u"CLI Param")
    description = _(u"Read a Command-Line Interface parameter")

    def __init__(self, **kwargs):
        InputNode.__init__(self, **kwargs)
        self.name    = InterfaceValue(self, 'name',    default='', type=Interface.PARAMETER, slot=False, doc=_("Command line interface parameter name"))
        self.value   = InterfaceValue(self, 'value',   default='', type=Interface.OUTPUT,    doc=_("value retrieved"))
        self.default = InterfaceValue(self, 'default', default='', type=Interface.PARAMETER, slot=False, doc=_("default value if not specified at runtime"))
        """@type options: L{optparse.Values}"""
        self.options = None

    def run(self):
        # Options were parsed in main
        value = getattr(self.options, self.paramname)
        if empty(value):
            logcore.debug("Expected parameter '%s' is missing from command-line, use default." % self.paramname)
            value = self.default.value
        self.info(_("CLI Parameter '%s'='%s'") % (self.paramname, value))
        self.value.value = value

    @property
    def paramname(self):
        name = self.name.value
        if empty(name):
            raise Exception(_("Error in getting name of CLI Parameter"))
        return name


class CommandLineStdinInputNode (InputNode):
    label    = _(u"CLI Stdin")
    description = _(u"Read the Command-Line Interface standard input")

    def __init__(self, **kwargs):
        InputNode.__init__(self, **kwargs)
        self.output   = InterfaceStream(self, 'output', default='EOF', type=Interface.OUTPUT, doc="standard input content")

    def run(self):
        for line in sys.stdin:
            self.output.write(line)
        self.output.flush()

class FileListInputNode (InputNode):
    label    = _(u"File list")
    description = _(u"List files of a folder")

#
# Output nodes
#

class OutputNode (Node):
    category = _(u"Output Nodes")
    label    = _(u"")


class FileOutputNode (OutputNode):
    label    = _(u"File")
    description = _(u"Write the content to a file")

    def __init__(self, **kwargs):
        OutputNode.__init__(self, **kwargs)
        self.filepath = InterfaceValue(self, 'filepath', default='',  type=Interface.PARAMETER, slot=False, doc="file to write")
        self.input    = InterfaceStream(self, 'input', default='EOF', type=Interface.INPUT, doc="input to write")

    def run(self):
        self.info(_("Write content to file '%s'") % self.filepath.value)
        f = open(self.filepath.value, 'wb')
        for line in self.input:
            f.write(line)
        f.close()

class CommandLineStdoutOutputNode (OutputNode):
    label       = _(u"CLI Stdout")
    description = _(u"Write to the Command-Line Interface standard output")

    def __init__(self, **kwargs):
        OutputNode.__init__(self, **kwargs)
        self.outstream = sys.stdout
        self.input     = InterfaceStream(self, 'input', default='EOF', type=Interface.INPUT, doc="standard output")

    def run(self):
        for line in self.input:
            self.outstream.write(line)
        self.outstream.flush()
