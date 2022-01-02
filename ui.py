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
# This includes everything that is related the user interface

# ------------------ INTERNAL MODULES --------------------
from .globals import *

# ------------------- EXTERNAL MODULES -------------------
import sys, os, json
import time
from math import *

import bpy
from bpy.props import FloatProperty, PointerProperty
from bpy.types import PropertyGroup

import numpy as np

# append the add-on's path to Blender's python PATH
sys.path.insert(0, LookingGlassAddon.path)
sys.path.insert(0, LookingGlassAddon.libpath)

# TODO: Would be better, if from .lib import pylightio could be called,
#		but for some reason that does not import all modules and throws
#		"AliceLG.lib.pylio has no attribute 'lookingglass"
import pylightio as pylio

# ---------------- GLOBAL ADDON LOGGER -------------------
import logging
LookingGlassAddonLogger = logging.getLogger('Alice/LG')



# ------------- Add-on UI -------------
# Class that contains all functions relevant for the UI
class LookingGlassAddonUI:

	# This callback is required to be able to update the list of connected Looking Glass devices
	def connected_device_list_callback(self, context):

		# prepare a item list with entries of the form "identifier, name, description"
		items = []

		# if at least one Looking Glass is connected OR debug mode is activated
		if pylio.DeviceManager.count() > 0 or LookingGlassAddon.debugging_use_dummy_device:

			# then for each display in the device list
			for idx, device in enumerate(sorted(pylio.DeviceManager.to_list(), key=lambda device_type: device_type.index)):

				# if this device is a real one OR the debug mode is active
				if (not device.emulated or LookingGlassAddon.debugging_use_dummy_device):

					# add an entry in the item list
					items.append((str(device.id), 'Display ' + str(device.index) + ': ' + device.name, 'Use this Looking Glass for lightfield rendering.'))

			# FOR DEBUGGING ONLY
			if LookingGlassAddon.debugging_use_dummy_device:

				# then for each display in the device list
				for idx, device in enumerate(pylio.DeviceManager.to_list(None, True)):

					# if this device is a real one OR the debug mode is active
					if (not device.emulated or LookingGlassAddon.debugging_use_dummy_device):

						# add an entry in the item list
						items.append((str(device.id), 'Display ' + str(device.index) + ': ' + device.name, 'Use this Looking Glass for lightfield rendering.'))

		else:

			# add an entry to notify the user about the missing Looking Glass
			items.append(('-1', 'No Looking Glass Found', 'Please connect a Looking Glass.'))



		# return the item list
		return items


	# This callback is required to be able to update the list of emulated Looking Glass devices
	def emulated_device_list_callback(self, context):

		# prepare a item list with entries of the form "identifier, name, description"
		items = []

		# if at least one emulated Looking Glass exists
		if pylio.DeviceManager.count(False, True) > 0:

			# then for each display in the device list
			for idx, device in enumerate(sorted(pylio.DeviceManager.to_list(False, True), key=lambda device_type: device_type.index, reverse=True)):

				# if this device is a real one OR the debug mode is active
				if device.emulated:

					# add an entry in the item list
					items.append((str(device.index), device.name, 'Use this Looking Glass type for lightfield rendering.'))

		else:

			# add an entry to notify the user about the missing Looking Glass
			items.append(('-1', 'No Emulated Devices Found', 'Please connect a Looking Glass.'))



		# return the item list
		return items

	# This callback is required to be able to update the list of presets
	def quilt_preset_list_callback(self, context):

		# prepare a item list with entries of the form "identifier, name, description"
		items = []

		# then for each display in the device list
		for idx, preset in pylio.LookingGlassQuilt.formats.get().items():

			# if this preset is not marked as hidden
			if not pylio.LookingGlassQuilt.formats.is_hidden(id=idx):

				# add an entry in the item list
				items.append((str(idx), preset['description'], 'Use this Looking Glass for lightfield rendering.'))


		# return the item list
		return items

	# poll function for the Looking Glass camera selection
	# this prevents that an object is picked or listed, which is no camera
	def camera_selection_poll(self, object):

		# the object has to be a Camera of the current view layer
		return (object.type == 'CAMERA' and (object in [o for o in bpy.context.view_layer.objects]))


	# update function for the workspace selection
	def update_workspace_selection(self, context):

		if context != None:

			# if the settings shall be taken from the current viewport
			if context.scene.addon_settings.viewportMode == 'BLENDER':

				# status variable
				success = False

				# find the correct SpaceView3D object
				for screen in bpy.data.workspaces[context.scene.addon_settings.blender_workspace].screens:
					for area in screen.areas:
						for space in area.spaces:

							# if this is the correct space
							if str(space) == str(context.scene.addon_settings.blender_view3d):

								# save the space object in the global variable
								LookingGlassAddon.BlenderViewport = space
								success = True
								break

				# if the current space was not found in the chosen workspace
				if success == False:

					# find and use the first SpaceView3D object of the workspace
					for screen in bpy.data.workspaces[context.scene.addon_settings.blender_workspace].screens:
						for area in screen.areas:
							for space in area.spaces:
								if space.type == 'VIEW_3D':

									# save the space object in the global variable
									LookingGlassAddon.BlenderViewport = space
									success = True
									break

				# if there is no 3D View in this workspace, use the active 3D View instead
				if success == False:

					# update the viewport selection
					context.scene.addon_settings.blender_view3d = "None"

					# fall back to the use of the custom settings
					LookingGlassAddon.BlenderViewport = None

		return None


	# update function for the viewport selection
	def update_viewport_selection(self, context):

		if context != None:

			# if the settings shall be taken from the current viewport
			if context.scene.addon_settings.viewportMode == 'BLENDER':

				# if a viewport is chosen
				if str(context.scene.addon_settings.blender_view3d) != "None":

					# find the correct SpaceView3D object
					for screen in bpy.data.workspaces[context.scene.addon_settings.blender_workspace].screens:
						for area in screen.areas:
							for space in area.spaces:

								# if this is the correct space
								if str(space) == str(context.scene.addon_settings.blender_view3d):

									# save the space object in the global variable
									LookingGlassAddon.BlenderViewport = space
									break

				else:

					# fall back to the use of the custom settings
					LookingGlassAddon.BlenderViewport = None

		return None


	# update function for property updates concerning render settings
	def update_render_setting(self, context):

		# if a device is selected by the user
		if int(self.activeDisplay) != -1: pylio.DeviceManager.set_active(int(self.activeDisplay))
		else: 						 	  pylio.DeviceManager.reset_active()

		# set device variable
		device = None

		# if a camera is selected
		if context.scene.addon_settings.lookingglassCamera != None:

			# GET DEVICE INFORMATION
			# +++++++++++++++++++++++++++++++++++++++++++++++++++++
			# if the settings are to be taken from device selection AND a device is active
			if context.scene.addon_settings.render_use_device == True and pylio.DeviceManager.get_active() is not None:

				# currently selected device
				device = pylio.DeviceManager.get_active()

			else:

				# make the emulated device the active device, if one was found
				device = pylio.DeviceManager.get_device(key='index', value=int(context.scene.addon_settings.render_device_type))


			# APPLY RENDER SETTINGS
			# +++++++++++++++++++++++++++++++++++++++++++++++++++++
			# apply render settings for the scene to get the correct rendering frustum
			context.scene.render.resolution_x = pylio.LookingGlassQuilt.formats.get()[int(context.scene.addon_settings.render_quilt_preset)]["view_width"]
			context.scene.render.resolution_y = pylio.LookingGlassQuilt.formats.get()[int(context.scene.addon_settings.render_quilt_preset)]["view_height"]

			# for landscape formatted devices
			if (context.scene.render.resolution_x / context.scene.render.resolution_y) / device.aspect > 1:

				# apply the correct aspect ratio
				context.scene.render.pixel_aspect_x = 1.0
				context.scene.render.pixel_aspect_y = context.scene.render.resolution_x / (context.scene.render.resolution_y * device.aspect)

			# for portrait formatted devices
			else:

				# apply the correct aspect ratio
				context.scene.render.pixel_aspect_x = (context.scene.render.resolution_y * device.aspect) / context.scene.render.resolution_x
				context.scene.render.pixel_aspect_y = 1.0

		return None


	# update function for property updates concerning camera selection
	def update_camera_selection(self, context):

		# if no Looking Glass was detected AND debug mode is not activated
		if not pylio.DeviceManager.count() and not LookingGlassAddon.debugging_use_dummy_device:

			# set the checkbox to False (because there is no device we
			# could take the settings from)
			context.scene.addon_settings.render_use_device = False

		# if a camera was selected
		if context.scene.addon_settings.lookingglassCamera != None:

			# if the frustum drawing operator is not invoked, but should be
			if LookingGlassAddon.FrustumInitialized == False and context.scene.addon_settings.showFrustum == True and LookingGlassAddon.background == False:
				bpy.ops.render.frustum('INVOKE_DEFAULT')

			# apply the settings to the selected camera object
			camera = context.scene.addon_settings.lookingglassCamera

			# keep clip end behind the clip start
			if context.scene.addon_settings.clip_end < context.scene.addon_settings.clip_start:
				context.scene.addon_settings.clip_end = context.scene.addon_settings.clip_start

			# keep clip start in front of the clip end
			if context.scene.addon_settings.clip_start > context.scene.addon_settings.clip_end:
				context.scene.addon_settings.clip_start = context.scene.addon_settings.clip_end

			# keep focal plane within the clipping volume
			if context.scene.addon_settings.focalPlane < context.scene.addon_settings.clip_start:
				context.scene.addon_settings.focalPlane = context.scene.addon_settings.clip_start
			elif context.scene.addon_settings.focalPlane > context.scene.addon_settings.clip_end:
				context.scene.addon_settings.focalPlane = context.scene.addon_settings.clip_end

			# apply the clipping values to the selected camera
			camera.data.clip_start = context.scene.addon_settings.clip_start
			camera.data.clip_end = context.scene.addon_settings.clip_end

			# update render settings
			LookingGlassAddonUI.update_render_setting(self, context)

		return None


	# update function for property updates concerning camera clipping in the livew view
	def update_camera_setting(self, context):

		# if a camera was selected
		if context.scene.addon_settings.lookingglassCamera != None:

			# apply the settings to the selected camera object
			camera = context.scene.addon_settings.lookingglassCamera


			# TODO: Check if this is really helpful. Maybe remove later or refine.
			# keep clip end behind the clip start
			if context.scene.addon_settings.clip_end < context.scene.addon_settings.clip_start:
				context.scene.addon_settings.clip_end = context.scene.addon_settings.clip_start

			# keep clip start in front of the clip end
			if context.scene.addon_settings.clip_start > context.scene.addon_settings.clip_end:
				context.scene.addon_settings.clip_start = context.scene.addon_settings.clip_end

			# keep focal plane within the clipping volume
			if context.scene.addon_settings.focalPlane < context.scene.addon_settings.clip_start:
				context.scene.addon_settings.focalPlane = context.scene.addon_settings.clip_start
			elif context.scene.addon_settings.focalPlane > context.scene.addon_settings.clip_end:
				context.scene.addon_settings.focalPlane = context.scene.addon_settings.clip_end



			# apply the clipping values to the selected camera
			camera.data.clip_start = context.scene.addon_settings.clip_start
			camera.data.clip_end = context.scene.addon_settings.clip_end

		return None



	# This callback populates the viewport selection with the WORKSPACES
	def workspaces_list_callback(self, context):

		# prepare a item list with entries of the form "identifier, name, description"
		items = []

		# check if the space still exists
		for workspace in bpy.data.workspaces.keys():

			# add an entry to notify the user about the missing Looking Glass
			items.append((workspace, workspace, 'The workspace the desired viewport is found.'))

		# return the item list
		return items



	# This callback populates the viewport selection with the 3DVIEWs
	def view3D_list_callback(self, context):

		# prepare a item list with entries of the form "identifier, name, description" for the EnumProperty
		items = []

		# check if the space still exists
		if context.scene.addon_settings.blender_workspace in bpy.data.workspaces:

			# find all 3D Views in the selected Workspace
			for screen in bpy.data.workspaces[context.scene.addon_settings.blender_workspace].screens:
				for area in screen.areas:
					for space in area.spaces:
						if space.type == 'VIEW_3D':

							# add an item to the item list
							items.append((str(space), 'Viewport ' + str(len(items) + 1), 'The Blender viewport to which the Looking Glass adjusts'))

		# if no spaces were found
		if len(items) == 0:

			# add a dummy entry to the item list
			items.append(('None', 'None', 'The Blender viewport to which the Looking Glass adjusts'))

		# return the item list
		return items



	# update function for property updates concerning lightfield window settings
	def update_lightfield_window_settings(self, context):

		# if the lightfield viewport is in quilt viewer mode
		if context.scene.addon_settings.renderMode == '1':

			# update the lightfield displayed on the device
			LookingGlassAddon.update_lightfield_window(int(context.scene.addon_settings.renderMode), LookingGlassAddon.quiltViewerLightfieldImage)


	# update function for property updates concerning quilt image selection
	def update_quilt_selection(self, context):

		# if a quilt was selected
		if context.scene.addon_settings.quiltImage != None:

			# update the setting observers
			LookingGlassAddon.quiltViewAsRender = context.scene.addon_settings.quiltImage.use_view_as_render
			LookingGlassAddon.quiltImageColorSpaceSetting = context.scene.addon_settings.quiltImage.colorspace_settings

			# if no pixel array exists
			if LookingGlassAddon.quiltPixels is None:

				# create a numpy array for the pixel data
				LookingGlassAddon.quiltPixels = np.empty(len(context.scene.addon_settings.quiltImage.pixels), dtype=np.float32)

			else:

				# resize the numpy array
				LookingGlassAddon.quiltPixels.resize(len(context.scene.addon_settings.quiltImage.pixels), refcheck=False)



			# GET PIXEL DATA
			# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
			# TODO: Change. The current approach is hacky and slow, but I don't
			#		know of any other way to access the pixel data WITH applied
			#		color management directly in memory. Seems like Blender
			#		does not expose this pixel data to the Python API
			#
			#		I asked this also on stackexchange but got no better way yet:
			#		https://blender.stackexchange.com/questions/206910/access-image-pixel-data-with-color-management-settings
			#

			# if the image has the "view as render" option inactive
			if context.scene.addon_settings.quiltImage.use_view_as_render == False:

				# save the original settings
				tempViewTransform = context.scene.view_settings.view_transform
				tempLook = context.scene.view_settings.look
				tempExposure = context.scene.view_settings.exposure
				tempGamma = context.scene.view_settings.gamma
				tempUseCurveMapping = context.scene.view_settings.use_curve_mapping

				# apply standard settings
				context.scene.view_settings.view_transform = "Standard"
				context.scene.view_settings.look = "None"
				context.scene.view_settings.exposure = 0
				context.scene.view_settings.gamma = 1
				context.scene.view_settings.use_curve_mapping = False


			# set the temporary file path
			tempFilepath = bpy.app.tempdir + 'temp' + str(int(time.time())) + '.png'

			# set the output settings
			tempUseRenderCache = context.scene.render.use_render_cache
			tempFileFormat = context.scene.render.image_settings.file_format
			tempColorDepth = context.scene.render.image_settings.color_depth
			tempColorMode = context.scene.render.image_settings.color_mode
			context.scene.render.use_render_cache = False
			context.scene.render.image_settings.file_format = 'PNG'
			context.scene.render.image_settings.color_depth = '8'
			context.scene.render.image_settings.color_mode = 'RGBA'

			# save the image to the temporary directory
			context.scene.addon_settings.quiltImage.save_render(filepath=tempFilepath, scene=context.scene)

			# restore output render settings
			context.scene.render.use_render_cache = tempUseRenderCache
			context.scene.render.image_settings.file_format = tempFileFormat
			context.scene.render.image_settings.color_depth = tempColorDepth
			context.scene.render.image_settings.color_mode = tempColorMode

			# if the image has the "view as render" option inactive
			if context.scene.addon_settings.quiltImage.use_view_as_render == False:

				# restore the original settings
				context.scene.view_settings.view_transform = tempViewTransform
				context.scene.view_settings.look = tempLook
				context.scene.view_settings.exposure = tempExposure
				context.scene.view_settings.gamma = tempGamma
				context.scene.view_settings.use_curve_mapping = tempUseCurveMapping

			# if the file was created
			if os.path.isfile(tempFilepath) == True:

				# append the loaded image to the list
				tempImage = bpy.data.images.load(filepath=tempFilepath)

				# copy pixel data to the array and a BGL Buffer
				tempImage.pixels.foreach_get(LookingGlassAddon.quiltPixels)

			# TODO: The following lines would be enough, if the color
			#		management settings would be applied in memory. Not deleted
			#		for later
			#
			# # copy pixel data to the array and a BGL Buffer
			# context.scene.addon_settings.quiltImage.pixels.foreach_get(LookingGlassAddon.quiltPixels)
			# LookingGlassAddon.quiltTextureBuffer = bgl.Buffer(bgl.GL_FLOAT, len(context.scene.addon_settings.quiltImage.pixels), LookingGlassAddon.quiltPixels)

			# delete the temporary Blender image
			bpy.data.images.remove(tempImage)

			# delete the temporary file
			os.remove(tempFilepath)

			# CREATE A NEW PYLIGHTIO LIGHTFIELD IMAGE FROM THE BLENDER QUILT
			# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
			# convert to uint8
			quiltPixels = 255 * LookingGlassAddon.quiltPixels
			quiltPixels = quiltPixels.astype(dtype=np.uint8)

			# if no quilt viewer LightfieldImage is selected
			if context.scene.addon_settings.quiltImage is None:

				# free the view data of the lightfield image, if one was loaded
				if LookingGlassAddon.quiltViewerLightfieldImage:
					LookingGlassAddon.quiltViewerLightfieldImage.clear_views()
					LookingGlassAddon.quiltViewerLightfieldImage = None

			# create a LightfieldImage from the selected quilt
			LookingGlassAddon.quiltViewerLightfieldImage = pylio.LightfieldImage.from_buffer(pylio.LookingGlassQuilt, quiltPixels, context.scene.addon_settings.quiltImage.size[0], context.scene.addon_settings.quiltImage.size[1], context.scene.addon_settings.quiltImage.channels, quilt_name = context.scene.addon_settings.quiltImage.name)

			# update the lightfield displayed on the device
			LookingGlassAddon.update_lightfield_window(int(context.scene.addon_settings.renderMode), LookingGlassAddon.quiltViewerLightfieldImage)

		# if the quilt selection was deleted
		else:

			# free the view data of the lightfield image, if one was loaded
			if LookingGlassAddon.quiltViewerLightfieldImage:
				LookingGlassAddon.quiltViewerLightfieldImage.clear_views()
				LookingGlassAddon.quiltViewerLightfieldImage = None

			# update the lightfield displayed on the device
			LookingGlassAddon.update_lightfield_window(int(context.scene.addon_settings.renderMode), LookingGlassAddon.quiltViewerLightfieldImage)

			# reset the variables
			LookingGlassAddon.quiltPixels = None


# Preferences pane for this Addon in the Blender preferences
class LookingGlassAddonSettings(bpy.types.PropertyGroup):

	# PANEL: GENERAL
	# a list of connected Looking Glass displays
	activeDisplay: bpy.props.EnumProperty(
										items = LookingGlassAddonUI.connected_device_list_callback,
										name="Please select a Looking Glass.",
										update=LookingGlassAddonUI.update_render_setting,
										)

	# a boolean to toogle the render window on or off
	ShowLightfieldWindow: bpy.props.BoolProperty(
											name="Lightfield Window",
											description = "Creates a window for the lightfield rendering on the current Looking Glass device.",
											default = False,
											)

	quiltPreset: bpy.props.EnumProperty(
										items = LookingGlassAddonUI.quilt_preset_list_callback,
										name="View Resolution",
										update=LookingGlassAddonUI.update_render_setting,
										)


	# PANEL: CAMERA SETTINGS
	# pointer property that can be used to load a pre-rendered quilt image
	lookingglassCamera: bpy.props.PointerProperty(
										name="Looking Glass Camera",
										type=bpy.types.Object,
										description = "Select a camera, which defines the view for your Looking Glass or quilt image",
										poll = LookingGlassAddonUI.camera_selection_poll,
										update = LookingGlassAddonUI.update_camera_selection,
										#options = {'ANIMATABLE'}
										)

	showFocalPlane: bpy.props.BoolProperty(
										name="Show Focal Plane",
										description="If enabled, the focal plane of the Looking Glass is shown in the viewport",
										default = True,
										)

	showFrustum: bpy.props.BoolProperty(
										name="Show Camera Frustum",
										description="If enabled, the render volume of the Looking Glass is shown in the viewport",
										default = True,
										)

	clip_start: bpy.props.FloatProperty(
										name = "Clip Start",
										default = 4.2,
										min = 0.000001,
										soft_min = 0.1,
										precision = 1,
										step = 10,
										description = "Far clipping plane of the Looking Glass frustum.",
										update = LookingGlassAddonUI.update_camera_setting,
										)

	clip_end: bpy.props.FloatProperty(
										name = "Clip End",
										default = 6.5,
										min = 0,
										precision = 1,
										step = 10,
										description = "Far clipping plane of the Looking Glass frustum.",
										update = LookingGlassAddonUI.update_camera_setting,
										)

	# the virtual distance of the plane, which represents the focal plane of the Looking Glass
	focalPlane: bpy.props.FloatProperty(
										name = "Focal Plane",
										default = 5,
										min = 0,
										precision = 1,
										step = 10,
										description = "Virtual distance to the focal plane. (This plane is directly mapped to the LCD display of the Looking Glass)",
										update = LookingGlassAddonUI.update_camera_setting,
										)


	# PANEL: RENDER SETTINGS
	# Use the device to set device settings
	render_use_device: bpy.props.BoolProperty(
										name="Use Device Settings",
										description="If enabled, the render settings are taken from the selected device",
										default = True,
										update=LookingGlassAddonUI.update_render_setting,
										)

	# Add a suffix with metadata to the file name
	render_add_suffix: bpy.props.BoolProperty(
										name="Add Metadata",
										description="If enabled, metadata will be added to the quilt filename as a suffix. That metadata is used by Holoplay Studio and other applications in the Looking Glass ecosystem to automatically determine the correct settings for displaying or editing the quilt.",
										default = True,
										update=LookingGlassAddonUI.update_render_setting,
										)

	# Orientation of the views
	render_device_type: bpy.props.EnumProperty(
										items = LookingGlassAddonUI.emulated_device_list_callback,
										name="Device Type",
										update = LookingGlassAddonUI.update_render_setting,
										)

	# Quilt presets
	render_quilt_preset: bpy.props.EnumProperty(
									items = LookingGlassAddonUI.quilt_preset_list_callback,
									name="Quilt Preset",
									update = LookingGlassAddonUI.update_render_setting,
									)

	# File handling
	render_output: bpy.props.EnumProperty(
									items = [('0', 'View and Quilt Files', 'Each view is rendered to a separate file in the output directory in addition to the quilt.'),
											 ('1', 'Only Quilt File', 'Each view is rendered to a temporary file in the output directory. These files are deleted after the quilt is complete.')],
									default='1',
									name="Output",
									)

	# Progress bar
	render_progress: bpy.props.FloatProperty(
										name = "",
										subtype='PERCENTAGE',
										default = 0,
										min = 0,
										max = 100,
										precision = 0,
										step = 100,
										description = "Total quilt rendering progress",
										)

	# Cancel button
	render_stop: bpy.props.BoolProperty(
										name="Cancel render job",
										description="Press this button or the 'ESC' key to stop the quilt rendering.",
										default = False,
										)


	# PANEL: LIGHTFIELD WINDOW SETTINGS
	# UI elements for user control
	renderMode: bpy.props.EnumProperty(
										items = [('0', 'Viewport', 'Viewport rendering of the current scene within the Looking Glass', 'VIEW3D', 0),
												 ('1', 'Quilt Viewer', 'Display a prerendered quilt image in the Looking Glass', 'RENDER_RESULT', 1)],
										default='0',
										name="Render Mode",
										update=LookingGlassAddonUI.update_lightfield_window_settings,
										)

	# Lightfield Viewport Modes
	lightfieldMode: bpy.props.EnumProperty(
										items = [('0', 'Refresh Mode: Automatic', 'Automatically refresh the lightfield viewport'),
												 ('1', 'Refresh Mode: Manual', 'Refresh the lightfield viewport manually')],
										default='0',
										name="Lightfield Viewport Modes",
										update=LookingGlassAddonUI.update_lightfield_window_settings,
										)

	# Lightfield Preview Resolution in Auto lightfield mode
	lightfield_preview_mode: bpy.props.EnumProperty(
										items = [('0', 'No Preview', 'Lightfield window updates are performed after (not during) user interactions.'),
												 ('1', 'Low-resolution Preview', '1024x1024 quilt, 32 views'),
												 ('2', 'Skipped-views Preview I', 'Skip every second view'),
												 ('3', 'Skipped-views Preview II', 'Skip every third view'),
												 ('4', 'Restricted Viewcone Preview', 'Render only a restricted view cone'),
												 ],
										default='0',
										name="Lightfield Preview Mode",
										update=LookingGlassAddonUI.update_lightfield_window_settings,
										)

	# pointer property that can be used to load a pre-rendered quilt image
	quiltImage: bpy.props.PointerProperty(
										name="Quilt",
										type=bpy.types.Image,
										description = "Quilt image for display in the Looking Glass",
										update = LookingGlassAddonUI.update_quilt_selection,
										)


	viewport_use_preview_mode: bpy.props.BoolProperty(
										name="Use Preview Mode",
										description="If enabled, a simplified lightfield is rendered during scene changes (for higher render speed)",
										default = True,
										)

	viewport_manual_refresh: bpy.props.BoolProperty(
										name="Refresh Looking Glass",
										description="Redraw the lightfield in the Looking Glass",
										default = False,
										)

	viewport_show_cursor: bpy.props.BoolProperty(
										name="Lightfield Cursor",
										description="If enabled, a lightfield mouse cursor is rendered in the lightfield window",
										default = True,
										)

	viewport_cursor_size: bpy.props.FloatProperty(
										name="Lightfield Cursor Size",
										description="The size of the lightfield mouse cursor in the lightfield window",
										default = 0.05,
										min = 0.0,
										max = 0.1,
										precision = 3,
										step = 1,
										)

	viewport_cursor_color: bpy.props.FloatVectorProperty(name="Lightfield Cursor Color",
									subtype='COLOR',
									default=[1.0, 0.627451, 0.156863])



	# PANEL: OVERLAY & SHADER SETTINGS
	viewportMode: bpy.props.EnumProperty(
										items = [
													('BLENDER', 'Blender ', 'Use the settings of a Blender viewport', 'BLENDER', 0),
													('CUSTOM', 'Custom', 'Specify the settings for the Looking Glass viewport manually', 'OVERLAY', 1)
												],
										default='BLENDER',
										name="Viewport Mode",
										)

	blender_workspace: bpy.props.EnumProperty(
										name="Workspace",
										items = LookingGlassAddonUI.workspaces_list_callback,
										update = LookingGlassAddonUI.update_workspace_selection
										)

	blender_view3d: bpy.props.EnumProperty(
										name="3D View",
										items = LookingGlassAddonUI.view3D_list_callback,
										update = LookingGlassAddonUI.update_viewport_selection
										)

	# Shading
	shadingMode: bpy.props.EnumProperty(
										items = [('WIREFRAME', '', 'Use the OpenGL wireframe rendering mode', 'SHADING_WIRE', 0),
												 ('SOLID', '', 'Use the OpenGL solid rendering mode', 'SHADING_SOLID', 1),
												 ('MATERIAL', '', 'Use the current render engines material preview rendering mode', 'SHADING_RENDERED', 2)],
										default='SOLID',
										name="Shading",
										)

	viewport_show_xray: bpy.props.BoolProperty(
										name="",
										description="If enabled, the whole scene is rendered transparent in the Looking Glass",
										default = False,
										)

	viewport_xray_alpha: bpy.props.FloatProperty(
										name = "X-Ray Alpha",
										default = 0.5,
										min = 0.001,
										max = 1,
										precision = 3,
										step = 1,
										description = "Amount of alpha to use",
										)

	viewport_use_dof: bpy.props.BoolProperty(
										name="Depth of Field",
										description="If enabled, the lightfield is rendered using the depth of field settings of the multiview cameras",
										default = False,
										update = LookingGlassAddonUI.update_camera_setting,
										)

	# GUIDES
	viewport_show_floor: bpy.props.BoolProperty(
										name="Floor",
										description="If enabled, the floor grid is displayed in the Looking Glass",
										default = True,
										)

	viewport_show_axes: bpy.props.BoolVectorProperty(
										name="Axes",
										subtype="XYZ",
										description="If enabled, the x axis is displayed in the Looking Glass",
										size=3,
										default = (True, True, False),
										)

	viewport_grid_scale: bpy.props.FloatProperty(
										name = "Grid Scale",
										default = 1,
										min = 0.001,
										precision = 3,
										step = 0.1,
										description = "Multiplier for the distance between 3D View grid lines",
										)


	# OBJECTS
	viewport_show_extras: bpy.props.BoolProperty(
										name="Extras",
										description="If enabled, object details including empty wire, cameras, and light sources are displayed in the Looking Glass",
										default = True,
										)

	viewport_show_relationship_lines: bpy.props.BoolProperty(
										name="Relationship Lines",
										description="If enabled, relationship lines indicating parents or constraints are displayed in the Looking Glass",
										default = False,
										)

	viewport_show_outline_selected: bpy.props.BoolProperty(
										name="Show Outline Selected",
										description="If enabled, the outline of the selected object is displayed in the Looking Glass",
										default = False,
										)

	viewport_show_bones: bpy.props.BoolProperty(
										name="Bones",
										description="If enabled, bones are displayed in the Looking Glass",
										default = False,
										)

	viewport_show_motion_paths: bpy.props.BoolProperty(
										name="Motion Paths",
										description="If enabled, motion paths (without bones) are displayed in the Looking Glass",
										default = False,
										)

	viewport_show_origins: bpy.props.BoolProperty(
										name="Origins",
										description="If enabled, the object center dots are displayed in the Looking Glass",
										default = False,
										)

	viewport_show_origins_all: bpy.props.BoolProperty(
										name="Origins (All)",
										description="If enabled, the object center dot of all objects are displayed in the Looking Glass",
										default = False,
										)

	# GEOMETRY
	viewport_show_wireframes: bpy.props.BoolProperty(
										name="",
										description="If enabled, the face edges wires are displayed in the Looking Glass",
										default = False,
										)

	viewport_wireframe_threshold: bpy.props.FloatProperty(
										name="Wireframe",
										min=0,
										max=1,
										precision=3,
										description="Adjust the angle threshold for displaying edges in the Looking Glass",
										default = 1,
										)

	viewport_show_face_orientation: bpy.props.BoolProperty(
										name="Face Orientation",
										description="If enabled, the face orientation is displayed in the Looking Glass",
										default = False,
										)


# ----------------- PANEL FOR GENERAL SETTINGS --------------------
# an operator that refreshes the list of connected Looking Glasses
class LOOKINGGLASS_OT_refresh_display_list(bpy.types.Operator):
	bl_idname = "lookingglass.refresh_display_list"
	bl_label = "Refresh list"
	bl_description = "Refreshes the list of connected Looking Glass deviced from the HoloPlay Service"
	bl_options = {'REGISTER', 'INTERNAL'}

	def execute(self, context):

		# log info
		LookingGlassAddonLogger.info("Refreshing device information ...")

		# if a service for display communication was successfully added
		if (not LookingGlassAddon.service is None):

			# if the service is ready
			if LookingGlassAddon.service.is_ready():

				# refresh the list of connected devices using the active service
				pylio.DeviceManager.refresh()

				# log info
				LookingGlassAddonLogger.info(" [#] Number of connected displays: %i" % pylio.DeviceManager.count())

				# loop through all connected devices
				for idx, device in enumerate(pylio.DeviceManager.to_list()):

					# log info
					LookingGlassAddonLogger.info(" [#] Display %i: %s" % (idx, device.name,))

			# if no Looking Glass was detected AND debug mode is deaqctivated
			if not pylio.DeviceManager.count() and not LookingGlassAddon.debugging_use_dummy_device:

				# set the checkbox to False (because there is no device we
				# could take the settings from)
				context.scene.addon_settings.render_use_device = False

			# if a Looking Glass was detected, but non was previously selected
			elif pylio.DeviceManager.count():

				# get currently active device
				device = pylio.DeviceManager.get_active()

				# if None is active or the active device is an emulated one
				if not device or (device and device.emulated):

					# log info
					LookingGlassAddonLogger.info(" [#] Setting active display %i: %s" % (pylio.DeviceManager.to_list()[0].id, pylio.DeviceManager.to_list()[0].name,))

					# make the first connected display the active display
					pylio.DeviceManager.set_active(pylio.DeviceManager.to_list()[0].id)

					# get currently active device
					device = pylio.DeviceManager.get_active()

					# set the checkbox to True (because now we want to use the device settings)
					context.scene.addon_settings.render_use_device = True

				# try to find the suitable default quilt preset
				preset = pylio.LookingGlassQuilt.formats.find(device.default_quilt_width, device.default_quilt_height, device.default_quilt_rows, device.default_quilt_columns)

				# then update the selected quilt preset from the device's default quilt
				if preset:
					context.scene.addon_settings.quiltPreset = str(preset)

				# fallback solution, if the default quilt is not found:
				# We use the Looking Glass Portrait standard quilt (48 views)
				else:
					context.scene.addon_settings.quiltPreset = "4"

		return {'FINISHED'}


# an operator that controls lightfield window opening and closing
class LOOKINGGLASS_OT_lightfield_window(bpy.types.Operator):
	bl_idname = "lookingglass.lightfield_window"
	bl_label = "Lightfield Window"
	bl_description = "Creates a window for the lightfield rendering on the current Looking Glass device"
	bl_options = {'REGISTER', 'INTERNAL'}


	# Update the Boolean property that creates the hologram rendering window
	def execute(self, context):

		# set the property to the correct value
		context.scene.addon_settings.ShowLightfieldWindow = (not context.scene.addon_settings.ShowLightfieldWindow)

		# if the bool property was set to True
		if context.scene.addon_settings.ShowLightfieldWindow == True:

			# assign the current viewport for the shading & overlay settings
			bpy.ops.lookingglass.blender_viewport_assign('EXEC_DEFAULT')

			# Invoke modal operator for the lightfield rendering
			bpy.ops.render.viewport('INVOKE_DEFAULT')

		return {'FINISHED'}



class LOOKINGGLASS_PT_panel_general(bpy.types.Panel):
	bl_idname = "LOOKINGGLASS_PT_panel_general" # unique identifier for buttons and menu items to reference.
	bl_label = "Looking Glass" # display name in the interface.
	bl_space_type = "VIEW_3D"
	bl_region_type = "UI"
	bl_category = "Looking Glass"


	# Draw handler for the panel layout
	def draw(self, context):
		layout = self.layout
		column = layout.column()

		# Device selection
		row_orientation = column.row(align = True)
		column_1 = row_orientation.column(align=True)
		row_orientationa = column_1.row(align = True)
		row_orientationa.prop(context.scene.addon_settings, "activeDisplay", text="")
		row_orientationa.operator("lookingglass.refresh_display_list", text="", icon='FILE_REFRESH')
		row_orientation.separator()

		# Lightfield window button
		column_2 = row_orientation.column(align=True)
		row_orientationb = column_2.row(align = True)
		row_orientationb.operator("lookingglass.lightfield_window", text="", icon='WINDOW', depress=context.scene.addon_settings.ShowLightfieldWindow)

		# Resolution selection of the quilt views
		row_preset = column.row()
		row_preset.prop(context.scene.addon_settings, "quiltPreset", text="")
		#column.separator()

		# if no Looking Glass was detected AND debug mode is not activated OR the active device is an emulated one
		if (not pylio.DeviceManager.count() and not LookingGlassAddon.debugging_use_dummy_device):

			# deactivate quilt preset and lightfield window buttons
			row_preset.enabled = False
			row_orientationb.enabled = False

		# if the HoloPlay Service is not added or not ready
		if (LookingGlassAddon.service is None or not LookingGlassAddon.service.is_ready()) and not LookingGlassAddon.debugging_use_dummy_device:

			# deactivate the looking glass selection and lightfield window button
			row_orientationa.enabled = False
			row_orientationb.enabled = False



# ------------- The Camera Settings Panel ----------------
# an operator that adds a camera to the scene
class LOOKINGGLASS_OT_add_camera(bpy.types.Operator):
	bl_idname = "object.add_lookingglass_camera"
	bl_label = "Add Looking Glass Camera"
	bl_description = "Creates a new camera object with settings optimized for the Looking Glass"
	bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

	def execute(self, context):

		# first we add a new camera and link it to the scene
		camera_data = bpy.data.cameras.new(name='Looking Glass Camera')
		camera = bpy.data.objects.new('Looking Glass Camera', camera_data)
		bpy.context.scene.collection.objects.link(camera)

		# set the camera position
		camera.location.z = context.scene.addon_settings.focalPlane

		# then we apply all the default settings to the camera
		camera.data.sensor_fit = 'VERTICAL'
		camera.data.angle_y = radians(14)
		camera.data.clip_start = context.scene.addon_settings.clip_start
		camera.data.clip_end = context.scene.addon_settings.clip_end

		# if currently no camera is selected
		if context.scene.addon_settings.lookingglassCamera == None:

			# use the new camera as the Looking Glass Camera
			context.scene.addon_settings.lookingglassCamera = camera

		return {'FINISHED'}

# the panel for the camera settings
class LOOKINGGLASS_PT_panel_camera(bpy.types.Panel):
	bl_idname = "LOOKINGGLASS_PT_panel_camera" # unique identifier for buttons and menu items to reference.
	bl_label = "Camera Setup" # display name in the interface.
	bl_space_type = "VIEW_3D"
	bl_region_type = "UI"
	bl_category = "Looking Glass"
	bl_parent_id = "LOOKINGGLASS_PT_panel_general"


	# define own poll method to be able to hide / show the panel on demand
	@classmethod
	def poll(self, context):

		# the panel should always be drawn
		return True

	# draw the IntProperties for the tiles in the panel
	def draw(self, context):
		layout = self.layout

		# define a column of UI elements
		column = layout.column(align = True)

		row_orientation = column.row(align = True)
		row_orientation.prop(context.scene.addon_settings, "lookingglassCamera", icon='VIEW_CAMERA', text="")
		row_orientation.operator("object.add_lookingglass_camera", text="", icon='ADD')
		row_orientation.separator()
		row_orientation.prop(context.scene.addon_settings, "showFrustum", text="", icon='MESH_CUBE')
		row_orientation.prop(context.scene.addon_settings, "showFocalPlane", text="", icon='MESH_PLANE')

		column.separator()

		# display the clipping settings
		row_preset = column.row(align = True)
		row_preset.prop(context.scene.addon_settings, "clip_start")
		row_output = column.row(align = True)
		row_output.prop(context.scene.addon_settings, "clip_end")
		row_render_still = column.row(align = True)
		row_render_still.prop(context.scene.addon_settings, "focalPlane")

		# if no camera is Selected
		if context.scene.addon_settings.lookingglassCamera == None:

			# disable clipping and focal plane modifieres
			row_preset.enabled = False
			row_output.enabled = False
			row_render_still.enabled = False

# ------------- The Render Settings Panel ----------------
# the panel for the camera settings
class LOOKINGGLASS_PT_panel_render(bpy.types.Panel):
	bl_idname = "LOOKINGGLASS_PT_panel_render" # unique identifier for buttons and menu items to reference.
	bl_label = "Quilt Setup & Rendering" # display name in the interface.
	bl_space_type = "VIEW_3D"
	bl_region_type = "UI"
	bl_category = "Looking Glass"
	bl_parent_id = "LOOKINGGLASS_PT_panel_general"


	# define own poll method to be able to hide / show the panel on demand
	@classmethod
	def poll(self, context):

		# the panel should always be drawn
		return True

	# draw the UI for the configuration options
	def draw(self, context):
		layout = self.layout

		# Chose the settings from the device or use a preset?
		row_general_options = layout.column(align = True)
		row_use_device = row_general_options.row(align = True)
		render_use_device = row_use_device.prop(context.scene.addon_settings, "render_use_device")

		# Metadata handling
		row_metadata = row_general_options.row(align = True)
		render_add_suffix = row_metadata.prop(context.scene.addon_settings, "render_add_suffix")

		# Render orientation
		row_orientation = layout.row(align = True)
		column_1 = row_orientation.row(align = True)
		column_1.label(text="Device:")
		column_1.scale_x = 0.3
		column_2 = row_orientation.row(align = True)
		column_2.prop(context.scene.addon_settings, "render_device_type", text="")
		column_2.scale_x = 0.7

		# Quilt preset
		row_preset = layout.row(align = True)
		column_1 = row_preset.row(align = True)
		column_1.label(text="Quilt:")
		column_1.scale_x = 0.3
		column_2 = row_preset.row(align = True)
		column_2.prop(context.scene.addon_settings, "render_quilt_preset", text="")
		column_2.scale_x = 0.7

		# Output file handling
		row_output = layout.row(align = True)
		column_1 = row_output.row(align = True)
		column_1.label(text="Output:")
		column_1.scale_x = 0.3
		column_2 = row_output.row(align = True)
		column_2.prop(context.scene.addon_settings, "render_output", text="")
		column_2.scale_x = 0.7

		# if no lockfile was detected on start-up OR the render job is running
		if not LookingGlassAddon.has_lockfile or LookingGlassAddon.RenderInvoked:

			# Buttons and progress bars
			if LookingGlassAddon.RenderInvoked == True and LookingGlassAddon.RenderAnimation == False:
				# Show the corresponding progress bar for the rendering process
				row_render_still = layout.row(align = True)
				row_render_still.prop(context.scene.addon_settings, "render_progress", text="", slider=True)
				row_render_still.prop(context.scene.addon_settings, "render_stop", text="", icon='CANCEL')
			else:
				# Button to start rendering a single quilt using the current render settings
				row_render_still = layout.row(align = True)
				render_quilt = row_render_still.operator("render.quilt", text="Render Quilt", icon='RENDER_STILL')
				render_quilt.animation = False
				render_quilt.use_multiview = (context.preferences.addons[__package__].preferences.render_mode == '1')

			if LookingGlassAddon.RenderInvoked == True and LookingGlassAddon.RenderAnimation == True:
				# Show the corresponding progress bar for the rendering process
				row_render_animation = layout.row(align = True)
				row_render_animation.prop(context.scene.addon_settings, "render_progress", text="", slider=True)
				row_render_animation.prop(context.scene.addon_settings, "render_stop", text="", icon='CANCEL')
			else:
				# Button to start rendering a animation quilt using the current render settings
				row_render_animation = layout.row(align = True)
				render_quilt = row_render_animation.operator("render.quilt", text="Render Animation Quilt", icon='RENDER_ANIMATION')
				render_quilt.animation = True
				render_quilt.use_multiview = (context.preferences.addons[__package__].preferences.render_mode == '1')


		# if a lockfile was detected on start-up
		else:

			# disable the UI
			row_metadata.enabled = False
			row_use_device.enabled = False
			row_orientation.enabled = False
			row_preset.enabled = False
			row_output.enabled = False

			# inform the user and provide options to continue or to discard
			row_render_still = layout.row(align = True)
			row_render_still.label(text = "Last render job incomplete:", icon="ERROR")

			row_render_animation = layout.row(align = False)
			render_quilt = row_render_animation.operator("render.quilt", text="Continue", icon='RENDER_STILL')
			render_quilt.use_lockfile = True
			render_quilt.use_multiview = (context.preferences.addons[__package__].preferences.render_mode == '1')
			render_quilt = row_render_animation.operator("render.quilt", text="Discard", icon='CANCEL')
			render_quilt.use_lockfile = True
			render_quilt.use_multiview = (context.preferences.addons[__package__].preferences.render_mode == '1')
			render_quilt.discard_lockfile = True




		# disable the render settings, if a rendering process is running
		if LookingGlassAddon.RenderInvoked == True:
			row_metadata.enabled = False
			row_use_device.enabled = False
			row_orientation.enabled = False
			row_preset.enabled = False
			row_output.enabled = False

			if LookingGlassAddon.RenderAnimation == True: row_render_still.enabled = False
			if LookingGlassAddon.RenderAnimation == False: row_render_animation.enabled = False

		# if no camera is selected
		if context.scene.addon_settings.lookingglassCamera == None:

			# disable all elements
			row_metadata.enabled = False
			row_use_device.enabled = False
			row_orientation.enabled = False
			row_preset.enabled = False
			row_output.enabled = False
			row_render_still.enabled = False
			row_render_animation.enabled = False

		# if the settings are to be taken from device selection
		elif context.scene.addon_settings.render_use_device == True:

			# disable all elements
			row_orientation.enabled = False
			row_preset.enabled = False

		# if no Looking Glass was detected AND debug mode is not activated
		if not pylio.DeviceManager.count() and not LookingGlassAddon.debugging_use_dummy_device:

			# deactivate the checkbox
			row_use_device.enabled = False


# ------------- The Lightfield Settings Panel ----------------
# Operator for manual redrawing of the Looking Glass (for manual Live View Mode)
class LOOKINGGLASS_OT_refresh_lightfield(bpy.types.Operator):
	bl_idname = "lookingglass.refresh_lightfield"
	bl_label = "Refresh the lightfield window."
	bl_description = "Render the current view directly in your Looking Glass"
	bl_options = {'REGISTER', 'INTERNAL'}

	def execute(self, context):

		# refresh the Looking Glass
		context.scene.addon_settings.viewport_manual_refresh = True

		return {'FINISHED'}

class LOOKINGGLASS_PT_panel_lightfield(bpy.types.Panel):
	bl_idname = "LOOKINGGLASS_PT_panel_lightfield" # unique identifier for buttons and menu items to reference.
	bl_label = "Lightfield Window" # display name in the interface.
	bl_space_type = "VIEW_3D"
	bl_region_type = "UI"
	bl_category = "Looking Glass"


	# define own poll method to be able to hide / show the panel on demand
	@classmethod
	def poll(self, context):

		# if no Looking Glass is selected OR no lightfield window exists
		if int(context.scene.addon_settings.activeDisplay) == -1 or context.scene.addon_settings.ShowLightfieldWindow == False:

			# this panel is not needed, so return False:
			# the panel will not be drawn
			return False

		else:

			# this panel is needed, so return True:
			# the panel will be drawn
			return True


	# draw the IntProperties for the tiles in the panel
	def draw(self, context):
		layout = self.layout

		# TABS to swap between "live preview" and a "loaded quilt image"
		row = layout.row()
		row.prop(context.scene.addon_settings, "renderMode", expand=True)

		# define a column of UI elements
		column = layout.column(align = True)
		column.separator()

		# If no LookingGlass is selected
		if int(context.scene.addon_settings.activeDisplay) == -1:

			# ... then disable all UI elements except for the drop down menu and the refresh button
			column.enabled = False
			row.enabled = False

		# if the lightfield window is in viewport mode
		if context.scene.addon_settings.renderMode == '0':

			# Lightfield rendering mode & refresh button
			row_orientation = column.row()
			row_orientation.label(text="Lightfield Viewport Modes:")
			row_preset = column.row()
			row_preset.prop(context.scene.addon_settings, "lightfieldMode", text="")
			row_preset.operator("lookingglass.refresh_lightfield", text="", icon='FILE_REFRESH')

			# Preview settings
			row_output = column.row(align = True)
			row_output.prop(context.scene.addon_settings, "lightfield_preview_mode", text="")
			row_output.separator()
			row_output.prop(context.scene.addon_settings, "viewport_use_preview_mode", text="", icon='IMAGE_ZDEPTH')


		# if the lightfield window is in quilt viewer mode
		elif context.scene.addon_settings.renderMode == '1':

			# display all settings for the quilt view mode
			row = column.row(align = True)
			row.label(text="Select a Quilt Image to Display:")

			row = column.row(align = True)
			row.template_ID(context.scene.addon_settings, "quiltImage", open="image.open")



# ------------- Subpanel for overlay & shading settings ----------------
# Operator for manual redrawing of the Looking Glass (for manual Live View Mode)
class LOOKINGGLASS_OT_blender_viewport_assign(bpy.types.Operator):
	bl_idname = "lookingglass.blender_viewport_assign"
	bl_label = "Assign Active Viewport"
	bl_description = "Use the shading and overlay settings of this Blender viewport"
	bl_options = {'REGISTER', 'INTERNAL'}

	def execute(self, context):

		# if the user activated the option to
		# use the shading and overlay settings of the currently used Blender 3D viewport
		if context.scene.addon_settings.viewportMode == 'BLENDER':

			# set the Workspace list to the current workspace
			context.scene.addon_settings.blender_workspace = context.workspace.name

			# set the 3D View list to the current 3D view
			context.scene.addon_settings.blender_view3d = str(context.space_data)

		return {'FINISHED'}

# Panel for shading & overlay setting
class LOOKINGGLASS_PT_panel_overlays_shading(bpy.types.Panel):
	bl_label = "Shading & Overlays Settings" # display name in the interface.
	bl_space_type = "VIEW_3D"
	bl_region_type = "UI"
	bl_category = "Looking Glass"
	bl_options = {'DEFAULT_CLOSED'}
	bl_parent_id = "LOOKINGGLASS_PT_panel_lightfield"


	# define own poll method to be able to hide / show the panel on demand
	@classmethod
	def poll(self, context):

		# if no Looking Glass is selected OR no lightfield window exists
		if int(context.scene.addon_settings.activeDisplay) == -1 or context.scene.addon_settings.ShowLightfieldWindow == False:

			# this panel is not needed, so return False:
			# the panel will not be drawn
			return False

		else:

			# if the render mode is "Live View"
			if int(context.scene.addon_settings.renderMode) == 0:

				# this panel is  needed, so return True:
				# the panel will be drawn
				return True

			# else, if the render mode is "Quilt view"
			elif int(context.scene.addon_settings.renderMode) == 1:

				# this panel is not needed, so return False:
				# the panel will NOT be drawn
				return False


	# draw the IntProperties for the tiles in the panel
	def draw(self, context):
		layout = self.layout

		# define a column of UI elements
		column = layout.column(align = True)

		# if the automatic render mode is active
		if int(context.scene.addon_settings.renderMode) == 0:

			# TABS to swap between "Custom Viewport" and a "Blender Viewport"
			row = column.row(align = True)
			row.prop(context.scene.addon_settings, "viewportMode", expand=True)

			# if the current mode is "BLENDER"
			if context.scene.addon_settings.viewportMode == "BLENDER":

				#column.separator()

				row = column.row(align = True)
				column = layout.column(align = True)
				row = column.row(align = True)
				row.label(text="Mirror Settings From:")
				row = column.row(align = True)
				row.prop(context.scene.addon_settings, "blender_workspace")
				row = column.row(align = True)
				row.prop(context.scene.addon_settings, "blender_view3d")

				column.separator()

				row = column.row(align = True)
				row.operator("lookingglass.blender_viewport_assign")

				# if the chosen workspace has no 3D View
				if context.scene.addon_settings.blender_view3d == "None":

					# disable the manual selection options
					row.enabled = False

			# if the current mode is "CUSTOM"
			elif context.scene.addon_settings.viewportMode == "CUSTOM":

				column.separator()

				row = column.row(align = True)
				row.label(text="Shading")
				#column.separator()
				row.prop(context.scene.addon_settings, "shadingMode", expand=True)
				column.separator()
				row = column.row(align = True)
				column_1 = row.column(align=True)
				column_1.prop(context.scene.addon_settings, "viewport_show_xray")
				column_2 = row.column(align=True)
				column_2.prop(context.scene.addon_settings, "viewport_xray_alpha", slider=True)

				# if x-ray is deactivated
				if context.scene.addon_settings.viewport_show_xray == False:
					# disable the slider
					column_2.enabled = False

				row = column.row(align = True)
				row.prop(context.scene.addon_settings, "viewport_use_dof")

				column.separator()

				row = column.row(align = True)
				row.label(text="Guides")
				row = column.row(align = True)
				row.prop(context.scene.addon_settings, "viewport_show_floor")
				row.prop(context.scene.addon_settings, "viewport_show_axes", toggle=1)
				column.separator()
				row = column.row(align = True)
				row.prop(context.scene.addon_settings, "viewport_grid_scale")

				column.separator()

				row = column.row(align = True)
				row.label(text="Objects")
				row = column.row(align = True)
				column_1 = row.column(align = True)
				column_1.prop(context.scene.addon_settings, "viewport_show_extras")
				column_1.prop(context.scene.addon_settings, "viewport_show_relationship_lines")
				column_1.prop(context.scene.addon_settings, "viewport_show_outline_selected")

				column_2 = row.column(align = True)
				column_2.prop(context.scene.addon_settings, "viewport_show_bones")
				column_2.prop(context.scene.addon_settings, "viewport_show_motion_paths")
				column_2.prop(context.scene.addon_settings, "viewport_show_origins")
				column_2.prop(context.scene.addon_settings, "viewport_show_origins_all")

				column.separator()

				row = column.row(align = True)
				row = row.label(text="Geometry")
				row = column.row(align = True)
				column_1 = row.column(align=True)
				column_1.prop(context.scene.addon_settings, "viewport_show_wireframes")
				column_2 = row.column(align=True)
				column_2.prop(context.scene.addon_settings, "viewport_wireframe_threshold", slider=True)
				row = column.row(align = True)
				row.prop(context.scene.addon_settings, "viewport_show_face_orientation")

				# if no wireframes shall be displayed
				if context.scene.addon_settings.viewport_show_wireframes == False:
					# disable the slider
					column_2.enabled = False
