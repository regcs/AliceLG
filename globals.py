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

	# this is only for debugging purposes
	debugging_use_dummy_device = False

	# console output: if set to true, the Alice/LG and pyLightIO logger messages
	# of all levels are printed to the console. If set to falls, only warnings and
	# errors are printed to console.
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

	# external python dependencies of the add-on
	# NOTE: The tuple has the form (import name, install name, install version, install options)
	external_dependecies = [
							('pynng', 'pynng', '', []),
							('cv2', 'opencv-python', '', ['--no-deps']),
							('pylightio', 'pylightio', '', []),
							]
	external_dependecies_installer = False

	# Blender arguments
	blender_arguments = ""
	addon_arguments = ""
	background = False

	# the pyLightIO service for display communication
	service = None

	# Lockfile
	has_lockfile = False

	# Was the frustum drawer initialized?
	FrustumInitialized = False
	FrustumRenderer = None

	# Was the hologram preview drawer initialized?
	ImageBlockRenderer = None
	ViewportBlockRenderer = None

	# The active Window and Viewport the user is currently working in
	BlenderWindow = None
	BlenderViewport = None

	# Rendering status
	RenderInvoked = False
	RenderAnimation = None

	# keymaps and mouse position
	keymap_view_3d = None
	keymap_items_view_3d_1 = None
	keymap_items_view_3d_2 = None
	keymap_image_editor = None
	keymap_items_image_editor_1 = None
	keymap_items_image_editor_2 = None
	mouse_window_x = 0
	mouse_window_y = 0
	mouse_region_x = 0
	mouse_region_y = 0


	# EXTEND PATH
	# +++++++++++++++++++++++++++++++++++++++

	# append the add-on's path to Blender's python PATH
	sys.path.insert(0, libpath)



	# ADDON CHECKS
	# +++++++++++++++++++++++++++++++++++++++
	# check if the specified module can be found in the "lib" directory
	@classmethod
	def is_installed(cls, module, debug=False):
		import importlib.machinery
		import sys
		if sys.version_info.major >= 3 or (sys.version_info.major == 3 and sys.version_info.minor >= 8):
		    from importlib.metadata import version
		else:
		    from importlib_metadata import version

		# extract info
		module_name, install_name, install_version, install_options = module

		# try to find the module in the "lib" directory
		module_spec = (importlib.machinery.PathFinder().find_spec(module_name, [cls.libpath]))
		if module_spec:
			if install_version:

				# check if the installed module version fits
				version_comparison = [ a >= b for a,b in zip(list(map(int, version(install_name).split('.'))), list(map(int, install_version.split('.'))))]
				if all(version_comparison):
					if debug: LookingGlassAddonLogger.info(" [#] Found module '%s' v.%s." % (module_name, version(install_name)))
					return True

				else:
					if debug: LookingGlassAddonLogger.info(" [#] Found module '%s' v.%s, but require version %s." % (module_name, version(install_name), install_version))
					return False
			else:
				if debug: LookingGlassAddonLogger.info(" [#] Found module '%s' v.%s." % (module_name, version(install_name)))
				return True

		if debug: LookingGlassAddonLogger.info(" [#] Could not find module '%s'." % module_name)
		return False

	# check if all defined dependencies can be found in the "lib" directory
	@classmethod
	def check_dependecies(cls, debug=False):

		# status
		found_all = True

		# are all modules in the packages list available in the "lib" directory?
		for module in cls.external_dependecies:
			if not cls.is_installed(module, debug):
				found_all = False

		return found_all

	# unload all dependencies
	@classmethod
	def unload_dependecies(cls):

		# if the addon is not in installer mode
		if not LookingGlassAddon.external_dependecies_installer:

			# are all modules in the packages list available in the "lib" directory?
			for module in cls.external_dependecies:

				# get names
				module_name, install_name, install_version, install_options = module

				# unload the module
				del sys.modules[module_name]
				#del module_name



	# LOOKING GLASS QUILT PRESETS
	# +++++++++++++++++++++++++++++++++++++++
	# set up quilt settings
	@classmethod
	def setupQuiltPresets(cls):

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

		# Low-resolution preview for faster live-view rendering
		# NOTE: Some code parts assume, that this is the last preset in the list.
		pylio.LookingGlassQuilt.formats.add({'description': "Low-resolution Preview", 'quilt_width': 1024, 'quilt_height': 1024, 'view_width': 256, 'view_height': 128, 'columns': 4, 'rows': 8, 'total_views': 32, 'hidden': True})


	# GLOBAL LIGHTFIELD VIEWPORT DATA
	# +++++++++++++++++++++++++++++++++++++++
	# the timeout value that determines when after the last depsgraph update
	# the lightfield window is updated with the selected higher resolution
	# quilt preset
	low_resolution_preview_timout = 0.4


	# GLOBAL QUILT VIEWER DATA
	# +++++++++++++++++++++++++++++++++++++++
	quiltPixels = None
	quiltViewerLightfieldImage = None
	# TODO: Is there a better way to check for color management setting changes?
	quiltViewAsRender = None
	quiltImageColorSpaceSetting = None



	# GLOBAL ADDON FUNCTIONS
	# +++++++++++++++++++++++++++++++++++++++
	# update the logger level
	@staticmethod
	def update_logger_levels(self, context):

		# update global variables for console output
		LookingGlassAddon.debugging_print_pylio_logger_all = bpy.context.preferences.addons[__package__].preferences.console_output
		LookingGlassAddon.debugging_print_internal_logger_all = bpy.context.preferences.addons[__package__].preferences.console_output

		# set logger levels according to the add-on preferences
		loggers_list = [logging.getLogger('pyLightIO'), logging.getLogger('Alice/LG')]
		for logger in loggers_list:
			for handler in logger.handlers:

				# if this is the TimedRotatingFileHandler
				if type(handler) == logging.handlers.TimedRotatingFileHandler:

					# if the level is DEBUG
					if bpy.context.preferences.addons[__package__].preferences.logger_level == '0':
						handler.setLevel(logging.DEBUG)

					# if the level is INFO
					elif bpy.context.preferences.addons[__package__].preferences.logger_level == '1':
						handler.setLevel(logging.INFO)

					# if the level is ERROR
					elif bpy.context.preferences.addons[__package__].preferences.logger_level == '2':
						handler.setLevel(logging.ERROR)


				# if this is the StreamHandler
				elif type(handler) == logging.StreamHandler:

					# update logger levels
					if bpy.context.preferences.addons[__package__].preferences.console_output:

						# if the level is DEBUG
						if bpy.context.preferences.addons[__package__].preferences.logger_level == '0':
							handler.setLevel(logging.DEBUG)

						# if the level is INFO
						elif bpy.context.preferences.addons[__package__].preferences.logger_level == '1':
							handler.setLevel(logging.INFO)

						# if the level is ERROR
						elif bpy.context.preferences.addons[__package__].preferences.logger_level == '2':
							handler.setLevel(logging.ERROR)

					else:

						# deactivate console output
						handler.setLevel(logging.CRITICAL + 1)

	# update the lightfield window to display a lightfield on the device
	@staticmethod
	def update_lightfield_window(window_mode, lightfield_image, flip_views=None, invert=None):
		''' update the lightfield image that is displayed on the current device '''
		''' window_mode = 0: Lightfield Viewport, window_mode = 1: Quilt Viewer, window_mode = -1: demo quilt '''

		# append the add-on's path to Blender's python PATH
		sys.path.insert(0, LookingGlassAddon.path)
		sys.path.insert(0, LookingGlassAddon.libpath)

		# TODO: Would be better, if from .lib import pylightio could be called,
		#		but for some reason that does not import all modules and throws
		#		"AliceLG.lib.pylio has no attribute 'lookingglass"
		import pylightio as pylio

		# update the variable for the current Looking Glass device
		device = pylio.DeviceManager.get_active()

		# if a valid device is connected
		if device:

			# if a LightfieldImage was given
			if lightfield_image:

				# VIEWPORT MODE
				##################################################################
				if window_mode == 0:

					if flip_views is None: flip_views = False
					if invert is None: invert = False

					# let the device display the image
					if device.service: device.display(lightfield_image, flip_views=flip_views, invert=invert)

				# QUILT VIEWER MODE
				##################################################################
				# if the quilt view mode is active AND an image is loaded
				elif window_mode == 1:

					if flip_views is None: flip_views = True
					if invert is None: invert = False

					# let the device display the image
					if device.service: device.display(lightfield_image, flip_views=flip_views, invert=invert)

			# if the demo quilt was requested
			elif lightfield_image is None:

				# let the device display the demo quilt
				if device.service: device.display(None)

			else:
				LookingGlassAddonLogger.error("Could not update the lightfield window. No LightfieldImage was given.")

	# STRING CACHE
	##################################################################	
	# see: https://blender.stackexchange.com/questions/299978/how-to-fix-unicodedecodeerror
	_alicelg_string_cache = {}
	@classmethod
	def intern_enum_items(cls, items):
		def intern_string(s):
			if not isinstance(s, str):
				return s
			# global _alicelg_string_cache
			if s not in cls._alicelg_string_cache:
				cls._alicelg_string_cache[s] = s
			return cls._alicelg_string_cache[s]
		return [tuple(intern_string(s) for s in item) for item in items]
