# ###################### BEGIN LICENSE BLOCK ###########################
#
# Copyright © 2021 Christian Stolze
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# ####################### END LICENSE BLOCK ############################

# EXTERNAL PACKAGE DEPENDENCIES
###################################################
from enum import Enum

# INTERNAL PACKAGE DEPENDENCIES
###################################################
# NONE

# PREPARE LOGGING
###################################################
import logging

# get the library logger
logger = logging.getLogger('pyLightIO')


# DEVICE MANAGER FOR LIGHTFIELD DISPLAYS
###############################################
class DeviceManager(object):
    '''
    The :class:`DeviceManager` class is the factory class for generating
    instances of the different device types implemented based on the
    :class:`pylightio.BaseDeviceType` class of pyLightIO. Each device manager is
    based on a service. This service handles all device communications, while
    the device manager provides all functions for organizing the devices
    internally.
    '''

    # DEFINE CLASS PROPERTIES AS PRIVATE MEMBERS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    __dev_count = 0             # number of device instances
    __dev_list = []             # list for initialized device instances
    __dev_active = None         # currently active device instance
    __dev_service = None         # the service used by the device manager


    # CLASS METHODS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    @classmethod
    def get_service(cls):
        '''
        Returns the service which is used by this device manager.
        '''
        return cls.__dev_service

    @classmethod
    def set_service(cls, service):
        '''
        Set the service to used by this device manager.

        :param service: The instance of a service class, which is based on the
            :class:`pylightio.BaseServiceType` class.
        :type service: class:`pylightio.BaseServiceType`

        :return: The new service of the device manager.
        :rtype: :class:`pylightio.BaseServiceType`
        '''
        cls.__dev_service = service
        return cls.__dev_service

    @classmethod
    def refresh(cls, emulate_remaining = True):
        '''
        Refresh the device list of the device manager. This calls the service's
        `get_devices()` method.

        :param emulate_remaining: If `True`, the device manager adds one emulated
            device of each type to the device list.
        :type emulate_remaining: bool, optional (default: `True`)
        :return: No return value.
        :rtype: None
        '''

        # if the service ready
        if cls.__dev_service and cls.__dev_service.is_ready():

            instances = []

            # set all (not emulated) devices to "disconnected"
            # NOTE: We don't delete the devices, because that would be more
            #       complex to handle when the user already used the specific
            #       device type instance for their settings
            for d in cls.__dev_list:
                if d.emulated == False:
                    d.connected = False

            # request devices
            devices = cls.__dev_service.get_devices()
            if devices:

                # for each device returned create a LookingGlassDevice instance
                # of the corresponding type
                for idx, device in enumerate(devices):

                    # try to find the instance of this device
                    instance = list(filter(lambda d: d.serial == device['calibration']['serial'], cls.__dev_list))

                    # if no instance of this device exists
                    if not instance:

                        # create a device instance of the corresponding type
                        instance = cls.add_device(device['hardwareVersion'], device)

                    else:

                        # update the configuration
                        instance[0].configuration = device

                        # make sure the state of the device instance is "connected"
                        instance[0].connected = True

            return None

        logger.error("No Looking Glass Bridge connection. The device list could not be obtained. ")

    @classmethod
    def add_device(cls, device_type, device_configuration = None):
        '''
        Add a new device of type `device_type` to the device manager.

        :param emulate_remaining: If `True`, the device manager adds one emulated
            device of each type to the device list.
        :type emulate_remaining: bool, optional (default: `True`)
        :return: The added device.
        :rtype: :class:`pylightio.BaseDeviceType` or subclass of it
        '''
        # try to find the class for the specified type, if it exists
        DeviceTypeClass = [subclass for subclass in BaseDeviceType.__subclasses__() if subclass.type == device_type]

        # call the corresponding type
        if DeviceTypeClass:

            # create the device instance
            device = DeviceTypeClass[0](cls.__dev_service, device_configuration)

            # increment device count
            # NOTE: this number is never decreased to prevent ambiguities of the id
            cls.__dev_count += 1

            # append registered device to the device list
            cls.__dev_list.append(device)

            return device

        # otherwise raise an exception
        raise ValueError("There is no Looking Glass of type '%s'." % device_type)


    @classmethod
    def remove_device(cls, device):
        '''
        Remove a previously added device from the device manager.

        :param device: The :class:`pylightio.BaseDeviceType` to be removed.
        :type device: :class:`pylightio.BaseDeviceType` or a subclass of it
        :return: `True` if the device was successfully removed.
        :rtype: bool
        '''

        # if the device is in the list
        if device in cls.__dev_list:

            # create the device instance
            logger.info("Removing device '%s' ..." % (device))

            # if this device is the active device, set_active
            if cls.get_active() == device.id: cls.reset_active()

            cls.__dev_list.remove(device)

            return True

        # otherwise raise an exception
        raise ValueError("The device '%s' is not in the list." % device)

        return False

    @classmethod
    def add_emulated(cls, filter=None):
        '''
        Add one emulated device for each supported device type to the device
        manager. A `filter` can be applied to add only specific device types.

        :param filter: List of :class:`pylightio.BaseDeviceType` to be added.
        :type filter: :class:`pylightio.BaseDeviceType` or a subclass of it
        '''

        # for each device type which is not in "except" list
        for DeviceType in set(BaseDeviceType.__subclasses__()) - set([DeviceType for DeviceType in cls.__subclasses__() if DeviceType.type in filter ]):

            # if not already emulated
            if not (DeviceType.type in [d.type for d in cls.__dev_list if d.emulated == True]):

                # create an instance without passing a configuration
                # (that will created an emulated device)
                instance = cls.add_device(DeviceType.type)

        return True

    @classmethod
    def to_list(cls, show_connected = True, show_emulated = False, filter_by_type = None):
        ''' enumerate the devices of this device manager as list '''
        return [d for d in cls.__dev_list if ((show_connected == None or d.connected == show_connected) and (show_emulated == None or d.emulated == show_emulated)) and (filter_by_type == None or type(d) == filter_by_type)]

    @classmethod
    def count(cls, show_connected = True, show_emulated = False, filter_by_type = None):
        ''' get number of devices '''
        return len(cls.to_list(show_connected, show_emulated, filter_by_type))

    @classmethod
    def get_active(cls):
        '''
        Return the active device,i.e., the one currently used by the user.
        '''
        return cls.__dev_active

    @classmethod
    def set_active(cls, id=None, key=None, value=None):
        ''' set the active device (i.e., the one currently used by the user) '''

        # if a custom key and value are given
        if key is not None and value is not None:

            for device in cls.__dev_list:
                if hasattr(device, key) and (getattr(device, key) == value):
                    cls.__dev_active = device
                    return device

        # otherwise we use the id
        elif (id is not None):

            for device in cls.__dev_list:
                if (device.id == id):
                    cls.__dev_active = device
                    return device

            # else raise exception
            raise ValueError("The given device with id '%i' is not in the list." % id)

        # else raise exception
        raise ValueError("No valid keyword and value were given to identify the device.")

    @classmethod
    def get_device(cls, id=None, key=None, value=None):
        ''' get device instance based on the given key/value pair or id '''

        # if a custom key and value are given
        if key is not None and value is not None:

            for device in cls.__dev_list:
                if hasattr(device, key) and (getattr(device, key) == value):
                    return device

        # otherwise we use the id
        elif (id is not None):

            for device in cls.__dev_list:
                if (device.id == id):
                    return device

            # else raise exception
            raise ValueError("The given device with id '%i' is not in the list." % id)

        # else raise exception
        raise ValueError("No valid keyword and value were given to identify the device.")

    @classmethod
    def reset_active(cls):
        ''' set the active device to None '''
        cls.__dev_active = None

    @classmethod
    def exists(cls, serial=None, type=None):
        ''' check if the device instance already exists '''
        if serial and serial in [d.serial for d in cls.__dev_list]:
            return True

        return False


# BASE CLASS FOR DEVICE TYPES
###############################################
# base class for the implementation of different lightfield display types.
# all device types implemented must be a subclass of this base class
class BaseDeviceType(object):


    # PRIVATE MEMBERS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    __id = None             # ID of the device instance
    __type = None           # the unique identifier string of each device type
    __service = None        # the service the device was registered with
    __emulated = False      # is the device instance emulated?
    __connected = True      # is the device still connected?
    __presets = []          # list for the quilt presets

    __lightfield = None     # the lightfield currently displayed on this device


    # INSTANCE METHODS - IMPLEMENTED BY BASE CLASS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # NOTE: Here is the place to implement functions that should not be overriden
    #       by the subclasses, which represent the specific device types

    def __init__(self, service, configuration=None):
        ''' initialize the device instance '''

        # assign an id
        self.id = DeviceManager.count(None, None)

        # if a configuration was passed
        if configuration:

            # use it
            self.configuration = configuration

            # bind the specified service to the device instance
            self.service = service

            # set the state variables for connected devices
            self.connected = True
            self.emulated = False

            # create the device instance
            logger.info("Created class instance for the connected device '%s' of type '%s'." % (self, self.type))

        else:

            # otherwise apply the device type's dummy configuration
            # and assume the device is emulated
            self.configuration = self.emulated_configuration

            # use it
            self.service = None

            # set the state variables for connected devices
            self.connected = False
            self.emulated = True

            # create the device instance
            logger.info("Emulating device '%s' of type '%s'." % (self, self.type))

    def __str__(self):
        ''' the display name of the device when the instance is called '''

        if self.emulated == False: return self.name + " (id: " + str(self.id) + ")"
        if self.emulated == True: return "[Emulated] " + self.name + " (id: " + str(self.id) + ")"


    # TEMPLATE METHODS - IMPLEMENTED BY SUBCLASS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # NOTE: These methods must be implemented by the subclasses, which represent
    #       the specific device types.
    def display(self, lightfield, custom_decoder = None, **kwargs):
        ''' do some checks if required and hand it over for displaying '''
        # NOTE: This method should only pre-process the image, if the device
        #       type requires that. Then call service methods to display it.

        pass



    # CLASS PROPERTIES - GENRAL
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    @property
    def id(self):
        return self.__id

    @id.setter
    def id(self, value):
        self.__id = value

    @property
    def sevice(self):
        return self.__sevice

    @sevice.setter
    def sevice(self, value):
        self.__sevice = value

    @property
    def emulated(self):
        return self.__emulated

    @emulated.setter
    def emulated(self, value):
        self.__emulated = value

    @property
    def connected(self):
        return self.__connected

    @connected.setter
    def connected(self, value):
        self.__connected = value

    @property
    def presets(self):
        return self.__presets

    @presets.setter
    def presets(self, value):
        self.__presets = value

    # CLASS PROPERTIES
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    @property
    def name(self):
        return self.__name

    @name.setter
    def name(self, value):
        self.__name = value

    @property
    def configuration(self):
        return self.__configuration

    @configuration.setter
    def configuration(self, value):
        self.__configuration = value

    @property
    def lightfield(self):
        return self.__lightfield

    @lightfield.setter
    def lightfield(self, value):
        self.__lightfield = value
