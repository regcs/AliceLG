# ##### BEGIN GPL LICENSE BLOCK #####
#
#  Copyright © 2021 Christian Stolze
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

import bpy
import os

# ------------ GLOBAL VARIABLES ---------------
# CLASS USED FOR THE IMPORTANT GLOBAL VARIABLES AND LISTS IN THIS ADDON
class LookingGlassAddon:

	# addon name
	name = None

	# path to the addon directory
	path = bpy.path.abspath(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
	tmp_path = bpy.path.abspath(os.path.dirname(os.path.dirname(os.path.realpath(__file__))) + "/tmp/")
	libpath = bpy.path.abspath(os.path.dirname(os.path.dirname(os.path.realpath(__file__))) + "/lib/")

	# python dependencies of the add-on present?
	python_dependecies = False
	show_preferences = True

	# Was the connection to the holoplay service successfully initialized?
	HoloPlayService = False
	service = None

	# List of dictionaries with one dictionary for each connected Looking Glass
	# Each Dictionary contains all available data on the Looking Glass (including calibrations data)
	deviceList = []

	# Lockfile
	has_lockfile = False

	# List of windows on Linux
	LinuxWindowList = []

	# Was the operator for the lightfield window invoked?
	LightfieldWindowInitialized = None
	LightfieldWindowInvoker = None
	LightfieldWindowIsFullscreen = False

	# Was the modal operator for the frustum initialized?
	FrustumInitialized = False
	FrustumDrawHandler = None

	# The Window object representing the Blender main window and the Space object, which are used for the lightfield rendering
	lightfieldWindow = None
	lightfieldRegion = None
	lightfieldArea = None
	lightfieldSpace = None

	# The active Window and Viewport the user is currently working in
	BlenderWindow = None
	BlenderViewport = None

	# Rendering status
	RenderInvoked = False
	RenderAnimation = None

	# SHADER SOURCES
	# +++++++++++++++++++++++++++++++++++++++
	lightfieldVertexShaderSource = None
	lightfieldFragmentShaderSource = None



	# GLOBAL LIST OF QUILT Settings
	# +++++++++++++++++++++++++++++++++++++++
	# define a list
	qs = []

	# set up quilt settings
	def setupQuiltPresets():

		# there are 5 presets to choose from:
		# - portrait standard settings
		LookingGlassAddon.qs.append({
				"width": 3360,
				"height": 3360,
				"columns": 8,
				"rows": 6,
				"totalViews": 48,
				"quiltOffscreen": None,
				"viewOffscreens": []
				})

		# - portrait settings with many views
		LookingGlassAddon.qs.append({
				"width": 4026,
				"height": 4096,
				"columns": 11,
				"rows": 8,
				"totalViews": 88,
				"quiltOffscreen": None,
				"viewOffscreens": []
				})

		# - portrait settings with many views
		LookingGlassAddon.qs.append({
				"width": 4225,
				"height": 4095,
				"columns": 13,
				"rows": 7,
				"totalViews": 91,
				"quiltOffscreen": None,
				"viewOffscreens": []
				})

		# - portrait settings with many views
		LookingGlassAddon.qs.append({
				"width": 4224,
				"height": 4096,
				"columns": 12,
				"rows": 8,
				"totalViews": 96,
				"quiltOffscreen": None,
				"viewOffscreens": []
				})

		# - portrait settings with many views
		LookingGlassAddon.qs.append({
				"width": 4224,
				"height": 4230,
				"columns": 12,
				"rows": 9,
				"totalViews": 108,
				"quiltOffscreen": None,
				"viewOffscreens": []
				})

		# - standard settings
		LookingGlassAddon.qs.append({
				"width": 2048,
				"height": 2048,
				"columns": 4,
				"rows": 8,
				"totalViews": 32,
				"quiltOffscreen": None,
				"viewOffscreens": []
				})

		# - high resolution settings (4k)
		LookingGlassAddon.qs.append({
				"width": 4095,
				"height": 4095,
				"columns": 5,
				"rows": 9,
				"totalViews": 45,
				"quiltOffscreen": None,
				"viewOffscreens": []
				})

		# - 8k settings
		LookingGlassAddon.qs.append({
				"width": 4096 * 2,
				"height": 4096 * 2,
				"columns": 5,
				"rows": 9,
				"totalViews": 45,
				"quiltOffscreen": None,
				"viewOffscreens": []
				})

		# - LOW RESOLUTION FOR PREVIEW
		LookingGlassAddon.qs.append({
				"width": 512,
				"height": 512,
				"columns": 4,
				"rows": 8,
				"totalViews": 32,
				"quiltOffscreen": None,
				"viewOffscreens": []
				})

		# iterate through all presets
		for i in range(0, len(LookingGlassAddon.qs), 1):

			# calculate viewWidth and viewHeight
			LookingGlassAddon.qs[i]["viewWidth"] = int(round(LookingGlassAddon.qs[i]["width"] / LookingGlassAddon.qs[i]["columns"]))
			LookingGlassAddon.qs[i]["viewHeight"] = int(round(LookingGlassAddon.qs[i]["height"] / LookingGlassAddon.qs[i]["rows"]))


	# GLOBAL QUILT VIEWER DATA
	# +++++++++++++++++++++++++++++++++++++++
	quiltPixels = None
	quiltTextureBuffer = None
	quiltTextureID = None
	# TODO: Is there a better way to check for color management setting changes?
	quiltViewAsRender = None
	quiltImageColorSpaceSetting = None
