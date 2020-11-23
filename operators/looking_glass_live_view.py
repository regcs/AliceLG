# ##### BEGIN GPL LICENSE BLOCK #####
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

import bpy, bgl
import gpu
import json
import subprocess
import logging
import time
import os, sys
import ctypes
from gpu_extras.batch import batch_for_shader
from gpu_extras.presets import draw_texture_2d, draw_circle_2d
from bpy_extras.view3d_utils import location_3d_to_region_2d

from bgl import *
from math import *
from mathutils import *
from bpy.types import AddonPreferences, PropertyGroup
from bpy.props import FloatProperty, PointerProperty

# TODO: Is there a better way to share global variables between all addon files and operators?
from .looking_glass_global_variables import *



# ------------ LIGHTFIELD RENDERING -------------
# Modal operator for controlled redrawing of the image object
# NOTE: This code is only for a more conveniant testing of the draw function
#	   If you want to stop the test, press 'ESC'
class LOOKINGGLASS_OT_render_lightfield(bpy.types.Operator):

	bl_idname = "render.lightfield"
	bl_label = "Looking Glass Lightfield Rendering"
	bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

	# WINDOW RELATED VARIABLES
	window_manager = None
	WindowCheck = False

	# SETTINGS VARIABLES
	standard_preset = 1
	qs = []

	# DRAWING OPERATION VARIABLES
	modal_redraw = True
	updateQuilt = True
	depsgraph_update_time = 0.000
	preset = standard_preset
	last_preset = 3
	viewportViewMatrix = None

	# HANDLER IDENTIFIERS
	_handle_viewDrawing = []
	_handle_lightfieldDrawing = None
	_handle_trackViewportUpdates = None
	_handle_trackDepsgraphUpdates = None
	_handle_trackFrameChanges = None
	_handle_trackActiveSpaceView3D = None

	# DEBUGING VARIABLES
	start_multi_view = 0



	# Inititalize the Looking Glass
	@classmethod
	def __init__(self):

		print("Initializing the lightfield rendering operator ...")



	# delete all objects
	@classmethod
	def __del__(self):

		print("Stopped lightfield Rendering operator ...")




    # poll method
	@classmethod
	def poll(self, context):

		# print("POLLING: ", LookingGlassAddon.lightfieldWindow)

		# if the lightfield window exists
		if LookingGlassAddon.lightfieldWindow != None:

			# return True, so the operator is executed
			return True

		else:

			print("FAILED INITIALIZING THE LIVE VIEW!")

			# return False, so the operator is NOT executed
			return False



	# cancel the modal operator
	def cancel(self, context):

		print("Stopping timer.")

		# stop timer
		context.window_manager.event_timer_remove(self.timerEvent)

		print("Stopping depsgraph handlers.")

		# remove the app handler that checks for depsgraph updates
		bpy.app.handlers.depsgraph_update_post.remove(self.trackDepsgraphUpdates)
		bpy.app.handlers.frame_change_post.remove(self.trackDepsgraphUpdates)

		print("Stopping viewport tracking handlers.")
		# remove the handler for the viewport tracking
		if self._handle_trackActiveSpaceView3D: bpy.types.SpaceView3D.draw_handler_remove(self._handle_trackActiveSpaceView3D, 'WINDOW')

		print("Stopping viewport update tracking handlers.")
		# remove the handler for the viewport tracking
		if self._handle_trackViewportUpdates: bpy.types.SpaceView3D.draw_handler_remove(self._handle_trackViewportUpdates, 'WINDOW')

		print("Removing view draw handlers: ")
		print(self._handle_viewDrawing)

		# remove the draw handlers for all quilt views
		for handle in self._handle_viewDrawing:
			if handle: bpy.types.SpaceView3D.draw_handler_remove(handle, 'WINDOW')

		# clear the list of handles
		self._handle_viewDrawing.clear()

		print("Removing lightfield draw handlers: ")
		# remove the draw handler for the lightfield window
		if self._handle_lightfieldDrawing: bpy.types.SpaceView3D.draw_handler_remove(self._handle_lightfieldDrawing, 'WINDOW')

		print("Free quilt and view offscreens.")

		# iterate through all presets
		for i in range(0, len(self.qs), 1):

			# free the GPUOffscreen for the quilt / lightfield
			self.qs[i]["quiltOffscreen"].free()

			# iterate through all quilt views
			for view in range(0, self.qs[i]["totalViews"], 1):

				# and free the corresponding GPUOffscreen
				self.qs[i]["viewOffscreens"][view].free()

			# clear the list
			self.qs[i]["viewOffscreens"].clear()

		# set status variables to default state
		LookingGlassAddon.lightfieldWindow = None
		LookingGlassAddon.lightfieldSpace = None
		LookingGlassAddon.BlenderWindow = None
		LookingGlassAddon.BlenderViewport = None

		print("Everything is done.")


		# return None since this is expected by the operator
		return None




	def invoke(self, context, event):
		start = time.time()

		# make an internal variable for the window_manager,
		# which can be accessed from methods that have no "context" parameter
		self.window_manager = context.window_manager



		# PREPARE THE SHADERS AND LIGHTFIELD RENDERING
		################################################################

		# setup the quilt
		self.setupQuilt(self.preset)

		# Load the blit shaders
		if self.loadBlitShaders() == 0:
			print("ERROR: Blit shader not compiled")
			raise Exception()

		# Load the lightfield shaders
		if self.loadlightFieldShaders() == 0:
			print("ERROR: Lightfield shader not compiled")
			raise Exception()

		# Load the specific calibration data of the LG into the shaders
		self.loadCalibrationIntoShader()

		# pass quilt settings to the lightfield shader
		self.passQuiltSettingsToShader()



		# PREPARE THE LIGHTFIELD WINDOW AND OVERRIDE CONTEXT
		################################################################

		# make a temporary variable
		print("Window: ", LookingGlassAddon.lightfieldWindow)
		print(" # x: ", LookingGlassAddon.lightfieldWindow.x)
		print(" # y: ", LookingGlassAddon.lightfieldWindow.y)
		print(" # width: ", LookingGlassAddon.lightfieldWindow.width)
		print(" # height: ", LookingGlassAddon.lightfieldWindow.height)

		# we use the last area for our lightfield drawing
		# NOTE: This is an arbitrary choice, but it needs to be consistent throughout the code
		area = LookingGlassAddon.lightfieldWindow.screen.areas[-1]

		# Switch this area to a SpaceView3D so that we can create the override context from it
		area.type = "VIEW_3D"

		# find the correct region
		for region in area.regions:
			if region.type == "WINDOW":

				# create an override context for the drawing operations later
				for space in area.spaces:
					if space.type == "VIEW_3D":

						# remember the area, so that Blender will only draw the lightfield in this area
						self.lightfieldArea = area
						LookingGlassAddon.lightfieldSpace = space

						# create an override context
						self.override = context.copy()

						self.override['area'] = area
						self.override['region'] = region
						self.override['space_data'] = space
						self.override['scene'] = context.scene
						self.override['view_layer'] = context.view_layer


						# ADJUST VIEWPORT SETTINGS
						# set space to WIREFRAME
						# space.shading.type = 'WIREFRAME'

						# set FOV to 14° as suggested by the LookingGlassFactory documentation
						# we calculate the field of view from the projection matrix
						self.viewportViewMatrix = space.region_3d.view_matrix.inverted()
						projectionMatrix = space.region_3d.perspective_matrix @ self.viewportViewMatrix

						# FOV = 2 * arctan(sensor_size / focal_length)
						# => focal_length = sensor_size / tan(FOV / 2)
						#
						# for Blender viewport: fov = degrees(2.0 * atan(1.0 / projectionMatrix[1][1]))
						#
						# since we only know the ratio "sensor_size / focal_length", which is given by "1 / projectionMatrix[1][1]",
						# we need to calculate sensor_size from the projection matrix and the focal length and than set the new
						# focal length
						sensor_size = space.lens / projectionMatrix[1][1]

						# set the new focal length, corresponding to a FOV of 14°
						space.lens = sensor_size / tan(radians(14 / 2))

						# lock viewport to local camera
						space.use_local_camera = True
						space.lock_camera = True

						# set space to a specific camera (automatically None, if none is selected)
						space.camera = context.window_manager.lookingglassCamera

						# if a camera is selected
						if context.window_manager.lookingglassCamera != None:

							# set view mode to "CAMERA"
							space.region_3d.view_perspective = 'CAMERA'

						# hide header
						space.show_region_header = False
						space.show_region_tool_header = False
						space.show_region_toolbar = False
						space.show_region_ui = False
						space.show_gizmo = False
						space.show_gizmo_tool = False

					break

				break




		# REGISTER ALL HANDLERS FOR THE LIGHTFIELD RENDERING
		################################################################

		# HANDLERS FOR CONTROL PURPOSES
		# ++++++++++++++++++++++++++++++
		# we exploit the draw_hanlder of the SpaceView3D to track the SpaceView which is currently modified by the user
		self._handle_trackActiveSpaceView3D = bpy.types.SpaceView3D.draw_handler_add(self.trackActiveSpaceView3D, (context,), 'WINDOW', 'PRE_VIEW')

		# we exploit the draw_hanlder of the SpaceView3D to track the SpaceView which is currently modified by the user
		self._handle_trackViewportUpdates = bpy.types.SpaceView3D.draw_handler_add(self.trackViewportUpdates, (context,), 'WINDOW', 'PRE_VIEW')

		# Register app handlers that check if the LookingGlass shall be updated:
		#  (1) Every time something in the scene changed (for camera movement and scene editing)
		#  (2) Every time, the current frame changed (for animations)
		self._handle_trackDepsgraphUpdates = bpy.app.handlers.depsgraph_update_post.append(self.trackDepsgraphUpdates)
		self._handle_trackFrameChanges = bpy.app.handlers.frame_change_post.append(self.trackDepsgraphUpdates)



		# HANDLERS FOR DRAWING PURPOSES
		# ++++++++++++++++++++++++++++++
		# TODO: this needs to be adjusted to enable switching between resolutions with different numbers of views
		# draw handler for rendering the views
		# NOTE: - we use 45 handlers, because this enables rendering of all views at maximum speed (limited by the fps of the Blender viewport)
		for view in range(0, 45, 1):#self.qs[self.preset]["totalViews"]):

			self._handle_viewDrawing.append(bpy.types.SpaceView3D.draw_handler_add(self.copyViewToQuilt, (context, view), 'WINDOW', 'POST_PIXEL'))

		# draw callback to draw the lightfield in the window
		self._handle_lightfieldDrawing = bpy.types.SpaceView3D.draw_handler_add(self.drawLightfield, (context,), 'WINDOW', 'POST_PIXEL')




		print("Invoked modal operator: ", time.time() - start)

		# Create timer event that runs every millisecond to check if the lightfield needs to be updated
		self.timerEvent = context.window_manager.event_timer_add(0.001, window=context.window)

		# add the modal handler
		context.window_manager.modal_handler_add(self)

		# keep the modal operator running
		return {'RUNNING_MODAL'}



	# modal operator for controlled redrawing of the lightfield
	def modal(self, context, event):



		# Check, whether the lightfield window still exists
		################################################################
		# search in all open Blender windows
		self.WindowCheck = False
		for window in context.window_manager.windows:
			if window == LookingGlassAddon.lightfieldWindow:
				self.WindowCheck = True
				break

		# if it doesn't exist OR should be closed
		if self.WindowCheck == False:

			# cancel the operator
			return self.cancel(context)


		# Control lightfield redrawing in viewport mode
		################################################################

		# if the TIMER event for the lightfield rendering is called AND the live view is active
		if event.type == 'TIMER' and int(self.window_manager.renderMode) == 0:

			# if something has changed
			if self.modal_redraw == True or (self.depsgraph_update_time != 0.000 and time.time() - self.depsgraph_update_time > 0.5) or (int(context.window_manager.liveMode) == 1 and context.window_manager.liveview_manual_refresh == True):

				if (self.depsgraph_update_time != 0.000 and time.time() - self.depsgraph_update_time > 0.5) or (int(context.window_manager.liveMode) == 1 and context.window_manager.liveview_manual_refresh == True):

					# set to the currently chosen quality
					self.preset = int(context.window_manager.viewResolution)

 					# set to redraw
					self.modal_redraw = True

					# reset time variable
					self.depsgraph_update_time = 0.000

				# reset status variable for manual refreshes
				context.window_manager.liveview_manual_refresh = False

				# update the viewport settings
				self.updateViewportSettings()

				# running modal
				return {'RUNNING_MODAL'}


		# Control events in the viewport
		################################################################
		if event.type == 'LEFTMOUSE':

			# print("Event: ", event.type, event.mouse_x, event.mouse_region_x)

			return {'PASS_THROUGH'}


		# if the live view mode is inactive
		elif int(self.window_manager.liveMode) != 0:

			# we prevent any event handling by Blender in the lightfield viewport
			return {'RUNNING_MODAL'}

		# pass event through
		return {'PASS_THROUGH'}



	# Application handler that continously checks for changes of the
	# Multiview used for Looking Glass rendering
	def trackViewportUpdates(self, context):

		# if this call belongs to the lightfield window
		if context.window == LookingGlassAddon.lightfieldWindow:

			# if automatic live view is activated AND the lightfield viewport is in perspective view mode AND a valid lightfield viewport exists
			if (int(self.window_manager.renderMode) == 0 and int(self.window_manager.liveMode) == 0) and LookingGlassAddon.lightfieldSpace != None:

				# if no camera is selected for the Looking Glass AND the viewport perspective matrix has changed
				if LookingGlassAddon.lightfieldSpace.camera == None and (LookingGlassAddon.lightfieldSpace.region_3d.view_matrix != self.viewportViewMatrix):
					# print("VIEWPORT UPDATE: ", self.viewportViewMatrix)

					# update the control variable
					self.viewportViewMatrix = LookingGlassAddon.lightfieldSpace.region_3d.view_matrix.copy()

					# invoke an update of the Looking Glass viewport
					self.modal_redraw = True
					#self.updateQuilt = True

					# remember time of last depsgraph update
					self.depsgraph_update_time = time.time()

					# if the low quality quilt settings are inactive, but should be active
					if self.preset < 3 and self.window_manager.liveview_use_lowres_preview == True:

						# activate them
						self.preset = 3



	# Application handler that continously checks for changes of the
	# Multiview used for Looking Glass rendering
	def trackDepsgraphUpdates(self, scene, depsgraph):

		# if automatic live view is activated AND something in the scene has changed
		if (int(self.window_manager.renderMode) == 0 and int(self.window_manager.liveMode) == 0) and len(depsgraph.updates.values()) > 0:
			#print("DEPSGRAPH UPDATE: ", len(depsgraph.updates.values()), self.preset)

			# invoke an update of the Looking Glass viewport
			self.modal_redraw = True
			#self.updateQuilt = True

			# remember time of last depsgraph update
			self.depsgraph_update_time = time.time()

			# if the low quality quilt settings are inactive, but should be active
			if self.preset < 3 and self.window_manager.liveview_use_lowres_preview == True:

				# activate them
				self.preset = 3



	# this function is called as a draw handler to enable the Looking Glass Addon
	# to keep track of the SpaceView3D which is currently manipulated by the User
	def trackActiveSpaceView3D(self, context):

		# if the space data exists
		if context.space_data != None and LookingGlassAddon.BlenderWindow != LookingGlassAddon.lightfieldWindow:

			# in any case, we need to track the active window
			# NOTE: this is important for finding the correct "Scene" and "View Layer"
			LookingGlassAddon.BlenderWindow = context.window

			# if the user chose to automatically track the viewport
			if self.window_manager.blender_track_viewport == True:

				# if the user activated the option to
				# use the shading and overlay settings of the currently used Blender 3D viewport
				if self.window_manager.viewportMode == 'BLENDER' and context.space_data != LookingGlassAddon.lightfieldSpace:

					# save the current space data in the global variable
					LookingGlassAddon.BlenderViewport = context.space_data

					# set the Workspace list to the current workspace
					self.window_manager.blender_workspace = context.workspace.name

					# set the 3D View list to the current 3D view
					self.window_manager.blender_view3d = str(LookingGlassAddon.BlenderViewport)



	# set up quilt settings
	def setupQuilt(self, preset):

		# there are 3 presets to choose from:
		# - standard settings
		self.qs.append({
				"width": 2048,
				"height": 2048,
				"columns": 4,
				"rows": 8,
				"totalViews": 32,
				"quiltOffscreen": None,
				"viewOffscreens": []
				})

		# - high resolution settings (4k)
		self.qs.append({
				"width": 4095,
				"height": 4095,
				"columns": 5,
				"rows": 9,
				"totalViews": 45,
				"quiltOffscreen": None,
				"viewOffscreens": []
				})

		# - 8k settings
		self.qs.append({
				"width": 4096 * 2,
				"height": 4096 * 2,
				"columns": 5,
				"rows": 9,
				"totalViews": 45,
				"quiltOffscreen": None,
				"viewOffscreens": []
				})

		# - LOW RESOLUTION FOR PREVIEW
		self.qs.append({
				"width": 512,
				"height": 512,
				"columns": 5,
				"rows": 9,
				"totalViews": 45,
				"quiltOffscreen": None,
				"viewOffscreens": []
				})


		# iterate through all presets
		for i in range(0, len(self.qs), 1):

			# calculate viewWidth and viewHeight
			self.qs[i]["viewWidth"] = int(self.qs[i]["width"] / self.qs[i]["columns"])
			self.qs[i]["viewHeight"] = int(self.qs[i]["height"] / self.qs[i]["rows"])

			# create a GPUOffscreen for the quilt / lightfield
			self.qs[i]["quiltOffscreen"] = gpu.types.GPUOffScreen(self.qs[i]["width"], self.qs[i]["height"])

			# create a list for the GPUOffscreens of the different views
			for view in range(0, self.qs[i]["totalViews"], 1):

				self.qs[i]["viewOffscreens"].append(gpu.types.GPUOffScreen(int(self.qs[i]["viewWidth"]), int(self.qs[i]["viewHeight"])))


		# set the last preset to the default value
		self.preset = preset
		self.last_preset = self.preset


	# pass quilt values to shader
	def passQuiltSettingsToShader(self):

		# Pass quilt settings to the lightfield shader
		self.lightFieldShader.bind()

		self.lightFieldShader.uniform_int("overscan", 0)
		self.lightFieldShader.uniform_int("tile_x", self.qs[self.preset]["columns"])
		self.lightFieldShader.uniform_int("tile_y", self.qs[self.preset]["rows"])
		self.lightFieldShader.uniform_int("tile_z", self.qs[self.preset]["totalViews"])

		# set viewportion to the full view
		#print("viewPortion: ", (self.qs[self.preset]["viewWidth"] * self.qs[self.preset]["columns"] / self.qs[self.preset]["width"], self.qs[self.preset]["viewHeight"] * self.qs[self.preset]["rows"] / self.qs[self.preset]["height"]))
		self.lightFieldShader.uniform_float("viewPortion_x", self.qs[self.preset]["viewWidth"] * self.qs[self.preset]["columns"] / self.qs[self.preset]["width"])
		self.lightFieldShader.uniform_float("viewPortion_y", self.qs[self.preset]["viewHeight"] * self.qs[self.preset]["rows"] / self.qs[self.preset]["height"])




	# TODO: Check, if the utilization of a blit shader would have any benefit in Blender. Otherwise remove this here.
	# Compile the blit shader, which can copy a view into the
	# correct position in the quilt
	def loadBlitShaders(self):

		# Blit shader sourcecodes
		self.blitVertexShaderSource = '''
			out vec2 texCoords;

			layout (location = 0)
			in vec2 vertPos_data;

			void main()
			{
				gl_Position = vec4(vertPos_data.xy, 0.0, 1.0);
				texCoords = (vertPos_data.xy + 1.0) * 0.5;
			}
		'''

		self.blitFragmentShaderSource = '''
			out vec4 fragColor;

			in vec2 texCoords;

			uniform sampler2D blitTex;
			void main()
			{
				fragColor = texture(blitTex, texCoords.xy);
			}
		'''

		# set up fullscreen quad vertices
		vertPos_data = ((-1, -1), (1, 1), (1, 1), (-1, -1))

		# Compile shader via GPU module
		self.blitShader = gpu.types.GPUShader(self.blitVertexShaderSource, self.blitFragmentShaderSource)
		self.blitShaderBatch = batch_for_shader(
			self.blitShader, 'TRIS',
			{"vertPos_data": vertPos_data,},
		)
		print(self.blitShader, self.blitShader.program)
		# return the OpenGL program code
		return self.blitShader.program



	# Compile the lightfield shader, which prepares the quilt for display
	# on the LookingGlass as a hologram
	def loadlightFieldShaders(self):

		# Vertex shader
		self.lightfieldVertexShaderSource = '''
			layout (location = 0)
			in vec2 vertPos_data;
			out vec2 texCoords;
			void main()
			{
				gl_Position = vec4(vertPos_data.xy, 0.0, 1.0);
				texCoords = (vertPos_data.xy + 1.0) * 0.5;
			}
		'''

		# Fragment shader
		self.lightfieldFragmentShaderSource = '''
			in vec2 texCoords;
			out vec4 fragColor;

			// Calibration values
			uniform float pitch;
			uniform float tilt;
			uniform float center;
			uniform int invView;
			uniform float subp;
			uniform float displayAspect;
			uniform int ri;
			uniform int bi;

			// Quilt settings
			uniform int tile_x;
			uniform int tile_y;
			uniform int tile_z;
			// uniform vec3 tile;
			uniform float viewPortion_x;
			uniform float viewPortion_y;
			// uniform vec2 viewPortion;
			uniform float quiltAspect;
			uniform int overscan;
			uniform int quiltInvert;

			// NOTE: added by reg.cs
			// make tile and viewPortion as a vector
			// because I didn't new how to pass a vec uniform
			// with the Blender API
			// - tile = (qs_columns, qs_rows, qs_totalViews)
			// - viewPortion = (self.qs[self.preset]["viewWidth"] * self.qs[self.preset]["columns"] / self.qs[self.preset]["width"], self.qs[self.preset]["viewHeight"] * self.qs_row / self.qs[self.preset]["height"])
			vec3 tile = vec3(tile_x, tile_y, tile_z);
			vec2 viewPortion = vec2(viewPortion_x, viewPortion_y);


			uniform int debug;
			uniform sampler2D screenTex;


			vec2 texArr(vec3 uvz)
			{
				// NOTE: their are 1/qs_totalViews possible values of uvz.z
				//		verification: float z = floor(0.02222222 * view * tile.z); => change view to show the corresponding view from the quilt

				// NOTE: For some reason, I don't understand yet
				//	   I had to change uvz * tile.z to (1 + uvz.z) * tile.z)
				//	   in order to get the correct quilt display
				//
				//	 # TODO => there must be something wrong in my code elsewhere that causes this weird behavior

				// decide which section to take from based on the z.
				float z = floor((1 + uvz.z) * tile.z);
				float x = (mod(z, tile.x) + uvz.x) / tile.x;
				float y = (floor(z / tile.x) + uvz.y) / tile.y;
				return vec2(x, y) * viewPortion.xy;
			}

			// recreate CG clip function (clear pixel if any component is negative)
			void clip(vec3 toclip)
			{
				if (any(lessThan(toclip, vec3(0,0,0)))) discard;
			}

			void main()
			{

				if (debug == 1)
				{

					fragColor = texture(screenTex, texCoords.xy);

				}
				else {
					float invert = 1.0;
					if (invView + quiltInvert == 1) invert = -1.0;
					vec3 nuv = vec3(texCoords.xy, 0.0);
					nuv -= 0.5;
					float modx = clamp (step(quiltAspect, displayAspect) * step(float(overscan), 0.5) + step(displayAspect, quiltAspect) * step(0.5, float(overscan)), 0, 1);
					nuv.x = modx * nuv.x * displayAspect / quiltAspect + (1.0-modx) * nuv.x;
					nuv.y = modx * nuv.y + (1.0-modx) * nuv.y * quiltAspect / displayAspect;
					nuv += 0.5;
					clip (nuv);
					clip (1.0-nuv);
					vec4 rgb[3];
					for (int i=0; i < 3; i++)
					{
						nuv.z = (texCoords.x + i * subp + texCoords.y * tilt) * pitch - center;
						nuv.z = mod(nuv.z + ceil(abs(nuv.z)), 1.0);
						nuv.z *= invert;
						rgb[i] = texture(screenTex, texArr(nuv));
					}
					fragColor = vec4(rgb[ri].r, rgb[1].g, rgb[bi].b, 1.0);
				}
			}
		'''

		# Compile lightfield shader via GPU module
		self.lightFieldShader = gpu.types.GPUShader(self.lightfieldVertexShaderSource, self.lightfieldFragmentShaderSource)

		# prepare a batch used for drawing the lightfield into a texture of correct size
		self.lightFieldShaderBatch = batch_for_shader(
			self.lightFieldShader, 'TRI_FAN',
			{
				"vertPos_data": ((-1, -1), (1, -1), (1, 1), (-1, 1)),
			},
		)

		# return the OpenGL program code
		return self.lightFieldShader.program



	# Load Looking Glass calibration into the lightfield shader
	def loadCalibrationIntoShader(self):

		# if a Looking Glass is selected
		if int(self.window_manager.activeDisplay) > -1:

			# get the calibration data from the deviceList
			for device in LookingGlassAddon.deviceList:

				if device['index'] == int(self.window_manager.activeDisplay):

					# obtain information from the connected Looking Glass and
					# load its calibration into the lightfield shader
					self.lightFieldShader.bind()
					self.lightFieldShader.uniform_float("pitch", device['pitch'])
					self.lightFieldShader.uniform_float("tilt", device['tilt'])
					self.lightFieldShader.uniform_float("center", device['center'])
					self.lightFieldShader.uniform_int("invView", device['invView'])
					self.lightFieldShader.uniform_int("quiltInvert", 0)
					self.lightFieldShader.uniform_float("subp", device['subp'])
					self.lightFieldShader.uniform_int("ri", device['ri'])
					self.lightFieldShader.uniform_int("bi", device['bi'])
					self.lightFieldShader.uniform_float("displayAspect", device['aspectRatio'])
					self.lightFieldShader.uniform_float("quiltAspect", device['aspectRatio'])

					break


	# set up the camera for each view and the shader of the rendering object
	def setupVirtualCameraForView(self, camera, view, viewMatrix, projectionMatrix):

		# get the calibration data of the Looking Glass from the deviceList
		for device in LookingGlassAddon.deviceList:

			if device['index'] == int(self.window_manager.activeDisplay):

				# if a camera is used for the Looking Glass
				if camera != None:

					# The field of view set by the camera
					# NOTE 1: - the Looking Glass Factory documentation suggests to use a FOV of 14°. We use the focal length of the Blender camera instead.
					# NOTE 2: - we take the angle directly from the projection matrix
					fov = 2.0 * atan(1 / projectionMatrix[1][1])

					# calculate cameraSize from its distance to the focal plane and the FOV
					# NOTE: - we take an arbitrary distance of 5 m (we could also use the focal distance of the camera, but might be confusing)
					cameraDistance = self.window_manager.focalPlane # TODO: would camera.data.dof.focus_distance be better?
					cameraSize = cameraDistance * tan(fov / 2)

					# start at viewCone * 0.5 and go up to -viewCone * 0.5
					# TODO: The Looking Glass Factory dicumentation suggests to use a viewcone of 35°, but the device calibration has 40° by default.
					#		Which one should we take?
					offsetAngle = (0.5 - view / (self.qs[self.preset]["totalViews"] - 1)) * radians(device['viewCone'])

					# calculate the offset that the camera should move
					offset = cameraDistance * tan(offsetAngle)

					# translate the view matrix (position) by the calculated offset in x-direction
					viewMatrix = Matrix.Translation((offset, 0, 0)) @ viewMatrix

					# modify the projection matrix, relative to the camera size and aspect ratio
					projectionMatrix[0][2] += offset / (cameraSize * device['aspectRatio'])

				# TODO: THE FOLLOWING WORKS IN PRINCIPLE, BUT IS DISTORTED. WHY?
				# otherwise we take the active viewport camera
				else:

					# The field of view set by the camera
					# NOTE 1: - the Looking Glass Factory documentation suggests to use a FOV of 14°. We use the focal length of the Blender camera instead.
					# NOTE 2: - we take the angle directly from the projection matrix
					fov = 2.0 * atan(1 / projectionMatrix[1][1])

					# calculate cameraSize from its distance to the focal plane and the FOV
					# NOTE: - we take an arbitrary distance of 5 m (TODO: IS THERE A SPECIFIC BETTER VALUE FOR THE VIEWPORT CAM?)
					cameraDistance = self.window_manager.focalPlane #camera.data.dof.focus_distance
					cameraSize = cameraDistance * tan(fov / 2)

					# start at viewCone * 0.5 and go up to -viewCone * 0.5
					# ToDo: The Looking Glass Factory dicumentation suggests to use a viewcone of 35°, but the device calibration has 40° by default. Which one should we take?
					offsetAngle = (0.5 - view / (self.qs[self.preset]["totalViews"] - 1)) * radians(device['viewCone'])

					# calculate the offset that the camera should move
					offset = cameraDistance * tan(offsetAngle)

					# translate the view matrix (position) by the calculated offset in x-direction
					viewMatrix = Matrix.Translation((offset, 0, cameraDistance)) @ viewMatrix

					# modify the projection matrix, relative to the camera size and aspect ratio
					projectionMatrix[0][2] += offset / (cameraSize * device['aspectRatio'])

				break

		# return the projection matrix
		return viewMatrix, projectionMatrix



	# Update the viewport settings
	def updateViewportSettings(self):

		# Adjust the viewport render settings
		######################################################

		# if the settings shall be taken from the current viewport
		if self.window_manager.viewportMode == 'BLENDER':

			# check if the space still exists
			found = False
			for workspace in bpy.data.workspaces:
				for screen in workspace.screens:
					for area in screen.areas:
						for space in area.spaces:
							if space.type == 'VIEW_3D':
								if LookingGlassAddon.BlenderViewport == space:

									# get the area
									LookingGlassAddon.BlenderViewportArea = area

									found = True
									break

			# if the SpaceView3D still exists
			if found == True:

				# SHADING ATTRIBUTES
				# define some exceptions that must not be taken into
				attributeExceptions = ["__doc__", "__module__", "__slots__", "bl_rna", "rna_type"]

				# use the "space data" of the selected viewport
				attributeList = dir(self.override['space_data'].shading)
				for attr in attributeList:

					if not attr in attributeExceptions:
						#print("[SHADING]", attr, " = ", getattr(LookingGlassAddon.BlenderViewport.shading, attr))

						try:
							setattr(self.override['space_data'].shading, attr, getattr(LookingGlassAddon.BlenderViewport.shading, attr))
						except Exception as e:
							print(" # ", e)
							pass

				attributeList = dir(self.override['space_data'].overlay)
				for attr in attributeList:

					if not attr in attributeExceptions:
						#print("[OVERLAY]", attr, " = ", getattr(LookingGlassAddon.BlenderViewport.overlay, attr))

						try:
							setattr(self.override['space_data'].overlay, attr, getattr(LookingGlassAddon.BlenderViewport.overlay, attr))
						except Exception as e:
							print(" # ", e)
							pass

			else:

				# reset the global variable and fall back to custom settings
				LookingGlassAddon.BlenderViewport = None

		# if the custom settings shall be used OR the chosen Blender Viewport is invalid
		if self.window_manager.viewportMode == 'CUSTOM' or LookingGlassAddon.BlenderViewport == None:

			# APPLY THE CURRENT USER SETTINGS FOR THE LIGHTFIELD RENDERING
			# SHADING ATTRIBUTES
			self.override['space_data'].shading.type = self.window_manager.shadingMode
			self.override['space_data'].shading.show_xray = bool(self.window_manager.liveview_show_xray)
			self.override['space_data'].shading.xray_alpha = float(self.window_manager.liveview_xray_alpha)
			self.override['space_data'].shading.use_dof = bool(int(self.window_manager.liveview_use_dof))

			# OVERLAY ATTRIBUTES: Guides
			self.override['space_data'].overlay.show_floor = bool(int(self.window_manager.liveview_show_floor))
			self.override['space_data'].overlay.show_axis_x = bool(int(self.window_manager.liveview_show_axes[0]))
			self.override['space_data'].overlay.show_axis_y = bool(int(self.window_manager.liveview_show_axes[1]))
			self.override['space_data'].overlay.show_axis_z = bool(int(self.window_manager.liveview_show_axes[2]))
			self.override['space_data'].overlay.grid_scale = float(self.window_manager.liveview_grid_scale)
			# OVERLAY ATTRIBUTES: Objects
			self.override['space_data'].overlay.show_extras = bool(int(self.window_manager.liveview_show_extras))
			self.override['space_data'].overlay.show_relationship_lines = bool(int(self.window_manager.liveview_show_relationship_lines))
			self.override['space_data'].overlay.show_outline_selected = bool(int(self.window_manager.liveview_show_outline_selected))
			self.override['space_data'].overlay.show_bones = bool(int(self.window_manager.liveview_show_bones))
			self.override['space_data'].overlay.show_motion_paths = bool(int(self.window_manager.liveview_show_motion_paths))
			self.override['space_data'].overlay.show_object_origins = bool(int(self.window_manager.liveview_show_origins))
			self.override['space_data'].overlay.show_object_origins_all = bool(int(self.window_manager.liveview_show_origins_all))
			# OVERLAY ATTRIBUTES: Geometry
			self.override['space_data'].overlay.show_wireframes = bool(int(self.window_manager.liveview_show_wireframes))
			self.override['space_data'].overlay.show_face_orientation = bool(int(self.window_manager.liveview_show_face_orientation))

		# if the low quality quilt settings are active AND the user selected the "SOLID SHADER PREVIEW" option
		if self.preset == 3 and self.window_manager.liveview_use_solid_preview == True:

			# change the shading type to SOLID
			LookingGlassAddon.lightfieldSpace.shading.type = 'SOLID'

		# always disable the hdri preview spheres
		self.override['space_data'].overlay.show_look_dev = False





	# Draw function which copies data from the 3D View
	def copyViewToQuilt(self, context, view):

		# if the quilt must be redrawn AND the current image editor belongs to the lightfield window AND the Multiview object exists
		if self.modal_redraw == True and context.area == self.lightfieldArea:

			# Update quilt settings
			######################################################

			# if this function call belongs to the first view
			if view == 0:

				self.start_multi_view = time.time()

				# if the quilt and view settings changed
				if self.last_preset != self.preset:

					# update the preset variable
					self.last_preset = self.preset

					# pass quilt settings to the lightfield shader
					self.passQuiltSettingsToShader()

			# print("copyViewToQuilt start (view: ", view, ": ", time.time() - self.start_multi_view, (self.qs[self.preset]["viewOffscreens"][view].width, self.qs[self.preset]["viewOffscreens"][view].height))

			# Render the current view into an offscreen
			######################################################

			# select camera that belongs to the view
			camera = context.window_manager.lookingglassCamera

			# PREPARE THE MODELVIEW AND PROJECTION MATRICES
			# if a camera is selected
			if camera != None:

				# get camera's modelview matrix
				view_matrix = camera.matrix_world.copy()

				# correct for the camera scaling
				view_matrix = view_matrix @ Matrix.Scale(1/camera.scale.x, 4, (1, 0, 0))
				view_matrix = view_matrix @ Matrix.Scale(1/camera.scale.y, 4, (0, 1, 0))
				view_matrix = view_matrix @ Matrix.Scale(1/camera.scale.z, 4, (0, 0, 1))

				# calculate the inverted view matrix because this is what the draw_view_3D function requires
				view_matrix = view_matrix.inverted()

				# get the camera's projection matrix
				projection_matrix = camera.calc_matrix_camera(
						bpy.data.scenes[LookingGlassAddon.BlenderWindow.scene.name].view_layers[LookingGlassAddon.BlenderWindow.view_layer.name].depsgraph,
						x = self.qs[self.preset]["viewWidth"],# for final renders: x = bpy.context.scene.render.resolution_x,
						y = self.qs[self.preset]["viewHeight"],# for final renders: y = bpy.context.scene.render.resolution_y,
						scale_x = ((LookingGlassAddon.lightfieldWindow.width / LookingGlassAddon.lightfieldWindow.height) / (self.qs[self.preset]["rows"] / self.qs[self.preset]["columns"])), # for final renders: bpy.context.scene.render.pixel_aspect_x,
						scale_y = 1, # for final renders: bpy.context.scene.render.pixel_aspect_y,
					)

			# otherwise we take the lightfield viewport matrices
			else:

				# get viewports modelview matrix
				view_matrix = LookingGlassAddon.lightfieldSpace.region_3d.view_matrix.copy()

				# get the viewports projection matrix
				projection_matrix = LookingGlassAddon.lightfieldSpace.region_3d.window_matrix.copy()

			# calculate the offset-projection of the current view
			view_matrix, projection_matrix = self.setupVirtualCameraForView(camera, view, view_matrix, projection_matrix)



			# RENDER THE VIEW INTO THE OFFSCREEN
			# draw the viewport rendering to the offscreen for the current view
			start_test = time.time()
			self.qs[self.preset]["viewOffscreens"][view].draw_view3d(
				# we use the "Scene" and the "View Layer" that is active in the Window
				# the user currently works in
				LookingGlassAddon.BlenderWindow.scene,
				LookingGlassAddon.BlenderWindow.view_layer,
				self.override['space_data'],
				self.override['region'],
				view_matrix,
				projection_matrix)

			#print("draw_view3d (view: ", view, "): ", time.time() - start_test)
			# print("copyViewToQuilt end: ", time.time() - self.start_multi_view)

			# if this was the last view
			if view == self.qs[self.preset]["totalViews"] - 1:

				# update the quilt image in the image_editor,
				# which is used for display in the LookingGlass
				self.updateQuilt = True

				# reset draw variable:
				# This is here to prevent excessive redrawing
				self.modal_redraw = False



	# Blit all the views into the quilt, if something has changed
	# and then apply the lightfield shader. Finally, draw the lightfield
	# directly into the SpaceView3D created for the LookingGlass.
	def drawLightfield(self, context):

		# if this call belongs to the lightfield window
		if context.window == LookingGlassAddon.lightfieldWindow:

			#print("drawQuilt ", self.updateQuilt)

			# if the live view mode is active
			if int(self.window_manager.renderMode) == 0:

				start_blit = time.time()
				# if the quilt must be updated
				if self.updateQuilt == True:

					# bind the offscreen used for the quilt
					with self.qs[self.preset]["quiltOffscreen"].bind():

						start_blit = time.time()
						# for all views
						for view in range(self.qs[self.preset]["totalViews"]):

							# push/pop the projection matrices
							with gpu.matrix.push_pop_projection():

								# reset matrices:
								# Use normalized device coordinates [-1, 1]
								gpu.matrix.load_matrix(Matrix.Identity(4))
								gpu.matrix.load_projection_matrix(Matrix.Identity(4))

								# calculate the position of the view
								x = (view % self.qs[self.preset]["columns"]) * self.qs[self.preset]["viewWidth"]
								y = int(view / self.qs[self.preset]["columns"]) * self.qs[self.preset]["viewHeight"]

								# Copy the view texture into the quilt texture,
								# but transform the position and dimensions to
								# normalized device coordinates before that
								draw_texture_2d(self.qs[self.preset]["viewOffscreens"][view].color_texture, (2 * x / self.qs[self.preset]["width"] - 1, 2 * y / self.qs[self.preset]["height"] - 1), 2 * self.qs[self.preset]["viewWidth"] / self.qs[self.preset]["width"], 2 * self.qs[self.preset]["viewHeight"] / self.qs[self.preset]["height"])

								# print("Copied view ", view, (x, y), " into the quilt texture. Required time: ", time.time() - start_blit)

			# if the quilt view mode is active AND an image is loaded
			elif int(self.window_manager.renderMode) == 1 and context.window_manager.quiltImage != None:

				# copy the image that is in the quilt view to the quilt offscreen
				# print("Quilt view mode: ")
				# print(" # ", context.window_manager.quiltImage)

				# if the image is a multiview image
				if context.window_manager.quiltImage.is_multiview == True:

					# Todo: How can I access the views of a multiview to copy them into the quilt?
					print(" # MULTIVIEW IMAGE")

				else:

					# Todo: How can I access the views of a multiview to copy them into the quilt?
					print(" # QUILT IMAGE")

					# assume that we have a 45 view quilt image and load it into a OpenGL texture
					# TODO: Integrate a setting for quilts with 32 images
					context.window_manager.quiltImage.gl_load()

					# bind the offscreen used for the quilt
					with self.qs[self.preset]["quiltOffscreen"].bind(True):

						# reset matrices:
						# Use normalized device coordinates [-1, 1]
						gpu.matrix.load_matrix(Matrix.Identity(4))
						gpu.matrix.load_projection_matrix(Matrix.Identity(4))

						# Blit the image into the quilt texture
						# (use normalized device coordinates)
						draw_texture_2d(context.window_manager.quiltImage.bindcode, (-1, -1), 2, 2)

					# free the previously created OpenGL texture
					context.window_manager.quiltImage.gl_free()


			# Draw the lightfield
			##################################################################
			start_blit = time.time()

			# bind the quilt texture
			bgl.glActiveTexture(bgl.GL_TEXTURE0)
			bgl.glBindTexture(bgl.GL_TEXTURE_2D, self.qs[self.preset]["quiltOffscreen"].color_texture)

			# bind the lightfield shader for drawing operations
			self.lightFieldShader.bind()

			# load the current debug view mode into the shader
			self.lightFieldShader.uniform_int("debug", context.window_manager.debug_view)

			# draw the quilt texture
			self.lightFieldShaderBatch.draw(self.lightFieldShader)

			# if the quilt was updated
			if self.updateQuilt == True:

				# reset state variable to avoid excessive redrawing
				self.updateQuilt = False







# ------------ CAMERA FRUSTUM RENDERING -------------
# Modal operator for rendering a camera frustum reprsenting the Looking Glass
# in Blenders 3D viewport
class LOOKINGGLASS_OT_render_frustum(bpy.types.Operator):

	bl_idname = "render.frustum"
	bl_label = "Looking Glass Frustum Rendering"
	bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

	# WINDOW RELATED VARIABLES
	window_manager = None

	# HANDLER IDENTIFIERS
	_handle_drawCameraFrustum = None



	# Inititalize the Looking Glass
	@classmethod
	def __init__(self):

		print("Initializing the frustum rendering operator ...")



	# delete all objects
	@classmethod
	def __del__(self):

		print("Stopped the frustum rendering operator ...")




    # poll method
	@classmethod
	def poll(self, context):

		# return True, so the operator is executed
		return True




	# cancel the modal operator
	def cancel(self, context):

		print("Removing draw handler: ")

		# remove the handler for the frustum drawing
		if self._handle_drawCameraFrustum: bpy.types.SpaceView3D.draw_handler_remove(self._handle_drawCameraFrustum, 'WINDOW')

		print("Everything is done.")


		# return None since this is expected by the operator
		return None




	def invoke(self, context, event):
		start = time.time()

		# make an internal variable for the window_manager,
		# which can be accessed from methods that have no "context" parameter
		self.window_manager = context.window_manager



		# SETUP THE FRUSTUM
		################################################################

		# setup the frustum & shader
		self.setupCameraFrustumShader()




		# REGISTER ALL HANDLERS FOR THE FRUSTUM RENDERING
		################################################################

		# HANDLERS FOR DRAWING PURPOSES
		# ++++++++++++++++++++++++++++++
		# draw handler to display the frustum of the Looking Glass camera
		self._handle_drawCameraFrustum = bpy.types.SpaceView3D.draw_handler_add(self.drawCameraFrustum, (context,), 'WINDOW', 'POST_VIEW')

		print("Invoked modal operator: ", time.time() - start)

		# add the modal handler
		self.window_manager.modal_handler_add(self)

		# keep the modal operator running
		return {'RUNNING_MODAL'}



	# modal operator for controlled redrawing of the lightfield
	def modal(self, context, event):

		# pass event through
		return {'PASS_THROUGH'}



	# setup the camera frustum shader
	def setupCameraFrustumShader(self):

		# we use our own vertex shader, which basically is the Blender internal '3D_UNIFORM_COLOR',
		# but which has additional uniforms that we can use to parse the frustum vertices

		frustum_vertex_shader = '''

			uniform mat4 ModelViewProjectionMatrix;

			// the variables defining the frustum and focal plane
			uniform float clipStart;
			uniform float clipEnd;
			uniform float focalPlane;
			uniform float angle;
			uniform float aspectRatio;

			#ifdef USE_WORLD_CLIP_PLANES
			uniform mat4 ModelMatrix;
			#endif

			in vec3 pos;

			void main()
			{
				// calculate


				gl_Position = ModelViewProjectionMatrix * vec4(pos, 1.0);

			#ifdef USE_WORLD_CLIP_PLANES
			  world_clip_planes_calc_clip_distance((ModelMatrix * vec4(pos, 1.0)).xyz);
			#endif
			}
		'''


		# we predefine the indices because these never change
		self.frustum_indices_lines = (
			(0, 1), (0, 3), (1, 2), (3, 2),
			(4, 5), (4, 7), (5, 6), (7, 6),
			(0, 4), (1, 5), (3, 7), (2, 6))

		self.frustum_indices_faces = (
				# front
				(0, 1, 2),
				(2, 3, 0),
				# right
				(1, 5, 6),
				(6, 2, 1),
				# back
				(7, 6, 5),
				(5, 4, 7),
				# left
				(4, 0, 3),
				(3, 7, 4),
				# bottom
				(4, 5, 1),
				(1, 0, 4),
				# top
				(3, 2, 6),
				(6, 7, 3)
			)

		self.frustum_indices_focalplane_outline = (
			(8, 9), (9, 10), (10, 11), (11, 8))

		self.frustum_indices_focalplane_face = (
				# focal plane
				(8, 9, 10),
				(10, 11, 8)
			)


		# compile the shader that will be used for drawing
		self.frustum_shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')





	# drawing function, which draws the camera frustum in the active SpaceView3D
	def drawCameraFrustum(self, context):

		# if a camera is selected AND the space is not in camera mode
		if self.window_manager.lookingglassCamera != None and context.space_data.region_3d.view_perspective != 'CAMERA':

			# currently selected device and its calibration data
			device = LookingGlassAddon.deviceList[int(self.window_manager.activeDisplay)]

			# currently selected camera
			camera = self.window_manager.lookingglassCamera

			# get modelview matrix
			view_matrix = camera.matrix_world # cameraLookingGlassAddon.BlenderViewport.region_3d.view_matrix.copy()

			# we obtain the viewframe of the camera to calculate the focal and clipping world_clip_planes_calc_clip_distance
			# based on the intercept theorems
			view_frame = camera.data.view_frame(scene=bpy.context.scene)
			view_frame_upper_right = view_frame[0]
			view_frame_lower_right = view_frame[1]
			view_frame_lower_left = view_frame[2]
			view_frame_upper_left = view_frame[3]
			view_frame_distance = abs(view_frame_upper_right[2])

			# get the clipping settings
			clipStart = camera.data.clip_start
			clipEnd = camera.data.clip_end

			# TODO: Find a way to predefine the vertex buffers and batches so that these don't need to be created in every frame
			# define the vertices of the camera frustum in camera coordinates
			# NOTE: - the z-value is negative, because the Blender camera always looks into negative z-direction
			coords_local = [
							# near clipping plane
							(view_frame_lower_right[0] / view_frame_distance * clipStart, view_frame_lower_right[1] / view_frame_distance * clipStart, -clipStart), (view_frame_lower_left[0] / view_frame_distance * clipStart, view_frame_lower_left[1] / view_frame_distance * clipStart, -clipStart),
							(view_frame_upper_left[0] / view_frame_distance * clipStart, view_frame_upper_left[1] / view_frame_distance * clipStart, -clipStart), (view_frame_upper_right[0] / view_frame_distance * clipStart, view_frame_upper_right[1] / view_frame_distance * clipStart, -clipStart),
							# far clipping plane
							(view_frame_lower_right[0] / view_frame_distance * clipEnd, view_frame_lower_right[1] / view_frame_distance * clipEnd, -clipEnd), (view_frame_lower_left[0] / view_frame_distance * clipEnd, view_frame_lower_left[1] / view_frame_distance * clipEnd, -clipEnd),
							(view_frame_upper_left[0] / view_frame_distance * clipEnd, view_frame_upper_left[1] / view_frame_distance * clipEnd, -clipEnd), (view_frame_upper_right[0] / view_frame_distance * clipEnd, view_frame_upper_right[1] / view_frame_distance * clipEnd, -clipEnd),
							# focal plane
							(view_frame_lower_right[0] / view_frame_distance * self.window_manager.focalPlane, view_frame_lower_right[1] / view_frame_distance * self.window_manager.focalPlane, -self.window_manager.focalPlane), (view_frame_lower_left[0] / view_frame_distance * self.window_manager.focalPlane, view_frame_lower_left[1] / view_frame_distance * self.window_manager.focalPlane, -self.window_manager.focalPlane),
							(view_frame_upper_left[0] / view_frame_distance * self.window_manager.focalPlane, view_frame_upper_left[1] / view_frame_distance * self.window_manager.focalPlane, -self.window_manager.focalPlane), (view_frame_upper_right[0] / view_frame_distance * self.window_manager.focalPlane, view_frame_upper_right[1] / view_frame_distance * self.window_manager.focalPlane, -self.window_manager.focalPlane),
							]

			# if the camera fustum shall be drawn
			if self.window_manager.showFrustum == True:
				batch_lines = batch_for_shader(self.frustum_shader, 'LINES', {"pos": coords_local}, indices=self.frustum_indices_lines)
				batch_faces = batch_for_shader(self.frustum_shader, 'TRIS', {"pos": coords_local}, indices=self.frustum_indices_faces)

			# if the focal plane shall be drawn
			if self.window_manager.showFocalPlane == True:
				batch_focalplane_outline = batch_for_shader(self.frustum_shader, 'LINES', {"pos": coords_local}, indices=self.frustum_indices_focalplane_outline)
				batch_focalplane_face = batch_for_shader(self.frustum_shader, 'TRIS', {"pos": coords_local}, indices=self.frustum_indices_focalplane_face)

			# draw everything
			self.frustum_shader.bind()

			# get the current projection matrix
			viewMatrix = gpu.matrix.get_model_view_matrix()
			projectionMatrix = gpu.matrix.get_projection_matrix()

			# load the model view matrix, which transforms the local camera coordinates to world coordinates.
			# this makes sure that the frustum is always drawn relative to the camera location
			gpu.matrix.reset()
			gpu.matrix.load_matrix(viewMatrix @ view_matrix)
			gpu.matrix.load_projection_matrix(projectionMatrix)

			bgl.glEnable(bgl.GL_DEPTH_TEST)
			bgl.glDepthMask(bgl.GL_TRUE)

			# if the camera fustum shall be drawn
			if self.window_manager.showFrustum == True:
				# draw outline
				self.frustum_shader.uniform_float("color", (0.3, 0, 0, 1))
				batch_lines.draw(self.frustum_shader)

			# if the focal plane shall be drawn
			if self.window_manager.showFocalPlane == True:
				# draw focal plane outline
				self.frustum_shader.uniform_float("color", (1, 1, 1, 1))
				batch_focalplane_outline.draw(self.frustum_shader)

			bgl.glDepthMask(bgl.GL_FALSE)
			bgl.glDisable(bgl.GL_DEPTH_TEST)
			bgl.glEnable(bgl.GL_BLEND)

			# if the camera fustum shall be drawn
			if self.window_manager.showFrustum == True:
				# fill faces
				self.frustum_shader.uniform_float("color", (0.5, 0.5, 0.5, 0.05))
				batch_faces.draw(self.frustum_shader)

			# if the focal plane shall be drawn
			if self.window_manager.showFocalPlane == True:
				# draw focal plane face
				self.frustum_shader.uniform_float("color", (0.1, 0.1, 0.1, 0.1))
				batch_focalplane_face.draw(self.frustum_shader)

			bgl.glDisable(bgl.GL_BLEND)

			# reset the matrices to their original state
			gpu.matrix.reset()
			gpu.matrix.load_matrix(viewMatrix)
			gpu.matrix.load_projection_matrix(projectionMatrix)
