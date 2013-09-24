import os
import time
import xml.etree.ElementTree as ET

class UsbmtcInterface(object):
  BUFFSIZE = 3000
  DEFAULT_DELAY = 0.1
  ASK_DELAY = 0
  
  def __init__(self, devicePath, debug=False):
    # Get a handle to the IO device
    self.FILE = os.open(devicePath, os.O_RDWR)
    self.debug = debug
  
  def write(self, message, delay = None):
    if self.debug:
      print(message)
      
    delay = float(delay) if (delay is not None) else self.DEFAULT_DELAY
    
    os.write(self.FILE, bytes(message, 'UTF-8'))
    
    if delay:
      time.sleep(delay)
    
  def read(self, numbytes=BUFFSIZE):
    reply = str(os.read(self.FILE, numbytes), 'UTF-8')
    if self.debug:
      print(reply)
    return reply
  
  def ask(self, message, numbytes=BUFFSIZE, delay=None):
    delay = float(delay) if (delay is not None) else self.ASK_DELAY
    self.write(message, delay=delay)
    return self.read(numbytes)
  
  def close(self):
    os.close(self.FILE)
    
    
class Device(object):
  class _Dummy(object):
    """Dummy class to enable faked hierarchic access."""
    def __init__(self, device, path):
      self.__dict__['device'] = device
      self.__dict__['path'] = path

    def __getattr__(self, attr):
      path = self.__dict__['path'] + [attr]
      device = self.__dict__['device']
      
      if not device.isEndpoint(path):
        return Device._Dummy(device, path)
      else:
        return device.getPath(path)
      
    def __setattr__(self, attr, value):
      path = self.__dict__['path'] + [attr]
      device = self.__dict__['device']
      return device.setPath(path, value)
  
  class _ConfigRepresentation(object):
    class Category(object):
      def __init__(self, desc=None):
        self.desc = desc
        self.members = dict()
      
      def __repr__(self):
        return '<Category %s>' % self.members
  
    class Attribute(object):
      def __init__(self, command, readOnly = False, type=str, desc=None, option=None, choices=None, mark='?',
                   delay = None):
        self.command = command
        self.readOnly = readOnly
        self.type = type
        self.choices = choices
        self.option = option
        self.desc = desc
        self.mark = mark
        self.delay = delay
        
      def __repr__(self):
        return '<Attribute %s (%s)>' % (self.command, self.type.__name__)
      
      def getSetCommand(self, value):
        # If choices are given, it must be one of those
        if self.choices:
          valid = False
          for choice in self.choices:
            if str(value) == choice['val']:
              value = choice.get('wirenameSet', choice.get('wirename', choice['val'].upper()))
              valid = True
              break
          if not valid:
            raise ValueError("Value is not a valid option")
          
        return self.command + ' ' + str(value)
  
      def getRequestCommand(self):
        cmd = self.command + self.mark
        if self.option:
          cmd += ' ' + self.option
        return cmd

      def parseAnwser(self, anwser):
        # If choices are given, it must be one of those
        if self.choices:
          valid = False
          for choice in self.choices:
            choiceVal = choice.get('wirename', choice['val'].upper())
            if anwser == choiceVal:
              anwser = choice['val']
              valid = True
              break
          if not valid:
            raise ValueError("Value returned by the device is not a valid option")
        try:
          val = self.type(anwser)
        except ValueError:
          val = anwser
        return val

    class Action(object):
      def __init__(self, command, desc=None, option=None, delay = None):
        self.command = command
        self.option = option
        self.desc = desc
        self.delay = delay
        
      def __repr__(self):
        return '<Action %s>' % (self.command)
      
  def __init__(self, interface, descriptorFile):
    self._interface = interface
    self._commands = Device._parseXMLET(ET.parse(descriptorFile))
    
  @staticmethod
  def _parseXMLET(tree):
    config = dict()
    
    def parseCategory(d, elements):
      for element in elements:
        assert element.tag in ['category', 'attribute', 'action']
        
        name = element.attrib['name']
        desc = element.findall("description")[0].text if element.findall("description") else None
        
        if element.tag == 'category':
          newCat = Device._ConfigRepresentation.Category(desc=desc)
          d.members[name] = parseCategory(newCat, element)
          continue
        
        delay = element.attrib.get('delay', None)
        delay = float(delay) if delay else None
        
        if element.tag == 'attribute':
          # Find choices
          choices = list()
          for choiceElement in element.findall("choice"):
            assert 'val' in choiceElement.attrib
            choices.append(choiceElement.attrib)
          choices = choices if len(choices) > 0 else None
          
          # Get all attribute parameters
          command = element.attrib['command']
          attrType = {'str' : str, 'int' : int, 'float' : float}[element.attrib.get('type', 'str')]
          readOnly = {'True' : True, 'False' : False}[element.attrib.get('readonly', 'False')]
          option = element.attrib.get('option', None)
          
          newAtr = Device._ConfigRepresentation.Attribute(command, readOnly = readOnly, choices = choices, 
                                                          type = attrType, option=option, desc = desc, 
                                                          delay = delay)
          d.members[name] = newAtr
          
        if element.tag == 'action':
          # Get all action parameters
          command = element.attrib['command']
          option = element.attrib.get('option', None)
          
          newAct = Device._ConfigRepresentation.Action(command, option=option, desc = desc, delay = delay)
          d.members[name] = newAct
          
      return d
    
    return parseCategory(Device._ConfigRepresentation.Category(''), tree.getroot())
  
  @property
  def bus(self):
    return Device._Dummy(self, [])
  
  def isEndpoint(self, path):
    if type(path) == str:
      path = path.split('.')
    return type(self._getPath(path)) != Device._ConfigRepresentation.Category
  
  def _getPath(self, path):
    """Get internal configuration representation by path"""
    if type(path) == str:
      path = path.split('.')
      
    p = list(reversed(path))
    element = self._commands
    while len(p) > 0:
      element = element.members[p.pop()]
    return element

  
  def getPath(self, path):
    if type(path) == str:
      path = path.split('.')
    
    e = self._getPath(path)
    if type(e) == Device._ConfigRepresentation.Action:
      function = lambda : self._interface.write(e.command, delay = e.delay)
      function.__doc__ = e.desc if e.desc else ''
      return function
    
    if type(e) == Device._ConfigRepresentation.Attribute:
      anwser = self._interface.ask(e.getRequestCommand(), delay = e.delay)
      return e.parseAnwser(anwser)
    
    if type(e) == Device._ConfigRepresentation.Category:
      raise KeyError("You have accessed a category, please decent further")
  
    assert True, "Unhandled type returned by _getPath"
    
  def setPath(self, path, value):
    if type(path) == str:
      path = path.split('.')
    
    e = self._getPath(path)
    
    assert type(e) == Device._ConfigRepresentation.Attribute, "Not an attribute"
    assert not e.readOnly, "Attribute must be writable"
    
    self._interface.write(e.getSetCommand(value), delay = e.delay)

  def getSettings(self, path=None, onlyWritable = True):
    settings = dict()
    
    if path is None:
      path = list()
      
    for name, e in self._getPath(path).members.items():
      if type(e) == Device._ConfigRepresentation.Attribute and (not e.readOnly or not onlyWritable):
        settings[name] = self.getPath(path + [name])
    
      if type(e) == Device._ConfigRepresentation.Category:
        settings[name]  = self.getSettings(path + [name], onlyWritable)
    return settings
  
  def setSettings(self, settings, path=None, tries = 5, floatPrecision = 0.001, delay=0.5, cycles=2):
    for cycle in range(cycles):
      if path is None:
        path = list()
        
      for name, e in settings.items():
        newPath = path + [name]
        if type(e) == dict:
          self.setSettings(e, newPath)
          continue
        
        entry = self._getPath(newPath)
        if entry.readOnly:
          continue
        
        # Apply setting and make sure that it is correct
        settingsCorrect = False
        newSetting = entry.type(e)
        for i in range(tries):
          currentSetting = self.getPath(newPath)
          
          if entry.type == float:
            settingsCorrect = (abs(newSetting - currentSetting) <= abs(min(newSetting, currentSetting)*floatPrecision))
          else:
            settingsCorrect = (entry.type(e) == currentSetting)
            
          if settingsCorrect:
            break
          
          self.setPath(newPath, e)
          
          if i > 1:
            time.sleep(delay)
          
        if not settingsCorrect:
          raise ValueError("Could not apply setting %s" % '.'.join(newPath))