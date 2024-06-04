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

# -------------------- DEFINE ADDON ----------------------
bl_info = {
	"name": "Alice/LG",
	"author": "Christian Stolze",
	"version": (2, 3, 0),
	"blender": (2, 93, 6),
	"location": "View3D > Looking Glass Tab",
	"description": "Alice/LG takes your artworks through the Looking Glass (lightfield displays)",
	"category": "View",
	"warning": "",
	"doc_url": "https://github.com/regcs/AliceLG/blob/master/README.md",
	"tracker_url": "https://github.com/regcs/AliceLG/issues"
}


########################################################
#              Prepare Add-on Initialization
########################################################

# Load System Modules
# ++++++++++++++++++++++++++++++++++++++++++++++++++++++
import importlib
import sys, platform


# Load Globals
# ++++++++++++++++++++++++++++++++++++++++++++++++++++++
# required for proper reloading of the addon by using F8
try:

	importlib.reload(globals)

except:

	from .globals import *

# Debugging Settings
# ++++++++++++++++++++++++++++++++++++++++++++++++++++++
# this is only for debugging purposes
LookingGlassAddon.debugging_use_dummy_device = False

# console output: if set to true, the Alice/LG and pyLightIO logger messages
# of all levels are printed to the console. If set to falls, only warnings and
# errors are printed to console.
LookingGlassAddon.debugging_print_pylio_logger_all = False
LookingGlassAddon.debugging_print_internal_logger_all = False



# --------------------- LOGGER -----------------------
import logging, logging.handlers

# log uncaught exceptions
# +++++++++++++++++++++++++++++++++++++++++++++
# define system exception hook for logging
def log_exhook(exc_type, exc_value, exc_traceback):

	# log that an unhandled exception occured in Alice/LG's log file
	LookingGlassAddonLogger.critical("An unhandled error occured. Here is the traceback:\n", exc_info=(exc_type, exc_value, exc_traceback))
	
	# then continue with the system behavior
	sys.__excepthook__(exc_type, exc_value, exc_traceback)

# overwrite the excepthook
sys.excepthook = log_exhook

# log file names
# +++++++++++++++++++++++++++++++++++++++++++++
# this function is by @ranrande from stackoverflow:
# https://stackoverflow.com/a/67213458
def logfile_namer(default_name):
	if len(default_name.split(".")) == 2:
		base_filename, ext = default_name.split(".")
		return f"{base_filename}.{ext}"

	elif len(default_name.split(".")) == 3:
		base_filename, ext, date = default_name.split(".")
		return f"{base_filename}.{date}.{ext}"

# logger for pyLightIO
# +++++++++++++++++++++++++++++++++++++++++++++
# NOTE: This is just to get the logger messages invoked by pyLightIO.
#		To log messages for Alice/LG use the logger defined below.
# create logger
logger = logging.getLogger('pyLightIO')
logger.setLevel(logging.DEBUG)

# create console handler and set level to WARNING
console_handler = logging.StreamHandler()

if LookingGlassAddon.debugging_print_pylio_logger_all == True: console_handler.setLevel(logging.DEBUG)
elif LookingGlassAddon.debugging_print_pylio_logger_all == False: console_handler.setLevel(logging.WARNING)

# create timed rotating file handler and set level to debug: Create a new logfile every day and keep the last seven days
logfile_handler = logging.handlers.TimedRotatingFileHandler(LookingGlassAddon.logpath + 'pylightio.log', when="D", interval=1, backupCount=7, encoding='utf-8')
logfile_handler.setLevel(logging.INFO)
logfile_handler.namer = logfile_namer

# create formatter
console_formatter = logging.Formatter('[%(name)s] [%(levelname)s] %(asctime)s - %(message)s', datefmt='%m/%d/%Y %H:%M:%S')
logfile_formatter = logging.Formatter('[%(levelname)s] %(asctime)s - %(message)s', datefmt='%m/%d/%Y %H:%M:%S')

# add formatter to ch
console_handler.setFormatter(console_formatter)
logfile_handler.setFormatter(logfile_formatter)

# add console handler to logger
logger.addHandler(console_handler)
logger.addHandler(logfile_handler)

# logger for Alice/LG
# +++++++++++++++++++++++++++++++++++++++++++++
# NOTE: This is the addon's own logger. Use it to log messages on different levels.
# create logger
LookingGlassAddonLogger = logging.getLogger('Alice/LG')
LookingGlassAddonLogger.setLevel(logging.DEBUG)

# create console handler and set level to WARNING
console_handler = logging.StreamHandler()

if LookingGlassAddon.debugging_print_internal_logger_all == True: console_handler.setLevel(logging.DEBUG)
if LookingGlassAddon.debugging_print_internal_logger_all == False: console_handler.setLevel(logging.INFO)

# create timed rotating file handler and set level to debug: Create a new logfile every day and keep the last seven days
logfile_handler = logging.handlers.TimedRotatingFileHandler(LookingGlassAddon.logpath + 'alice-lg.log', when="D", interval=1, backupCount=7, encoding='utf-8')
logfile_handler.setLevel(logging.INFO)
logfile_handler.namer = logfile_namer

# create formatter
console_formatter = logging.Formatter('[%(name)s] [%(levelname)s] %(asctime)s - %(message)s', datefmt='%m/%d/%Y %H:%M:%S')
logfile_formatter = logging.Formatter('[%(levelname)s] %(asctime)s - %(message)s', datefmt='%m/%d/%Y %H:%M:%S')

# add formatter to ch
console_handler.setFormatter(console_formatter)
logfile_handler.setFormatter(logfile_formatter)

# add console handler to logger
LookingGlassAddonLogger.addHandler(console_handler)
LookingGlassAddonLogger.addHandler(logfile_handler)



# ------------- LOAD INTERNAL MODULES ----------------
# append the add-on's path to Blender's python PATH
sys.path.insert(0, LookingGlassAddon.path)
sys.path.insert(0, LookingGlassAddon.libpath)






########################################################
#                  Add-on Initialization
########################################################
import bpy
from bpy.types import AddonPreferences
from bpy.app.handlers import persistent

# define add-on name for display purposes
LookingGlassAddon.name = bl_info['name'] + " v" + '.'.join(str(v) for v in bl_info['version'])

# log a info message
LookingGlassAddonLogger.info("----------------------------------------------")
LookingGlassAddonLogger.info("Initializing '%s' ..." % LookingGlassAddon.name)
LookingGlassAddonLogger.info(" [#] Add-on path: %s" % LookingGlassAddon.path)

# Check Blender Version
# +++++++++++++++++++++++++++++++++++++++++++++
# check, if a supported version of Blender is executed
if bpy.app.version < bl_info['blender']:
	raise Exception("This version of Blender is not supported by " + bl_info['name'] + ". Please use v" + '.'.join(str(v) for v in bl_info['blender']) + " or higher.")


# Load Internal Modules
# +++++++++++++++++++++++++++++++++++++++++++++
# if NOT all the dependenceis are satisfied, debug will produce log messages.
if not LookingGlassAddon.check_dependecies(debug=LookingGlassAddon.debugging_print_internal_logger_all):

	# reload/import all preferences' related code
	try:

		importlib.reload(preferences)

	except:

		from .preferences import *

else:

	try:
		# reload all preferences' related code
		importlib.reload(preferences)

		# reload the modal operators for the viewport & quilt rendering
		importlib.reload(lightfield_viewport)
		importlib.reload(lightfield_render)

		# reload all UI related code
		importlib.reload(ui)

	except:

		# import all preferences' related code
		from .preferences import *

		# import the modal operators for the viewport & quilt rendering
		from .lightfield_viewport import *
		from .lightfield_render import *

		# import all UI related code
		from .ui import *





# ----------------- ADDON INITIALIZATION --------------------
@persistent
def LookingGlassAddonInitHandler(dummy1, dummy2):

	# update the logger levels according to the preferences
	LookingGlassAddon.update_logger_levels(None, None)

	# if NOT all dependencies are satisfied
	if not LookingGlassAddon.check_dependecies():

		# check if Blender is run in background mode
		if LookingGlassAddon.background:

			# if the dependencies shall be installed
			if '--alicelg-install' in LookingGlassAddon.addon_arguments:
				bpy.ops.lookingglass.install_dependencies('EXEC_DEFAULT') 
		
		else:

			# show the preference pane
			bpy.ops.preferences.addon_show(module=__package__)

	else:

		# ------------ BPY EXTENSIONS ---------------
		# EXTENSION OF BPY TYPES BY USEFULL PROPERTIES
		# Addon settings
		bpy.types.WindowManager.addon_settings = bpy.props.PointerProperty(type=LookingGlassAddonSettingsWM)
		bpy.types.Scene.addon_settings = bpy.props.PointerProperty(type=LookingGlassAddonSettingsScene)

		# Camera settings
		bpy.types.Camera.is_lightfield = bpy.props.BoolProperty(default=False, options=set(['HIDDEN']))

		# ------------ INITIALIZATION ---------------
		# check if lockfile exists and set status variable
		LookingGlassAddon.has_lockfile = os.path.exists(bpy.path.abspath(LookingGlassAddon.tmp_path + os.path.basename(bpy.data.filepath) + ".lock"))

		# if the loaded file has a lockfile
		if LookingGlassAddon.has_lockfile:

			# initialize the RenderSettings
			# NOTE: This  loads the last render settings from the lockfile
			RenderSettings(bpy.context.scene, False, LookingGlassAddon.has_lockfile, (bpy.context.preferences.addons[__package__].preferences.camera_mode == '1'), blocking=LookingGlassAddon.background)

		else:

			# get active device
			device = pylio.DeviceManager.get_active()

			# try to find the suitable default quilt preset
			if device: preset = pylio.LookingGlassQuilt.formats.find(device.default_quilt_width, device.default_quilt_height, device.default_quilt_rows, device.default_quilt_columns)

			# then update the selected quilt preset from the device's default quilt
			if device and preset:
				bpy.context.scene.addon_settings.quiltPreset = str(preset)
				bpy.context.scene.addon_settings.render_quilt_preset = str(preset)

			elif not (device and preset):

				# fallback solution, if the default quilt is not found:
				# We use the Looking Glass Go standard quilt (48 views)
				bpy.context.scene.addon_settings.quiltPreset = "5"
				bpy.context.scene.addon_settings.render_quilt_preset = "5"

		# check if Blender is run in background mode
		if LookingGlassAddon.background:

			# if the current blender session has a file
			if bpy.data.filepath != "":

				# if the a quilt shall be rendered
				if '--alicelg-render' in LookingGlassAddon.addon_arguments:
					bpy.ops.render.quilt('EXEC_DEFAULT', use_multiview=True, blocking=True)

				# if the a quilt shall be rendered
				elif '--alicelg-render-anim' in LookingGlassAddon.addon_arguments:
					bpy.ops.render.quilt('EXEC_DEFAULT', animation=True, use_multiview=True, blocking=True)

		else:

			# stop and delete old renderers, if they still exist (e.g., after loading a new file)
			if LookingGlassAddon.FrustumRenderer is not None: 
				LookingGlassAddon.FrustumRenderer.stop()
				LookingGlassAddon.FrustumRenderer = None
			if LookingGlassAddon.ImageBlockRenderer is not None: 
				LookingGlassAddon.ImageBlockRenderer.stop()
				LookingGlassAddon.ImageBlockRenderer = None
			if LookingGlassAddon.ViewportBlockRenderer is not None:
				LookingGlassAddon.ViewportBlockRenderer.stop()
				LookingGlassAddon.ViewportBlockRenderer = None

			# create and start the frustum and the block renderer
			LookingGlassAddon.FrustumRenderer = FrustumRenderer()
			LookingGlassAddon.ImageBlockRenderer = BlockRenderer()
			LookingGlassAddon.ViewportBlockRenderer = BlockRenderer()


            # start the renderers
			LookingGlassAddon.FrustumRenderer.start(bpy.context)

			# get the active window
			LookingGlassAddon.BlenderWindow = bpy.context.window

			# if the lightfield window was active
			if bpy.context.window_manager.addon_settings.ShowLightfieldWindow == True:

				# for each scene in the file
				for scene in bpy.context.blend_data.scenes:

					# set the lightfield window button state to 'deactivated'
				    window_manager.addon_settings.ShowLightfieldWindow = False

			# if no Looking Glass was detected AND debug mode is not activated
			if not pylio.DeviceManager.count() and not LookingGlassAddon.debugging_use_dummy_device:

				# set the "use device" checkbox in quilt setup to False
				# (because there is no device we could take the settings from)
				bpy.context.scene.addon_settings.render_use_device = False

			# update the Looking Glass camera synchronization
			# NOTE: Looks weird, but is a way to trigger update function of the property, 
			#       which sets the app handlers if required. If not done, app handlers may stay
			#       inactive when a file was loaded although they should be active.
			bpy.context.scene.addon_settings.toggleCameraSync = bpy.context.scene.addon_settings.toggleCameraSync




# ---------- ADDON INITIALIZATION & CLEANUP -------------
def register():

	# extract the arguments Blender was called with
	try:
		index = sys.argv.index("--") + 1
	except ValueError:
		index = len(sys.argv)

	# separate the passed arguments into Blender arguments (before "--") and
	# add-on arguments (after "--")
	LookingGlassAddon.blender_arguments = sys.argv[:index]
	LookingGlassAddon.addon_arguments = sys.argv[index:]

	# check if Blender is run in background mode
	if ('--background' in LookingGlassAddon.blender_arguments or '-b' in LookingGlassAddon.blender_arguments):

		# update the corresponding status variable
		LookingGlassAddon.background = True

	# if NOT all dependencies are satisfied
	if not LookingGlassAddon.check_dependecies():

		# register the preferences operators
		bpy.utils.register_class(LOOKINGGLASS_OT_install_dependencies)

		# register the preferences panels
		bpy.utils.register_class(LOOKINGGLASS_PT_install_dependencies)

		# log info
		LookingGlassAddonLogger.info(" [#] Missing dependencies. Please install them in the preference pane or using the 'blender -- --alicelg-install' command line call.")

		# run initialization helper function as app handler
		# NOTE: this is needed to run certain modal operators of the addon on startup
		#		or when a new file is loaded
		bpy.app.handlers.load_post.append(LookingGlassAddonInitHandler)

		# for the addon unregistering we need to remember that we started
		# in the dependency installer mode
		LookingGlassAddon.external_dependecies_installer = True

	else:

		# register all basic operators of the addon
		bpy.utils.register_class(LookingGlassAddonSettingsWM)
		bpy.utils.register_class(LookingGlassAddonSettingsScene)
		bpy.utils.register_class(LOOKINGGLASS_OT_refresh_display_list)
		bpy.utils.register_class(LOOKINGGLASS_OT_lightfield_window)
		bpy.utils.register_class(LOOKINGGLASS_OT_refresh_lightfield)
		bpy.utils.register_class(LOOKINGGLASS_OT_blender_viewport_assign)
		bpy.utils.register_class(LOOKINGGLASS_OT_add_camera)

		# Looking Glass quilt rendering
		bpy.utils.register_class(LOOKINGGLASS_OT_render_quilt)

		# Looking Glass viewport
		bpy.utils.register_class(LOOKINGGLASS_OT_render_viewport)
		bpy.utils.register_class(BlockRenderer.LOOKINGGLASS_OT_update_block_renderer)

		keyconfigs_addon = bpy.context.window_manager.keyconfigs.addon
		if keyconfigs_addon:
			# 3D Viewport
			LookingGlassAddon.keymap_view_3d = keyconfigs_addon.keymaps.new(name="3D View", space_type='VIEW_3D')
			LookingGlassAddon.keymap_items_view_3d_1 = LookingGlassAddon.keymap_view_3d.keymap_items.new("wm.update_block_renderer", 'MOUSEMOVE', 'ANY')
			LookingGlassAddon.keymap_items_view_3d_2 = LookingGlassAddon.keymap_view_3d.keymap_items.new("wm.update_block_renderer", 'LEFTMOUSE', 'ANY')
			# Image editor
			LookingGlassAddon.keymap_image_editor = keyconfigs_addon.keymaps.new(name="Image", space_type='IMAGE_EDITOR')
			LookingGlassAddon.keymap_items_image_editor_1 = LookingGlassAddon.keymap_image_editor.keymap_items.new("wm.update_block_renderer", 'MOUSEMOVE', 'ANY')
			LookingGlassAddon.keymap_items_image_editor_2 = LookingGlassAddon.keymap_image_editor.keymap_items.new("wm.update_block_renderer", 'LEFTMOUSE', 'ANY')

		# UI elements
		# add-on preferences
		bpy.utils.register_class(LOOKINGGLASS_PT_preferences)
		# addon panels
		bpy.utils.register_class(LOOKINGGLASS_PT_panel_general)
		bpy.utils.register_class(LOOKINGGLASS_PT_panel_camera)
		bpy.utils.register_class(LOOKINGGLASS_PT_panel_render)
		bpy.utils.register_class(LOOKINGGLASS_PT_panel_lightfield)
		bpy.utils.register_class(LOOKINGGLASS_PT_panel_overlays_shading)
        # addon header buttons: 3D viewport
		bpy.utils.register_class(LOOKINGGLASS_PT_panel_blocks_viewport_options)
		bpy.utils.register_class(LOOKINGGLASS_HT_button_viewport_blocks)
		bpy.types.VIEW3D_HT_header.append(LOOKINGGLASS_HT_button_viewport_blocks.draw_item)
        # addon header buttons: image editor
		bpy.utils.register_class(LOOKINGGLASS_PT_panel_blocks_imageeditor_options)
		bpy.utils.register_class(LOOKINGGLASS_HT_button_imageeditor_blocks)
		bpy.types.IMAGE_HT_header.append(LOOKINGGLASS_HT_button_imageeditor_blocks.draw_item)

		# log info
		LookingGlassAddonLogger.info(" [#] Registered add-on operators in Blender.")

		# setup the quilt presets
		LookingGlassAddon.setupQuiltPresets()

		# run initialization helper function as app handler
		# NOTE: this is needed to run certain modal operators of the addon on startup
		#		or when a new file is loaded
		bpy.app.handlers.load_post.append(LookingGlassAddonInitHandler)

		# log info
		LookingGlassAddonLogger.info(" [#] Done.")

		# log info
		LookingGlassAddonLogger.info("Connecting to Looking Glass Bridge ...")

		# create a service using "Looking Glass Bridge" backend
		LookingGlassAddon.service = pylio.ServiceManager.add(pylio.lookingglass.services.LookingGlassBridge, client_name = LookingGlassAddon.name)

		# if a service was added
		if type(LookingGlassAddon.service) == pylio.lookingglass.services.LookingGlassBridge:

			# if the service is ready
			if LookingGlassAddon.service.is_ready():

				# log info
				LookingGlassAddonLogger.info(" [#] Connected to Looking Glass Bridge version: %s" % LookingGlassAddon.service.get_version())

			else:

				# log info
				LookingGlassAddonLogger.info(" [#] Connection failed.")

			# make the device manager use the created service instance
			pylio.DeviceManager.set_service(LookingGlassAddon.service)

			# create a set of emulated devices
			# NOTE: This automatically creates an emulated Looking Glass for
			#		each device type that is defined in pyLightIO.
			pylio.DeviceManager.add_emulated()

		# if the service is ready OR dummy devices shall be added
		if LookingGlassAddon.service.is_ready() or LookingGlassAddon.debugging_use_dummy_device:

			# refresh the list of connected devices using the active pylio service
			pylio.DeviceManager.refresh()

			# if device are connected, make the first one the active one
			if LookingGlassAddon.debugging_use_dummy_device: pylio.DeviceManager.set_active(pylio.DeviceManager.to_list(None, None)[0].id)
			if pylio.DeviceManager.count(): pylio.DeviceManager.set_active(pylio.DeviceManager.to_list()[0].id)


			# # prepare the error string from the error code
			# if (errco == hpc.client_error.CLIERR_NOSERVICE.value):
			# 	errstr = "Looking Glass Bridge not running"
			#
			# elif (errco == hpc.client_error.CLIERR_SERIALIZEERR.value):
			# 	errstr = "Client message could not be serialized"
			#
			# elif (errco == hpc.client_error.CLIERR_VERSIONERR.value):
			# 	errstr = "Incompatible version of Looking Glass Bridge";
			#
			# elif (errco == hpc.client_error.CLIERR_PIPEERROR.value):
			# 	errstr = "Interprocess pipe broken"
			#
			# elif (errco == hpc.client_error.CLIERR_SENDTIMEOUT.value):
			# 	errstr = "Interprocess pipe send timeout"
			#
			# elif (errco == hpc.client_error.CLIERR_RECVTIMEOUT.value):
			# 	errstr = "Interprocess pipe receive timeout"
			#
			# else:
			# 	errstr = "Unknown error";


def unregister():

	# if the a service for display communication is active
	if LookingGlassAddon.service:

		# Unregister at Looking Glass Bridge
		pylio.ServiceManager.remove(LookingGlassAddon.service)

	# log info
	LookingGlassAddonLogger.info("Unregister the addon:")

	# log info
	LookingGlassAddonLogger.info(" [#] Stopping frustum and block renderers.")

	# stop the frustum and block renderers
	if LookingGlassAddon.FrustumRenderer: LookingGlassAddon.FrustumRenderer.stop()
	if LookingGlassAddon.ImageBlockRenderer: LookingGlassAddon.ImageBlockRenderer.stop()
	if LookingGlassAddon.ViewportBlockRenderer: LookingGlassAddon.ViewportBlockRenderer.stop()

	# log info
	LookingGlassAddonLogger.info(" [#] Removing all registered classes.")

	# if NOT all dependencies are satisfied
	if not LookingGlassAddon.check_dependecies() or LookingGlassAddon.external_dependecies_installer:

		# unregister only the preferences
		if hasattr(bpy.types, "LOOKINGGLASS_PT_install_dependencies"): bpy.utils.unregister_class(LOOKINGGLASS_PT_install_dependencies)
		if hasattr(bpy.types, "LOOKINGGLASS_OT_install_dependencies"): bpy.utils.unregister_class(LOOKINGGLASS_OT_install_dependencies)
		if hasattr(bpy.types, "LOOKINGGLASS_PT_preferences"): bpy.utils.unregister_class(LOOKINGGLASS_PT_preferences)

		# remove initialization helper app handler
		bpy.app.handlers.load_post.remove(LookingGlassAddonInitHandler)

	else:

		# remove initialization helper app handler
		bpy.app.handlers.load_post.remove(LookingGlassAddonInitHandler)

		# unregister all classes of the addon
		bpy.utils.unregister_class(LookingGlassAddonSettingsWM)
		bpy.utils.unregister_class(LookingGlassAddonSettingsScene)
		bpy.utils.unregister_class(LOOKINGGLASS_OT_refresh_display_list)
		bpy.utils.unregister_class(LOOKINGGLASS_OT_refresh_lightfield)
		bpy.utils.unregister_class(LOOKINGGLASS_OT_lightfield_window)
		bpy.utils.unregister_class(LOOKINGGLASS_OT_blender_viewport_assign)
		bpy.utils.unregister_class(LOOKINGGLASS_OT_add_camera)

		# Looking Glass quilt rendering
		bpy.utils.unregister_class(LOOKINGGLASS_OT_render_quilt)

		# remove the keymap
		keyconfigs_addon = bpy.context.window_manager.keyconfigs.addon
		if keyconfigs_addon:
			# 3D Viewport
			if LookingGlassAddon.keymap_view_3d: LookingGlassAddon.keymap_view_3d.keymap_items.remove(LookingGlassAddon.keymap_items_view_3d_2)
			if LookingGlassAddon.keymap_view_3d: LookingGlassAddon.keymap_view_3d.keymap_items.remove(LookingGlassAddon.keymap_items_view_3d_1)
			if LookingGlassAddon.keymap_view_3d: keyconfigs_addon.keymaps.remove(LookingGlassAddon.keymap_view_3d)
			# Image editor
			if LookingGlassAddon.keymap_image_editor: LookingGlassAddon.keymap_image_editor.keymap_items.remove(LookingGlassAddon.keymap_items_image_editor_2)
			if LookingGlassAddon.keymap_image_editor: LookingGlassAddon.keymap_image_editor.keymap_items.remove(LookingGlassAddon.keymap_items_image_editor_1)
			if LookingGlassAddon.keymap_image_editor: keyconfigs_addon.keymaps.remove(LookingGlassAddon.keymap_image_editor)

		# Looking Glass viewport
		bpy.utils.unregister_class(BlockRenderer.LOOKINGGLASS_OT_update_block_renderer)
		bpy.utils.unregister_class(LOOKINGGLASS_OT_render_viewport)

		# UI elements
        # addon header buttons
		bpy.types.IMAGE_HT_header.remove(LOOKINGGLASS_HT_button_imageeditor_blocks.draw_item)
		bpy.types.VIEW3D_HT_header.remove(LOOKINGGLASS_HT_button_viewport_blocks.draw_item)
		if hasattr(bpy.types, "LOOKINGGLASS_HT_button_viewport_blocks"): bpy.utils.unregister_class(LOOKINGGLASS_HT_button_viewport_blocks)
		if hasattr(bpy.types, "LOOKINGGLASS_HT_button_imageeditor_blocks"): bpy.utils.unregister_class(LOOKINGGLASS_HT_button_imageeditor_blocks)
		if hasattr(bpy.types, "LOOKINGGLASS_PT_panel_blocks_viewport_options"): bpy.utils.unregister_class(LOOKINGGLASS_PT_panel_blocks_viewport_options)
		if hasattr(bpy.types, "LOOKINGGLASS_PT_panel_blocks_imageeditor_options"): bpy.utils.unregister_class(LOOKINGGLASS_PT_panel_blocks_imageeditor_options)
        # addon panels
		if hasattr(bpy.types, "LOOKINGGLASS_PT_panel_general"): bpy.utils.unregister_class(LOOKINGGLASS_PT_panel_general)
		if hasattr(bpy.types, "LOOKINGGLASS_PT_panel_camera"): bpy.utils.unregister_class(LOOKINGGLASS_PT_panel_camera)
		if hasattr(bpy.types, "LOOKINGGLASS_PT_panel_render"): bpy.utils.unregister_class(LOOKINGGLASS_PT_panel_render)
		if hasattr(bpy.types, "LOOKINGGLASS_PT_panel_lightfield"): bpy.utils.unregister_class(LOOKINGGLASS_PT_panel_lightfield)
		if hasattr(bpy.types, "LOOKINGGLASS_PT_panel_overlays_shading"): bpy.utils.unregister_class(LOOKINGGLASS_PT_panel_overlays_shading)
        # preferences
		bpy.utils.unregister_class(LOOKINGGLASS_PT_preferences)
		# delete all variables
		if hasattr(bpy.types.Scene, "addon_settings"): del bpy.types.Scene.addon_settings


	# log info
	LookingGlassAddonLogger.info(" [#] Unloading the python dependencies.")

	# unload all libraries
	LookingGlassAddon.unload_dependecies()

	# log info
	LookingGlassAddonLogger.info(" [#] Shutting down the loggers.")

	# shut down both loggers (pylightio and Alice/LG)
	logger.handlers.clear()
	LookingGlassAddonLogger.handlers.clear()
	logging.shutdown()

	# log info
	LookingGlassAddonLogger.info(" [#] Done.")
