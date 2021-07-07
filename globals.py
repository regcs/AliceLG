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
import sys, os, json


# ------------ GLOBAL VARIABLES ---------------
# CLASS USED FOR THE IMPORTANT GLOBAL VARIABLES AND LISTS IN THIS ADDON
class LookingGlassAddon:

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

	# the scene from which the lightfield viewport was invoked
	LightfieldWindowInvoker = None

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
		sys.path.append(cls.path)
		sys.path.append(cls.libpath)

		# TODO: Would be better, if from .lib import pylightio could be called,
		#		but for some reason that does not import all modules and throws
		#		"AliceLG.lib.pylio has no attribute 'lookingglass'"
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
	quiltLightfieldImage = None
	# TODO: Is there a better way to check for color management setting changes?
	quiltViewAsRender = None
	quiltImageColorSpaceSetting = None
