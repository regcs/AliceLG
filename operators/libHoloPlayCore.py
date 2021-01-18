# ##### BEGIN GPL LICENSE BLOCK #####
#
#  Copyright © 2020 Christian Stolze
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# ##### END GPL LICENSE BLOCK #####

import sys, os, platform
import json, struct, subprocess
import ctypes
from math import *
from enum import Enum
from pprint import pprint

# Note: Use libhidapi-hidraw, i.e. hidapi with hidraw support,
# or the joystick device will be gone when execution finishes.
import hid as hidapi

# TODO: Is there a better way to share global variables between all addon files and operators?
#from .looking_glass_global_variables import *

# -------------------- Load Library ----------------------
# Load the HoloPlay Core SDK Library
print("Loading HoloPlay Core SDK library")
print(" # Running on OS: ", platform.system())
print(" # System architecture: ", platform.architecture())
print(" # Searching for HoloPlay Core SDK")

# ------------ FREE HOLOPLAY CORE REPLACEMENT ---------------
class freeHoloPlayCoreAPI:

    # INTERNAL VARIABLES
    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
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

        // Calibration values
        uniform float pitch;
        uniform float tilt;
        uniform float center;
        uniform int invView;
        uniform float subp;
        uniform float displayAspect;
        uniform int ri;
        uniform int bi;

        // Quilt settings
        uniform vec3 tile;
        uniform vec2 viewPortion;
        uniform float quiltAspect;
        uniform int overscan;
        uniform int quiltInvert;
        uniform int debug;
        uniform sampler2D screenTex;

        // CALCULATE PARAMETERS USED IN THIS SHADER
        float subp2 = subp * pitch;

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

        void main()
        {
            float a;
            vec4 res;

            a = (-texCoords.x - texCoords.y * tilt) * pitch - center;
            res.r = texture(screenTex, quilt_map(texCoords.xy, a-ri*subp2)).r;
            res.g = texture(screenTex, quilt_map(texCoords.xy, a-   subp2)).g;
            res.b = texture(screenTex, quilt_map(texCoords.xy, a-bi*subp2)).b;

            if (debug == 1) {
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
    def __init__(self):

        # we use the RefreshState function to build
        # the list of Looking Glass devices, since it is the same code
        self.RefreshState()

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
    def get_device_hdmi_name(self):
        # on macOS: system_profiler SPDisplaysDataType -json delivers Display Info
        # on macOS: system_profiler SPUSBDataType -json delivers USB device info

		# if on macOS
        if platform.system() == "Darwin":

            # use the 'system_profiler' terminal command to obtain basic display infos
            info = subprocess.check_output(['system_profiler', 'SPDisplaysDataType', '-json'])
            info = json.loads(info.decode('ascii'))

            # go through all displays
            for display in info['SPDisplaysDataType'][0]['spdisplays_ndrvs']:
                # until we find a Looking Glass
                if 'LKG' == display['_name'][:3]:
                    break
            else:
                display['_name'] = 'LKG79PxDUMMY'

            # return the name
            return display['_name']

        # if on Windows
        elif platform.system() == "Windows":

            return 'LKG79PxDUMMY'

        elif platform.system() == "Linux":

            return 'LKG79PxDUMMY'

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



    # FUNCTIONS RESEMBLING THE HOLO PLAY CORE SDK FUNCTIONALITY
    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    # --- DUMMY METHODS ---
    # NOTE: The following methods do not provide the real functionality, which
    #       is provided by the HoloPlay Core SDK of the Looking Glass Factory.
    #       They are included to keep the Blender add-on (Alice/LG) fully
    #       compatible to the official HoloPlay Core SDK.
    def InitializeApp(self, app_name, hpc_license_type):
        # we always return no error to fake communication with holo play service
        return self.client_error.CLIERR_NOERROR.value

    def GetHoloPlayServiceVersion(self, buffer=None, buffer_length=0):
        if buffer != None:
            version_string = 'None'
            buffer.value = version_string.encode('ascii')
            return buffer

    def GetHoloPlayCoreVersion(self, buffer, buffer_length):
        if buffer != None:
            version_string = '1.0.0'
            buffer.value = version_string.encode('ascii')
            return buffer



    # --- REQUIRED METHODS ---
    # NOTE: The following methods are required by the Blender add-on
    # Refresh the device list
    def RefreshState(self):

        # clear the list
        self.devices.clear()

        # iterate through all HID devices
        for dev in hidapi.enumerate():

            # if this device belongs to the Looking Glass Factory
            if dev['product_string'] == self.product_string and dev['manufacturer_string'] == self.manufacturer_string and dev['usage_page'] == 1:
                pprint(dev)

                # if the path could not be detected
                if dev['path'] == '':

                    # TODO: We need a work around!
                    # NOTE: We might obtain that from ioreg's IOServiceLegacyMatchingRegistryID entry?

                    # NOTE: Path is sometimes empty on macOS, because hidapi.enumerate is unable to provide the path
                    #       on macOS. Might be related to too long paths (https://github.com/flirc/hidapi/commit/8d251c3854c3b1877509ab07a623dafc8e803db5)
                    #       that occur for certain USB Hubs.
                    dev['path'] = b"id:4294971243"


                # create a dictionary with an index for this device
                cfg = dict(index = len(self.devices))

                # add HID device data
                cfg['hiddev'] = hidapi.Device(vid=dev['vendor_id'], pid=dev['product_id'], serial=dev['serial_number'], path=dev['path'])

                # Parse odd value-object format from json
                cfg.update({key: value['value'] if isinstance(value, dict) else value for (key,value) in self.loadconfig(cfg['hiddev']).items()})

                # calculate any values derived values from the cfg values
                cfg['tilt'] = cfg['screenH'] / (cfg['screenW'] * cfg['slope'])
                cfg['pitch'] = - cfg['screenW'] / cfg['DPI']  * cfg['pitch']  * sin(atan(cfg['slope']))
                cfg['subp'] = 1.0 / (3 * cfg['screenW'])
                cfg['ri'], cfg['bi'] = (2,0) if cfg['flipSubp'] else (0,2)

                # find hdmi name and device type
                cfg['hdmi'] = self.get_device_hdmi_name()
                cfg['type'] = self.get_device_type(cfg['screenW'], cfg['screenH'])

                # TODO: HoloPlay Core SDK delivers these values as calibration data
                #       but they are not in the JSON
                cfg['x'] = 0
                cfg['y'] = 0
                cfg['fringe'] = 0.0

                # close the device
                cfg['hiddev'].close()

                # append the device and its data to the internal device list
                self.devices.append(cfg)

    # Return number of Looking Glass devices
    def GetNumDevices(self):
        return len(self.devices)

    # TODO: How do we obtain the HDMI name? Important for identification.
    # Return device's HDMI name
    def GetDeviceHDMIName(self, index, buffer, buffersize):
        buffer.value = next(item for item in self.devices if item["index"] == index)['hdmi'].encode('ascii')

    # Return device's serial
    def GetDeviceSerial(self, index, buffer, buffersize):
        buffer.value = next(item for item in self.devices if item["index"] == index)['serial'].encode('ascii')

    # TODO: How do we infer the actual type? HoloPlayCore SDK uses the following:
    #       standard, portrait (?), large, pro, 8k
    # Return device's type
    def GetDeviceType(self, index, buffer, buffersize):
        buffer.value = next(item for item in self.devices if item["index"] == index)['type'].encode('ascii')

    # Return device's window x position
    def GetDevicePropertyWinX(self, index):
        return int(next(item for item in self.devices if item["index"] == index)['x'])

    # Return device's window y position
    def GetDevicePropertyWinY(self, index):
        return int(next(item for item in self.devices if item["index"] == index)['y'])

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






# if __name__ == '__main__':
#
#     print("Initializing free HoloPlay Core replacement.")
#
#     # initialize free HoloPlayCore
#     hpc = freeHoloPlayCoreAPI()
#
#     errco = hpc.InitializeApp('Test', hpc.license_type.LICENSE_NONCOMMERCIAL.value)
#     if errco == 0:
#
# 		# allocate string buffer
#         buffer = ctypes.create_string_buffer(1000)
#
#         # get HoloPlay Service Version
#         hpc.GetHoloPlayServiceVersion(buffer, 1000)
#         print(" # HoloPlay Service version: " + buffer.value.decode('ascii').strip())
#
# 		# get HoloPlay Core SDK version
#         hpc.GetHoloPlayCoreVersion(buffer, 1000)
#         print(" # HoloPlay Core SDK version: " + buffer.value.decode('ascii').strip())
#
#         # get number of devices
#         print(" # Number of connected displays: " + str(hpc.GetNumDevices()))
#
#         for i in range(hpc.GetNumDevices()):
#             print(" # Device %i" % i)
#
# 			# get device HDMI name
#             hpc.GetDeviceHDMIName(i, buffer, 1000)
#             dev_hdmi = buffer.value.decode('ascii').strip()
#
#             # get device serial
#             hpc.GetDeviceSerial(i, buffer, 1000)
#             dev_serial = buffer.value.decode('ascii').strip()
#
#             # get device type
#             hpc.GetDeviceType(i, buffer, 1000)
#             dev_type = buffer.value.decode('ascii').strip()
#
#             print("  - hdmi:", dev_hdmi)
#             print("  - serial:", dev_serial)
#             print("  - type:", dev_type)
#             # Calibration information
#             print("  - x:", hpc.GetDevicePropertyWinX(i))
#             print("  - y:", hpc.GetDevicePropertyWinY(i))
#             print("  - width:", hpc.GetDevicePropertyScreenW(i))
#             print("  - height:", hpc.GetDevicePropertyScreenH(i))
#             print("  - aspect:", hpc.GetDevicePropertyDisplayAspect(i))
#             print("  - pitch:", hpc.GetDevicePropertyPitch(i))
#             print("  - tilt:", hpc.GetDevicePropertyTilt(i))
#             print("  - center:", hpc.GetDevicePropertyCenter(i))
#             print("  - subp:", hpc.GetDevicePropertySubp(i))
#             print("  - fringe:", hpc.GetDevicePropertyFringe(i))
#             print("  - ri:", hpc.GetDevicePropertyRi(i))
#             print("  - bi:", hpc.GetDevicePropertyBi(i))
#             print("  - invView:", hpc.GetDevicePropertyInvView(i))
#             print("  - viewCone:", hpc.GetDevicePropertyFloat(i, b"/calibration/viewCone/value"))
