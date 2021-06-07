# ############################## LICENSE BLOCK ###############################
#
#                      freeHPC - Free HoloPlay Core API
#                      ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
# MIT License
#
# Copyright © 2021 Yann Vernier, Christian Stolze
# All rights reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
# ############################################################################

# This is a slighty modified version of https://github.com/regcs/freehpc

import sys, os, platform
import json, binascii, struct
import ctypes
import subprocess
from math import *
from enum import Enum

# TODO: Is there a better way to share global variables between all addon files and operators?
from .looking_glass_global_variables import *

# append the add-on's lib path to Blender's python PATH, so that the modules
# can be loaded
sys.path.append(LookingGlassAddon.path)
sys.path.append(LookingGlassAddon.libpath)

# for debugging only
from pprint import pprint

# Note: Use libhidapi-hidraw, i.e. hidapi with hidraw support,
# or the joystick device will be gone when execution finishes.
import hid as hidapi

try:

    from .lib import pynng
    from .lib import cbor

    # all python dependencies are fulfilled
    python_dependecies = True

except:

    # not all python dependencies are fulfilled
    python_dependecies = False
    pass



# FREE HOLOPLAY CORE API
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

class freeHoloPlayCoreAPI:

    # INTERNAL VARIABLES
    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Version of free HoloPlay Core API
    version = '1.0.0'

    # HoloPlay Service communication & information
    driver_address = "ipc:///tmp/holoplay-driver.ipc"
    socket = None
    holoplay_service_version = 'None'

    # list of all Looking Glass Devices
    devices = []

    # internal HID identification
    vendor_id = 0x04d8
    product_id = 0xef7e # is this specific to versions of the Looking Glasses?
    manufacturer_string = u'Looking Glass Factory'
    product_string = u'HoloPlay'



    # CONSTANTS
    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # hpc_client_error
    ###################
    #   Enum definition for errors returned from the HoloPlayCore dynamic library.
    #
    #   This encapsulates potential errors with the connection itself,
    #   as opposed to hpc_service_error, which describes potential error messages
    #   included in a successful reply from HoloPlay Service.

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


    # hpc_service_error
    ###################
    #   Enum definition for error codes included in HoloPlay Service responses.
    #
    #   Most error messages from HoloPlay Service concern access to the HoloPlay Service
    #   internal renderer, which is supported but not the primary focus of the current
    #   version of HoloPlay Core.
    #
    #   Future versions of HoloPlay Service may return error codes not defined by this
    #   spec.

    class service_error(Enum):
        ERR_NOERROR = 0
        ERR_BADCBOR = 1
        ERR_BADCOMMAND = 2
        ERR_NOIMAGE = 3
        ERR_LKGNOTFOUND = 4
        ERR_NOTINCACHE = 5
        ERR_INITTOOLATE = 6
        ERR_NOTALLOWED = 7


    # hpc_license_type
    ###################
    #   Enum definition for possible types of licenses associated with a HoloPlay Core app.
    #
    #   Non-commercial apps can't run on Looking Glass devices without an associated commercial license.

    class license_type(Enum):
        LICENSE_NONCOMMERCIAL = 0
        LICENSE_COMMERCIAL = 1



    # LIGHTFIELD SHADERS
    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Vertex shader
    LightfieldVertShaderGLSL = '''
        // INPUT AND OUTPUT VARIABLES
        layout (location = 0)
        in vec2 vertPos_data;
        out vec2 texCoords;

        // VERTEX SHADER
        void main()
        {
        	gl_Position = vec4(vertPos_data.xy, 0.0, 1.0);
        	texCoords = (vertPos_data.xy + 1.0) * 0.5;
        }
    '''

    # Fragment shader
    LightfieldFragShaderGLSL = '''
        in vec2 texCoords;
        out vec4 fragColor;

        // CALIBRATION VALUES
        uniform float pitch;
        uniform float tilt;
        uniform float center;
        uniform int invView;
        uniform float subp;
        uniform float displayAspect;
        uniform int ri;
        uniform int bi;

        // QUILT SETTINGS
        uniform vec3 tile;
        uniform vec2 viewPortion;
        uniform int debug;

        // QUILT TEXTURE
        uniform sampler2D screenTex;

        // GET CORRECT VIEW
        vec2 quilt_map(vec2 pos, float a) {

            // Tile ordering
            vec2 tile2 = vec2(tile.x - 1, tile.y - 1), dir=vec2(-1, -1);

            a = fract(a) * tile.y;
            tile2.y += dir.y * floor(a);
            a = fract(a) * tile.x;
            tile2.x += dir.x * floor(a);
            return (tile2 + pos) / tile.xy;

        }

        // SHADER
        void main()
        {

            float a;
            vec4 res;

            a = (-texCoords.x - texCoords.y * tilt) * pitch - center;
            res.r = texture(screenTex, quilt_map(texCoords.xy, a-ri*subp)).r;
            res.g = texture(screenTex, quilt_map(texCoords.xy, a-   subp)).g;
            res.b = texture(screenTex, quilt_map(texCoords.xy, a-bi*subp)).b;

            if (debug == 1) {
                // use quilt texture
                res = texture(screenTex, texCoords.xy);
            }
            else if (debug == 2) {
                // Mark center line only in central view
                res.r = res.r * 0.001 + (texCoords.x>0.49 && texCoords.x<0.51 && fract(a)>0.48&&fract(a)<0.51 ?1.0:0.0);
                res.g = res.g * 0.001 + texCoords.x;
                res.b = res.b * 0.001 + texCoords.y;
            }

            res.a = 1.0;
            fragColor = res;

        }
    '''



    # INTERNAL FUNCTIONS
    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # send a NNG message to the HoloPlay Service
    def nng_send_message(self, input_object):

        # if a NNG socket is open
        if self.socket != None and self.socket != 0:

            # dump a CBOR message
            dump = cbor.dumps(input_object)

            # send it to the socket
            self.socket.send(dump)

            # receive the CBOR-formatted response
            response = self.socket.recv()

            # return the message length and its conent
            return [len(response), cbor.loads(response)]

    # obtain calibration data from JSON data
    def loadconfig(self, hiddev):
        "Loads cfg JSON from LG HID"
        jsonlen = struct.unpack('>I', self.readpage(hiddev, 0, 4))[0] + 4
        assert jsonlen != 0xffffffff
        data = bytearray()
        while len(data) < jsonlen:
            page = len(data)//64
            l = min(64, jsonlen-64*page)
            data[64*page:] = self.readpage(hiddev, page, l)
        return json.loads(data[4:].decode('ascii'))


    # read JSON data page
    def readpage(self, hiddev=None, addr=0, size=64):
        if hiddev != None:
            send = bytearray(struct.pack('>BH64x', 0, addr))
            hiddev.send_feature_report(b'\0' + send)
            r = bytearray(hiddev.read(1+1+2+64, timeout=1000))

            while r[1:4] != send[:3]:
                r = bytearray(hiddev.read(1+1+2+64, timeout=1000))
                if len(r) < 1+1+2+64:
                    r += bytearray(hiddev.read(1+1+2+64-len(r), timeout=10))
        # First byte holds button bitmask
        # second byte is command for EEPROM management (0=read)
        # third and fourth are EEPROM page address
        # Verify 1:4 so we are reading the correct data
        assert r[1:4] == send[:3]
        return r[4:4+size]


    # TODO: How do we differentiate between multiple connected LKGs?
    #       Might be rare case, but still should be implemented!
    def get_device_hdmi_name(self, cfg):

        # set default output
        returnName = b'LKG00PxDUMMY'

		# if on macOS
        if platform.system() == "Darwin":

            # on macOS: system_profiler SPDisplaysDataType -json delivers Display Info
            # on macOS: system_profiler SPUSBDataType -json delivers USB device info

            # use the 'system_profiler' terminal command to obtain basic display infos
            info = subprocess.check_output(['system_profiler', 'SPDisplaysDataType', '-json'])
            info = json.loads(info.decode('ascii'))

            # go through all displays
            for display in info['SPDisplaysDataType'][0]['spdisplays_ndrvs']:
                # until we find a Looking Glass
                if 'LKG' == display['_name'][:3]:
                    returnName = display['_name'].encode()
                    break

        # if on Windows
        elif platform.system() == "Windows":

            # The following is modified code part from:
            # https://github.com/torarve/RunRes/blob/master/runres.py (MIT License)
            # and mixed with https://stackoverflow.com/questions/4958683/how-do-i-get-the-actual-monitor-name-as-seen-in-the-resolution-dialog
            # LICENSE: (MIT License)
            from ctypes import wintypes

            # load user32.dll, which contains all the functions to obtain
            # display informations
            user32 = ctypes.WinDLL('user32', use_last_error=True)

            # Define the DISPLAY_DEVICE Structure
            class DISPLAY_DEVICE(ctypes.Structure):
            	_fields_ = [
            		("cb", ctypes.wintypes.DWORD),
            		("DeviceName", ctypes.wintypes.CHAR*32),
            		("DeviceString", ctypes.wintypes.CHAR*128),
            		("StateFlags", ctypes.wintypes.DWORD),
            		("DeviceID", ctypes.wintypes.CHAR*128),
            		("DeviceKey", ctypes.wintypes.CHAR*128)
            	]

            # make an instance of this structure and set its cbSize
            display_device = DISPLAY_DEVICE()
            display_device.cb = ctypes.sizeof(display_device)

            # index and output variable
            i = 0

            # iterate through all display devices
            while user32.EnumDisplayDevicesA(None, i, ctypes.pointer(display_device),0):
                i += 1

                # we need to call that function again to get the Monitor name
                user32.EnumDisplayDevicesA(display_device.DeviceName, 0, ctypes.pointer(display_device), 0)

                # if it is a Looking Glass
                if b'LKG' in display_device.DeviceString:
                    returnName = display_device.DeviceString
                    break


        # if on Linux
        elif platform.system() == "Linux":

            info = subprocess.check_output(['xrandr', '--prop'])
            for width,height,x,y,edid in re.findall(rb"^\S+ connected(?: primary)? (?P<width>\d+)x(?P<height>\d+)(?P<x>[-+]\d+)(?P<y>[-+]\d+).*\n\s+EDID:\s*\n(?P<edid>(?:\s+[0-9a-f]+\n)+)", info, re.MULTILINE):
                edid = binascii.a2b_hex(b''.join(edid.split()))
                try:
                    name = re.search(rb"\0\0\0\xfc\0([^\n]{,13})", edid)[1]
                except TypeError:	# Found no name
                    continue
                if not (name.startswith(b'LKG') and int(width)==cfg['screenW'] and int(height)==cfg['screenH']):
                    continue	# Wrong name or resolution

                cfg['windowCoords'] = [int(x), int(y)]
                returnName = name
                break


        # return the obtained name
        return returnName.decode('ascii')

    # TODO: Maybe using the resolution is not future proof, but don't know how
    #       to infer it otherwise. May be improved later, if required.
    def get_device_type(self, width, height):

		# if 8.9'' Looking Glass
        if width == 2560 and height == 1600:
            return 'standard'

        # TODO: How do we differentiate the PRO device?
        #       And is that necessary? Probably not, because it is the same screen.
		# if 15.6'' Looking Glass or 15.6'' Looking Glass Pro
        elif width == 3840 and height == 2160:
            return 'large'

		# if Looking Glass 8k
        elif width == 7680 and height == 4320:
            return '8k'

		# if 7.9'' Looking Glass Portrait
        elif width == 1536 and height == 2048:
            return 'portrait'


    # just a helper function for the screen positions on Windows
    def get_monitor_name(self, name):

        # load user32.dll, which contains all the functions to obtain
        # display informations
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        class DISPLAY_DEVICE(ctypes.Structure):
        	_fields_ = [
        		("cb", ctypes.wintypes.DWORD),
        		("DeviceName", ctypes.wintypes.CHAR*32),
        		("DeviceString", ctypes.wintypes.CHAR*128),
        		("StateFlags", ctypes.wintypes.DWORD),
        		("DeviceID", ctypes.wintypes.CHAR*128),
        		("DeviceKey", ctypes.wintypes.CHAR*128)
        	]
        device_name = DISPLAY_DEVICE()
        device_name.cb = ctypes.sizeof(device_name)
        index = 0
        user32.EnumDisplayDevicesA(None, index, ctypes.pointer(device_name),0)
        user32.EnumDisplayDevicesA(name.encode(), 0, ctypes.pointer(device_name), 0)
        return device_name.DeviceString


    # TODO: Maybe using the resolution is not future proof, but don't know how
    #       to infer it otherwise. May be improved later, if required.
    def get_device_screen_position(self, name):

        # set default output
        global x, y
        windowCoords = [0, 0]

		# if on macOS
        if platform.system() == "Darwin":

            # TODO: The following is only a placeholder.
            #       Find a way to obtain the position!

            # use the 'system_profiler' terminal command to obtain basic display infos
            info = subprocess.check_output(['system_profiler', 'SPDisplaysDataType', '-json'])
            info = json.loads(info.decode('ascii'))

            # go through all displays
            for display in info['SPDisplaysDataType'][0]['spdisplays_ndrvs']:
                # until we find a Looking Glass
                if display['_name'] == name:

                    # TODO: Are there keys that return the position?
                    windowCoords = [0, 0]

                    break



        # if on Windows
        elif platform.system() == "Windows":

            # The following is taken from:
            # https://github.com/glitchassassin/lackey/blob/7adadfacd7f45d81186710be992f5668b15399fe/lackey/PlatformManagerWindows.py/
            # LICENSE: (MIT License)
            from ctypes import wintypes

            # load user32.dll, which contains all the functions to obtain
            # display informations
            user32 = ctypes.WinDLL('user32', use_last_error=True)

            # this is for the monitor name
            CCHDEVICENAME = 32
            def _MonitorEnumProcCallback(hMonitor, hdcMonitor, lprcMonitor, dwData):
                global x, y
                class MONITORINFOEX(ctypes.Structure):
                    _fields_ = [("cbSize", ctypes.wintypes.DWORD),
                                ("rcMonitor", ctypes.wintypes.RECT),
                                ("rcWork", ctypes.wintypes.RECT),
                                ("dwFlags", ctypes.wintypes.DWORD),
                                ("szDevice", ctypes.wintypes.WCHAR*CCHDEVICENAME)]
                lpmi = MONITORINFOEX()
                lpmi.cbSize = ctypes.sizeof(MONITORINFOEX)
                user32.GetMonitorInfoW(hMonitor, ctypes.byref(lpmi))

                # if this is the monitor we are looking for
                if self.get_monitor_name(lpmi.szDevice) == name:
                    windowCoords = [lprcMonitor.contents.left, lprcMonitor.contents.top]

                    # stop enumeration here
                    return False
                else:
                    return True

            MonitorEnumProc = ctypes.WINFUNCTYPE(
                ctypes.c_bool,
                ctypes.c_ulong,
                ctypes.c_ulong,
                ctypes.POINTER(ctypes.wintypes.RECT),
                ctypes.c_int)

            # enumerate all monitors and try to find the one with
            # the specified name
            callback = MonitorEnumProc(_MonitorEnumProcCallback)
            if user32.EnumDisplayMonitors(0, 0, callback, 0) == 0:
                raise WindowsError("Unable to enumerate monitors")



        # TODO: Implement on Linux. Using 'xdotool', maybe?
        # if on Linux
        elif platform.system() == "Linux":

            # use the 'xdotool' terminal command to obtain basic display infos
            info = subprocess.check_output(['xdotool', '???'])


        # return the obtained name
        return windowCoords

    # calculate the values derived from the calibration data
    def calculate_derived(self, cfg):

        # calculate any values derived values from the cfg values
        cfg['tilt'] = cfg['screenH'] / (cfg['screenW'] * cfg['slope'])
        cfg['pitch'] = - cfg['screenW'] / cfg['DPI']  * cfg['pitch']  * sin(atan(abs(cfg['slope'])))
        cfg['subp'] = cfg['pitch'] / (3 * cfg['screenW'])
        cfg['ri'], cfg['bi'] = (2,0) if cfg['flipSubp'] else (0,2)


    # FUNCTIONS RESEMBLING THE HOLO PLAY CORE SDK FUNCTIONALITY
    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    # --- HOLOPLAY SERVICE METHODS ---
    # The following functions are only used when communicating with HoloPlay
    # Service
    def InitializeApp(self, app_name, hpc_license_type):

        # set default error value:
        # NOTE: - if communication with HoloPlay Service fails, we use the
        #         direct HID approach to read calibration data
        error = self.client_error.CLIERR_NOERROR.value

        # if all python dependencies are fulfilled
        if python_dependecies == True:

            # open a Req0 socket
            self.socket = pynng.Req0(recv_timeout = 5000)

            # try to address the HoloPlay Service
            try:

                self.socket.dial(self.driver_address, block = True)

                # TODO: Set proper error values
                # set error value
                error = self.client_error.CLIERR_NOERROR.value

            except:

                # Close socket and reset status variable
                if self.socket != None:
                    self.socket.close()
                    self.socket = None

                pass

        # if everything is fine:
        if error == self.client_error.CLIERR_NOERROR.value:

            # we use the RefreshState function to build
            # the list of Looking Glass devices, since it is the same code
            self.RefreshState()

        # return error value
        return error

    # Close the socket to the HoloPlay Service
    def CloseApp(self):

        # if all python dependencies are fulfilled
        if self.socket != None and self.socket != 0:

            # close the Req0 socket
            self.socket.close()

    # Version of the HoloPlay Service
    def GetHoloPlayServiceVersion(self, buffer=None, buffer_length=0):
        if buffer != None:
            # prepare output
            buffer.value = self.holoplay_service_version.encode('ascii')
            return buffer

    def GetHoloPlayCoreVersion(self, buffer, buffer_length):
        if buffer != None:
            buffer.value = self.version.encode('ascii')
            return buffer



    # --- REQUIRED METHODS ---
    # NOTE: The following methods are required by the Blender add-on
    # Refresh the device list
    def RefreshState(self):

        # clear the list
        self.devices.clear()

        # list of unsuitable devices
        delete_list = []

        # HOLOPLAY SERVICE COMMUNICATION
        # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        # if all python dependencies are fulfilled AND a NNG socket is open
        if python_dependecies == True and (self.socket != 0 and self.socket != None):

            # request calibration data
            response = self.nng_send_message({'cmd': {'info': {}}, 'bin': ''})
            if response != None:

                # TODO: Implement error checks
                error = response[1]['error']

                # HoloPlay Service related information
                self.holoplay_service_version = response[1]['version']

                # create a dictionary with an index for this device
                self.devices = response[1]['devices']

                # iterate through all devices
                for i in range(0, len(self.devices)):

                    # if a calibration can be obtained
                    if self.devices[i]['state'] == "ok":

                        # to flatten the dict, we extract the separate "calibration"
                        # dict and delete it
                        cfg = self.devices[i]['calibration']
                        self.devices[i].pop('calibration', None)

                        # parse odd value-object format from calibration json
                        cfg.update({key: value['value'] if isinstance(value, dict) else value for (key,value) in cfg.items()})

                        # calculate the derived values (e.g., tilt, pich, etc.)
                        self.calculate_derived(cfg)

                        # TODO: HoloPlay Core SDK delivers the fringe value,
                        #       but it is not in the JSON. LoneTechs assumed that it is
                        #       a border crop setting, to hide lit up pixels outside of the big block
                        # arbitrarily assign 0.0 to fringe
                        cfg['fringe'] = 0.0

                        # reimplement the calibration data, but at the higher level
                        self.devices[i].update(cfg)

                    # in case device state was not 'ok'
                    else:

                        # append this device to the list of devices
                        # which need to be deleted afterwards
                        delete_list.append(self.devices[i])


                # delete all devices, with bad state
                for dev in delete_list: self.devices.remove(dev)

                # update the index of each device
                for i in range(0, len(self.devices)): self.devices[i]['index'] = i


        # DIRECT HID READING
        # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        # otherwise we use the fallback method and read calibration data over HID
        else:

            # iterate through all HID devices
            for dev in hidapi.enumerate():

                # if this device belongs to the Looking Glass Factory
                if (dev['product_string'] == self.product_string and dev['manufacturer_string'] == self.manufacturer_string and dev['usage_page'] == 1):

                    # if the path could not be detected
                    if len(dev['path']) == 0:

                        # TODO: We need a work around!
                        # NOTE: We might obtain that from ioreg's IOServiceLegacyMatchingRegistryID entry?

                        # NOTE: Path is sometimes empty on macOS, because hidapi.enumerate is unable to provide the path
                        #       on macOS. Might be related to too long paths (https://github.com/flirc/hidapi/commit/8d251c3854c3b1877509ab07a623dafc8e803db5)
                        #       that occur for certain USB Hubs.
                        dev['path'] = b"id:4295030796"


                    # create a dictionary with an index for this device
                    cfg = dict(index = len(self.devices))

                    # try to connect and read the device information
                    try:

                        # add HID device data
                        cfg['hiddev'] = hidapi.Device(vid=dev['vendor_id'], pid=dev['product_id'], serial=dev['serial_number'], path=dev['path'])

                        # Parse odd value-object format from json
                        cfg.update({key: value['value'] if isinstance(value, dict) else value for (key,value) in self.loadconfig(cfg['hiddev']).items()})

                        # calculate the derived values (e.g., tilt, pich, etc.)
                        self.calculate_derived(cfg)

                        # find hdmi name, device type, and monitor position in
                        # virtual screen coordinates
                        cfg['hwid'] = self.get_device_hdmi_name(cfg)
                        cfg['hardwareVersion'] = self.get_device_type(cfg['screenW'], cfg['screenH'])
                        if 'windowCoords' not in cfg:
                            cfg['windowCoords'] = self.get_device_screen_position(cfg['hwid'])

                        # TODO: HoloPlay Core SDK delivers the fringe value,
                        #       but it is not in the JSON. LoneTechs assumed that it is
                        #       a border crop setting, to hide lit up pixels outside of the big block
                        # arbitrarily assign 0.0 to fringe
                        cfg['fringe'] = 0.0

                        # close the device
                        cfg['hiddev'].close()

                        # append the device and its data to the internal device list
                        self.devices.append(cfg)

                    except:
                        pass

    # Return number of Looking Glass devices
    def GetNumDevices(self):
        return len(self.devices)

    # TODO: How do we obtain the HDMI name? Important for identification.
    # Return device's HDMI name
    def GetDeviceHDMIName(self, index, buffer, buffersize):
        buffer.value = next(item for item in self.devices if item["index"] == index)['hwid'].encode('ascii')

    # Return device's serial
    def GetDeviceSerial(self, index, buffer, buffersize):
        buffer.value = next(item for item in self.devices if item["index"] == index)['serial'].encode('ascii')

    # TODO: How do we infer the actual type? HoloPlayCore SDK uses the following:
    #       standard, portrait (?), large, pro, 8k
    # Return device's type
    def GetDeviceType(self, index, buffer, buffersize):
        buffer.value = next(item for item in self.devices if item["index"] == index)['hardwareVersion'].encode('ascii')

    # Return device's window x position
    def GetDevicePropertyWinX(self, index):
        return int(next(item for item in self.devices if item["index"] == index)['windowCoords'][0])

    # Return device's window y position
    def GetDevicePropertyWinY(self, index):
        return int(next(item for item in self.devices if item["index"] == index)['windowCoords'][1])

    # Return device's screen width
    def GetDevicePropertyScreenW(self, index):
        return int(next(item for item in self.devices if item["index"] == index)['screenW'])

    # Return device's screen height
    def GetDevicePropertyScreenH(self, index):
        return int(next(item for item in self.devices if item["index"] == index)['screenH'])

    # Return device's screen aspect ratio
    def GetDevicePropertyDisplayAspect(self, index):
        return float(self.GetDevicePropertyScreenW(index) / self.GetDevicePropertyScreenH(index))

    # Return device's pitch value
    def GetDevicePropertyPitch(self, index):
        return float(next(item for item in self.devices if item["index"] == index)['pitch'])

    # Return device's tilt value
    def GetDevicePropertyTilt(self, index):
        return float(next(item for item in self.devices if item["index"] == index)['tilt'])

    # Return device's center value
    def GetDevicePropertyCenter(self, index):
        return float(next(item for item in self.devices if item["index"] == index)['center'])

    # Return device's subp value
    def GetDevicePropertySubp(self, index):
        return float(next(item for item in self.devices if item["index"] == index)['subp'])

    # Return device's fringe value
    def GetDevicePropertyFringe(self, index):
        return float(next(item for item in self.devices if item["index"] == index)['fringe'])

    # Return device's Ri value
    def GetDevicePropertyRi(self, index):
        return int(next(item for item in self.devices if item["index"] == index)['ri'])

    # Return device's Bi value
    def GetDevicePropertyBi(self, index):
        return int(next(item for item in self.devices if item["index"] == index)['bi'])

    # Return device's invView value
    def GetDevicePropertyInvView(self, index):
        return int(next(item for item in self.devices if item["index"] == index)['invView'])

    # Return device's float property value
    # NOTE: implement it in this strange way, so we can keep the calls in the
    #       Blender add-on unmodified
    def GetDevicePropertyFloat(self, index, property_string):
        if property_string == b"/calibration/viewCone/value":
            return next(item for item in self.devices if item["index"] == index)['viewCone']
        else:
            return 0.0
