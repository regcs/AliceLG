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
	"name": "Alice/LG-beta",
	"author": "Christian Stolze",
	"version": (1, 1, 5),
	"blender": (2, 83, 0),
	"location": "3D View > Looking Glass Tab",
	"description": "Alice/LG takes your artworks through the Looking Glass (lightfield displays)",
	"category": "View",
	"warning": "",
	"doc_url": "",
	"tracker_url": ""
}

# this is only for debugging purposes
debugging_use_dummy_device = False



# ------------- LOAD ALL INTERNAL MODULES ----------------
# required for proper reloading of the addon by using F8
if "bpy" in locals():

	import importlib

	# reload the modal operators for the viewport & quilt rendering
	importlib.reload(operators.looking_glass_viewport)
	importlib.reload(operators.looking_glass_render_quilt)

	# TODO: Is there a better way to share global variables between all addon files and operators?
	importlib.reload(operators.looking_glass_global_variables)

	# reload the free Holoplay Core SDK
	importlib.reload(operators.libHoloPlayCore.freeHoloPlayCoreAPI)

else:

	# import the modal operators for the viewport & quilt rendering
	from .operators.looking_glass_viewport import *
	from .operators.looking_glass_render_quilt import *

	# TODO: Is there a better way to share global variables between all addon files and operators?
	from .operators.looking_glass_global_variables import *

	# import the Holoplay Core SDK Python Wrapper
	#from .operators import libHoloPlayCore as hpc
	from .operators import libHoloPlayCore
	hpc = libHoloPlayCore.freeHoloPlayCoreAPI()





# ------------- LOAD ALL REQUIRED PYTHON MODULES ----------------
# NOTE: This needs to be called after loading the internal modules,
# 		because we need to check if "bpy" was already loaded for reload
import bpy
import sys, platform
import ctypes
from pprint import pprint
from bpy.types import AddonPreferences, PropertyGroup
from bpy.props import FloatProperty, PointerProperty
from bpy.app.handlers import persistent

# check, if a supported version of Blender is executed
if bpy.app.version < bl_info['blender']:
	raise Exception("This version of Blender is not supported by " + bl_info['name'] + ". Please use v" + '.'.join(str(v) for v in bl_info['blender']) + " or higher.")


# define name for registration
LookingGlassAddon.name = bl_info['name'] + " v" + '.'.join(str(v) for v in bl_info['version'])

print("Initializing add-on ", LookingGlassAddon.name)
print(" # Add-on path is: " + LookingGlassAddon.path)

# append the add-on's path to Blender's python PATH
sys.path.append(LookingGlassAddon.path)
sys.path.append(LookingGlassAddon.libpath)

try:

	from .lib import pynng
	from .lib import cbor

	# all python dependencies are fulfilled
	LookingGlassAddon.python_dependecies = True
	LookingGlassAddon.show_preferences = False

except:

	# not all python dependencies are fulfilled
	LookingGlassAddon.python_dependecies = False
	LookingGlassAddon.show_preferences = True

	pass


# ------------- DEFINE ADDON PREFERENCES ----------------
# an operator that installs the python dependencies
class LOOKINGGLASS_OT_install_dependencies(bpy.types.Operator):
	bl_idname = "lookingglass.install_dependencies"
	bl_label = "Install (This may take a few minutes)"
	bl_description = "Install all Python dependencies required by this add-on to the add-on directory."
	bl_options = {'REGISTER', 'INTERNAL'}

	def execute(self, context):

		# if dependencies are missing
		if LookingGlassAddon.python_dependecies == False:

			# NOTE: - pip should be preinstalled for Blender 2.81+
			#		  therefore we don't check for it anymore
			import subprocess
			import datetime

			# path to python (NOTE: bpy.app.binary_path_python was deprecated since 2.91)
			if bpy.app.version < (2, 91, 0): python_path = bpy.path.abspath(bpy.app.binary_path_python)
			if bpy.app.version >= (2, 91, 0): python_path = bpy.path.abspath(sys.executable)

			# generate logfile
			logfile = open(bpy.path.abspath(LookingGlassAddon.libpath + "/install.log"), 'a')

			# install the dependencies to the add-on's library path
			subprocess.call([python_path, '-m', 'pip', 'install', 'cbor>=1.0.0', '--target', LookingGlassAddon.libpath], stdout=logfile)
			subprocess.call([python_path, '-m', 'pip', 'install', 'cffi>=1.12.3', '--target', LookingGlassAddon.libpath], stdout=logfile)
			subprocess.call([python_path, '-m', 'pip', 'install', 'pycparser>=2.19', '--target', LookingGlassAddon.libpath], stdout=logfile)
			subprocess.call([python_path, '-m', 'pip', 'install', 'sniffio>=1.1.0', '--target', LookingGlassAddon.libpath], stdout=logfile)
			if platform.system() == "Windows": subprocess.call([python_path, '-m', 'pip', 'install', '--upgrade', 'pynng', '--target', LookingGlassAddon.libpath], stdout=logfile)

			logfile.write("###################################" + '\n')
			logfile.write("Installed: " + str(datetime.datetime.now()) + '\n')
			logfile.write("###################################" + '\n')

			# close logfile
			logfile.close()

			try:

				from .lib import pynng
				from .lib import cbor

				# all python dependencies are fulfilled
				LookingGlassAddon.python_dependecies = True

			except:

				# not all python dependencies are fulfilled
				LookingGlassAddon.python_dependecies = False
				pass

		return {'FINISHED'}

# Preferences pane for this Addon in the Blender preferences
class LookingGlassAddonPreferences(AddonPreferences):
	bl_idname = __name__

	# draw function
	def draw(self, context):

		# Notify the user and provide an option to install
		layout = self.layout
		row = layout.row()

		# draw an Button for Installation of python dependencies
		if LookingGlassAddon.python_dependecies == False:

			row.label(text="Some Python modules are missing for AliceLG to work. Install them to the add-on path?")
			row = layout.row()
			row.operator("lookingglass.install_dependencies", icon='PLUS')

		else:

			row.label(text="All required Python modules were installed.")
			row = layout.row()
			row.label(text="Please restart Blender to activate the changes!", icon='ERROR')



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

				# get device HDMI name
				hpc.GetDeviceHDMIName(dev_index, buffer, 1000)
				dev_hdmi = buffer.value.decode('ascii').strip()

				# get device serial
				hpc.GetDeviceSerial(dev_index, buffer, 1000)
				dev_serial = buffer.value.decode('ascii').strip()

				# get device type
				hpc.GetDeviceType(dev_index, buffer, 1000)
				dev_type = buffer.value.decode('ascii').strip()
				if dev_type == "standard":

					dev_name = "8.9'' Looking Glass"

				elif dev_type == "portrait":

					dev_name = "7.9'' Looking Glass Portrait"

				elif dev_type == "large":

					dev_name = "15.6'' Looking Glass"

				elif dev_type == "pro":

					dev_name = "15.6'' Pro Looking Glass"

				elif dev_type == "8k":

					dev_name = "8k Looking Glass"


				# make an entry in the deviceList
				LookingGlassAddon.deviceList.append(
												{
													# device information
													'index': dev_index,
													'hdmi': dev_hdmi,
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

				# write detected LG to logfile
				with open(bpy.path.abspath(LookingGlassAddon.libpath + "/detected_lg.log"), "a") as logfile:
					pprint(LookingGlassAddon.deviceList[-1], logfile)

				pprint(LookingGlassAddon.deviceList[-1])


		# TODO: Remove this, it's only for debugging
		if debugging_use_dummy_device == True:

			# we add a dummy element
			LookingGlassAddon.deviceList.append({'index': len(LookingGlassAddon.deviceList), 'hdmi': 'LKG79PxDUMMY', 'name': "7.9'' Looking Glass", 'serial': 'LKG-2K-XXXXX', 'type': "portrait", 'x': -1536, 'y': 0, 'width': 1536, 'height': 2048, 'aspectRatio': 0.75, 'pitch': 354.70953369140625, 'tilt': -0.11324916034936905, 'center': -0.11902174353599548, 'subp': 0.0001302083401242271, 'fringe': 0.0, 'ri': 0, 'bi': 2, 'invView': 1, 'viewCone': 58.0})
			#LookingGlassAddon.deviceList.append({'index': len(LookingGlassAddon.deviceList), 'hdmi': 'LKG89LxDUMMY', 'name': "8.9'' Looking Glass", 'serial': 'LKG-2K-XXXXX', 'type': "standard", 'x': -2560, 'y': 0, 'width': 2560, 'height': 1600, 'aspectRatio': 1.600000023841858, 'pitch': 354.70953369140625, 'tilt': -0.11324916034936905, 'center': -0.11902174353599548, 'subp': 0.0001302083401242271, 'fringe': 0.0, 'ri': 0, 'bi': 2, 'invView': 1, 'viewCone': 40.0})
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
				items.append((str(device['index']), 'Display ' + str(device['index']) + ': ' + device['name'], 'Use this Looking Glass for lightfield rendering.'))

		else:

			# add an entry to notify the user about the missing Looking Glass
			items.append(('-1', 'No Looking Glass Found', 'Please connect a Looking Glass.'))



		# return the item list
		return items

	# poll function for the Looking Glass camera selection
	# this prevents that an object is picked, which is no camera
	def camera_selection_poll(self, object):

		# TODO
		# notify user
		# if not object.type == 'CAMERA': self.report({"ERROR"}, "Selected object", object, "is no camera.")

		return object.type == 'CAMERA'


	# Update the Boolean property that creates the hologram rendering window
	def toggleFullscrenMode(self, context):

		# assign the current viewport for the shading & overlay settings
		if context != None: bpy.ops.lookingglass.toggle_fullscreen(context.copy(), 'EXEC_DEFAULT')


	# update function for the workspace selection
	def update_workspace_selection(self, context):

		if context != None:

			# if the settings shall be taken from the current viewport
			if context.scene.settings.viewportMode == 'BLENDER':

				# status variable
				success = False

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


	# update function for property updates concerning render settings
	def update_render_setting(self, context):

		# if a camera is selected
		if context.scene.settings.lookingglassCamera != None:

			# UPDATE RENDER SETTINGS
			# +++++++++++++++++++++++++++++++++++++++++++++++++++++
			# if the settings are to be taken from device selection
			if context.scene.settings.render_use_device == True:

				# currently selected device
				device = LookingGlassAddon.deviceList[int(context.scene.settings.activeDisplay)]

				# apply render settings for the scene to get the correct rendering frustum
				context.scene.render.resolution_x = LookingGlassAddon.qs[int(context.scene.settings.quiltPreset)]["viewWidth"]
				context.scene.render.resolution_y = LookingGlassAddon.qs[int(context.scene.settings.quiltPreset)]["viewHeight"]

				# for landscape formatted devices
				if (context.scene.render.resolution_x / context.scene.render.resolution_y) / device['aspectRatio'] > 1:

					# apply the correct aspect ratio
					context.scene.render.pixel_aspect_x = 1.0
					context.scene.render.pixel_aspect_y = context.scene.render.resolution_x / (context.scene.render.resolution_y * device['aspectRatio'])

				# for portrait formatted devices
				else:

					# apply the correct aspect ratio
					context.scene.render.pixel_aspect_x = (context.scene.render.resolution_y * device['aspectRatio']) / context.scene.render.resolution_x
					context.scene.render.pixel_aspect_y = 1.0

			else:

				# apply render settings for the scene to get the correct rendering frustum
				context.scene.render.resolution_x = LookingGlassAddon.qs[int(context.scene.settings.render_quilt_preset)]["viewWidth"]
				context.scene.render.resolution_y = LookingGlassAddon.qs[int(context.scene.settings.render_quilt_preset)]["viewHeight"]

				# TODO: At the moment this is hardcoded.
				# 		May make sense to use the Blender preset mechanisms instead ("preset_add", "execute_preset", etc.)
				# if for Looking Glass Portrait
				if context.scene.settings.render_device_type == 'portrait':

					# apply the correct aspect ratio
					context.scene.render.pixel_aspect_x = (0.75 *  context.scene.render.resolution_y) / context.scene.render.resolution_x
					context.scene.render.pixel_aspect_y = 1.0

				# if for Looking Glass 8.9''
				elif context.scene.settings.render_device_type == 'standard':

					# apply the correct aspect ratio
					context.scene.render.pixel_aspect_x = 1.0
					context.scene.render.pixel_aspect_y = (context.scene.render.resolution_x / context.scene.render.resolution_y) / 1.6

				# if for Looking Glass 15.6'' or 8k
				elif context.scene.settings.render_device_type == 'large' or context.scene.settings.render_device_type == '8k':

					# apply the correct aspect ratio
					context.scene.render.pixel_aspect_x = 1.0
					context.scene.render.pixel_aspect_y = (context.scene.render.resolution_x / context.scene.render.resolution_y) / 1.777777777


		return None


	# update function for property updates concerning camera selection
	def update_camera_selection(self, context):

		# if no Looking Glass was detected
		if len(LookingGlassAddon.deviceList) == 0:

			# set the checkbox to False (because there is no device we
			# could take the settings from)
			context.scene.settings.render_use_device = False

		# if a camera was selected
		if context.scene.settings.lookingglassCamera != None:

			# if the frustum drawing operator is not invoked, but should be
			if LookingGlassAddon.FrustumInitialized == False and context.scene.settings.showFrustum == True: bpy.ops.render.frustum('INVOKE_DEFAULT')

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

			# apply the clipping values to the selected camera
			camera.data.clip_start = context.scene.settings.clip_start
			camera.data.clip_end = context.scene.settings.clip_end

			# update render settings
			LookingGlassAddonFunctions.update_render_setting(self, context)

			# if a lightfield window exists
			if LookingGlassAddon.lightfieldWindow != None and LookingGlassAddon.lightfieldSpace != None:

				# set lightfield space to this camera (automatically NONE if no camera is selected)
				LookingGlassAddon.lightfieldSpace.camera = context.scene.settings.lookingglassCamera

				# set view mode to "CAMERA"
				if LookingGlassAddon.lightfieldSpace.region_3d.view_perspective != 'CAMERA': bpy.ops.view3d.view_camera(dict(window=LookingGlassAddon.lightfieldWindow, area=LookingGlassAddon.lightfieldArea, region=LookingGlassAddon.lightfieldRegion, space_data=LookingGlassAddon.lightfieldSpace))

		else:

			# if a valid space is existing
			if LookingGlassAddon.lightfieldWindow != None and LookingGlassAddon.lightfieldSpace != None:

				# set lightfield space to no camera
				LookingGlassAddon.lightfieldSpace.camera = None

				# set view mode to "PERSP"
				if LookingGlassAddon.lightfieldSpace.region_3d.view_perspective != 'PERSP': bpy.ops.view3d.view_camera(dict(window=LookingGlassAddon.lightfieldWindow, area=LookingGlassAddon.lightfieldArea, region=LookingGlassAddon.lightfieldRegion, space_data=LookingGlassAddon.lightfieldSpace))

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



			# apply the clipping values to the selected camera
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



	# update function for property updates concerning quilt image selection
	def update_quilt_selection(self, context):

		# if a quilt was selected
		if context.scene.settings.quiltImage != None:

			# update the setting observers
			LookingGlassAddon.quiltViewAsRender = context.scene.settings.quiltImage.use_view_as_render
			LookingGlassAddon.quiltImageColorSpaceSetting = context.scene.settings.quiltImage.colorspace_settings

			# if no pixel array exists
			if LookingGlassAddon.quiltPixels is None:

				# create a numpy array for the pixel data
				LookingGlassAddon.quiltPixels = np.empty(len(context.scene.settings.quiltImage.pixels), np.float32)

			else:

				# resize the numpy array
				LookingGlassAddon.quiltPixels.resize(len(context.scene.settings.quiltImage.pixels), refcheck=False)

				# delete the texture, if it is existing
				# NOTE: Unclear why glIsTexture expects integer and DeleteTexture a Buffer object
				if LookingGlassAddon.quiltTextureID != None and bgl.glIsTexture(LookingGlassAddon.quiltTextureID[0]) == True:
					bgl.glDeleteTextures(1, LookingGlassAddon.quiltTextureID)

			# create a new texture
			LookingGlassAddon.quiltTextureID = bgl.Buffer(bgl.GL_INT, [1])
			bgl.glGenTextures(1, LookingGlassAddon.quiltTextureID)



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
			if context.scene.settings.quiltImage.use_view_as_render == False:

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
			context.scene.settings.quiltImage.save_render(filepath=tempFilepath, scene=context.scene)

			# restore output render settings
			context.scene.render.use_render_cache = tempUseRenderCache
			context.scene.render.image_settings.file_format = tempFileFormat
			context.scene.render.image_settings.color_depth = tempColorDepth
			context.scene.render.image_settings.color_mode = tempColorMode

			# if the image has the "view as render" option inactive
			if context.scene.settings.quiltImage.use_view_as_render == False:

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
				LookingGlassAddon.quiltTextureBuffer = bgl.Buffer(bgl.GL_FLOAT, len(tempImage.pixels), LookingGlassAddon.quiltPixels)

			# TODO: The following lines would be enough, if the color
			#		management settings would be applied in memory. Not deleted
			#		for later
			#
			# # copy pixel data to the array and a BGL Buffer
			# context.scene.settings.quiltImage.pixels.foreach_get(LookingGlassAddon.quiltPixels)
			# LookingGlassAddon.quiltTextureBuffer = bgl.Buffer(bgl.GL_FLOAT, len(context.scene.settings.quiltImage.pixels), LookingGlassAddon.quiltPixels)



			# APPLY CORRECT COLOR FORMAT TO OPENGL TEXTURE
			# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
			if tempImage.colorspace_settings.name == 'sRGB':

				# bind the texture and apply bgl.GL_SRGB8_ALPHA8 as internal format
				# NOTE: We do all that, because otherwise the colorspace will be wrong in Blender
				#		see: https://developer.blender.org/T79788#1034183
				bgl.glBindTexture(bgl.GL_TEXTURE_2D, LookingGlassAddon.quiltTextureID.to_list()[0])
				bgl.glTexImage2D(bgl.GL_TEXTURE_2D, 0, bgl.GL_SRGB8_ALPHA8, context.scene.settings.quiltImage.size[0], context.scene.settings.quiltImage.size[1], 0, bgl.GL_RGBA, bgl.GL_FLOAT, LookingGlassAddon.quiltTextureBuffer)
				bgl.glTexParameteri(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_MIN_FILTER, bgl.GL_LINEAR)
				bgl.glTexParameteri(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_MAG_FILTER, bgl.GL_LINEAR)

			# else:
			# 	print("# USING GL_RGBA")
			# 	# use linear color space
			# 	bgl.glBindTexture(bgl.GL_TEXTURE_2D, LookingGlassAddon.quiltTextureID.to_list()[0])
			# 	bgl.glTexImage2D(bgl.GL_TEXTURE_2D, 0, bgl.GL_RGBA, context.scene.settings.quiltImage.size[0], context.scene.settings.quiltImage.size[1], 0, bgl.GL_RGBA, bgl.GL_FLOAT, LookingGlassAddon.quiltTextureBuffer)
			# 	bgl.glTexParameteri(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_MIN_FILTER, bgl.GL_LINEAR)
			# 	bgl.glTexParameteri(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_MAG_FILTER, bgl.GL_LINEAR)


			# delete the temporary Blender image
			bpy.data.images.remove(tempImage)

			# delete the temporary file
			os.remove(tempFilepath)

		# if the quilt selection was deleted
		else:

			# delete the texture
			bgl.glDeleteTextures(1, LookingGlassAddon.quiltTextureID)


# Preferences pane for this Addon in the Blender preferences
class LookingGlassAddonSettings(bpy.types.PropertyGroup):

	# PANEL: GENERAL
	# a list of connected Looking Glass displays
	activeDisplay: bpy.props.EnumProperty(
										items = LookingGlassAddonFunctions.looking_glass_list_callback,
										name="Please select a Looking Glass.",
										update=LookingGlassAddonFunctions.update_render_setting,
										)

	# a boolean to toogle the render window on or off
	ShowLightfieldWindow: bpy.props.BoolProperty(
											name="Lightfield Window",
											description = "Creates a window for the lightfield rendering. You need to move the window manually to the Looking Glass screen and toogle it fullscreen",
											default = False,
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

	quiltPreset: bpy.props.EnumProperty(
										items = [
												('0', 'Resolution: Portrait Quilt, 48 Views', 'Display an 3360x3360 quilt with 48 views in the connected Looking Glass Portrait.'),
												('1', 'Resolution: Portrait Quilt, 88 Views', 'Display an 4026x4096 quilt with 88 views in the connected Looking Glass Portrait.'),
												('2', 'Resolution: Portrait Quilt, 91 Views', 'Display an 4225x4095 quilt with 91 views in the connected Looking Glass Portrait.'),
												('3', 'Resolution: Portrait Quilt, 96 Views', 'Display an 4224x4096 quilt with 96 views in the connected Looking Glass Portrait.'),
												('4', 'Resolution: Portrait Quilt, 108 Views', 'Display an 4224x4230 quilt with 108 views in the connected Looking Glass Portrait.'),
												('5', 'Resolution: 2k Quilt, 32 Views', 'Display a 2k quilt with 32 views in the connected Looking Glass.'),
												('6', 'Resolution: 4k Quilt, 45 Views', 'Display a 4k quilt with 45 views in the connected Looking Glass.'),
												('7', 'Resolution: 8k Quilt, 45 Views', 'Display an 8k quilt with 45 views in the connected Looking Glass.')],
										default='0',
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
										name="Looking Glass Camera",
										type=bpy.types.Object,
										description = "Select a camera, which defines the view for your Looking Glass or quilt image",
										poll = LookingGlassAddonFunctions.camera_selection_poll,
										update = LookingGlassAddonFunctions.update_camera_selection,
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


	# PANEL: RENDER SETTINGS
	# Use the device to set device settings
	render_use_device: bpy.props.BoolProperty(
										name="Use Device Settings",
										description="If enabled, the render settings are taken from the selected device",
										default = True,
										update=LookingGlassAddonFunctions.update_render_setting,
										)

	# Add a suffix with metadata to the file name
	render_add_suffix: bpy.props.BoolProperty(
										name="Add Metadata",
										description="If enabled, metadata will be added to the quilt filename as a suffix. That metadata is used by Holoplay Studio and other applications in the Looking Glass ecosystem to automatically determine the correct settings for displaying or editing the quilt.",
										default = True,
										update=LookingGlassAddonFunctions.update_render_setting,
										)

	# Orientation of the views
	render_device_type: bpy.props.EnumProperty(
										items = [('portrait', 'Looking Glass Portrait', 'Render the quilt for the Looking Glasses Portrait.'),
												 ('standard', 'Looking Glass 8.9''', 'Render the quilt for the Looking Glass 8.9''.'),
 												 ('large', 'Looking Glass 15.6''', 'Render the quilt for the Looking Glass 15.6''.'),
		 										 ('8k', 'Looking Glass 8K', 'Render the quilt for the Looking Glass 8k.')],
										default='portrait',
										name="Device Type",
										update = LookingGlassAddonFunctions.update_render_setting,
										)

	# Quilt presets
	render_quilt_preset: bpy.props.EnumProperty(
									items = [('0', 'Portrait, 48 view', 'Render a 3360x3360 quilt with 48 views.'),
											 ('1', 'Portrait, 88 view', 'Render a 4026x4096 quilt with 88 views.'),
		 									 ('2', 'Portrait, 91 view', 'Render a 4225x4095 quilt with 91 views.'),
 											 ('3', 'Portrait, 96 view', 'Render a 4224x4096 quilt with 96 views.'),
 		 									 ('4', 'Portrait, 108 view', 'Render a 4224x4230 quilt with 108 views.'),
											 ('5', '2k Quilt, 32 view', 'Render a 2k quilt with 32 views.'),
		 									 ('6', '4k Quilt, 45 view', 'Render a 4k quilt with 45 views.'),
		 									 ('7', '8k Quilt, 45 view', 'Render a 8k quilt with 45 views.'),],
									default='0',
									name="Quilt Preset",
									update = LookingGlassAddonFunctions.update_render_setting,
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
										description = "Quilt image for display in the Looking Glass",
										update = LookingGlassAddonFunctions.update_quilt_selection,
										)


	viewport_use_lowres_preview: bpy.props.BoolProperty(
										name="Low-resolution Preview",
										description="If enabled, a low-resolution lightfield is rendered during scene changes (for higher render speed)",
										default = False,
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
										items = LookingGlassAddonFunctions.workspaces_list_callback,
										update = LookingGlassAddonFunctions.update_workspace_selection
										)

	blender_view3d: bpy.props.EnumProperty(
										name="3D View",
										items = LookingGlassAddonFunctions.view3D_list_callback,
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

	# # invoke the mouse position tracking operator
	# bpy.ops.wm.mouse_tracker('INVOKE_DEFAULT')

	# invoke the camera frustum rendering operator
	bpy.ops.render.frustum('INVOKE_DEFAULT')

	# get the active window
	LookingGlassAddon.BlenderWindow = bpy.context.window

	# if the lightfield window was active
	if bpy.context.scene.settings.ShowLightfieldWindow == True and bpy.context.scene.settings.lightfieldWindowIndex != -1:

		# get the lightfield window by the index of this window in the list of windows in the WindowManager
		LookingGlassAddon.lightfieldWindow = bpy.context.window_manager.windows.values()[bpy.context.scene.settings.lightfieldWindowIndex]

		# if the window was found
		if LookingGlassAddon.lightfieldWindow != None:

			# close this window
			bpy.ops.wm.window_close(dict(window=LookingGlassAddon.lightfieldWindow))

			# if the device list is not empty, create a new lightfield window
			if len(LookingGlassAddon.deviceList) > 0:

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

			else:

				# reset the window variable
				LookingGlassAddon.lightfieldWindow = None

				# deactivate the corresponding UI elements
				bpy.context.scene.settings.toggleLightfieldWindowFullscreen = False
				bpy.context.scene.settings.ShowLightfieldWindow = False


	# if no Looking Glass was detected
	if len(LookingGlassAddon.deviceList) == 0:

		# set the "use device" checkbox in quilt setup to False
		# (because there is no device we could take the settings from)
		bpy.context.scene.settings.render_use_device = False


	# check if lockfile exists and set status variable
	LookingGlassAddon.has_lockfile = os.path.exists(bpy.path.abspath(LookingGlassAddon.tmp_path + "/" + os.path.basename(bpy.data.filepath) + ".lock"))




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

		# if no Looking Glass was detected
		if len(LookingGlassAddon.deviceList) == 0:

			# set the checkbox to False (because there is no device we
			# could take the settings from)
			context.scene.settings.render_use_device = False

		return {'FINISHED'}


# an operator that controls lightfield window opening and closing
class LOOKINGGLASS_OT_lightfield_window(bpy.types.Operator):
	bl_idname = "lookingglass.lightfield_window"
	bl_label = "Lightfield Window"
	bl_description = "Creates a window for the lightfield rendering. You need to move the window manually to the Looking Glass screen and toogle it fullscreen"
	bl_options = {'REGISTER', 'INTERNAL'}


	# Update the Boolean property that creates the hologram rendering window
	def execute(self, context):

		# set the property to the correct value
		context.scene.settings.ShowLightfieldWindow = (not context.scene.settings.ShowLightfieldWindow)

		# if the bool property was set to True
		if context.scene.settings.ShowLightfieldWindow == True:

			# assign the current viewport for the shading & overlay settings
			bpy.ops.lookingglass.blender_viewport_assign('EXEC_DEFAULT')

			# if on linux, get the currently open windows
			if platform.system() == "Linux":
				LookingGlassAddon.LinuxWindowList = list(map(int, str(subprocess.run(['xdotool', 'search', '--name', 'Blender'], check=True, capture_output=True).stdout).replace('b\'','').split('\\n')[:-1]))
				print("Following Blender windows are open: ", LookingGlassAddon.LinuxWindowList)

			# Create a new main window
			bpy.ops.wm.window_new_main('INVOKE_DEFAULT')

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

		return {'FINISHED'}

# an operator that controls lightfield window opening and closing
class LOOKINGGLASS_OT_toggle_fullscreen(bpy.types.Operator):
	bl_idname = "lookingglass.toggle_fullscreen"
	bl_label = "Toggle Lightfield Window Fullscreen Mode"
	bl_description = "Press this button, if the lightfield window was moved to the Looking Glass to make it fullscreen."
	bl_options = {'REGISTER', 'INTERNAL'}

	# OPERATOR ARGUMENTS
	button_pressed: bpy.props.BoolProperty(default = False)

	# Update the Boolean property that creates the hologram rendering window
	def execute(self, context):

		# if a lightfield window exists AND the window shall be toggled
		if context != None and LookingGlassAddon.lightfieldWindow != None and LookingGlassAddon.LightfieldWindowIsFullscreen != context.scene.settings.toggleLightfieldWindowFullscreen:

			# toggle fullscreen mode off
			bpy.ops.wm.window_fullscreen_toggle(dict(window=LookingGlassAddon.lightfieldWindow))

			# update global variable
			LookingGlassAddon.LightfieldWindowIsFullscreen = context.scene.settings.toggleLightfieldWindowFullscreen

		# if a lightfield window exists AND the button was pressed
		elif context != None and LookingGlassAddon.lightfieldWindow != None and self.button_pressed == True:

			# toggle fullscreen mode off
			bpy.ops.wm.window_fullscreen_toggle(dict(window=LookingGlassAddon.lightfieldWindow))

			# update global variable
			LookingGlassAddon.LightfieldWindowIsFullscreen = (not LookingGlassAddon.LightfieldWindowIsFullscreen)

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
		if LookingGlassAddon.lightfieldWindow != None:
			toggle_fullscreen = row_1b.operator("lookingglass.toggle_fullscreen", text="", icon='FULLSCREEN_ENTER', depress=LookingGlassAddon.LightfieldWindowIsFullscreen)
			toggle_fullscreen.button_pressed = True
		row_1b.operator("lookingglass.lightfield_window", text="", icon='WINDOW', depress=context.scene.settings.ShowLightfieldWindow)

		# Resolution selection of the quilt views
		row_2 = column.row()
		row_2.prop(context.scene.settings, "quiltPreset", text="")
		row_2.prop(context.scene.settings, "debug_view", expand=True, text="", icon='TEXTURE')
		#column.separator()

		# if no Looking Glass was detected
		if len(LookingGlassAddon.deviceList) == 0:

			# deactivate quilt preset and debug buttons
			row_2.enabled = False


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

		row_1 = column.row(align = True)
		row_1.prop(context.scene.settings, "lookingglassCamera", icon='VIEW_CAMERA', text="")
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

	# draw the IntProperties for the tiles in the panel
	def draw(self, context):
		layout = self.layout

		# Render orientation
		column_0 = layout.column(align = True)
		render_use_device = column_0.prop(context.scene.settings, "render_use_device")
		render_add_suffix = column_0.prop(context.scene.settings, "render_add_suffix")

		# Render orientation
		row_1 = layout.row(align = True)
		column_1 = row_1.row(align = True)
		column_1.label(text="Device:")
		column_1.scale_x = 0.3
		column_2 = row_1.row(align = True)
		column_2.prop(context.scene.settings, "render_device_type", text="")
		column_2.scale_x = 0.7

		# Quilt preset
		row_2 = layout.row(align = True)
		column_1 = row_2.row(align = True)
		column_1.label(text="Quilt:")
		column_1.scale_x = 0.3
		column_2 = row_2.row(align = True)
		column_2.prop(context.scene.settings, "render_quilt_preset", text="")
		column_2.scale_x = 0.7

		# Output file handling
		row_3 = layout.row(align = True)
		column_1 = row_3.row(align = True)
		column_1.label(text="Output:")
		column_1.scale_x = 0.3
		column_2 = row_3.row(align = True)
		column_2.prop(context.scene.settings, "render_output", text="")
		column_2.scale_x = 0.7

		# if no lockfile was detected on start-up OR the render job is running
		if LookingGlassAddon.has_lockfile == False or LookingGlassAddon.RenderInvoked == True:

			# Buttons and progress bars
			if LookingGlassAddon.RenderInvoked == True and LookingGlassAddon.RenderAnimation == False:
				# Show the corresponding progress bar for the rendering process
				row_4 = layout.row(align = True)
				row_4.prop(context.scene.settings, "render_progress", text="", slider=True)
			else:
				# Button to start rendering a single quilt using the current render settings
				row_4 = layout.row(align = True)
				render_quilt = row_4.operator("render.quilt", text="Render Quilt", icon='RENDER_STILL')
				render_quilt.animation = False

			if LookingGlassAddon.RenderInvoked == True and LookingGlassAddon.RenderAnimation == True:
				# Show the corresponding progress bar for the rendering process
				row_5 = layout.row(align = True)
				row_5.prop(context.scene.settings, "render_progress", text="", slider=True)
			else:
				# Button to start rendering a animation quilt using the current render settings
				row_5 = layout.row(align = True)
				render_quilt = row_5.operator("render.quilt", text="Render Animation Quilt", icon='RENDER_ANIMATION')
				render_quilt.animation = True


		# if a lockfile was detected on start-up
		else:

			# disable the UI
			row_0.enabled = False
			row_1.enabled = False
			row_2.enabled = False
			row_3.enabled = False

			# inform the user and provide options to continue or to discard
			row_4 = layout.row(align = True)
			row_4.label(text = "Last render job incomplete:", icon="ERROR")

			row_5 = layout.row(align = False)
			render_quilt = row_5.operator("render.quilt", text="Continue", icon='RENDER_STILL')
			render_quilt.use_lockfile = True
			render_quilt = row_5.operator("render.quilt", text="Discard", icon='CANCEL')
			render_quilt.use_lockfile = True
			render_quilt.discard_lockfile = True




		# disable the render settings, if a rendering process is running
		if LookingGlassAddon.RenderInvoked == True:
			row_0.enabled = False
			row_1.enabled = False
			row_2.enabled = False
			row_3.enabled = False

			if LookingGlassAddon.RenderAnimation == True: row_4.enabled = False
			if LookingGlassAddon.RenderAnimation == False: row_5.enabled = False

		# if no camera is selected
		if context.scene.settings.lookingglassCamera == None:

			# disable all elements
			row_0.enabled = False
			row_1.enabled = False
			row_2.enabled = False
			row_3.enabled = False
			row_4.enabled = False
			row_5.enabled = False

		# if the settings are to be taken from device selection
		elif context.scene.settings.render_use_device == True:

			# disable all elements
			row_1.enabled = False
			row_2.enabled = False

		# if no Looking Glass was detected
		if len(LookingGlassAddon.deviceList) == 0:

			# deactivate the checkbox
			row_0.enabled = False


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


		# if the lightfield window is in quilt viewer mode
		elif context.scene.settings.renderMode == '1':

			# display all settings for the quilt view mode
			row = column.row(align = True)
			row.label(text="Select a Quilt Image to Display:")

			row = column.row(align = True)
			row.template_ID(context.scene.settings, "quiltImage", open="image.open")



# ------------- Subpanel for lightfield cursor settings ----------------
class LOOKINGGLASS_PT_panel_lightfield_cursor(bpy.types.Panel):
	bl_idname = "LOOKINGGLASS_PT_panel_lightfield_cursor" # unique identifier for buttons and menu items to reference.
	bl_label = "Lightfield Cursor Settings" # display name in the interface.
	bl_space_type = "VIEW_3D"
	bl_region_type = "UI"
	bl_category = "Looking Glass"
	bl_parent_id = "LOOKINGGLASS_PT_panel_lightfield"


	# define own poll method to be able to hide / show the panel on demand
	@classmethod
	def poll(self, context):

		# if no Looking Glass is selected OR no lightfield window exists OR lightfield window is in viewport mode
		if int(context.scene.settings.activeDisplay) == -1 or context.scene.settings.ShowLightfieldWindow == False or context.scene.settings.renderMode == '1':

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

		# Lightfield cursor settings
		column = layout.column(align = True)
		row_1 = column.row()
		row_1.prop(context.scene.settings, "viewport_cursor_size", text="Size", slider=True)
		row_1.prop(context.scene.settings, "viewport_show_cursor", text="", icon='RESTRICT_SELECT_OFF')
		row_2 = column.row()
		row_2.prop(context.scene.settings, "viewport_cursor_color", text="")



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
		if context.scene.settings.viewportMode == 'BLENDER':

			# set the Workspace list to the current workspace
			context.scene.settings.blender_workspace = context.workspace.name

			# set the 3D View list to the current 3D view
			context.scene.settings.blender_view3d = str(context.space_data)

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

				#column.separator()

				row = column.row(align = True)
				column = layout.column(align = True)
				row = column.row(align = True)
				row.label(text="Mirror Settings From:")
				row = column.row(align = True)
				row.prop(context.scene.settings, "blender_workspace")
				row = column.row(align = True)
				row.prop(context.scene.settings, "blender_view3d")

				column.separator()

				row = column.row(align = True)
				row.operator("lookingglass.blender_viewport_assign")

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



# ---------- MOUSE POSITION OPERATOR -------------
class LOOKINGGLASS_OT_wm_mouse_position(bpy.types.Operator):
	bl_idname = "wm.mouse_position"
	bl_label = "Invoke Mouse Operator"
	bl_options = {'REGISTER', 'INTERNAL'}

	x: bpy.props.IntProperty()
	y: bpy.props.IntProperty()

	def execute(self, context):
		# save mouse position in global variable
		LookingGlassAddon.mouse_x = self.x
		LookingGlassAddon.mouse_y = self.y

		#print("Tracker: ", (LookingGlassAddon.mouse_x, LookingGlassAddon.mouse_y))

		return {'FINISHED'}

	def invoke(self, context, event):
		self.x = event.mouse_x
		self.y = event.mouse_y

		return self.execute(context)


class LOOKINGGLASS_OT_wm_mouse_tracker(bpy.types.Operator):
	bl_idname = "wm.mouse_tracker"
	bl_label = "Mouse Position Tracker"
	bl_options = {'REGISTER', 'INTERNAL'}

	def modal(self, context, event):

		if event.type == 'MOUSEMOVE':

			if LookingGlassAddon.lightfieldWindow != None:

				LookingGlassAddon.mouse_x = event.mouse_x
				LookingGlassAddon.mouse_y = event.mouse_y
				# invoke the mouse position tracking operator
				#bpy.ops.wm.mouse_position('INVOKE_DEFAULT')
				#print((event.mouse_x, event.mouse_region_x))
				print((LookingGlassAddon.mouse_x, LookingGlassAddon.mouse_y))
				#print("")

		return {'PASS_THROUGH'}

	def invoke(self, context, event):

		# Create timer event that runs every 10 ms to check the mouse position
		#self.timerEvent = context.window_manager.event_timer_add(0.010, window=context.window)

		context.window_manager.modal_handler_add(self)
		return {'RUNNING_MODAL'}



# ---------- ADDON INITIALIZATION & CLEANUP -------------
def register():

	print("Initializing Holo Play Core:")

	# register all classes of the addon
	# Preferences & Settings
	if LookingGlassAddon.show_preferences == True: bpy.utils.register_class(LookingGlassAddonPreferences)
	bpy.utils.register_class(LookingGlassAddonSettings)
	bpy.utils.register_class(LOOKINGGLASS_OT_install_dependencies)
	bpy.utils.register_class(LOOKINGGLASS_OT_refresh_display_list)
	bpy.utils.register_class(LOOKINGGLASS_OT_toggle_fullscreen)
	bpy.utils.register_class(LOOKINGGLASS_OT_lightfield_window)
	bpy.utils.register_class(LOOKINGGLASS_OT_refresh_lightfield)
	bpy.utils.register_class(LOOKINGGLASS_OT_blender_viewport_assign)
	bpy.utils.register_class(LOOKINGGLASS_OT_add_camera)

	# Looking Glass quilt rendering
	bpy.utils.register_class(LOOKINGGLASS_OT_render_quilt)

	# Looking Glass viewport & camera frustum
	bpy.utils.register_class(LOOKINGGLASS_OT_render_lightfield)
	bpy.utils.register_class(LOOKINGGLASS_OT_render_frustum)

	# Mouse position tracker
	bpy.utils.register_class(LOOKINGGLASS_OT_wm_mouse_position)
	bpy.utils.register_class(LOOKINGGLASS_OT_wm_mouse_tracker)

	# UI elements
	bpy.utils.register_class(LOOKINGGLASS_PT_panel_general)
	bpy.utils.register_class(LOOKINGGLASS_PT_panel_camera)
	bpy.utils.register_class(LOOKINGGLASS_PT_panel_render)
	bpy.utils.register_class(LOOKINGGLASS_PT_panel_lightfield)
	bpy.utils.register_class(LOOKINGGLASS_PT_panel_lightfield_cursor)
	bpy.utils.register_class(LOOKINGGLASS_PT_panel_overlays_shading)



	# initialize HoloPlay Core SDK
	errco = hpc.InitializeApp(LookingGlassAddon.name.encode(), hpc.license_type.LICENSE_NONCOMMERCIAL.value)

	print(" # Registering at Holoplay Service as: " + LookingGlassAddon.name)

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

	# register all classes of the addon
	# Preferences & Settings
	if LookingGlassAddon.show_preferences == True: bpy.utils.unregister_class(LookingGlassAddonPreferences)
	bpy.utils.unregister_class(LookingGlassAddonSettings)
	bpy.utils.unregister_class(LOOKINGGLASS_OT_install_dependencies)
	bpy.utils.unregister_class(LOOKINGGLASS_OT_refresh_display_list)
	bpy.utils.unregister_class(LOOKINGGLASS_OT_refresh_lightfield)
	bpy.utils.unregister_class(LOOKINGGLASS_OT_toggle_fullscreen)
	bpy.utils.unregister_class(LOOKINGGLASS_OT_lightfield_window)
	bpy.utils.unregister_class(LOOKINGGLASS_OT_blender_viewport_assign)
	bpy.utils.unregister_class(LOOKINGGLASS_OT_add_camera)

	# Looking Glass quilt rendering
	bpy.utils.unregister_class(LOOKINGGLASS_OT_render_quilt)

	# Looking Glass viewport & camera frustum
	bpy.utils.unregister_class(LOOKINGGLASS_OT_render_lightfield)
	bpy.utils.unregister_class(LOOKINGGLASS_OT_render_frustum)

	# Mouse position tracker
	bpy.utils.unregister_class(LOOKINGGLASS_OT_wm_mouse_tracker)
	bpy.utils.unregister_class(LOOKINGGLASS_OT_wm_mouse_position)

	# UI elements
	bpy.utils.unregister_class(LOOKINGGLASS_PT_panel_general)
	bpy.utils.unregister_class(LOOKINGGLASS_PT_panel_camera)
	bpy.utils.unregister_class(LOOKINGGLASS_PT_panel_render)
	bpy.utils.unregister_class(LOOKINGGLASS_PT_panel_lightfield)
	bpy.utils.unregister_class(LOOKINGGLASS_PT_panel_lightfield_cursor)
	bpy.utils.unregister_class(LOOKINGGLASS_PT_panel_overlays_shading)

	# delete all variables
	del bpy.types.Scene.settings
