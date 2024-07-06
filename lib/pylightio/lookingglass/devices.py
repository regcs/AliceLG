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
# NONE

# INTERNAL PACKAGE DEPENDENCIES
###################################################
from pylightio.managers.devices import BaseDeviceType
from pylightio.lookingglass.lightfields import LookingGlassQuilt

# PREPARE LOGGING
###################################################
import logging

# get the library logger
logger = logging.getLogger('pyLightIO')



# LOOKING GLASS DEVICE MIXIN
###############################################
# Looking Glass mixin, introduced to reduce code that would be the same for
# each Looking Glass device type anyway
class LookingGlassDeviceMixin(object):

    # DEFINE PUBLIC CLASS ATTRIBUTES
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    type = None                       # the unique identifier string of this device type
    name = None                       # name of this device type
    formats = None                    # list of lightfield image formats that are supported
    emulated_configuration = None     # configuration used for emulated devices of this type


    # INSTANCE METHODS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # NOTE: Here is the place to define methods required by the BaseClass for any
    #       device type implementations
    def __init__(self, service, configuration=None):
        ''' initialize this specific values of this device type '''
        # call the initialization procedure of the BaseClass
        super().__init__(service, configuration)

    def display(self, lightfield, flip_views=False, aspect=None, invert=None, custom_decoder=None):
        ''' display a given lightfield image object on the device '''
        # NOTE: This method should only do validity checks.
        #       Then call service methods to display the lightfield on the device.

        # if None was given or the given lightfield image format is supported
        if lightfield == None or type(lightfield) in self.formats:

            # if a service is bound
            if self.service:

                # if no aspect ratio is given, use the device aspect ratio
                if not aspect: aspect = self.configuration['calibration']['aspect']
                if invert == None: invert = self.configuration['calibration']['invView']

                logger.info("Requesting '%s' to display the lightfield on '%s' ..." % (self.service, self))

                # request the service to display the lightfield on the device
                if self.service.display(self, lightfield, flip_views=flip_views, aspect=aspect, invert=invert, custom_decoder=custom_decoder):

                    # if that is successful, remember the lightfield for this device
                    self.lightfield = lightfield

                return True

            raise RuntimeError("No service was specified.")

        raise TypeError("The given lightfield image of type '%s' is not supported by this device." % type(lightfield))

    def clear(self):
        ''' clear the device display '''

        # if a service is bound
        if self.service:

            # clear the display
            if self.service.clear(self):

                # reset the instance's lightfield state variable
                self.lightfield = None

                return True

        raise RuntimeError("No service was specified.")


    # CLASS PROPERTIES - SPECIFIC TO LOOKING GLASS DEVICES
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # (A) general properties
    @property
    def index(self):
        return self.configuration['index']

    @index.setter
    def index(self, value):
        pass

    @property
    def serial(self):
        return self.calibration['serial']

    @serial.setter
    def serial(self, value):
        pass

    @property
    def hwid(self):
        return self.configuration['hwid']

    @hwid.setter
    def hwid(self, value):
        pass

    @property
    def type(self):
        return self.configuration['hardwareVersion']

    @type.setter
    def type(self, value):
        pass

    @property
    def calibration(self):
        return self.configuration['calibration']

    @calibration.setter
    def calibration(self, value):
        self.configuration['calibration'] = value

    @property
    def defaultQuilt(self):
        if isinstance(self.configuration['defaultQuilt'], str):
            import json
            return json.loads(self.configuration['defaultQuilt'])
        return self.configuration['defaultQuilt']

    @defaultQuilt.setter
    def defaultQuilt(self, value):
        self.configuration['defaultQuilt'] = value


    # (B) default quilt settings
    @property
    def default_quilt_width(self):
        return self.defaultQuilt['quiltX']

    @default_quilt_width.setter
    def default_quilt_width(self, value):
        pass

    @property
    def default_quilt_height(self):
        return self.defaultQuilt['quiltY']

    @default_quilt_height.setter
    def default_quilt_height(self, value):
        pass

    @property
    def default_quilt_columns(self):
        return self.defaultQuilt['tileX']

    @default_quilt_columns.setter
    def default_quilt_columns(self, value):
        pass

    @property
    def default_quilt_rows(self):
        return self.defaultQuilt['tileY']

    @default_quilt_rows.setter
    def default_quilt_rows(self, value):
        pass


    # (C) calibration properties
    @property
    def aspect(self):
        return self.calibration['aspect']

    @aspect.setter
    def aspect(self, value):
        pass

    @property
    def x(self):
        return self.configuration['x']

    @x.setter
    def x(self, value):
        pass

    @property
    def y(self):
        return self.configuration['y']

    @y.setter
    def y(self, value):
        pass

    @property
    def width(self):
        return self.calibration['screenW']

    @width.setter
    def width(self, value):
        pass

    @property
    def height(self):
        return self.calibration['screenH']

    @height.setter
    def height(self, value):
        pass

    @property
    def viewCone(self):
        return self.calibration['viewCone']

    @viewCone.setter
    def viewCone(self, value):
        pass


# SPECIFIC LOOKING GLASS DEVICE TYPES
###############################################
# Looking Glass Go
class LookingGlassGo(LookingGlassDeviceMixin, BaseDeviceType):

    # PUBLIC MEMBERS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    type = "go_p"                # the unique identifier string of this device type
    name = "Looking Glass Go"  # name of this device type
    formats = [LookingGlassQuilt]    # list of lightfield image formats that are supported
    emulated_configuration = {       # configuration used for emulated devices of this type
                'buttons': [0, 0, 0, 0],
                'calibration': {
                                    'DPI': 491.0,
                                    'configVersion': '1.0',
                                    'screenH': 2560.0,
                                    'screenW': 1440.0,
                                    'serial': 'LKG-EDUMMY',
                                    'viewCone': 40.0,
                                    'aspect': 0.5625,
                                    'invView': True
                                },
                'defaultQuilt': {
                                    'quiltAspect': 0.5625,
                                    'quiltX': 4092,
                                    'quiltY': 4092,
                                    'tileX': 11,
                                    'tileY': 6
                                },
                'hardwareVersion': 'go_p',
                'hwid': 'LKG0009DUMMY',
                'index': -1,
                'joystickIndex': -1,
                'state': 'ok',
            }


    # INSTANCE METHODS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # NOTE: Here is the place to define methods required by the BaseClass for any
    #       device type implementations

    # This type uses the LookingGlassBaseType and has no special requirements

# Looking Glass Portrait
class LookingGlassPortrait(LookingGlassDeviceMixin, BaseDeviceType):

    # PUBLIC MEMBERS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    type = "portrait"                # the unique identifier string of this device type
    name = "Looking Glass Portrait"  # name of this device type
    formats = [LookingGlassQuilt]    # list of lightfield image formats that are supported
    emulated_configuration = {       # configuration used for emulated devices of this type
                'buttons': [0, 0, 0, 0],
                'calibration': {
                                    'DPI': 324.0,
                                    'configVersion': '1.0',
                                    'screenH': 2048.0,
                                    'screenW': 1536.0,
                                    'serial': 'LKG-5-DUMMY',
                                    'viewCone': 40.0,
                                    'aspect': 0.75,
                                    'invView': True
                                },
                'defaultQuilt': {
                                    'quiltAspect': 0.75,
                                    'quiltX': 3360,
                                    'quiltY': 3360,
                                    'tileX': 8,
                                    'tileY': 6
                                },
                'hardwareVersion': 'portrait',
                'hwid': 'LKG0005DUMMY',
                'index': -2,
                'joystickIndex': -1,
                'state': 'ok',
            }


    # INSTANCE METHODS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # NOTE: Here is the place to define methods required by the BaseClass for any
    #       device type implementations

    # This type uses the LookingGlassBaseType and has no special requirements

# Looking Glass 16 Landscape
class LookingGlass16Landscape(LookingGlassDeviceMixin, BaseDeviceType):

    # PUBLIC MEMBERS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    type = "16_gen3_l"                # the unique identifier string of this device type
    name = "Looking Glass 16'' Landscape (Gen3)"  # name of this device type
    formats = [LookingGlassQuilt]    # list of lightfield image formats that are supported
    emulated_configuration = {       # configuration used for emulated devices of this type
                'buttons': [0, 0, 0, 0],
                'calibration': {
                                    'DPI': 283.0,
                                    'configVersion': '3.0',
                                    'screenH': 2160.0,
                                    'screenW': 3840.0,
                                    'serial': 'LKG-JDUMMY',
                                    'viewCone': 40.0,
                                    'aspect': 1.77777777,
                                    'invView': True
                                },
                'defaultQuilt': {
                                    'quiltAspect': 1.77777777,
                                    'quiltX': 5999,
                                    'quiltY': 5999,
                                    'tileX': 7,
                                    'tileY': 7
                                },
                'hardwareVersion': '16_gen3_l',
                'hwid': 'LKG0010DUMMY',
                'index': -3,
                'joystickIndex': -1,
                'state': 'ok',
            }


    # INSTANCE METHODS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # NOTE: Here is the place to define methods required by the BaseClass for any
    #       device type implementations

    # This type uses the LookingGlassBaseType and has no special requirements

# Looking Glass 16 Portrait
class LookingGlass16Portrait(LookingGlassDeviceMixin, BaseDeviceType):

    # PUBLIC MEMBERS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    type = "16_gen3_p"                # the unique identifier string of this device type
    name = "Looking Glass 16'' Portrait (Gen3)"  # name of this device type
    formats = [LookingGlassQuilt]    # list of lightfield image formats that are supported
    emulated_configuration = {       # configuration used for emulated devices of this type
                'buttons': [0, 0, 0, 0],
                'calibration': {
                                    'DPI': 283.0,
                                    'configVersion': '1.0',
                                    'screenH': 3840.0,
                                    'screenW': 2160.0,
                                    'serial': 'LKG-HDUMMY',
                                    'viewCone': 40.0,
                                    'aspect': 0.5625,
                                    'invView': True
                                },
                'defaultQuilt': {
                                    'quiltAspect': 0.5625,
                                    'quiltX': 5995,
                                    'quiltY': 6000,
                                    'tileX': 11,
                                    'tileY': 6
                                },
                'hardwareVersion': '16_gen3_p',
                'hwid': 'LKG0011DUMMY',
                'index': -4,
                'joystickIndex': -1,
                'state': 'ok',
            }


    # INSTANCE METHODS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # NOTE: Here is the place to define methods required by the BaseClass for any
    #       device type implementations

    # This type uses the LookingGlassBaseType and has no special requirements

# Looking Glass 32 Landscape
class LookingGlass32Landscape(LookingGlassDeviceMixin, BaseDeviceType):

    # PUBLIC MEMBERS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    type = "32_gen3_l"                # the unique identifier string of this device type
    name = "Looking Glass 32'' Landscape (Gen3)"  # name of this device type
    formats = [LookingGlassQuilt]    # list of lightfield image formats that are supported
    emulated_configuration = {       # configuration used for emulated devices of this type
                'buttons': [0, 0, 0, 0],
                'calibration': {
                                    'DPI': 280.0,
                                    'configVersion': '1.0',
                                    'screenH': 4320.0,
                                    'screenW': 7680.0,
                                    'serial': 'LKG-LDUMMY',
                                    'viewCone': 40.0,
                                    'aspect': 1.77777777,
                                    'invView': True
                                },
                'defaultQuilt': {
                                    'quiltAspect': 1.77777777,
                                    'quiltX': 8190,
                                    'quiltY': 8190,
                                    'tileX': 7,
                                    'tileY': 7
                                },
                'hardwareVersion': '32_gen3_l',
                'hwid': 'LKG0012DUMMY',
                'index': -5,
                'joystickIndex': -1,
                'state': 'ok',
            }


    # INSTANCE METHODS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # NOTE: Here is the place to define methods required by the BaseClass for any
    #       device type implementations

    # This type uses the LookingGlassBaseType and has no special requirements

# Looking Glass 32 Portrait
class LookingGlass32Portrait(LookingGlassDeviceMixin, BaseDeviceType):

    # PUBLIC MEMBERS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    type = "32_gen3_p"                # the unique identifier string of this device type
    name = "Looking Glass 32'' Portrait (Gen3)"  # name of this device type
    formats = [LookingGlassQuilt]    # list of lightfield image formats that are supported
    emulated_configuration = {       # configuration used for emulated devices of this type
                'buttons': [0, 0, 0, 0],
                'calibration': {
                                    'DPI': 280.0,
                                    'configVersion': '1.0',
                                    'screenH': 7680.0,
                                    'screenW': 4320.0,
                                    'serial': 'LKG-KDUMMY',
                                    'viewCone': 40.0,
                                    'aspect': 0.5625,
                                    'invView': True
                                },
                'defaultQuilt': {
                                    'quiltAspect': 0.5625,
                                    'quiltX': 8184,
                                    'quiltY': 8184,
                                    'tileX': 11,
                                    'tileY': 6
                                },
                'hardwareVersion': '32_gen3_p',
                'hwid': 'LKG0012DUMMY',
                'index': -6,
                'joystickIndex': -1,
                'state': 'ok',
            }


    # INSTANCE METHODS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # NOTE: Here is the place to define methods required by the BaseClass for any
    #       device type implementations

    # This type uses the LookingGlassBaseType and has no special requirements

# Looking Glass 65"
class LookingGlass65(LookingGlassDeviceMixin, BaseDeviceType):
    #PUBLIC MEMBERS
    #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    type = "65_gen2"                    # the unique identifier string of this device type
    name = "Looking Glass 65'' (Gen2)"        # name of this device type
    formats = [LookingGlassQuilt]       # list of lightfield image formats that are supported
    emulated_configuration = {          # configuration used for emulated devices of this type
                'buttons': [0, 0, 0, 0],
                'calibration': {
                                    'configVersion': '1.0',
                                    'serial': 'LKG-65-DUMMY',
                                    'DPI': 280.0,
                                    'screenH': 4320.0,
                                    'screenW': 7680.0,
                                    'viewCone': 40.0,
                                    'aspect': 1.77777777,
                                    'invView': True
                                },
                'defaultQuilt': {
                                    'quiltAspect': 1.77777777,
                                    'quiltX': 8192,
                                    'quiltY': 8190,
                                    'tileX': 8,
                                    'tileY': 9
                                },
                'hardwareVersion': '65',
                'hwid': 'LKG0008DUMMY',
                'index': -7,
                'joystickIndex': -1,
                'state': 'ok',
            }
    # INSTANCE METHODS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # NOTE: Here is the place to define methods required by the BaseClass for any
    #       device type implementations

    # This type uses the LookingGlassBaseType and has no special requirements

# 4K Gen2: 4K Gen2 Looking Glass
class LookingGlass4kGen2(LookingGlassDeviceMixin, BaseDeviceType):

    # PUBLIC MEMBERS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    type = "4k_gen2"                 # the unique identifier string of this device type
    name = "Looking Glass 16'' (Gen2)"      # name of this device type
    formats = [LookingGlassQuilt]    # list of lightfield image formats that are supported
    emulated_configuration = {       # configuration used for emulated devices of this type
                'buttons': [0, 0, 0, 0],
                'calibration': {
                                    'configVersion': '1.0',
                                    'serial': 'LKG-ADUMMY',
                                    'DPI': 283.0,
                                    'screenH': 2160.0,
                                    'screenW': 3840.0,
                                    'viewCone': 40.0,
                                    'aspect': 1.77777777,
                                    'invView': True
                                },
                'defaultQuilt': {
                                    'quiltAspect': 1.77777777,
                                    'quiltX': 4096,
                                    'quiltY': 4096,
                                    'tileX': 5,
                                    'tileY': 9
                                },
                'hardwareVersion': '4k_gen2',
                'hwid': 'LKG0007DUMMY',
                'index': -8,
                'joystickIndex': -1,
                'state': 'ok',
            }

    # INSTANCE METHODS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # NOTE: Here is the place to define methods required by the BaseClass for any
    #       device type implementations

    # This type uses the LookingGlassBaseType and has no special requirements

# 8K Gen2: 8K Gen2 Looking Glass
class LookingGlass8kGen2(LookingGlassDeviceMixin, BaseDeviceType):

    # PUBLIC MEMBERS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    type = "8k_gen2"                 # the unique identifier string of this device type
    name = "Looking Glass 32'' (Gen2)"      # name of this device type
    formats = [LookingGlassQuilt]    # list of lightfield image formats that are supported
    emulated_configuration = {       # configuration used for emulated devices of this type
                'buttons': [0, 0, 0, 0],
                'calibration': {
                                    'configVersion': '1.0',
                                    'serial': 'LKG-BDUMMY',
                                    'DPI': 280.0,
                                    'screenH': 4320.0,
                                    'screenW': 7680.0,
                                    'viewCone': 40.0,
                                    'aspect': 1.77777777,
                                    'invView': True
                                },
                'defaultQuilt': {
                                    'quiltAspect': 1.77777777,
                                    'quiltX': 8192,
                                    'quiltY': 8192,
                                    'tileX': 5,
                                    'tileY': 9
                                },
                'hardwareVersion': '8k_gen2',
                'hwid': 'LKG0006DUMMY',
                'index': -9,
                'joystickIndex': -1,
                'state': 'ok',
            }

    # INSTANCE METHODS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # NOTE: Here is the place to define methods required by the BaseClass for any
    #       device type implementations

    # This type uses the LookingGlassBaseType and has no special requirements

# Standard: 8.9'' Looking Glass
class LookingGlassStandard(LookingGlassDeviceMixin, BaseDeviceType):

    # PUBLIC MEMBERS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    type = "standard"                   # the unique identifier string of this device type
    name = "8.9'' Looking Glass (Gen1)"        # name of this device type
    formats = [LookingGlassQuilt]       # list of lightfield image formats that are supported
    emulated_configuration = {          # configuration used for emulated devices of this type
                'buttons': [0, 0, 0, 0],
                'calibration': {
                                    'configVersion': '1.0',
                                    'serial': 'LKG-2K-DUMMY',
                                    'DPI': 338.0,
                                    'screenH': 1600.0,
                                    'screenW': 2560.0,
                                    'viewCone': 40.0,
                                    'aspect': 1.6,
                                    'invView': True
                                },
                'defaultQuilt': {
                                    'quiltAspect': 1.6,
                                    'quiltX': 4096,
                                    'quiltY': 4096,
                                    'tileX': 5,
                                    'tileY': 9
                                },
                'hardwareVersion': 'standard',
                'hwid': 'LKG0001DUMMY',
                'index': -10,
                'joystickIndex': -1,
                'state': 'ok',
            }

    # INSTANCE METHODS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # NOTE: Here is the place to define methods required by the BaseClass for any
    #       device type implementations

    # This type uses the LookingGlassBaseType and has no special requirements

# Large: 15.6'' Looking Glass
class LookingGlassLarge(LookingGlassDeviceMixin, BaseDeviceType):

    # PUBLIC MEMBERS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    type = "large"                      # the unique identifier string of this device type
    name = "15.6'' Looking Glass (Gen1)"       # name of this device type
    formats = [LookingGlassQuilt]       # list of lightfield image formats that are supported
    emulated_configuration = {          # configuration used for emulated devices of this type
                'buttons': [0, 0, 0, 0],
                'calibration': {
                                    'configVersion': '1.0',
                                    'serial': 'LKG-4K-DUMMY',
                                    'DPI': 283.0,
                                    'screenH': 2160.0,
                                    'screenW': 3840.0,
                                    'viewCone': 40.0,
                                    'aspect': 1.77777777,
                                    'invView': True
                                },
                'defaultQuilt': {
                                    'quiltAspect': 1.77777777,
                                    'quiltX': 4096,
                                    'quiltY': 4096,
                                    'tileX': 5,
                                    'tileY': 9
                                },
                'hardwareVersion': 'large',
                'hwid': 'LKG0002DUMMY',
                'index': -11,
                'joystickIndex': -1,
                'state': 'ok',
            }

    # INSTANCE METHODS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # NOTE: Here is the place to define methods required by the BaseClass for any
    #       device type implementations

    # This type uses the LookingGlassBaseType and has no special requirements

# Large Pro: 15.6'' Pro Looking Glass
class LookingGlassLargePro(LookingGlassDeviceMixin, BaseDeviceType):

    # PUBLIC MEMBERS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    type = "pro"                        # the unique identifier string of this device type
    name = "15.6'' Pro Looking Glass (Gen1)"   # name of this device type
    formats = [LookingGlassQuilt]       # list of lightfield image formats that are supported
    emulated_configuration = {          # configuration used for emulated devices of this type
                'buttons': [0, 0, 0, 0],
                'calibration': {
                                    'configVersion': '1.0',
                                    'serial': 'LKG-4K-DUMMY',
                                    'DPI': 283.0,
                                    'screenH': 2160.0,
                                    'screenW': 3840.0,
                                    'viewCone': 40.0,
                                    'aspect': 1.77777777,
                                    'invView': True
                                },
                'defaultQuilt': {
                                    'quiltAspect': 1.77777777,
                                    'quiltX': 4096,
                                    'quiltY': 4096,
                                    'tileX': 5,
                                    'tileY': 9
                                },
                'hardwareVersion': 'pro',
                'hwid': 'LKG0003DUMMY',
                'index': -12,
                'joystickIndex': -1,
                'state': 'ok',
            }

    # INSTANCE METHODS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # NOTE: Here is the place to define methods required by the BaseClass for any
    #       device type implementations

    # This type uses the LookingGlassBaseType and has no special requirements

# 8k: 8k Looking Glass
class LookingGlass8k(LookingGlassDeviceMixin, BaseDeviceType):

    # PUBLIC MEMBERS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    type = "8k"                      # the unique identifier string of this device type
    name = "Looking Glass 8k (Gen1)"        # name of this device type
    formats = [LookingGlassQuilt]    # list of lightfield image formats that are supported
    emulated_configuration = {       # configuration used for emulated devices of this type
                'buttons': [0, 0, 0, 0],
                'calibration': {
                                    'configVersion': '1.0',
                                    'serial': 'LKG-8K-DUMMY',
                                    'DPI': 280.0,
                                    'screenH': 4320.0,
                                    'screenW': 7680.0,
                                    'viewCone': 40.0,
                                    'aspect': 1.77777777,
                                    'invView': True
                                },
                'defaultQuilt': {
                                    'quiltAspect': 1.77777777,
                                    'quiltX': 8192,
                                    'quiltY': 8192,
                                    'tileX': 5,
                                    'tileY': 9
                                },
                'hardwareVersion': '8k',
                'hwid': 'LKG0004DUMMY',
                'index': -13,
                'joystickIndex': -1,
                'state': 'ok',
            }

    # INSTANCE METHODS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # NOTE: Here is the place to define methods required by the BaseClass for any
    #       device type implementations

    # This type uses the LookingGlassBaseType and has no special requirements
