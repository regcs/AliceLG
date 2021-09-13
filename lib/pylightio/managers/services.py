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



# SERVICE MANAGER FOR LIGHTFIELD DISPLAYS
###############################################
# the service manager is the factory class for generating service instances of
# the different service types
class ServiceManager(object):

    # PRIVATE MEMBERS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    __active = None                                    # active service
    __service_count = []                               # number of created services
    __service_list = []                                # list of created services


    # CLASS METHODS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    @classmethod
    def add(cls, service_type):
        ''' open the service of the specified type '''

        # try to find the class for the specified type, if it exists
        ServiceTypeClass = [subclass for subclass in BaseServiceType.__subclasses__() if (subclass == service_type or subclass.type == service_type)]

        # if a service of the specified type was found
        if ServiceTypeClass:

            # create the service instance
            service = ServiceTypeClass[0]()

            # append registered device to the device list
            cls.__service_list.append(service)

            # make this service the active service if no service is active or this is the first ready service
            if (not cls.get_active() or (cls.get_active() and not cls.get_active().is_ready())):
                cls.set_active(service)

            logger.info("Added service '%s' to the service manager." % service)

            return service

        # otherwise raise an exception
        raise ValueError("There is no service of type '%s'." % service_type)

    @classmethod
    def to_list(cls):
        ''' enumerate the services of this service manager as list '''
        return cls.__service_list

    @classmethod
    def count(cls):
        ''' return number of services '''
        return len(cls.to_list())

    @classmethod
    def get_active(cls):
        ''' return the active service (i.e., the one currently used by the app / user) '''
        return cls.__active

    @classmethod
    def set_active(cls, service):
        ''' set the active service (i.e., the one currently used by the app / user) '''
        if service in cls.__service_list:
            cls.__active = service
            return service

        # else raise exception
        raise ValueError("The given device with id '%i' is not in the list." % id)

    @classmethod
    def reset_active(cls):
        ''' set the active service to None '''
        cls.__service_active = None

    @classmethod
    def remove(cls, service):
        ''' remove the service from the ServiceManager '''
        # NOTE:

        # if the device is in the list
        if service in cls.__service_list:

            # create the device instance
            logger.info("Removing service '%s' ..." % (service))

            # if this device is the active device, set_active
            if cls.get_active() == service: cls.reset_active()

            cls.__service_list.remove(service)

            # then delete the service instance
            del service

            return True

# BASE CLASS OF SERVICE TYPES
###############################################
# the service type class used for handling lightfield display communication
# all service type implementations must be a subclass of this base class
class BaseServiceType(object):

    # DEFINE CLASS PROPERTIES AS PROTECTED MEMBERS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    type = None                                         # the unique identifier string of a service type (required for the factory class)

    # DEFINE CLASS PROPERTIES AS PRIVATE MEMBERS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    __version = ""                                      # version string of the service

    # INSTANCE METHODS - IMPLEMENTED BY BASE CLASS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # NOTE: Here is the place to implement functions that should not be overriden
    #       by the subclasses, which represent the specific service types

    def __str__(self):
        ''' the display name of the service when the instance is called '''

        return "%s v%s" % (self.name, self.get_version())

    # TEMPLATE METHODS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # NOTE: These methods must be implemented by the subclasses, which represent
    #       the specific service type
    def __init__(self):
        ''' handle initialization of the class instance and the specific service '''
        pass

    def is_ready(self):
        ''' handles check if the service is ready '''
        pass

    def get_version(self):
        ''' method to obtain the service version '''
        pass

    def get_devices(self):
        ''' method to request the connected devices '''
        ''' this function should return a list of device configurations '''
        pass

    def display(self, device, lightfield, aspect=None, custom_decoder = None):
        ''' display a given lightfield image object on a device '''
        pass

    def clear(self, device):
        ''' clear the display of a given device '''
        pass

    def __del__(self):
        ''' handles closing / deinitializing the service '''
        pass

    # CLASS PROPERTIES
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    @property
    def service(self):
        return self.__service

    @service.setter
    def service(self, value):
        self.__service = value

    @property
    def version(self):
        return self.__version

    @version.setter
    def version(self, value):
        self.__version = value
