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

# MODULE DESCRIPTION:
# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# This includes all global variables that need to be accessable from all files

# ------------------ INTERNAL MODULES --------------------
from .globals import *

# ------------------- EXTERNAL MODULES -------------------
import bpy
import sys, os, json
from bpy.props import FloatProperty, PointerProperty
from bpy.app.handlers import persistent

# ---------------- GLOBAL ADDON LOGGER -------------------
import logging
LookingGlassAddonLogger = logging.getLogger('Alice/LG')


# ------------ GLOBAL VARIABLES ---------------
# CLASS USED FOR THE IMPORTANT GLOBAL VARIABLES AND LISTS IN THIS ADDON
class LookingGlassAddon:

	# debugging variables
	debugging_use_dummy_device = False
	debugging_print_pylio_logger_all = False
	debugging_print_internal_logger_all = False

	# addon name
	name = None

	# path to the addon directory
	path = bpy.path.abspath(os.path.dirname(os.path.realpath(__file__)))
	tmp_path = bpy.path.abspath(path + "/tmp/")
	libpath = bpy.path.abspath(path + "/lib/")
	logpath = bpy.path.abspath(path + "/logs/")
	presetpath = bpy.path.abspath(path + "/presets/")

	# python dependencies of the add-on present?
	python_dependecies = False
	show_preferences = True

	# the pyLightIO service for display communication
	service = None

	# Lockfile
	has_lockfile = False

	# Was the modal operator for the frustum initialized?
	FrustumInitialized = False
	FrustumDrawHandler = None

	# The active Window and Viewport the user is currently working in
	BlenderWindow = None
	BlenderViewport = None

	# Rendering status
	RenderInvoked = False
	RenderAnimation = None

	# LOOKING GLASS QUILT PRESETS
	# +++++++++++++++++++++++++++++++++++++++
	# set up quilt settings
	@classmethod
	def setupQuiltPresets(cls):

		# append the add-on's path to Blender's python PATH
		sys.path.append(LookingGlassAddon.path)
		sys.path.append(LookingGlassAddon.libpath)

		# TODO: Would be better, if from .lib import pylightio could be called,
		#		but for some reason that does not import all modules and throws
		#		"AliceLG.lib.pylio has no attribute 'lookingglass"
		import pylightio as pylio

		# read the user-defined quilt presets from the add-on directory
		# and add them to the pylio quilt presets
		for file_name in sorted(os.listdir(cls.presetpath)):
			if file_name.endswith('.preset'):
				with open(cls.presetpath + file_name) as preset_file:
					pylio.LookingGlassQuilt.formats.add(json.load(preset_file))



	# GLOBAL QUILT VIEWER DATA
	# +++++++++++++++++++++++++++++++++++++++
	quiltPixels = None
	quiltViewerLightfieldImage = None
	# TODO: Is there a better way to check for color management setting changes?
	quiltViewAsRender = None
	quiltImageColorSpaceSetting = None



	# GLOBAL ADDON FUNCTIONS
	# +++++++++++++++++++++++++++++++++++++++
	# update the lightfield window to display a lightfield on the device
	@staticmethod
	def update_lightfield_window(render_mode, lightfield_image, flip_views=None, invert=None):
		''' update the lightfield image that is displayed on the current device '''
		''' render_mode = 0: Lightfield Viewport, render_mode = 1: Quilt Viewer, render_mode = -1: demo quilt '''

		# append the add-on's path to Blender's python PATH
		sys.path.append(LookingGlassAddon.path)
		sys.path.append(LookingGlassAddon.libpath)

		# TODO: Would be better, if from .lib import pylightio could be called,
		#		but for some reason that does not import all modules and throws
		#		"AliceLG.lib.pylio has no attribute 'lookingglass"
		import pylightio as pylio

		# update the variable for the current Looking Glass device
		device = pylio.DeviceManager.get_active()
		if device:
			# if a LightfieldImage was given
			if lightfield_image:

				# VIEWPORT MODE
				##################################################################
				if render_mode == 0:

					# NOTE: We flip the views in Y direction, because the OpenGL
					#		and PIL definition of the image origin are different.
					#		(i.e., top-left vs. bottom-left)
					if flip_views == None: flip_views = True
					if invert == None: invert = False

					# let the device display the image
					device.display(lightfield_image, flip_views=flip_views, invert=invert)

				# QUILT VIEWER MODE
				##################################################################
				# if the quilt view mode is active AND an image is loaded
				elif render_mode == 1:

					# NOTE: We DON'T flip the views in Y direction, because the Blender
					#		and PIL definition of the image origin are the same.
					# TODO: CHECK IF THE NOTE IS TRUE. HAD SOME WEIRD THINGS GOING ON.
					if flip_views == None: flip_views = False
					if invert == None: invert = False

					# let the device display the image
					device.display(lightfield_image, flip_views=flip_views, invert=invert)

			# if the demo quilt was requested
			elif lightfield_image == None and render_mode == -1:

				# let the device display the demo quilt
				device.display(None)

			else:
				LookingGlassAddonLogger.error("Could not update the lightfield window. No LightfieldImage was given.")


	# GLOBAL ADDON PROPERTIES
	# +++++++++++++++++++++++++++++++++++++++
	# @property
	# def updateLiveViewer(self):
	# 	return __updateLiveViewer
	#
	# @updateLiveViewer.setter
	# def updateLiveViewer(self, state):
	# 	__updateLiveViewer = state
