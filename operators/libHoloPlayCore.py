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
import ctypes
from ctypes.util import find_library
from enum import Enum

# TODO: Is there a better way to share global variables between all addon files and operators?
from .looking_glass_global_variables import *


# -------------------- Load Library ----------------------
# get path of this addon
LookingGlassAddon.path = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), os.pardir))

# Load the HoloPlay Core SDK Library
print("Loading HoloPlay Core SDK library")
print(" # Running on OS: ", platform.system())
print(" # System architecture: ", platform.architecture())
print(" # Find addon path: ", LookingGlassAddon.path)
print(" # Searching for HoloPlay Core SDK")

# if on macOS
if platform.system() == "Darwin":

    # if the library is in the addon directory
    if os.path.isfile(LookingGlassAddon.path + "/lib/macos/libHoloPlayCore.dylib") == True:

        libpath = LookingGlassAddon.path + "/lib/macos/libHoloPlayCore.dylib"

    else:

        # try to find the library elsewhere
        libpath = find_library('HoloPlayCore')


# if on 32-bit Windows
elif platform.system() == "Windows" and platform.architecture()[0] == "32bit":

    # if the library is in the addon directory
    if os.path.isfile(LookingGlassAddon.path + "/lib/Win32/HoloPlayCore.dll") == True:

        libpath = LookingGlassAddon.path + "/lib/Win32/HoloPlayCore.dll"

    else:

        # try to find the library elsewhere
        libpath = find_library('HoloPlayCore')


# if on 64-bit Windows
elif platform.system() == "Windows" and platform.architecture()[0] == "64bit":

    # if the library is in the addon directory
    if os.path.isfile(LookingGlassAddon.path + "/lib/Win64/HoloPlayCore.dll") == True:

        libpath = LookingGlassAddon.path + "/lib/Win64/HoloPlayCore.dll"

    else:

        # try to find the library elsewhere
        libpath = find_library('HoloPlayCore')


# if on 64-bit Windows
elif platform.system() == "Linux":

    # if the library is in the addon directory
    if os.path.isfile(LookingGlassAddon.path + "/lib/linux/libHoloPlayCore.so") == True:

        libpath = LookingGlassAddon.path + "/lib/linux/libHoloPlayCore.so"

    else:

        # try to find the library elsewhere
        libpath = find_library('HoloPlayCore')


else:
    raise OSError("Unsupported operating system.")


# if the library was found
if os.path.isfile(libpath):
    print(" # HoloPlay Core SDK found in: " + libpath)
    hpc = ctypes.cdll.LoadLibrary(libpath)
else:
    raise FileNotFoundError("Could not find HoloPlay Core SDK.")




# ---------------------- Constants -----------------------


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



# ---------- PYTHON WRAPPE FOR HOLOPLAYCORE -------------
# Lightfield Shaders
LightfieldVertShaderGLSL = ctypes.c_char_p.in_dll(hpc, "hpc_LightfieldVertShaderGLSLExported").value.decode("utf-8")
LightfieldFragShaderGLSL = ctypes.c_char_p.in_dll(hpc, "hpc_LightfieldFragShaderGLSLExported").value.decode("utf-8")



# ----------------- GENERAL FUNCTIONS -------------------
# int hpc_InitializeApp(const char *app_name, int license)
InitializeApp = hpc.hpc_InitializeApp
InitializeApp.argtypes = [ctypes.c_char_p, ctypes.c_int]
InitializeApp.restype = ctypes.c_int

# int hpc_RefreshState()
RefreshState = hpc.hpc_RefreshState
RefreshState.argtypes = None
RefreshState.restype = ctypes.c_int

# int hpc_CloseApp()
CloseApp = hpc.hpc_CloseApp
CloseApp.argtypes = None
CloseApp.restype = ctypes.c_int

# int hpc_GetHoloPlayCoreVersion(const char *buffer, int bufferSize)
GetHoloPlayCoreVersion = hpc.hpc_GetHoloPlayCoreVersion
GetHoloPlayCoreVersion.argtypes = [ctypes.c_char_p, ctypes.c_int]
GetHoloPlayCoreVersion.restype = ctypes.c_int

# int hpc_GetHoloPlayServiceVersion(const char *buffer, int bufferSize)
GetHoloPlayServiceVersion = hpc.hpc_GetHoloPlayServiceVersion
GetHoloPlayServiceVersion.argtypes = [ctypes.c_char_p, ctypes.c_int]
GetHoloPlayServiceVersion.restype = ctypes.c_int

# int hpc_GetNumDevices()
GetNumDevices = hpc.hpc_GetNumDevices
GetNumDevices.argtypes = None
GetNumDevices.restype = ctypes.c_int


# ----------------- DEVICE PROPERTIES ------------------
# int hpc_GetDeviceHDMIName(int DEV_INDEX, const char *buffer, int bufferSize)
GetDeviceHDMIName = hpc.hpc_GetDeviceHDMIName
GetDeviceHDMIName.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
GetDeviceHDMIName.restype = ctypes.c_int

# int hpc_GetDeviceSerial(int DEV_INDEX, const char *buffer, int bufferSize)
GetDeviceSerial = hpc.hpc_GetDeviceSerial
GetDeviceSerial.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
GetDeviceSerial.restype = ctypes.c_int

# int hpc_GetDeviceType(int DEV_INDEX, const char *buffer, int bufferSize)
GetDeviceType = hpc.hpc_GetDeviceType
GetDeviceType.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
GetDeviceType.restype = ctypes.c_int

# int hpc_GetDevicePropertyWinX(int DEV_INDEX)
GetDevicePropertyWinX = hpc.hpc_GetDevicePropertyWinX
GetDevicePropertyWinX.argtypes = [ctypes.c_int]
GetDevicePropertyWinX.restype = ctypes.c_int

# int hpc_GetDevicePropertyWinY(int DEV_INDEX)
GetDevicePropertyWinY = hpc.hpc_GetDevicePropertyWinY
GetDevicePropertyWinY.argtypes = [ctypes.c_int]
GetDevicePropertyWinY.restype = ctypes.c_int

# int hpc_GetDevicePropertyScreenW(int DEV_INDEX)
GetDevicePropertyScreenW = hpc.hpc_GetDevicePropertyScreenW
GetDevicePropertyScreenW.argtypes = [ctypes.c_int]
GetDevicePropertyScreenW.restype = ctypes.c_int

# int hpc_GetDevicePropertyScreenH(int DEV_INDEX)
GetDevicePropertyScreenH = hpc.hpc_GetDevicePropertyScreenH
GetDevicePropertyScreenH.argtypes = [ctypes.c_int]
GetDevicePropertyScreenH.restype = ctypes.c_int

# float hpc_GetDevicePropertyDisplayAspect(int DEV_INDEX)
GetDevicePropertyDisplayAspect = hpc.hpc_GetDevicePropertyDisplayAspect
GetDevicePropertyDisplayAspect.argtypes = [ctypes.c_int]
GetDevicePropertyDisplayAspect.restype = ctypes.c_float

# float hpc_GetDevicePropertyPitch(int DEV_INDEX)
GetDevicePropertyPitch = hpc.hpc_GetDevicePropertyPitch
GetDevicePropertyPitch.argtypes = [ctypes.c_int]
GetDevicePropertyPitch.restype = ctypes.c_float

# float hpc_GetDevicePropertyTilt(int DEV_INDEX)
GetDevicePropertyTilt = hpc.hpc_GetDevicePropertyTilt
GetDevicePropertyTilt.argtypes = [ctypes.c_int]
GetDevicePropertyTilt.restype = ctypes.c_float

# float hpc_GetDevicePropertyCenter(int DEV_INDEX)
GetDevicePropertyCenter = hpc.hpc_GetDevicePropertyCenter
GetDevicePropertyCenter.argtypes = [ctypes.c_int]
GetDevicePropertyCenter.restype = ctypes.c_float

# float hpc_GetDevicePropertySubp(int DEV_INDEX)
GetDevicePropertySubp = hpc.hpc_GetDevicePropertySubp
GetDevicePropertySubp.argtypes = [ctypes.c_int]
GetDevicePropertySubp.restype = ctypes.c_float

# float hpc_GetDevicePropertyFringe(int DEV_INDEX)
GetDevicePropertyFringe = hpc.hpc_GetDevicePropertyFringe
GetDevicePropertyFringe.argtypes = [ctypes.c_int]
GetDevicePropertyFringe.restype = ctypes.c_float

# int hpc_GetDevicePropertyRi(int DEV_INDEX)
GetDevicePropertyRi = hpc.hpc_GetDevicePropertyRi
GetDevicePropertyRi.argtypes = [ctypes.c_int]
GetDevicePropertyRi.restype = ctypes.c_int

# int hpc_GetDevicePropertyBi(int DEV_INDEX)
GetDevicePropertyBi = hpc.hpc_GetDevicePropertyBi
GetDevicePropertyBi.argtypes = [ctypes.c_int]
GetDevicePropertyBi.restype = ctypes.c_int

# int hpc_GetDevicePropertyInvView(int DEV_INDEX)
GetDevicePropertyInvView = hpc.hpc_GetDevicePropertyInvView
GetDevicePropertyInvView.argtypes = [ctypes.c_int]
GetDevicePropertyInvView.restype = ctypes.c_int



# --------------------- VIEW CONE ----------------------
# float viewCone = hpc_GetDevicePropertyFloat(int DEV_INDEX, c_char_p ViewCone)
GetDevicePropertyFloat = hpc.hpc_GetDevicePropertyFloat
GetDevicePropertyFloat.argtypes = [ctypes.c_int, ctypes.c_char_p]
GetDevicePropertyFloat.restype = ctypes.c_float
