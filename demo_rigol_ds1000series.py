#!/usr/bin/python
import instrumentIO
import pprint

# Create interface and load description of protocol
interface = instrumentIO.UsbmtcInterface('/dev/usbtmc0', debug=False)
device  = instrumentIO.Device(interface, 'devices/rigol/rigol_ds1000series.xml')

# All defined attributes and commands can be accessed directly
# over the 'bus' attribute.
# Access to these properties always involes a command being sent
# to the device - so take care.

# Let's first read some property like the device ID
# Since it is a read-only property we cannot write to it.
print('Device ID:', device.bus.identity)

# Use autosetup to display the waveform nicely
device.bus.scope.autosetup()

# So let's enable averaging over two samples
device.bus.acquire.averageSampes = 2
device.bus.acquire.type = 'average'

# We can also download the whole configuration
# By default, this only includes writable attributes.
oldSettings = device.getSettings()

print("Configurable options:")
pprint.pprint(oldSettings)


# And reapply it again later on
device.bus.reset()
device.setSettings(oldSettings)


# Unlock the scope so that the user can use it again
device.bus.scope.unlock()
