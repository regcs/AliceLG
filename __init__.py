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

# -------------------- DEFINE ADDON ----------------------
bl_info = {
	"name": "Alice/LG",
	"author": "Christian Stolze",
	"version": (1, 0, 0),
	"blender": (2, 90, 0),
	"location": "3D View > Looking Glass Tab",
	"description": "Alice/LG takes your artworks thorugh the Looking Glass (lightfield displays)",
	"category": "View",
	"wiki_url": "",
    "warning": "",
    "doc_url": "",
    "tracker_url": ""
}

# this is only for debugging purposes
debugging_use_dummy_device = True



# ------------- LOAD ALL INTERNAL MODULES ----------------
# required for proper reloading of the addon by using F8
if "bpy" in locals():

	import importlib

	# reload the modal operators for the viewport & quilt rendering
	importlib.reload(operators.looking_glass_viewport)
	importlib.reload(operators.looking_glass_render_quilt)

	# TODO: Is there a better way to share global variables between all addon files and operators?
	importlib.reload(operators.looking_glass_global_variables)

	# reload the Holoplay Core SDK Python Wrapper
	importlib.reload(operators.libHoloPlayCore)

else:

	# import the modal operators for the viewport & quilt rendering
	from .operators.looking_glass_viewport import *
	from .operators.looking_glass_render_quilt import *

	# TODO: Is there a better way to share global variables between all addon files and operators?
	from .operators.looking_glass_global_variables import *

	# import the Holoplay Core SDK Python Wrapper
	from .operators import libHoloPlayCore as hpc





# ------------- LOAD ALL REQUIRED PYTHON MODULES ----------------
# NOTE: This needs to be called after loading the internal modules,
# 		because we need to check if "bpy" was already loaded for reload
import bpy
import platform
import ctypes
from bpy.types import AddonPreferences, PropertyGroup
from bpy.props import FloatProperty, PointerProperty
from bpy.app.handlers import persistent

# check, if a supported version of Blender is executed
if bpy.app.version < (2, 90, 0):
	raise Exception()




# ------------- DEFINE ADDON PREFERENCES ----------------
# Preferences pane for this Addon in the Blender preferences
class LookingGlassAddonPreferences(AddonPreferences):
	bl_idname = __name__

	# libpath: bpy.props.StringProperty(
	# 								   name="HoloPlayCore SDK",
	# 								   subtype='FILE_PATH',
	# 								   default = ""
	# 								   )
	#
	# def draw(self, context):
	#
	# 	# Lightfield
	# 	layout = self.layout
	# 	layout.prop(context.scene.settings, "viewport_cursor_color")



# ------------- Define update, getter, and setter functions ---------
# Preferences pane for this Addon in the Blender preferences
class LookingGlassAddonFunctions:

	# obtain list of connected Looking Glasses
	def LookingGlassDeviceList():

		# CREATE A LIST OF DICTIONARIES OF ALL CONNECTED DEVICES
		########################################################
		# empty the existing list
		LookingGlassAddon.deviceList.clear()

		# if the HoloPlayService was detected
		if LookingGlassAddon.HoloPlayService == True:

			# allocate a memory buffer for string information send by the Holoplay Service
			buffer = ctypes.create_string_buffer(1000)

			# Query the Holoplay Service to update the device information
			hpc.RefreshState()

			# for each connected device
			for dev_index in range(hpc.GetNumDevices()):

				#
				print(" ### Display ", dev_index, ":")

				# get device name
				hpc.GetDeviceHDMIName(dev_index, buffer, 1000)
				dev_name = buffer.value.decode('ascii').strip()

				# get device serial
				hpc.GetDeviceType(dev_index, buffer, 1000)
				dev_serial = buffer.value.decode('ascii').strip()

				# get device type
				hpc.GetDeviceType(dev_index, buffer, 1000)
				dev_type = buffer.value.decode('ascii').strip()
				if dev_type == "standard":

					dev_type = "8.9'' Looking Glass"

				elif dev_type == "portrait":

					dev_type = "7.9'' Looking Glass Portrait"

				elif dev_type == "large":

					dev_type = "15.6'' Looking Glass"

				elif dev_type == "pro":

					dev_type = "15.6'' Pro Looking Glass"

				if dev_type == "8k":

					dev_type = "8k Looking Glass"


				# make an entry in the deviceList
				LookingGlassAddon.deviceList.append(
												{
													# device information
													'index': dev_index,
													'name': dev_name,
													'serial': dev_serial,
													'type': dev_type,

													# window & screen properties
													'x': hpc.GetDevicePropertyWinX(dev_index),
													'y': hpc.GetDevicePropertyWinY(dev_index),
													'width': hpc.GetDevicePropertyScreenW(dev_index),
													'height': hpc.GetDevicePropertyScreenH(dev_index),
													'aspectRatio': hpc.GetDevicePropertyDisplayAspect(dev_index),

													# calibration data
													'pitch': hpc.GetDevicePropertyPitch(dev_index),
													'tilt': hpc.GetDevicePropertyTilt(dev_index),
													'center': hpc.GetDevicePropertyCenter(dev_index),
													'subp': hpc.GetDevicePropertySubp(dev_index),
													'fringe': hpc.GetDevicePropertyFringe(dev_index),
													'ri': hpc.GetDevicePropertyRi(dev_index),
													'bi': hpc.GetDevicePropertyBi(dev_index),
													'invView': hpc.GetDevicePropertyInvView(dev_index),

													# viewcone
													'viewCone': hpc.GetDevicePropertyFloat(dev_index, b"/calibration/viewCone/value")
												}
				)
				print("   - device info:", LookingGlassAddon.deviceList[-1])


		# TODO: Remove this, it's only for debugging
		if debugging_use_dummy_device == True:
			# we add a dummy element
			LookingGlassAddon.deviceList.append({'index': len(LookingGlassAddon.deviceList), 'name': 'LKG03xABNYQtR', 'serial': 'portrait', 'type': "7.9'' Looking Glass", 'x': -1536, 'y': 0, 'width': 1536, 'height': 2048, 'aspectRatio': 0.75, 'pitch': 354.70953369140625, 'tilt': -0.11324916034936905, 'center': -0.11902174353599548, 'subp': 0.0001302083401242271, 'fringe': 0.0, 'ri': 0, 'bi': 2, 'invView': 1, 'viewCone': 58.0})
			#LookingGlassAddon.deviceList.append({'index': 0, 'name': 'LKG03xABNYQtR', 'serial': 'standard', 'type': "8.9'' Looking Glass", 'x': -2560, 'y': 0, 'width': 2560, 'height': 1600, 'aspectRatio': 1.600000023841858, 'pitch': 354.70953369140625, 'tilt': -0.11324916034936905, 'center': -0.11902174353599548, 'subp': 0.0001302083401242271, 'fringe': 0.0, 'ri': 0, 'bi': 2, 'invView': 1, 'viewCone': 40.0})
			print("   - device info:", LookingGlassAddon.deviceList[len(LookingGlassAddon.deviceList) - 1])


	# This callback is required to be able to update the list of connected Looking Glass devices
	def looking_glass_list_callback(self, context):

		# prepare a item list with entries of the form "identifier, name, description"
		items = []

		# if at least one Looking Glass is connected
		if len(LookingGlassAddon.deviceList) > 0:

			# then for each display in the device list
			for device in LookingGlassAddon.deviceList:

				# add an entry in the item list
				items.append((str(device['index']), 'Display ' + str(device['index']) + ': ' + device['type'], 'Use this Looking Glass for lightfield rendering.'))

		else:

			# add an entry to notify the user about the missing Looking Glass
			items.append(('-1', 'No Looking Glass Found', 'Please connect a Looking Glass.'))



		# return the item list
		return items

	# poll function for the Looking Glass camera selection
	# this prevents that an object is picked, which is no camera
	def camera_selection_poll(self, object):

		return object.type == 'CAMERA'

	# Update the Boolean property that creates the hologram rendering window
	def ShowLightfieldWindow_update(self, context):

		# if the bool property was set to True
		if self['ShowLightfieldWindow'] == True:

			# Create a new main window
			bpy.ops.wm.window_new_main()

			# assume the last window in the screen list is the created window
			LookingGlassAddon.lightfieldWindow = context.window_manager.windows[-1]

			# Change the area type of the last area of the looking glass window to SpaceView3D
			area = LookingGlassAddon.lightfieldWindow.screen.areas[-1]
			area.type = "VIEW_3D"

			# hide all panels in the image editor and make the area full screen
			bpy.ops.screen.screen_full_area(dict(window=LookingGlassAddon.lightfieldWindow, screen=LookingGlassAddon.lightfieldWindow.screen, area=area), 'INVOKE_DEFAULT', use_hide_panels=True)

			# Invoke modal operator for the lightfield rendering
			bpy.ops.render.lightfield(dict(window=LookingGlassAddon.lightfieldWindow), 'INVOKE_DEFAULT')

		else:

			# if a lightfield window still exists
			if LookingGlassAddon.lightfieldWindow != None:

				# close this window
				bpy.ops.wm.window_close(dict(window=LookingGlassAddon.lightfieldWindow))



	# Update the Boolean property that creates the hologram rendering window
	def toggleFullscrenMode(self, context):

		# if the bool property was set to True
		if self['toggleLightfieldWindowFullscreen'] == True:

			# if the lightfield window exists
			if LookingGlassAddon.lightfieldWindow != None:

				# make it fullscreen
				bpy.ops.wm.window_fullscreen_toggle(dict(window=LookingGlassAddon.lightfieldWindow))

		else:

			# if a lightfield window still exists
			if LookingGlassAddon.lightfieldWindow != None:

				# toggle fullscreen mode off
				bpy.ops.wm.window_fullscreen_toggle(dict(window=LookingGlassAddon.lightfieldWindow))



	# update function for the viewport mode
	def update_track_viewport(self, context):

		if context != None:

			# if the settings shall be taken from the current viewport
			if context.scene.settings.viewportMode == 'BLENDER':

				# if the viewport tracking is not active
				if context.scene.settings.blender_track_viewport == False:

					# save the current space data in a global variable
					LookingGlassAddon.BlenderViewport = context.space_data

					# set the Workspace list to the current workspace
					context.scene.settings.blender_workspace = context.workspace.name

					# set the 3D View list to the current 3D view
					context.scene.settings.blender_view3d = str(LookingGlassAddon.BlenderViewport)

			# if the settings shall be taken from the current viewport
			elif context.scene.settings.viewportMode == 'CUSTOM':

				# reset the global variable
				LookingGlassAddon.BlenderViewport = None

		return None


	# update function for the workspace selection
	def update_workspace_selection(self, context):

		if context != None:

			# if the settings shall be taken from the current viewport
			if context.scene.settings.viewportMode == 'BLENDER':

				# if the viewport tracking is not active
				if context.scene.settings.blender_track_viewport == False:

					# status variable
					success = False

					# TODO: At the moment, we only

					# find the correct SpaceView3D object
					for screen in bpy.data.workspaces[context.scene.settings.blender_workspace].screens:
						for area in screen.areas:
							for space in area.spaces:

								# if this is the correct space
								if str(space) == str(context.scene.settings.blender_view3d):

									# save the space object in the global variable
									LookingGlassAddon.BlenderViewport = space
									success = True
									break

					# if the current space was not found in the chosen workspace
					if success == False:

						# find and use the first SpaceView3D object of the workspace
						for screen in bpy.data.workspaces[context.scene.settings.blender_workspace].screens:
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
						context.scene.settings.blender_view3d = "None"

						# fall back to the use of the custom settings
						LookingGlassAddon.BlenderViewport = None

		return None


	# update function for the viewport selection
	def update_viewport_selection(self, context):

		if context != None:

			# if the settings shall be taken from the current viewport
			if context.scene.settings.viewportMode == 'BLENDER':

				# if the viewport tracking is not active
				if context.scene.settings.blender_track_viewport == False:

					# if a viewport is chosen
					if str(context.scene.settings.blender_view3d) != "None":

						# find the correct SpaceView3D object
						for screen in bpy.data.workspaces[context.scene.settings.blender_workspace].screens:
							for area in screen.areas:
								for space in area.spaces:

									# if this is the correct space
									if str(space) == str(context.scene.settings.blender_view3d):

										# save the space object in the global variable
										LookingGlassAddon.BlenderViewport = space
										break
					else:

						# fall back to the use of the custom settings
						LookingGlassAddon.BlenderViewport = None

		return None


	# update function for property updates concerning camera clipping in the livew view
	def update_camera_setting(self, context):

		# if a camera was selected
		if context.scene.settings.lookingglassCamera != None:

			# apply the settings to the selected camera object
			camera = context.scene.settings.lookingglassCamera


			# TODO: Check if this is really helpful. Maybe remove later or refine.
			# keep clip end behind the clip start
			if context.scene.settings.clip_end < context.scene.settings.clip_start:
				context.scene.settings.clip_end = context.scene.settings.clip_start

			# keep clip start in front of the clip end
			if context.scene.settings.clip_start > context.scene.settings.clip_end:
				context.scene.settings.clip_start = context.scene.settings.clip_end

			# keep focal plane within the clipping volume
			if context.scene.settings.focalPlane < context.scene.settings.clip_start:
				context.scene.settings.focalPlane = context.scene.settings.clip_start
			elif context.scene.settings.focalPlane > context.scene.settings.clip_end:
				context.scene.settings.focalPlane = context.scene.settings.clip_end



			# apply the clipping value of the camera
			camera.data.clip_start = context.scene.settings.clip_start
			camera.data.clip_end = context.scene.settings.clip_end

			# if a valid space is existing
			if LookingGlassAddon.lightfieldSpace != None:

				# set space to the selected camera
				LookingGlassAddon.lightfieldSpace.camera = context.scene.settings.lookingglassCamera
				LookingGlassAddon.lightfieldSpace.use_local_camera = True
				LookingGlassAddon.lightfieldSpace.lock_camera = True

				# set view mode to "CAMERA VIEW"
				LookingGlassAddon.lightfieldSpace.region_3d.view_perspective = 'CAMERA'

				#print("SPACE SETTINGS UPDATED: ", LookingGlassAddon.lightfieldSpace, LookingGlassAddon.lightfieldSpace.camera)

		else:

			# if a valid space is existing
			if LookingGlassAddon.lightfieldSpace != None:

				# set space camera to None
				LookingGlassAddon.lightfieldSpace.camera = None

				# set view mode to "PERSPECTIVE VIEW"
				LookingGlassAddon.lightfieldSpace.region_3d.view_perspective = 'PERSP'


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
		if context.scene.settings.blender_workspace in bpy.data.workspaces:

			# find all 3D Views in the selected Workspace
			for screen in bpy.data.workspaces[context.scene.settings.blender_workspace].screens:
				for area in screen.areas:
					for space in area.spaces:
						# TODO: the check "space != LookingGlassAddon.lightfieldSpace" is somewhat hacky. But without it, an additional element is created in the list. Need to clarify later, why ...
						if space.type == 'VIEW_3D' and space != LookingGlassAddon.lightfieldSpace:

							# add an item to the item list
							items.append((str(space), 'Viewport ' + str(len(items) + 1), 'The Blender viewport to which the Looking Glass adjusts'))

		# if no spaces were found
		if len(items) == 0:

			# add a dummy entry to the item list
			items.append(('None', 'None', 'The Blender viewport to which the Looking Glass adjusts'))

		# return the item list
		return items




# Preferences pane for this Addon in the Blender preferences
class LookingGlassAddonSettings(bpy.types.PropertyGroup):

	# This callback is required to be able to update the list of connected Looking Glass devices
	def looking_glass_list_callback(self, context):

		# prepare a item list with entries of the form "identifier, name, description"
		items = []

		# if at least one Looking Glass is connected
		if len(LookingGlassAddon.deviceList) > 0:

			# then for each display in the device list
			for device in LookingGlassAddon.deviceList:

				# add an entry in the item list
				items.append((str(device['index']), 'Display ' + str(device['index']) + ': ' + device['type'], 'Use this Looking Glass for lightfield rendering.'))

		else:

			# add an entry to notify the user about the missing Looking Glass
			items.append(('-1', 'No Looking Glass Found', 'Please connect a Looking Glass.'))



		# return the item list
		return items



	# PANEL: GENERAL
	# a list of connected Looking Glass displays
	activeDisplay: bpy.props.EnumProperty(
										items = looking_glass_list_callback,
										default=0,
										name="Please select a Looking Glass."
										)

	# a boolean to toogle the render window on or off
	ShowLightfieldWindow: bpy.props.BoolProperty(
											name="Lightfield Window",
											description = "Creates a window for the lightfield rendering. You need to move the window manually to the Looking Glass screen and toogle it fullscreen",
											default = False,
											update=LookingGlassAddonFunctions.ShowLightfieldWindow_update
											)

	# a boolean to toogle the render window on or off
	toggleLightfieldWindowFullscreen: bpy.props.BoolProperty(
											name="Toggle Fullscreen Mode",
											description = "Press this button, if the lightfield window was moved to the Looking Glass to make it fullscreen.",
											default = False,
											update=LookingGlassAddonFunctions.toggleFullscrenMode
											)

	# the index of the lightfield window among the Blender windows
	lightfieldWindowIndex: bpy.props.IntProperty(
											name="Lightfield Window",
											default = -1,
											)

	viewResolution: bpy.props.EnumProperty(
										items = [
												('0', 'Resolution: 512 x 256 px', '2k quilt, 32 views'),
												('1', 'Resolution: 819 x 455 px', '4k quilt, 45 views'),
												('2', 'Resolution: 1638 x 910 px', '8k quilt, 45 views')],
										default='1',
										name="View Resolution"
										)

	debug_view: bpy.props.BoolProperty(
										name="Debug View",
										description="If enabled, the Looking Glass displays all quilts in the debug view",
										default = False,
										)


	# PANEL: CAMERA SETTINGS
	# pointer property that can be used to load a pre-rendered quilt image
	lookingglassCamera: bpy.props.PointerProperty(
										name="",
										type=bpy.types.Object,
										description = "Camera object, which defines the Looking Glass content",
										poll = LookingGlassAddonFunctions.camera_selection_poll,
										update = LookingGlassAddonFunctions.update_camera_setting
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
										min = 0,
										precision = 1,
										step = 10,
										description = "Far clipping plane of the Looking Glass frustum.",
										update = LookingGlassAddonFunctions.update_camera_setting,
										)

	clip_end: bpy.props.FloatProperty(
										name = "Clip End",
										default = 6.5,
										min = 0,
										precision = 1,
										step = 10,
										description = "Far clipping plane of the Looking Glass frustum.",
										update = LookingGlassAddonFunctions.update_camera_setting,
										)

	# the virtual distance of the plane, which represents the focal plane of the Looking Glass
	focalPlane: bpy.props.FloatProperty(
										name = "Focal Plane",
										default = 5,
										min = 0,
										precision = 1,
										step = 10,
										description = "Virtual distance to the focal plane. (This plane is directly mapped to the LCD display of the Looking Glass)",
										update = LookingGlassAddonFunctions.update_camera_setting,
										)


	# PANEL: LIGHTFIELD WINDOW SETTINGS
	# UI elements for user control
	renderMode: bpy.props.EnumProperty(
										items = [('0', 'Viewport', 'Viewport rendering of the current scene within the Looking Glass', 'VIEW3D', 0),
												 ('1', 'Quilt Viewer', 'Display a prerendered quilt image in the Looking Glass', 'RENDER_RESULT', 1)],
										default='0',
										name="Render Mode",
										)

	# Lightfield Window Mode
	lightfieldMode: bpy.props.EnumProperty(
										items = [('0', 'Refresh Mode: Automatic', 'Automatically refresh the lightfield viewport'),
												 ('1', 'Refresh Mode: Manual', 'Refresh the lightfield viewport manually')],
										default='0',
										name="Lightfield Window Mode",
										)

	# Lightfield Preview Resolution in Auto lightfield mode
	lightfield_preview_resolution: bpy.props.EnumProperty(
										items = [('0', 'Preview: 512 x 512', '32 views'),],
										default='0',
										name="Lightfield Preview Resolution",
										)

	# pointer property that can be used to load a pre-rendered quilt image
	quiltImage: bpy.props.PointerProperty(
										name="Quilt",
										type=bpy.types.Image,
										description = "Quilt image for display in the Looking Glass"
										)


	viewport_use_lowres_preview: bpy.props.BoolProperty(
										name="Low-resolution Preview",
										description="If enabled, a low-resolution lightfield is rendered during scene changes (for higher render speed)",
										default = True,
										)

	viewport_use_solid_preview: bpy.props.BoolProperty(
										name="Solid Shading Preview",
										description="If enabled, the lightfield is rendered in solid shading mode during scene changes (for higher render speed)",
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

	blender_track_viewport: bpy.props.BoolProperty(
										name="Use Active Viewport Settings",
										description="If enabled, the Looking Glass automatically adjusts to the settings of the currently used Blender viewport",
										default = True,
										update = LookingGlassAddonFunctions.update_track_viewport
										)

	blender_workspace: bpy.props.EnumProperty(
										name="Workspace",
										items = LookingGlassAddonFunctions.workspaces_list_callback,
										default=0,
										update = LookingGlassAddonFunctions.update_workspace_selection
										)

	blender_view3d: bpy.props.EnumProperty(
										name="3D View",
										items = LookingGlassAddonFunctions.view3D_list_callback,
										default=0,
										update = LookingGlassAddonFunctions.update_viewport_selection
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
										update = LookingGlassAddonFunctions.update_camera_setting,
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
										default = False,
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



# ----------------- ADDON INITIALIZATION --------------------
# TODO: Find out what the two arguments are that are required
@persistent
def LookingGlassAddonInitHandler(dummy1, dummy2):

	# Invoke modal operator for the camera frustum rendering
	bpy.ops.render.frustum('INVOKE_DEFAULT')

	# if the lightfield window is active
	if bpy.context.scene.settings.ShowLightfieldWindow == True and bpy.context.scene.settings.lightfieldWindowIndex != -1:
		print("WindowIndex: ", bpy.context.scene.settings.lightfieldWindowIndex)
		# get the lightfield window by the index of this window in the list of windows in the WindowManager
		LookingGlassAddon.lightfieldWindow = bpy.context.window_manager.windows.values()[bpy.context.scene.settings.lightfieldWindowIndex]

		# if the window was found
		if LookingGlassAddon.lightfieldWindow != None:

			# close this window
			bpy.ops.wm.window_close(dict(window=LookingGlassAddon.lightfieldWindow))

			# Create a new main window
			bpy.ops.wm.window_new_main(dict(window=bpy.context.window_manager.windows[0]))

			# assume the last window in the screen list is the created window
			LookingGlassAddon.lightfieldWindow = bpy.context.window_manager.windows[-1]

			# Change the area type of the last area of the looking glass window to SpaceView3D
			area = LookingGlassAddon.lightfieldWindow.screen.areas[-1]
			area.type = "VIEW_3D"

			# hide all panels in the image editor and make the area full screen
			bpy.ops.screen.screen_full_area(dict(window=LookingGlassAddon.lightfieldWindow, screen=LookingGlassAddon.lightfieldWindow.screen, area=area), use_hide_panels=True)

			# Invoke modal operator for the lightfield rendering
			bpy.ops.render.lightfield(dict(window=LookingGlassAddon.lightfieldWindow), 'INVOKE_DEFAULT')


# ----------------- PANEL FOR GENERAL SETTINGS --------------------
# an operator that refreshes the list of connected Looking Glasses
class LOOKINGGLASS_OT_refresh_display_list(bpy.types.Operator):
	bl_idname = "lookingglass.refresh_display_list"
	bl_label = "Refresh list"
	bl_description = "Refreshes the list of connected Looking Glass deviced from the HoloPlay Service"
	bl_options = {'REGISTER', 'INTERNAL'}

	def execute(self, context):

		# update the global list of all connected devices
		LookingGlassAddonFunctions.LookingGlassDeviceList()

		return {'FINISHED'}


# an operator that refreshes the list of connected Looking Glasses
class LOOKINGGLASS_OT_add_camera(bpy.types.Operator):
	bl_idname = "object.add_lookingglass_camera"
	bl_label = "Add Looking Glass Camera"
	bl_description = "Creates a new camera object with settings optimized for the Looking Glass"
	bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

	def execute(self, context):

		# first we add a new camera
		camera_data = bpy.data.cameras.new(name='Looking Glass Camera')
		camera = bpy.data.objects.new('Looking Glass Camera', camera_data)
		bpy.context.scene.collection.objects.link(camera)

		# set the camera position
		camera.location.z = context.scene.settings.focalPlane

		# then we apply all the default settings to the camera
		camera.data.sensor_fit = 'VERTICAL'
		camera.data.angle_y = radians(14)
		camera.data.clip_start = context.scene.settings.clip_start
		camera.data.clip_end = context.scene.settings.clip_end

		# if currently no camera is selected
		if context.scene.settings.lookingglassCamera == None:

			# use the new camera as the Looking Glass Camera
			context.scene.settings.lookingglassCamera = camera

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
		row_1 = column.row(align = True)
		column_1 = row_1.column(align=True)
		row_1a = column_1.row(align = True)
		row_1a.prop(context.scene.settings, "activeDisplay", text="")
		row_1a.operator("lookingglass.refresh_display_list", text="", icon='FILE_REFRESH')
		row_1.separator()

		# Lightfield window & debug button
		column_2 = row_1.column(align=True)
		row_1b = column_2.row(align = True)
		if LookingGlassAddon.lightfieldWindow != None: row_1b.prop(context.scene.settings, "toggleLightfieldWindowFullscreen", text="", toggle=True, icon='FULLSCREEN_ENTER')
		row_1b.prop(context.scene.settings, "ShowLightfieldWindow", text="", toggle=True, icon='WINDOW')

		# Resolution selection of the quilt views
		row_2 = column.row()
		row_2.prop(context.scene.settings, "viewResolution", text="")
		row_2.prop(context.scene.settings, "debug_view", expand=True, text="", icon='TEXTURE')
		column.separator()

		# Button to start rendering a single quilt using the current render settings
		row_3 = column.row()
		render_quilt = row_3.operator("render.quilt", text="Render Quilt", icon='RENDER_STILL')
		#render_quilt.animation = False
		#row_3.enabled = True

		# Button to start rendering a animation quilt using the current render settings
		row_4 = column.row()
		render_quilt = row_4.operator("render.quilt", text="Render Animation Quilt", icon='RENDER_ANIMATION')
		render_quilt.animation = True
		row_4.enabled = True


		# if the HoloPlay Service is NOT available
		if LookingGlassAddon.HoloPlayService == False and debugging_use_dummy_device == False:

			# deactivate the looking glass selection
			row_1a.enabled = False

		# if NO Looking Glass is selected or detected OR the user is in an fullscreen area
		# TODO: Blender doesn't allow creating a new window from a fullscreen area.
		# 		Can we still handle this by using override contexts? Until this is clarified
		#		the button will be disabled in fullscreen areas.
		if int(context.scene.settings.activeDisplay) == -1 or context.screen.show_fullscreen == True:

			# deactivate the lightfield window button and debug button
			row_1b.enabled = False



# ------------- The Camera Settings Panel ----------------
class LOOKINGGLASS_PT_panel_camera(bpy.types.Panel):
	bl_idname = "LOOKINGGLASS_PT_panel_camera" # unique identifier for buttons and menu items to reference.
	bl_label = "Camera Settings" # display name in the interface.
	bl_space_type = "VIEW_3D"
	bl_region_type = "UI"
	bl_category = "Looking Glass"


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

		row_1 = column.row(align = True)
		row_1.prop(context.scene.settings, "lookingglassCamera", icon='VIEW_CAMERA')
		row_1.operator("object.add_lookingglass_camera", text="", icon='ADD')
		row_1.separator()
		row_1.prop(context.scene.settings, "showFrustum", text="", icon='MESH_CUBE')
		row_1.prop(context.scene.settings, "showFocalPlane", text="", icon='MESH_PLANE')

		column.separator()

		# display the clipping settings
		row_2 = column.row(align = True)
		row_2.prop(context.scene.settings, "clip_start")
		row_3 = column.row(align = True)
		row_3.prop(context.scene.settings, "clip_end")
		row_4 = column.row(align = True)
		row_4.prop(context.scene.settings, "focalPlane")

		# if no camera is Selected
		if context.scene.settings.lookingglassCamera == None:

			# disable clipping and focal plane modifieres
			row_2.enabled = False
			row_3.enabled = False
			row_4.enabled = False




# ------------- The Lightfield Settings Panel ----------------
# Operator for manual redrawing of the Looking Glass (for manual Live View Mode)
class LOOKINGGLASS_OT_refresh_lightfield(bpy.types.Operator):
	bl_idname = "lookingglass.refresh_lightfield"
	bl_label = "Refresh the lightfield window."
	bl_description = "Render the current view directly in your Looking Glass"
	bl_options = {'REGISTER', 'INTERNAL'}

	def execute(self, context):

		# refresh the Looking Glass
		context.scene.settings.viewport_manual_refresh = True

		return {'FINISHED'}

class LOOKINGGLASS_PT_panel_lightfield(bpy.types.Panel):
	""" Lightfield Viewport Settings """
	bl_idname = "LOOKINGGLASS_PT_panel_lightfield" # unique identifier for buttons and menu items to reference.
	bl_label = "Lightfield Window" # display name in the interface.
	bl_space_type = "VIEW_3D"
	bl_region_type = "UI"
	bl_category = "Looking Glass"


	# define own poll method to be able to hide / show the panel on demand
	@classmethod
	def poll(self, context):

		# if no Looking Glass is selected OR no lightfield window exists
		if int(context.scene.settings.activeDisplay) == -1 or context.scene.settings.ShowLightfieldWindow == False:

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
		row.prop(context.scene.settings, "renderMode", expand=True)

		# define a column of UI elements
		column = layout.column(align = True)
		column.separator()

		# If no LookingGlass is selected
		if int(context.scene.settings.activeDisplay) == -1:

			# ... then disable all UI elements except for the drop down menu and the refresh button
			column.enabled = False
			row.enabled = False

		# if the lightfield window is in viewport mode
		if context.scene.settings.renderMode == '0':

			# Lightfield rendering mode & refresh button
			row_1 = column.row()
			row_1.label(text="Lightfield Window Mode:")
			row_2 = column.row()
			row_2.prop(context.scene.settings, "lightfieldMode", text="")
			row_2.operator("lookingglass.refresh_lightfield", text="", icon='FILE_REFRESH')

			# Preview settings
			row_3 = column.row(align = True)
			row_3.prop(context.scene.settings, "lightfield_preview_resolution", text="")
			row_3.separator()
			row_3.prop(context.scene.settings, "viewport_use_lowres_preview", text="", icon='IMAGE_ZDEPTH')
			row_3.prop(context.scene.settings, "viewport_use_solid_preview", text="", icon='SHADING_SOLID')
			column.separator()

			# Lightfield cursor settings
			row_4 = column.row()
			row_4.label(text="Lightfield Cursor:")
			row_5 = column.row(align = True)
			row_5.prop(context.scene.settings, "viewport_cursor_size", text="Size", slider=True)
			row_5.prop(context.scene.settings, "viewport_show_cursor", text="", icon='RESTRICT_SELECT_OFF')
			row_6 = column.row()
			row_6.prop(context.scene.settings, "viewport_cursor_color", text="")


		# if the lightfield window is in quilt viewer mode
		elif context.scene.settings.renderMode == '1':

			# display all settings for the quilt view mode
			row = column.row(align = True)
			row.label(text="Select a Quilt Image to Display:")

			row = column.row(align = True)
			row.template_ID(context.scene.settings, "quiltImage", open="image.open")



# ------------- Panel for overlay settings ----------------
class LOOKINGGLASS_PT_panel_overlays_shading(bpy.types.Panel):

	""" Looking Glass Properties """
	#bl_parent_id = "LOOKINGGLASS_PT_panel_lightfield"
	bl_label = "Shading & Overlays Settings" # display name in the interface.
	bl_space_type = "VIEW_3D"
	bl_region_type = "UI"
	bl_category = "Looking Glass"
	#bl_options = {'DEFAULT_CLOSED'}


	# define own poll method to be able to hide / show the panel on demand
	@classmethod
	def poll(self, context):

		# if no Looking Glass is selected OR no lightfield window exists
		if int(context.scene.settings.activeDisplay) == -1 or context.scene.settings.ShowLightfieldWindow == False:

			# this panel is not needed, so return False:
			# the panel will not be drawn
			return False

		else:

			# if the render mode is "Live View"
			if int(context.scene.settings.renderMode) == 0:

				# this panel is  needed, so return True:
				# the panel will be drawn
				return True

			# else, if the render mode is "Quilt view"
			elif int(context.scene.settings.renderMode) == 1:

				# this panel is not needed, so return False:
				# the panel will NOT be drawn
				return False


	# draw the IntProperties for the tiles in the panel
	def draw(self, context):
		layout = self.layout

		# define a column of UI elements
		column = layout.column(align = True)

		# if the automatic render mode is active
		if int(context.scene.settings.renderMode) == 0:

			# TABS to swap between "Custom Viewport" and a "Blender Viewport"
			row = column.row(align = True)
			row.prop(context.scene.settings, "viewportMode", expand=True)

			# if the current mode is "BLENDER"
			if context.scene.settings.viewportMode == "BLENDER":

				column.separator()

				row = column.row(align = True)
				row.prop(context.scene.settings, "blender_track_viewport")

				# if the viewport tracking is not activated
				if context.scene.settings.blender_track_viewport == False:

					column = layout.column(align = True)
					row = column.row(align = True)
					row.label(text="Viewport to Copy Settings from:")
					row = column.row(align = True)
					row.prop(context.scene.settings, "blender_workspace")
					row = column.row(align = True)
					row.prop(context.scene.settings, "blender_view3d")

					# if the chosen workspace has no 3D View
					if context.scene.settings.blender_view3d == "None":

						# disable the manual selection options
						row.enabled = False

			# if the current mode is "CUSTOM"
			elif context.scene.settings.viewportMode == "CUSTOM":

				column.separator()

				row = column.row(align = True)
				row.label(text="Shading")
				#column.separator()
				row.prop(context.scene.settings, "shadingMode", expand=True)
				column.separator()
				row = column.row(align = True)
				column_1 = row.column(align=True)
				column_1.prop(context.scene.settings, "viewport_show_xray")
				column_2 = row.column(align=True)
				column_2.prop(context.scene.settings, "viewport_xray_alpha", slider=True)

				# if x-ray is deactivated
				if context.scene.settings.viewport_show_xray == False:
					# disable the slider
					column_2.enabled = False

				row = column.row(align = True)
				row.prop(context.scene.settings, "viewport_use_dof")

				column.separator()

				row = column.row(align = True)
				row.label(text="Guides")
				row = column.row(align = True)
				row.prop(context.scene.settings, "viewport_show_floor")
				row.prop(context.scene.settings, "viewport_show_axes", toggle=1)
				column.separator()
				row = column.row(align = True)
				row.prop(context.scene.settings, "viewport_grid_scale")

				column.separator()

				row = column.row(align = True)
				row.label(text="Objects")
				row = column.row(align = True)
				column_1 = row.column(align = True)
				column_1.prop(context.scene.settings, "viewport_show_extras")
				column_1.prop(context.scene.settings, "viewport_show_relationship_lines")
				column_1.prop(context.scene.settings, "viewport_show_outline_selected")

				column_2 = row.column(align = True)
				column_2.prop(context.scene.settings, "viewport_show_bones")
				column_2.prop(context.scene.settings, "viewport_show_motion_paths")
				column_2.prop(context.scene.settings, "viewport_show_origins")
				column_2.prop(context.scene.settings, "viewport_show_origins_all")

				column.separator()

				row = column.row(align = True)
				row = row.label(text="Geometry")
				row = column.row(align = True)
				column_1 = row.column(align=True)
				column_1.prop(context.scene.settings, "viewport_show_wireframes")
				column_2 = row.column(align=True)
				column_2.prop(context.scene.settings, "viewport_wireframe_threshold", slider=True)
				row = column.row(align = True)
				row.prop(context.scene.settings, "viewport_show_face_orientation")

				# if no wireframes shall be displayed
				if context.scene.settings.viewport_show_wireframes == False:
					# disable the slider
					column_2.enabled = False




# ---------- ADDON INITIALIZATION & CLEANUP -------------
def register():

	print("Initializing Holo Play Core:")
	# define name for registration
	LookingGlassAddon.name = bl_info['name'] + " v" + '.'.join(str(v) for v in bl_info['version'])

	print(" # Registering at Holoplay Service as: " + LookingGlassAddon.name)

	# initialize HoloPlay Core SDK
	errco = hpc.InitializeApp(LookingGlassAddon.name.encode(), hpc.license_type.LICENSE_NONCOMMERCIAL.value)

	# register all classes of the addon
	# Preferences
	bpy.utils.register_class(LookingGlassAddonPreferences)
	bpy.utils.register_class(LookingGlassAddonSettings)
	bpy.utils.register_class(LOOKINGGLASS_OT_refresh_display_list)
	bpy.utils.register_class(LOOKINGGLASS_OT_refresh_lightfield)
	bpy.utils.register_class(LOOKINGGLASS_OT_add_camera)

	# Looking Glass quilt rendering
	bpy.utils.register_class(LOOKINGGLASS_OT_render_quilt)

	# Looking Glass viewport & camera frustum
	bpy.utils.register_class(LOOKINGGLASS_OT_render_lightfield)
	bpy.utils.register_class(LOOKINGGLASS_OT_render_frustum)

	# UI elements
	bpy.utils.register_class(LOOKINGGLASS_PT_panel_general)
	bpy.utils.register_class(LOOKINGGLASS_PT_panel_camera)
	bpy.utils.register_class(LOOKINGGLASS_PT_panel_lightfield)
	bpy.utils.register_class(LOOKINGGLASS_PT_panel_overlays_shading)

	# load the panel variables
	bpy.types.Scene.settings = bpy.props.PointerProperty(type=LookingGlassAddonSettings)

	# setup the quilt presets
	LookingGlassAddon.setupQuiltPresets()

	# run initialization helper function as app handler
	# NOTE: this is needed to run certain modal operators of the addon on startup
	#		or when a new file is loaded
	bpy.app.handlers.load_post.append(LookingGlassAddonInitHandler)



	# if no errors were detected
	if errco == 0 or debugging_use_dummy_device == True:

		# set status variable
		LookingGlassAddon.HoloPlayService = True

		# allocate string buffer
		buffer = ctypes.create_string_buffer(1000)

		# get HoloPlay Service Version
		hpc.GetHoloPlayServiceVersion(buffer, 1000)
		print(" # HoloPlay Service version: " + buffer.value.decode('ascii').strip())

		# get HoloPlay Core SDK version
		hpc.GetHoloPlayCoreVersion(buffer, 1000)
		print(" # HoloPlay Core SDK version: " + buffer.value.decode('ascii').strip())

		# get number of devices
		print(" # Number of connected displays: " + str(hpc.GetNumDevices()))

		# obtain the device list
		LookingGlassAddonFunctions.LookingGlassDeviceList()

		# get shader source codes
		# TODO: Maybe it would make sense to load the shader directly here
		#		and pass it on to the rendering operators as global variable
		LookingGlassAddon.lightfieldVertexShaderSource = hpc.LightfieldVertShaderGLSL
		LookingGlassAddon.lightfieldFragmentShaderSource = hpc.LightfieldFragShaderGLSL

		print("########################################################################")
		print("Initialized the Looking Glass Addon.")

	else:

		# prepare the error string from the error code
		if (errco == hpc.client_error.CLIERR_NOSERVICE.value):
			errstr = "HoloPlay Service not running"

		elif (errco == hpc.client_error.CLIERR_SERIALIZEERR.value):
			errstr = "Client message could not be serialized"

		elif (errco == hpc.client_error.CLIERR_VERSIONERR.value):
			errstr = "Incompatible version of HoloPlay Service";

		elif (errco == hpc.client_error.CLIERR_PIPEERROR.value):
			errstr = "Interprocess pipe broken"

		elif (errco == hpc.client_error.CLIERR_SENDTIMEOUT.value):
			errstr = "Interprocess pipe send timeout"

		elif (errco == hpc.client_error.CLIERR_RECVTIMEOUT.value):
			errstr = "Interprocess pipe receive timeout"

		else:
			errstr = "Unknown error";

		# print the error
		print(" # Client access error (code = ", errco, "):", errstr)

		print("########################################################################")
		print("Looking Glass Connection failed. No lightfield viewport available.")


def unregister():

	# if the addon was previously successfully initialized
	if LookingGlassAddon.HoloPlayService == True:

		# Unregister at the Holoplay Service
		hpc.CloseApp()

	# remove initialization helper app handler
	bpy.app.handlers.load_post.remove(LookingGlassAddonInitHandler)

	# unregister all classes
	bpy.utils.unregister_class(LookingGlassAddonPreferences)
	bpy.utils.unregister_class(LookingGlassAddonSettings)
	bpy.utils.unregister_class(LOOKINGGLASS_PT_panel_general)
	bpy.utils.unregister_class(LOOKINGGLASS_PT_panel_camera)
	bpy.utils.unregister_class(LOOKINGGLASS_PT_panel_lightfield)
	bpy.utils.unregister_class(LOOKINGGLASS_PT_panel_overlays_shading)

	bpy.utils.unregister_class(LOOKINGGLASS_OT_refresh_display_list)
	bpy.utils.unregister_class(LOOKINGGLASS_OT_refresh_lightfield)
	bpy.utils.unregister_class(LOOKINGGLASS_OT_add_camera)

	bpy.utils.unregister_class(LOOKINGGLASS_OT_render_frustum)
	bpy.utils.unregister_class(LOOKINGGLASS_OT_render_lightfield)
	bpy.utils.unregister_class(LOOKINGGLASS_OT_render_quilt)

	# delete all variables
	del bpy.types.Scene.settings

	print("########################################################################")
	print("Deinitialized the Looking Glass Addon.")
