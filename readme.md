pyInstruments - A simple way to communicate with your lab instruments
======================================================================

Introduction
------------

This software was born after I bought a RIGOL DS1052E oscilloscope.
When I dug into remote-controlling my new toy, there was no proper and
simple way to do it. I was looking for a nice solution where I could
simply manipulate the device without reading the documentation every time.

The communication commands are described via a simple XML file and might
also be of use for other projects.

Usage
------

The interface should be simple but versatile. See for yourself:

```python
import instrumentIO

# Create interface and load description of protocol
interface = instrumentIO.UsbmtcInterface('/dev/usbtmc0', debug=False)
device  = instrumentIO.Device(interface, 'devices/rigol_ds1000series.xml')

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
```

We can even read out all configurable options and reapply them afterwards:

```python
# We can also download the whole configuration
# By default, this only includes writable attributes.
oldSettings = device.getSettings()

# Reset to default settings
device.bus.reset()

# And reapply the saved settings
device.setSettings(oldSettings)
```

After this code the oscilloscope is in the exact same configuration 
as before the internal reset.

Status
------

Rigol DS1000 series
-------------------
 
 - Most commands are implemented. Missing features are:
   - All triggers except edge trigger
   - Logic analyzer
   - Key press actions
 - No option to read waveform date back
