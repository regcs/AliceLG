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
import sys, os, io, struct
import pynng, cv2
import math
import numpy as np

# debugging
import time

# INTERNAL PACKAGE DEPENDENCIES
###################################################
from pylightio.managers.services import BaseServiceType
from pylightio.formats import *
from pylightio.external import cbor

# PREPARE LOGGING
###################################################
import logging

# get the library logger
logger = logging.getLogger('pyLightIO')



# SERVICE TYPES FOR LOOKING GLASS DEVICES
###############################################
# Looking Glass Bridge for Looking Glass lightfield displays
class LookingGlassBridge(BaseServiceType):

    # DEFINE CLASS PROPERTIES AS PROTECTED MEMBERS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    type = 'lookingglassbridge'                            # the unique identifier string of this service type (required for the factory class)
    name = 'Looking Glass Bridge'                           # the name this service type

    # DEFINE CLASS PROPERTIES AS PRIVATE MEMBERS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    __socket = None                                             # NNG socket
    __address = 'ipc:///tmp/holoplay-driver.ipc'                # driver url (alternative: "ws://localhost:11222/driver", "ipc:///tmp/holoplay-driver.ipc")
    __dialer = None                                             # NNG Dialer of the socket
    __devices = []                                              # list of devices supported by this service (#TODO: this needs to be implemented)
    __decoder_format = LightfieldImage.decoderformat.numpyarray # the decoder format in which the lightfield data is passed to the service

    # Error
    ###################
    #   Enum definition for errors returned from the HoloPlayCore dynamic library.
    #
    #   This encapsulates potential errors with the connection itself,
    #   as opposed to hpc_service_error, which describes potential error messages
    #   included in a successful reply from Looking Glass Bridge.
    class client_error(Enum):
        CLIERR_NOERROR = 0
        CLIERR_NOSERVICE = 1
        CLIERR_VERSIONERR = 2
        CLIERR_SERIALIZEERR = 3
        CLIERR_DESERIALIZEERR = 4
        CLIERR_MSGTOOBIG = 5
        CLIERR_SENDTIMEOUT = 6
        CLIERR_RECVTIMEOUT = 7
        CLIERR_PIPEERROR = 8
        CLIERR_APPNOTINITIALIZED = 9

    # INSTANCE METHODS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    def __init__(self, timeout = 5000, client_name = ""):
        ''' initialize the class instance and create the NNG socket '''

        # open a Req0 socket
        self.__socket = pynng.Req0(recv_timeout = timeout, send_timeout = timeout)

        # if the NNG socket is open
        if self.__is_socket():

            logger.info("Created socket: %s" % self.__socket)

            # connect to Looking Glass Bridge App
            if self.__connect():

                # send initialization command
                response = self.__send_message(self.__init(client_name))
                if response != None:

                    # if no error was received
                    if response[1]['error'] == 0:

                        # fill version string of the Looking Glass Bridge
                        self.version = response[1]['version']

                # log info
                logger.info("Connected to Looking Glass Bridge v%s." % self.get_version())

    def is_ready(self):
        ''' check if the service is ready: Is NNG socket created and connected to Looking Glass Bridge App? '''
        if self.__is_connected():
            return True

        return False

    def get_version(self):
        ''' return the looking glass bridge version '''

        # if the NNG socket is connected to Looking Glass Bridge App and version still unknown
        if self.__is_connected() and not self.version:

            # request service version
            response = self.__send_message({'cmd': {'info': {}}, 'bin': ''})
            if response != None:

                # if no error was received
                if response[1]['error'] == 0:

                    # fill version string of the Looking Glass Bridge
                    self.version = response[1]['version']

        return self.version

    def get_devices(self):
        ''' send a request to the service and request the connected devices '''
        ''' this function should return a list object '''

        # if the service is ready
        if self.is_ready():

            # request calibration data
            response = self.__send_message(self.__get_devices())
            if response != None:

                # if no errors were received
                if response[1]['error'] == 0:

                    # get the list of devices with status "ok"
                    devices = [device for device in response[1]['devices'] if device['state'] == "ok"]

                    # iterate through all devices
                    for device in devices:

                        # parse odd value-object format from calibration json
                        device['calibration'].update({key: value['value'] if isinstance(value, dict) else value for (key, value) in device['calibration'].items()})

                        # calculate the derived values (e.g., tilt, pich, etc.)
                        device['calibration'].update(self.__calculate_derived(device['calibration']))

                        # return the device list
                        return devices

    def display(self, device, lightfield, flip_views=False, aspect=None, invert=False, custom_decoder = None):
        ''' display a given lightfield image object on a device '''
        ''' Looking Glass Bridge expects a lightfield image in LookingGlassQuilt format '''

        logger.info("Preparing lightfield image '%s' for display on '%s' ..." % (lightfield, device))

        # if the service is ready
        if self.is_ready():
            start_total = time.time()
            # if a lightfield was given
            if lightfield != None:

                # convert the lightfield into a suitable format for this service
                # NOTE: Looking Glass Bridge expects a byte stream
                start = time.time()
                decoded_lightfield_data = lightfield.decode(self.__decoder_format, flip_views=flip_views, custom_decoder=custom_decoder)

                # lightfield is decoded as numpy array
                if self.__decoder_format == LightfieldImage.decoderformat.numpyarray and type(decoded_lightfield_data) == np.ndarray:

                    # flip the individual views vertically, if required
                    start = time.time()
                    if flip_views:
                        merged_numpy = lightfield.merged_numpy.view()[:, ::-1, :, :, :]

                        logger.debug(" [#] Flipping the numpy array of shape %s took %.3f ms." % (merged_numpy.shape, (time.time() - start) * 1000))
                        start = time.time()
                    else:
                        merged_numpy = lightfield.merged_numpy.view()

                    # convert BGR(A) <-> RGB on little-endian systems to make the
                    # data in the numpy buffer comply with the BITMAP file format
                    # specifications
                    start = time.time()
                    if sys.byteorder == "little":

                        if lightfield.colorchannels == 3:

                            bytes = cv2.cvtColor(merged_numpy.reshape(lightfield.metadata['quilt_height'], lightfield.metadata['quilt_width'], lightfield.colorchannels), cv2.COLOR_BGR2RGB)

                            logger.debug(" [#] Converting from BGR to RGB took %.3f ms." % ((time.time() - start) * 1000))

                        elif lightfield.colorchannels == 4:

                            bytes = cv2.cvtColor(merged_numpy.reshape(lightfield.metadata['quilt_height'], lightfield.metadata['quilt_width'], lightfield.colorchannels), cv2.COLOR_BGRA2RGB)

                            logger.debug(" [#] Converting from BGRA to RGB took %.3f ms." % ((time.time() - start) * 1000))

                    elif not sys.byteorder == "little" and lightfield.colorchannels == 4:

                        # TODO: Actually we would not need this, if we could
                        #       read in RGB mode to gpu.types.Buffer, but we can't
                        #       due to a Blender bug / limitation:
                        #
                        #       https://developer.blender.org/T91828
                        bytes = cv2.cvtColor(merged_numpy.reshape(lightfield.metadata['quilt_height'], lightfield.metadata['quilt_width'], lightfield.colorchannels), cv2.COLOR_RGBA2RGB)

                        logger.debug(" [#] Converting from RGBA to RGB took %.3f ms." % ((time.time() - start) * 1000))

                    else:

                        bytes = merged_numpy.reshape(lightfield.metadata['quilt_height'], lightfield.metadata['quilt_width'], lightfield.colorchannels)

                        logger.debug(" [#] Reading bytes from %s took %.3f ms." % (type(bytes), (time.time() - start) * 1000))

                    # parse the quilt metadata
                    settings = {'vx': lightfield.metadata['columns'], 'vy':lightfield.metadata['rows'], 'vtotal': lightfield.metadata['rows'] * lightfield.metadata['columns'], 'aspect': aspect, 'invert': invert}

                    # pass the quilt to the device
                    logger.info(" [#] Lightfield image with shape %s is being sent to '%s'." % (bytes.shape, self))
                    self.__send_message(self.__show_quilt(device.configuration['index'], bytes, settings), image_shape=(lightfield.metadata['quilt_height'],lightfield.metadata['quilt_width'], 3))
                    logger.info(" [#] Done (total time: %.3f ms)." % ((time.time() - start_total) * 1000))

                    return True

                raise TypeError("The '%s' expected lightfield data conversion to %s, but %s was passed." % (self, np.ndarray, type(decoded_lightfield_data)))

            # otherwise show the demo quilt
            else:

                # pass the quilt to the device
                logger.info(" [#] Display of demo quilt is requested for '%s' ..." % self)
                self.__send_message(self.__show_demo(device.configuration['index']))
                logger.info(" [#] Done.")

                return True

        raise RuntimeError("The '%s' is not ready. Is Looking Glass Bridge app running?" % (self))

    def clear(self, device):
        ''' clear the display of a given device '''

        # if the service is ready
        if self.is_ready():

            # clear the display
            if self.__send_message(self.__hide(device.configuration['index'])):

                return True

        raise RuntimeError("The '%s' is not ready. Is Looking Glass Bridge app running?" % (self))

    def __del__(self):
        ''' disconnect from Looking Glass Bridge App and close NNG socket '''
        if self.__is_connected():

            # disconnect and close socket
            self.__disconnect()
            self.__close()

    # PRIVATE INSTANCE METHODS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # NOTE: Here is the place to define internal functions required only for this
    #       specific service implementation

    def __is_socket(self):
        ''' check if the socket is open '''
        return (self.__socket != None and self.__socket != 0)

    def __is_connected(self):
        ''' check if a connection to a service is active '''
        return (self.__socket != None and self.__socket != 0 and self.__dialer)

    def __connect(self):
        ''' connect to looking glass bridge '''

        # set default error value
        error = self.client_error.CLIERR_NOERROR.value

        # if there is not already a connection
        if self.__dialer == None:

            # try to connect to the Looking Glass Bridge
            try:

                self.__dialer = self.__socket.dial(self.__address, block = True)

                # TODO: Set proper error values
                error = self.client_error.CLIERR_NOERROR.value

                return True

            # if the connection was not established
            except:# pynng.exceptions.ConnectionRefused

                # Close socket and reset status variable
                self.__close()

                logger.error("Could not connect. Is Looking Glass Bridge running?")

                return False

        logger.info("Already connected to Looking Glass Bridge v%s." % self.get_version())
        return True

    def __disconnect(self):
        ''' disconnect from looking glass bridge '''

        # if a connection is active
        if self.__is_connected():
            self.__dialer.close()
            self.__dialer = None
            logger.info("Closed connection to %s." % self.name)
            return True

        # otherwise
        logger.info("There is no active connection to close.")
        return False

    def __close(self):
        ''' close NNG socket '''

        # Close socket and reset status variable
        if self.__is_socket():
            self.__socket.close()

            # reset state variables
            self.__socket = None
            self.__dialer = None
            self.version = ""

    def __send_message(self, input_object, image_shape=None):
        ''' send a message to Looking Glass Bridge '''

        # if a NNG socket is open
        if self.__is_socket():
            start = time.time()

            # dump a CBOR message
            if image_shape is None:
                cbor_dump = cbor.dumps(input_object)
            else:
                cbor_dump = cbor.dumps(input_object, image_shape=image_shape)

            logger.debug(" [#] Encoding command as CBOR before sending took %.3f ms." % ((time.time() - start) * 1000))
            start = time.time()

            # send it to the socket
            self.__socket.send(cbor_dump)

            logger.debug(" [#] Sending command of length %i took %.3f ms." % (len(cbor_dump), (time.time() - start) * 1000))
            start = time.time()

            # receive the CBOR-formatted response
            if not ('show' in input_object['cmd'].keys()):
                response = self.__socket.recv()
            else:
                return#response = self.__socket.recv()

            logger.debug(" [#] Waiting for response took %.3f ms." % ((time.time() - start) * 1000))

            # return the decoded CBOR response length and its conent
            return [len(response), cbor.loads(response)]

    def __calculate_derived(self, calibration):
        ''' calculate the values derived from the calibration json delivered by Looking Glass Bridge '''

        calibration['aspect'] = calibration['screenW'] / calibration['screenH']
        calibration['tilt'] = calibration['screenH'] / (calibration['screenW'] * calibration['slope'])
        calibration['pitch'] = - calibration['screenW'] / calibration['DPI']  * calibration['pitch']  * math.sin(math.atan(abs(calibration['slope'])))
        calibration['subp'] = calibration['pitch'] / (3 * calibration['screenW'])
        calibration['ri'], calibration['bi'] = (2,0) if calibration['flipSubp'] else (0,2)
        calibration['fringe'] = 0.0

        return calibration


    # PRIVATE STATIC METHODS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    @staticmethod
    def __init(client_name):
        ''' initialize the client at Looking Glass Bridge with the given name '''

        # log info
        logger.debug("Registering at Looking Glass Bridge with INIT command:")

        # define CBOR command
        command = {
            'cmd': {
                'init': {'appid': client_name},
            },
            'bin': '',
        }
        return command

    @staticmethod
    def __get_devices():
        ''' tell Looking Glass Bridge to send the calibrations of all devices '''

        # log info
        logger.debug("Requesting device list from Looking Glass Bridge with INFO command:")

        # define CBOR command
        command = {
            'cmd': {
                'info': {},
            },
            'bin': '',
        }
        return command

    @staticmethod
    def __show_demo(dev_index):
        ''' tell Looking Glass Bridge to show the demo quilt '''

        # log info
        logger.debug("Requesting demo quilt from Looking Glass Bridge with SHOW command:")

        # define CBOR command
        command = {
            'cmd': {
                'show': {
                    'targetDisplay': dev_index,
                },
            },
        }
        return command

    @staticmethod
    def __show_quilt(dev_index, bindata, settings):
        ''' tell Looking Glass Bridge to display the incoming quilt '''

        # log info
        logger.debug("Requesting quilt display from Looking Glass Bridge with SHOW command:")

        # define CBOR command
        command = {
            'cmd': {
                'show': {
                    'targetDisplay': dev_index,
                    'source': 'bindata',
                    'quilt': {
                        'type': 'image',
                        'settings': settings
                    }
                },
            },
            'bin': bindata,
        }
        return command

    @staticmethod
    def __load_quilt(dev_index, name, settings = None):
        ''' tell Looking Glass Bridge to load a cached quilt '''

        # log info
        logger.debug("Requesting to load cached quilt from Looking Glass Bridge with SHOW command:")

        # define CBOR command
        command = {
            'cmd': {
                'show': {
                    'targetDisplay': dev_index,
                    'source': 'cache',
                    'quilt': {
                        'type': 'image',
                        'name': name
                    },
                },
            },
            'bin': bytes(),
        }

        # if settings were specified
        if settings: command['cmd']['show']['quilt']['settings'] = settings

        return command

    @staticmethod
    def __cache_quilt(dev_index, bindata, name, settings):
        ''' tell Looking Glass Bridge to cache the incoming quilt '''

        # log info
        logger.debug("Requesting to cache quilt by Looking Glass Bridge with CACHE command:")

        # define CBOR command
        command = {
            'cmd': {
                'cache': {
                    'targetDisplay': dev_index,
                    'quilt': {
                        'type': 'image',
                        'name': name,
                        'settings': settings
                    }
                }
            },
            'bin': bindata,
        }
        return command

    @staticmethod
    def __hide(dev_index):
        ''' tell Looking Glass Bridge to hide the displayed quilt '''

        # log info
        logger.debug("Requesting to hide quilt from Looking Glass Bridge with HIDE command:")

        # define CBOR command
        command = {
            'cmd': {
                'hide': {
                    'targetDisplay': dev_index,
                },
            },
            'bin': bytes(),
        }
        return command

    @staticmethod
    def __wipe(dev_index):
        ''' tell Looking Glass Bridge to clear the display (shows the logo quilt) '''

        # log info
        logger.debug("Requesting to wipe the quilt from Looking Glass Bridge with HIDE command:")

        # define CBOR command
        command = {
            'cmd': {
                'targetDisplay': dev_index,
                'wipe': {},
            },
            'bin': bytes(),
        }
        return command
