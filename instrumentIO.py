import os
import time
import sys
import xml.etree.ElementTree as ElementTree


class UsbmtcInterface(object):
    BUFFSIZE = 3000
    DEFAULT_DELAY = 0.1
    ASK_DELAY = 0

    def __init__(self, device_path, debug=False):
        # Get a handle to the IO device
        self.file = os.open(device_path, os.O_RDWR)
        self.debug = debug

    def write(self, message, delay=None):
        if self.debug:
            print(message)

        delay = float(delay) if (delay is not None) else self.DEFAULT_DELAY

        if sys.version_info[0] == 2:
            os.write(self.file, message)
        else:
            #noinspection PyArgumentList
            os.write(self.file, bytes(message, 'UTF-8'))

        if delay:
            time.sleep(delay)

    def read(self, numbytes=BUFFSIZE):
        if sys.version_info[0] == 2:
            reply = os.read(self.file, numbytes)
        else:
            #noinspection PyArgumentList
            reply = str(os.read(self.file, numbytes), 'UTF-8')

        if self.debug:
            print(reply)
        return reply

    def ask(self, message, numbytes=BUFFSIZE, delay=None):
        delay = float(delay) if (delay is not None) else self.ASK_DELAY
        self.write(message, delay=delay)
        return self.read(numbytes)

    def close(self):
        os.close(self.file)


#noinspection PyProtectedMember
class Device(object):
    class _Dummy(object):
        """Dummy class to enable faked hierarchic access."""

        def __init__(self, device, path):
            self.__dict__['device'] = device
            self.__dict__['path'] = path

        def __getattr__(self, attr):
            path = self.__dict__['path'] + [attr]
            device = self.__dict__['device']

            if not device.is_endpoint(path):
                return Device._Dummy(device, path)
            else:
                return device.get_path(path)

        def __setattr__(self, attr, value):
            path = self.__dict__['path'] + [attr]
            device = self.__dict__['device']
            return device.set_path(path, value)

    class _ConfigRepresentation(object):
        class Category(object):
            def __init__(self, desc=None):
                self.desc = desc
                self.members = dict()

            def __repr__(self):
                return '<Category %s>' % self.members

        class Attribute(object):
            def __init__(self, command, read_only=False, value_type=str, desc=None, option=None, choices=None, mark='?',
                         delay=None):
                self.command = command
                self.read_only = read_only
                self.type = value_type
                self.choices = choices
                self.option = option
                self.desc = desc
                self.mark = mark
                self.delay = delay

            def __repr__(self):
                return '<Attribute %s (%s)>' % (self.command, self.type.__name__)

            def get_set_command(self, value):
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

            def get_request_command(self):
                cmd = self.command + self.mark
                if self.option:
                    cmd += ' ' + self.option
                return cmd

            def parse_answer(self, answer):
                # If choices are given, it must be one of those
                if self.choices:
                    valid = False
                    for choice in self.choices:
                        choice_val = choice.get('wirename', choice['val'].upper())
                        if answer == choice_val:
                            answer = choice['val']
                            valid = True
                            break
                    if not valid:
                        raise ValueError("Value returned by the device is not a valid option")
                try:
                    val = self.type(answer)
                except ValueError:
                    val = answer
                return val

        class Action(object):
            def __init__(self, command, desc=None, option=None, delay=None):
                self.command = command
                self.option = option
                self.desc = desc
                self.delay = delay

            def __repr__(self):
                return '<Action %s>' % self.command

    def __init__(self, interface, descriptor_file):
        self._interface = interface

        description = Device._parse_xml_elementtree(ElementTree.parse(descriptor_file))
        self._commands = description['commands']

    @staticmethod
    def _parse_xml_elementtree(tree):
        def parse_category(d, elements):
            for element in elements:
                assert element.tag in ['category', 'attribute', 'action']

                name = element.attrib['name']
                desc = element.findall("description")[0].text if element.findall("description") else None

                if element.tag == 'category':
                    new_category = Device._ConfigRepresentation.Category(desc=desc)
                    d.members[name] = parse_category(new_category, element)
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
                    attr_type = {'str': str, 'int': int, 'float': float}[element.attrib.get('type', 'str')]
                    read_only = {'true': True, 'false': False}[element.attrib.get('readonly', 'false')]
                    option = element.attrib.get('option', None)

                    new_atr = Device._ConfigRepresentation.Attribute(command, read_only=read_only, choices=choices,
                                                                    value_type=attr_type, option=option, desc=desc,
                                                                    delay=delay)
                    d.members[name] = new_atr

                if element.tag == 'action':
                    # Get all action parameters
                    command = element.attrib['command']
                    option = element.attrib.get('option', None)

                    new_action = Device._ConfigRepresentation.Action(command, option=option, desc=desc, delay=delay)
                    d.members[name] = new_action

            return d
        root = tree.getroot()

        # Parse command definitions
        commands_element = root.findall("commands")[0]
        commands = parse_category(Device._ConfigRepresentation.Category(''), commands_element)

        description = {'commands': commands}
        return description

    @property
    def bus(self):
        return Device._Dummy(self, [])

    def is_endpoint(self, path):
        if type(path) == str:
            path = path.split('.')
        return type(self._get_path(path)) != Device._ConfigRepresentation.Category

    def _get_path(self, path):
        """Get internal configuration representation by path"""
        if type(path) == str:
            path = path.split('.')

        p = list(reversed(path))
        element = self._commands
        while len(p) > 0:
            element = element.members[p.pop()]
        return element


    def get_path(self, path):
        if type(path) == str:
            path = path.split('.')

        e = self._get_path(path)
        if type(e) == Device._ConfigRepresentation.Action:
            function = lambda: self._interface.write(e.command, delay=e.delay)
            function.__doc__ = e.desc if e.desc else ''
            return function

        if type(e) == Device._ConfigRepresentation.Attribute:
            answer = self._interface.ask(e.get_request_command(), delay=e.delay)
            return e.parse_answer(answer)

        if type(e) == Device._ConfigRepresentation.Category:
            raise KeyError("You have accessed a category, please decent further")

        assert True, "Unhandled type returned by _get_path"

    def set_path(self, path, value):
        if type(path) == str:
            path = path.split('.')

        e = self._get_path(path)

        assert type(e) == Device._ConfigRepresentation.Attribute, "Not an attribute"
        assert not e.read_only, "Attribute must be writable"

        self._interface.write(e.get_set_command(value), delay=e.delay)

    def get_settings(self, path=None, only_writable=True):
        settings = dict()

        if path is None:
            path = list()

        for name, e in self._get_path(path).members.items():
            if type(e) == Device._ConfigRepresentation.Attribute and (not e.read_only or not only_writable):
                settings[name] = self.get_path(path + [name])

            if type(e) == Device._ConfigRepresentation.Category:
                settings[name] = self.get_settings(path + [name], only_writable)
        return settings

    def set_settings(self, settings, path=None, tries=5, float_precision=0.001, delay=0.5, cycles=2):
        for cycle in range(cycles):
            if path is None:
                path = list()

            for name, e in settings.items():
                new_path = path + [name]
                if type(e) == dict:
                    self.set_settings(e, new_path)
                    continue

                entry = self._get_path(new_path)
                if entry.read_only:
                    continue

                # Apply setting and make sure that it is correct
                settings_correct = False
                new_setting = entry.type(e)
                for i in range(tries):
                    current_setting = self.get_path(new_path)

                    if entry.type == float:
                        settings_correct = (
                        abs(new_setting - current_setting) <= abs(min(new_setting, current_setting) * float_precision))
                    else:
                        settings_correct = (entry.type(e) == current_setting)

                    if settings_correct:
                        break

                    self.set_path(new_path, e)

                    if i > 1:
                        time.sleep(delay)

                if not settings_correct:
                    raise ValueError("Could not apply setting %s" % '.'.join(new_path))
