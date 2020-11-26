1# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# ------------ LOAD HOLOPLAY CORE WRAPPER ---------------
# CLASS USED FOR THE IMPORTANT GLOBAL VARIABLES AND LISTS IN THIS ADDON
class LookingGlassAddon:

	# Was the connection to the holoplay service successfully initialized?
	HoloPlayService = False

	# List of dictionaries with one dictionary for each connected Looking Glass
	# Each Dictionary contains all available data on the Looking Glass (including calibrations data)
	deviceList = []

	# Was the modal operator for the frustum initialized?
	FrustumInitialized = False

	# The Window object representing the Blender main window and the Space object, which are used for the lightfield rendering
	lightfieldWindow = None
	lightfieldSpace = None

	# The active Window and Viewport the user is currently working in
	BlenderWindow = None
	BlenderViewport = None
