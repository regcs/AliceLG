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

import sys, platform
import bpy, bgl
import gpu
import time, timeit
from math import *
from mathutils import *
from gpu_extras.batch import batch_for_shader
from gpu_extras.presets import draw_texture_2d
from bpy_extras.view3d_utils import location_3d_to_region_2d, region_2d_to_origin_3d, region_2d_to_vector_3d
import numpy as np

# TODO: Is there a better way to share global variables between all addon files and operators?
from .globals import *

# append the add-on's path to Blender's python PATH
sys.path.append(LookingGlassAddon.path)
sys.path.append(LookingGlassAddon.libpath)

# TODO: Would be better, if from .lib import pylightio could be called,
#		but for some reason that does not import all modules and throws
#		"AliceLG.lib.pylio has no attribute 'lookingglass"
import pylightio as pylio

# ---------------- GLOBAL ADDON LOGGER -------------------
import logging
LookingGlassAddonLogger = logging.getLogger('Alice/LG')




# ------------ LIGHTFIELD RENDERING -------------
# Modal operator for controlled redrawing of the lightfield window.
class LOOKINGGLASS_OT_render_viewport(bpy.types.Operator):

	bl_idname = "render.viewport"
	bl_label = "Looking Glass Lightfield Viewport rendering"
	bl_options = {'REGISTER', 'INTERNAL', 'UNDO'}


	# PUBLIC CLASS MEMBERS
	# ++++++++++++++++++++++++++++++++++++++++++++++++++

	# ADDON SETTINGS
	settings = None

	# SETTINGS VARIABLES
	preset = 1
	last_preset = 1

	# lightfield
	lightfield_image = None

	# DRAWING OPERATION VARIABLES
	modal_redraw = True
	depsgraph_update_time = 0.000

	# LIGHTFIELD CURSOR
	modified_mouse_x = 0
	modified_mouse_y = 0
	mouse_x = 0
	mouse_y = 0
	cursor = Vector((0, 0, 0))
	normal = Vector((0, 0, 1))

	# DEBUGING VARIABLES
	start_multi_view = 0

	# PROTECTED CLASS MEMBERS
	# ++++++++++++++++++++++++++++++++++++++++++++++++++

	# HANDLER IDENTIFIERS
	_handle_view_rendering = None
	_handle_lightfield_display = None
	_handle_lightfield_cursor = None
	_handle_trackDepsgraphUpdates = None
	_handle_trackFrameChanges = None
	_handle_trackActiveWindow = None


	# METHODS
	# ++++++++++++++++++++++++++++++++++++++++++++++++++
	# poll method
	@classmethod
	def poll(cls, context):

		# if a context exists, execute the operator
		if context: return True



	# cancel the modal operator
	def cancel(self, context):

		# log info
		LookingGlassAddonLogger.info("Closing lightfield viewport ...")

		# stop timer
		context.window_manager.event_timer_remove(self.timerEvent)

		# remove the app handler that checks for depsgraph updates
		bpy.app.handlers.depsgraph_update_post.remove(self.trackDepsgraphUpdates)
		bpy.app.handlers.frame_change_post.remove(self.trackDepsgraphUpdates)

		# remove the handler for the viewport tracking
		if self._handle_trackActiveWindow: bpy.types.SpaceView3D.draw_handler_remove(self._handle_trackActiveWindow, 'WINDOW')

		# log info
		LookingGlassAddonLogger.info(" [#] Cancelled control handlers.")

		# remove the draw handlers for all quilt views
		if self._handle_view_rendering: bpy.types.SpaceView3D.draw_handler_remove(self._handle_view_rendering, 'WINDOW')

		# remove the draw handler for the lightfield cursor
		if self._handle_lightfield_cursor: bpy.types.SpaceView3D.draw_handler_remove(self._handle_lightfield_cursor, 'WINDOW')

		# remove the draw handler for the displaying the lightfield on the device
		if self._handle_lightfield_display: bpy.types.SpaceView3D.draw_handler_remove(self._handle_lightfield_display, 'WINDOW')

		# log info
		LookingGlassAddonLogger.info(" [#] Cancelled drawing handlers.")

		# iterate through all presets
		for i, preset in self.qs.items():

			# free the GPUOffscreen for the view rendering
			self.qs[i]["viewOffscreen"].free()

		# log info
		LookingGlassAddonLogger.info(" [#] Freed GPUOffscreens of the lightfield views.")

		# set status variables to default state
		#LookingGlassAddon.BlenderWindow = None
		LookingGlassAddon.BlenderViewport = None

		# set the button controls for the lightfield window to False
		self.settings.ShowLightfieldWindow = False

			# make current scene the invoking scene
			LookingGlassAddon.LightfieldWindowInvoker = context.scene

			# iterate through all scenes
			for scene in bpy.data.scenes:
				if scene != None and scene.settings != None:

		# SCENE UPDATES
		# ++++++++++++++++++++++++++
		if context != None:

			# make current scene the invoking scene
			LookingGlassAddon.LightfieldWindowInvoker = context.scene

			# iterate through all scenes
			for scene in bpy.data.scenes:
				if scene != None and scene.settings != None:

					# update the status variables
					scene.settings.ShowLightfieldWindow = False

			# reset global variable
			LookingGlassAddon.LightfieldWindowInvoker = None

		# clear the quilt
		self.device.clear()

		# free the view data of the lightfield image
		if self.lightfield_image: self.lightfield_image.clear_views()

		# delete the current LightfieldImage
		if self.lightfield_image: self.lightfield_image = None

		# log info
		LookingGlassAddonLogger.info(" [#] Done.")

	# invoke the operator
	def invoke(self, context, event):
		start = time.time()

		# log info
		LookingGlassAddonLogger.info("Invoking lightfield viewport ...")

		# get the current settings of this scene
		self.settings = context.scene.settings

		# update the variable for the current Looking Glass device
		if int(self.settings.activeDisplay) != -1: self.device = pylio.DeviceManager.get_active()



		# PREPARE THE OFFSCREEN RENDERING
		################################################################

		# set to the currently chosen quality
		self.preset = self.last_preset = int(context.scene.settings.quiltPreset)

		# get all quilt presets from pylio
		self.qs = pylio.LookingGlassQuilt.formats.get()

		# iterate through all presets
		for i, preset in self.qs.items():

			# create a GPUOffscreen for the views
			self.qs[i]["viewOffscreen"] = gpu.types.GPUOffScreen(int(self.qs[i]["view_width"]), int(self.qs[i]["view_height"]))

		# log info
		LookingGlassAddonLogger.info(" [#] Prepared GPUOffscreens for view rendering.")


		# PREPARE THE OVERRIDE CONTEXT THAT CONTAINS THE RENDER SETTINGS
		################################################################

		# create an override context from the invoking context
		self.override = context.copy()

		# update the viewport settings
		self.updateViewportSettings(context)

		# log info
		LookingGlassAddonLogger.info(" [#] Created override context.")


		# REGISTER ALL HANDLERS FOR THE LIGHTFIELD RENDERING
		################################################################

		# HANDLERS FOR CONTROL PURPOSES
		# ++++++++++++++++++++++++++++++
		# we exploit the draw_hanlder of the SpaceView3D to track the SpaceView which is currently modified by the user
		self._handle_trackActiveWindow = bpy.types.SpaceView3D.draw_handler_add(self.trackActiveWindow, (context,), 'WINDOW', 'PRE_VIEW')

		# Register app handlers that check if the LookingGlass shall be updated:
		#  (1) Every time something in the scene changed (for camera movement and scene editing)
		#  (2) Every time, the current frame changed (for animations)
		self._handle_trackDepsgraphUpdates = bpy.app.handlers.depsgraph_update_post.append(self.trackDepsgraphUpdates)
		self._handle_trackFrameChanges = bpy.app.handlers.frame_change_post.append(self.trackDepsgraphUpdates)

		# log info
		LookingGlassAddonLogger.info(" [#] Initialized control handlers.")

		# HANDLERS FOR DRAWING PURPOSES
		# ++++++++++++++++++++++++++++++
		# draw callback for rendering the views
		self._handle_view_rendering = bpy.types.SpaceView3D.draw_handler_add(self.render_view, (context,), 'WINDOW', 'POST_PIXEL')

		# draw callback to display the lightfield in the Looking Glass
		self._handle_lightfield_display = bpy.types.SpaceView3D.draw_handler_add(self.display_lightfield, (context,), 'WINDOW', 'POST_PIXEL')

		# draw callback to draw the lightfield cursor
		#self._handle_lightfield_cursor = bpy.types.SpaceView3D.draw_handler_add(self.updateLightfieldCursor, (context,), 'WINDOW', 'PRE_VIEW')

		# log info
		LookingGlassAddonLogger.info(" [#] Initialized drawing handlers.")



		# HANDLERS FOR OPERATOR CONTROL
		# ++++++++++++++++++++++++++++++
		# Create timer event that runs every millisecond to check if the lightfield needs to be updated
		self.timerEvent = context.window_manager.event_timer_add(0.001, window=context.window)

		# add the modal handler
		context.window_manager.modal_handler_add(self)

		# log info
		LookingGlassAddonLogger.info(" [#] Initialized modal operator.")
		LookingGlassAddonLogger.info(" [#] Done.")

		# keep the modal operator running
		return {'RUNNING_MODAL'}



	# modal operator for controlled redrawing of the lightfield
	def modal(self, context, event):

		# update the internal variable for the settings, in case the scene has changed
		self.settings = context.scene.settings

		# update the variable for the current Looking Glass device
		if int(self.settings.activeDisplay) != -1: self.device = pylio.DeviceManager.get_active()

		# cancel the operator, if the lightfield viewport was deactivated
		if not self.settings.ShowLightfieldWindow:
			self.cancel(context)
			return {'FINISHED'}

		# if this scene was created AFTER the lightfield viewport was
		# invoked, it might not have the correct setting for the lightfield window
		# button
		if self.settings != None and LookingGlassAddon.LightfieldWindowInvoker != None:

			if self.settings.ShowLightfieldWindow != LookingGlassAddon.LightfieldWindowInvoker.settings.ShowLightfieldWindow:

				# adjust the setting
				self.settings.ShowLightfieldWindow = LookingGlassAddon.LightfieldWindowInvoker.settings.ShowLightfieldWindow



		# Control lightfield redrawing in viewport mode
		################################################################

		# if the TIMER event for the lightfield rendering is called AND the automatic render mode is active
		if event.type == 'TIMER':

			# if something has changed OR the user requested a manual redrawing
			if self.modal_redraw == True or (self.depsgraph_update_time != 0.000 and time.time() - self.depsgraph_update_time > 0.5) or (int(context.scene.settings.lightfieldMode) == 1 and context.scene.settings.viewport_manual_refresh == True):

				# update the viewport settings
				self.updateViewportSettings(context)

				if (self.depsgraph_update_time != 0.000 and time.time() - self.depsgraph_update_time > 0.5) or (int(context.scene.settings.lightfieldMode) == 1 and context.scene.settings.viewport_manual_refresh == True):

					# set to the currently chosen quality
					self.preset = int(context.scene.settings.quiltPreset)

 					# set to redraw
					self.modal_redraw = True

					# reset time variable
					self.depsgraph_update_time = 0.000

					# reset status variable for manual refreshes
					context.scene.settings.viewport_manual_refresh = False

				# running modal
				return {'RUNNING_MODAL'}




		# handle lightfield cursor calculation in the viewport
		################################################################

		# if mouse was moved AND the viewport is in camera view mode
		if event.type == 'MOUSEMOVE' and context.space_data and context.space_data.region_3d.view_perspective == 'CAMERA':

			# save current mouse position
			self.mouse_x = self.modified_mouse_x = event.mouse_x
			self.mouse_y = self.modified_mouse_y = event.mouse_y

			# currently selected camera
			camera = self.settings.lookingglassCamera

			# if the lightfield viewport is attached to a camera AND a Blender viewport is active
			if camera and LookingGlassAddon.BlenderViewport:

				# REMAP MOUSE POSITIONS
				# +++++++++++++++++++++++++++++++++++++++++++++
				# NOTE: - this is required because the "CAMERA" view mode
				#		  does not fill the complete window area

				# get modelview matrix
				view_matrix = camera.matrix_world

				# obtain the viewframe of the camera in 3D coordinates
				view_frame = camera.data.view_frame(scene=context.scene)

				# transform the coordinates from camera to world coordinates
				view_frame = [view_matrix @ p for p in view_frame]

				# transform world coordinates of each edge to screen coordinates in pixels
				view_frame_2D = [location_3d_to_region_2d(context.region, LookingGlassAddon.BlenderViewport.region_3d, p) for p in view_frame]

				# if all viewframe points were obtained
				if any(p is None for p in view_frame_2D) == False:

					# calculate dimensions in pixels
					view_frame_width = abs(view_frame_2D[2][0] - view_frame_2D[0][0])
					view_frame_height = abs(view_frame_2D[1][1] - view_frame_2D[0][1])

					# remap mouse coordinates in complete window to corresponding coordinates in the camera view frame
					self.modified_mouse_x = int(round(view_frame_2D[2][0] + (event.mouse_x / context.region.width) * view_frame_width))
					self.modified_mouse_y = int(round(view_frame_2D[2][1] + (event.mouse_y / context.region.height) * view_frame_height))

			# calculate hit position
			self.updateLightfieldCursor(context)

			# force area redraw to draw the cursor
			if context.area:
				context.area.tag_redraw()

			return {'RUNNING_MODAL'}

		else:

			# pass event through
			return {'PASS_THROUGH'}


	# calculate hit position of a ray cast into the viewport to find the location
	# for the lightfield cursor in the lightfield
	def updateLightfieldCursor(self, context):

		# lightfield cursor is drawn in the Looking Glass viewport
		# because the standard cursor is too small and ... just 2D
		view_direction = region_2d_to_vector_3d(context.region, LookingGlassAddon.BlenderViewport.region_3d, (self.modified_mouse_x, self.modified_mouse_y))
		ray_start = region_2d_to_origin_3d(context.region, LookingGlassAddon.BlenderViewport.region_3d, (self.modified_mouse_x, self.modified_mouse_y))

		# calculate the ray end point (10000 is just an arbitrary length)
		ray_end = ray_start + (view_direction * 10000)

		# cast the ray into the scene
		# NOTE: The first parameter ray_cast expects was changed in Blender 2.91
		if bpy.app.version < (2, 91, 0): result, self.cursor, self.normal, index, object, matrix = context.scene.ray_cast(context.view_layer, ray_start, ray_end)
		if bpy.app.version >= (2, 91, 0): result, self.cursor, self.normal, index, object, matrix = context.scene.ray_cast(context.view_layer.depsgraph, ray_start, ray_end)
		#print("CURSOR HIT TEST RESULT: ", result)
		# if no object was under the mouse cursor
		if self.cursor.length == 0:

			# set normal in view direction
			self.normal = view_direction.normalized()

			# set cursor in onto the focal plane
			self.cursor = ray_start + (view_direction * self.settings.focalPlane)




	# Application handler that continously checks for changes of the depsgraph
	def trackDepsgraphUpdates(self, scene, depsgraph):

		# if no quilt rendering is currently Running
		if LookingGlassAddon.RenderInvoked == False:

			# if automatic live view is activated AND something in the scene has changed
			if (int(self.settings.renderMode) == 0 and int(self.settings.lightfieldMode) == 0) and len(depsgraph.updates.values()) > 0:
				#print("DEPSGRAPH UPDATE: ", depsgraph.updates.values())

				# invoke an update of the Looking Glass viewport
				self.modal_redraw = True

				# remember time of last depsgraph update
				self.depsgraph_update_time = time.time()

				# if the low quality quilt settings are inactive, but should be active
				if self.preset < 3 and self.settings.viewport_use_lowres_preview == True:

					# activate them
					self.preset = 3

			# if quilt viewer is active AND an image is selected
			elif int(self.settings.renderMode) == 1 and scene.settings.quiltImage != None:

				# set status variable
				changed = False

				# go through the updates
				for DepsgraphUpdate in depsgraph.updates.values():
					#print(" # ", DepsgraphUpdate.is_updated_geometry, DepsgraphUpdate.is_updated_shading, DepsgraphUpdate.is_updated_transform, DepsgraphUpdate.id.name)

					# TODO: Hacky, but this identifies color management changes
					if DepsgraphUpdate.is_updated_geometry  == True and DepsgraphUpdate.is_updated_shading == True and DepsgraphUpdate.is_updated_transform == True:

						# update status variable
						changed = True

						break

				# are there any changes in the image or color management settings?
				if LookingGlassAddon.quiltViewAsRender != scene.settings.quiltImage.use_view_as_render or LookingGlassAddon.quiltImageColorSpaceSetting.name != scene.settings.quiltImage.colorspace_settings.name:

					# update status variable
					changed = True

				# update the quilt image, if something had changed
				if changed == True: scene.settings.quiltImage = scene.settings.quiltImage


	# this function is called as a draw handler to enable the Looking Glass Addon
	# to keep track of the SpaceView3D which is currently manipulated by the User
	def trackActiveWindow(self, context):

		# if the space data exists AND this is not the active window
		if context.space_data != None and LookingGlassAddon.BlenderWindow != context.window:

			# in any case, we need to track the active window
			# NOTE: this is important for finding the correct "Scene" and "View Layer"
			LookingGlassAddon.BlenderWindow = context.window



	# set up the camera for each view and the shader of the rendering object
	def setupVirtualCameraForView(self, camera, view, viewMatrix, projectionMatrix):

		# if a camera is used for the Looking Glass
		if camera != None:

			# The field of view set by the camera
			# NOTE 1: - the Looking Glass Factory documentation suggests to use a FOV of 14°. We use the focal length of the Blender camera instead.
			# NOTE 2: - we take the angle directly from the projection matrix
			fov = 2.0 * atan(1 / projectionMatrix[1][1])

			# calculate cameraSize from its distance to the focal plane and the FOV
			# NOTE: - we take an arbitrary distance of 5 m (we could also use the focal distance of the camera, but might be confusing)
			cameraDistance = self.settings.focalPlane
			cameraSize = cameraDistance * tan(fov / 2)

			# start at viewCone * 0.5 and go up to -viewCone * 0.5
			offsetAngle = (0.5 - view / (self.qs[self.preset]["total_views"] - 1)) * radians(self.device.viewCone)

			# calculate the offset that the camera should move
			offset = cameraDistance * tan(offsetAngle)

			# translate the view matrix (position) by the calculated offset in x-direction
			viewMatrix = Matrix.Translation((offset, 0, 0)) @ viewMatrix

			# modify the projection matrix, relative to the camera size and aspect ratio
			projectionMatrix[0][2] += offset / (cameraSize * self.device.aspect)

		# TODO: THE FOLLOWING WORKS IN PRINCIPLE, BUT IS DISTORTED. WHY?
		# otherwise we take the active viewport camera
		else:

			# The field of view set by the camera
			# NOTE 1: - the Looking Glass Factory documentation suggests to use a FOV of 14°. We use the focal length of the Blender camera instead.
			# NOTE 2: - we take the angle directly from the projection matrix
			fov = 2.0 * atan(1 / projectionMatrix[1][1])

			# calculate cameraSize from its distance to the focal plane and the FOV
			# NOTE: - we take an arbitrary distance of 5 m (TODO: IS THERE A SPECIFIC BETTER VALUE FOR THE VIEWPORT CAM?)
			cameraDistance = self.settings.focalPlane
			cameraSize = cameraDistance * tan(fov / 2)

			# start at viewCone * 0.5 and go up to -viewCone * 0.5
			offsetAngle = (0.5 - view / (self.qs[self.preset]["total_views"] - 1)) * radians(self.device.viewCone)

			# calculate the offset that the camera should move
			offset = cameraDistance * tan(offsetAngle)

			# translate the view matrix (position) by the calculated offset in x-direction
			viewMatrix = Matrix.Translation((offset, 0, cameraDistance)) @ viewMatrix

			# modify the projection matrix, relative to the camera size and aspect ratio
			projectionMatrix[0][2] += offset / (cameraSize * self.device.aspect)

		# return the projection matrix
		return viewMatrix, projectionMatrix



	# Update the viewport settings
	def updateViewportSettings(self, context):

		# Adjust the viewport render settings
		######################################################

		# if the settings shall be taken from a Blender viewport
		if self.settings.viewportMode == 'BLENDER':

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
							#print(" # ", e)
							pass

				attributeList = dir(self.override['space_data'].overlay)
				for attr in attributeList:

					if not attr in attributeExceptions:
						#print("[OVERLAY]", attr, " = ", getattr(LookingGlassAddon.BlenderViewport.overlay, attr))

						try:
							setattr(self.override['space_data'].overlay, attr, getattr(LookingGlassAddon.BlenderViewport.overlay, attr))
						except Exception as e:
							#print(" # ", e)
							pass

			else:

				# reset the global variable and fall back to custom settings
				LookingGlassAddon.BlenderViewport = None

		# if the custom settings shall be used OR the chosen Blender Viewport is invalid
		if self.settings.viewportMode == 'CUSTOM' or LookingGlassAddon.BlenderViewport == None:

			# APPLY THE CURRENT USER SETTINGS FOR THE LIGHTFIELD RENDERING
			# SHADING ATTRIBUTES
			self.override['space_data'].shading.type = self.settings.shadingMode
			self.override['space_data'].shading.show_xray = bool(self.settings.viewport_show_xray)
			self.override['space_data'].shading.xray_alpha = float(self.settings.viewport_xray_alpha)
			self.override['space_data'].shading.use_dof = bool(int(self.settings.viewport_use_dof))

			# OVERLAY ATTRIBUTES: Guides
			self.override['space_data'].overlay.show_floor = bool(int(self.settings.viewport_show_floor))
			self.override['space_data'].overlay.show_axis_x = bool(int(self.settings.viewport_show_axes[0]))
			self.override['space_data'].overlay.show_axis_y = bool(int(self.settings.viewport_show_axes[1]))
			self.override['space_data'].overlay.show_axis_z = bool(int(self.settings.viewport_show_axes[2]))
			self.override['space_data'].overlay.grid_scale = float(self.settings.viewport_grid_scale)
			# OVERLAY ATTRIBUTES: Objects
			self.override['space_data'].overlay.show_extras = bool(int(self.settings.viewport_show_extras))
			self.override['space_data'].overlay.show_relationship_lines = bool(int(self.settings.viewport_show_relationship_lines))
			self.override['space_data'].overlay.show_outline_selected = bool(int(self.settings.viewport_show_outline_selected))
			self.override['space_data'].overlay.show_bones = bool(int(self.settings.viewport_show_bones))
			self.override['space_data'].overlay.show_motion_paths = bool(int(self.settings.viewport_show_motion_paths))
			self.override['space_data'].overlay.show_object_origins = bool(int(self.settings.viewport_show_origins))
			self.override['space_data'].overlay.show_object_origins_all = bool(int(self.settings.viewport_show_origins_all))
			# OVERLAY ATTRIBUTES: Geometry
			self.override['space_data'].overlay.show_wireframes = bool(int(self.settings.viewport_show_wireframes))
			self.override['space_data'].overlay.show_face_orientation = bool(int(self.settings.viewport_show_face_orientation))

		# if the settings rely on a specific viewport / SpaceView3D
		elif self.settings.viewportMode != 'CUSTOM' and LookingGlassAddon.BlenderViewport != None:

			# if CYCLES is activated in the current viewport
			if LookingGlassAddon.BlenderViewport.shading.type == 'RENDERED' and context.engine == 'CYCLES':

				# change the shading type to SOLID
				self.override['space_data'].shading.type = 'SOLID'

				# notify user
				self.report({"WARNING"}, "Render engine (%s) not supported in lightfield viewport. Switched to SOLID mode." % context.engine)

		# always disable the hdri preview spheres
		self.override['space_data'].overlay.show_look_dev = False



	@staticmethod
	def from_texture_to_numpy_array(texture, array):
		"""copy the current texture to a numpy array"""

		# TODO: Replace these BGL calls with the new BPY API for OpenGL
		# ++++++++++++++
		# The following seems to be the basic approach for Blender 3.0 to get the
		# offscreen image data into a buffer. Not implemented in 2.93:
		# with offscreen.bind():
		#     fb = gpu.state.active_framebuffer_get()
		#     buffer = fb.read_color(0, 0, WIDTH, HEIGHT, 4, 0, 'UBYTE')
		#
		# offscreen.free()
		#
		# ++++++++++++++
		#
		# ALTERNATIVELY (also working only in Blender 3.0+):
		#
		# - get the gpu.types.GPUTexture of the GPUOffscreen from its texture_color attribute
		# - use the read() method of gpu.types.GPUTexture to obtain a buffer with pixel data
		#
		# ++++++++++++++

		# activate the texture
		bgl.glActiveTexture(bgl.GL_TEXTURE0)
		bgl.glBindTexture(bgl.GL_TEXTURE_2D, texture)

		# then we pass the numpy array to the bgl.Buffer as template,
		# which causes Blender to write the buffer data into the numpy array directly
		buffer = bgl.Buffer(bgl.GL_BYTE, array.shape, array)
		bgl.glGetTexImage(bgl.GL_TEXTURE_2D, 0, bgl.GL_RGBA, bgl.GL_UNSIGNED_BYTE, buffer)
		bgl.glBindTexture(bgl.GL_TEXTURE_2D, 0)


	# Draw function which copies data from the 3D View
	def render_view(self, context):

		# if the quilt must be redrawn
		if self.modal_redraw == True and (context.scene.settings.lookingglassCamera or LookingGlassAddon.BlenderViewport):

			# UPDATE QUILT SETTINGS
			# ++++++++++++++++++++++++++++++++++++++++++++++++

			self.start_multi_view = time.time()

			# if the quilt and view settings changed
			if self.last_preset != self.preset or self.lightfield_image == None:

				# update the preset variable
				self.last_preset = self.preset

				# free the view data of the lightfield image
				if self.lightfield_image: self.lightfield_image.clear_views()

				# delete the current LightfieldImage
				if self.lightfield_image: self.lightfield_image = None

				# create a pylio LightfieldImage
				self.lightfield_image = pylio.LightfieldImage.new(pylio.LookingGlassQuilt, id=self.preset)

				# create a new set of LightfieldViews
				self.lightfield_image.set_views([pylio.LightfieldView(np.empty((self.qs[self.preset]["viewOffscreen"].height, self.qs[self.preset]["viewOffscreen"].width, 4), dtype=np.uint8), pylio.LightfieldView.formats.numpyarray) for view in range(0, self.qs[self.preset]["total_views"])], pylio.LightfieldView.formats.numpyarray)

			LookingGlassAddonLogger.debug("Start rendering lightfield views ...")
			LookingGlassAddonLogger.debug(" [#] View dimensions: %i x %i" % (self.qs[self.preset]["viewOffscreen"].width, self.qs[self.preset]["viewOffscreen"].height))
			LookingGlassAddonLogger.debug(" [#] LightfieldImage views: %i" % len(self.lightfield_image.get_view_data()))
			LookingGlassAddonLogger.debug(" [#] Using quilt preset: %i" % self.preset)


			# PREPARE VIEW & PROJECTION MATRIX
			# ++++++++++++++++++++++++++++++++++++++++++++++++

			# select camera that belongs to the view
			camera = context.scene.settings.lookingglassCamera

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
				camera_view_matrix = view_matrix.inverted_safe()

				# get the camera's projection matrix
				camera_projection_matrix = camera.calc_matrix_camera(
						depsgraph=context.view_layer.depsgraph,
						x = self.qs[self.preset]["view_width"],
						y = self.qs[self.preset]["view_height"],
						scale_x = 1.0,
						scale_y = (self.qs[self.preset]["rows"] / self.qs[self.preset]["columns"]) / self.device.aspect,
					)

			# otherwise we take the (lightfield) viewport matrices
			elif LookingGlassAddon.BlenderViewport:

				# get viewports modelview matrix
				camera_view_matrix = LookingGlassAddon.BlenderViewport.region_3d.view_matrix.copy()

				# get the viewports projection matrix
				camera_projection_matrix = LookingGlassAddon.BlenderViewport.region_3d.window_matrix.copy()

			LookingGlassAddonLogger.debug(" [#] Geting view & projection matrices took %.6f s" % (time.time() - self.start_multi_view))


			# RENDER THE VIEWS
			# ++++++++++++++++++++++++++++++++++++++++++++++++

			# loop through all required views
			for view in range(0, self.qs[self.preset]["total_views"]):

				start_test = time.time()
				# calculate the offset-projection of the current view
				view_matrix, projection_matrix = self.setupVirtualCameraForView(camera, view, camera_view_matrix.copy(), camera_projection_matrix.copy())

				LookingGlassAddonLogger.debug(" [#] [%i] Settin up view camera took %.6f s" % (view, time.time() - start_test))
				start_test = time.time()

				# RENDER THE VIEW INTO THE OFFSCREEN
				# ++++++++++++++++++++++++++++++++++++++++++++++++
				# NOTE: - the draw_view3d method does not apply the color management
				# 		- files bug report (on 2020-12-28): https://developer.blender.org/T84227

				with self.qs[self.preset]["viewOffscreen"].bind():

					# TODO: activate the "do_color_management=True" for Blender 3.0
					#       to get the correct color space data
					# draw the viewport rendering to the offscreen for the current view
					self.qs[self.preset]["viewOffscreen"].draw_view3d(
						# we use the "Scene" and the "View Layer" that is active in the Window
						# the user currently works in
						scene=context.scene,
						view_layer=context.view_layer,
						view3d=self.override['space_data'],
						region=self.override['region'],
						view_matrix=view_matrix,
						projection_matrix=projection_matrix)

					LookingGlassAddonLogger.debug(" [#] [%i] Drawing view into offscreen took %.6f s" % (view, time.time() - start_test))
					start_test = time.time()

					# copy texture into LightfieldView array
					self.from_texture_to_numpy_array(self.qs[self.preset]["viewOffscreen"].color_texture, self.lightfield_image.get_view_data()[view])

					# draw the lightfield mouse cursor if desired
					if self.settings.viewport_show_cursor == True:

						# # calculate the position of the view in the quilt
						# x = 2 * (view % self.qs[self.preset]["columns"]) * self.qs[self.preset]["view_width"] / self.qs[self.preset]["quilt_width"] - 1
						# y = 2 * int(view / self.qs[self.preset]["columns"]) * self.qs[self.preset]["view_height"] / self.qs[self.preset]["quilt_height"] - 1

						self.drawCursor3D(context, view, view_matrix, projection_matrix, self.settings.viewport_cursor_size, 8)


					LookingGlassAddonLogger.debug(" [#] [%i] Copying texture to numpy array took %.6f" % (view, time.time() - start_test))

			LookingGlassAddonLogger.debug("-----------------------------")
			LookingGlassAddonLogger.debug("Rendering took in total %.3f s" % (time.time() - self.start_multi_view))
			LookingGlassAddonLogger.debug("-----------------------------")

			# update the quilt image in the image_editor,
			# which is used for display in the LookingGlass
			LookingGlassAddon.updateLiveViewer = True

			# reset draw variable:
			# This is here to prevent excessive redrawing
			self.modal_redraw = False



	# display the rendered LightfieldImage on the display
	def display_lightfield(self, context):

		# VIEWPORT MODE
		##################################################################
		if LookingGlassAddon.updateLiveViewer and (int(self.settings.renderMode) == 0 or (int(self.settings.renderMode) == 1 and context.scene.settings.quiltImage == None)):

			# let the device display the image
			# NOTE: We flip the views in Y direction, because the OpenGL
			#		and PIL definition of the image origin are different.
			#		(i.e., top-left vs. bottom-left)
			self.device.display(self.lightfield_image, flip_views=True, invert=False)

			# reset state variable to avoid excessive redrawing
			LookingGlassAddon.updateLiveViewer = False


		# QUILT VIEWER MODE
		##################################################################
		# TODO: Currently only quilts are supported. Maybe implement support
		#		for Multiview images later? (context.scene.settings.quiltImage.is_multiview == True)
		# if the quilt view mode is active AND an image is loaded
		elif LookingGlassAddon.updateQuiltViewer and (int(self.settings.renderMode) == 1 and self.settings.quiltImage != None):

			# Prepare image as LightfieldImage
			# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

			# convert to uint8
			quiltPixels = 255 * LookingGlassAddon.quiltPixels
			quiltPixels = quiltPixels.astype(dtype=np.uint8)

			# create a Lightfield image
			self.quilt_viewer_image = pylio.LightfieldImage.from_buffer(pylio.LookingGlassQuilt, quiltPixels, self.settings.quiltImage.size[0], self.settings.quiltImage.size[1], self.settings.quiltImage.channels)

			# let the device display the image
			# NOTE: We DON'T flip the views in Y direction, because the Blender
			#		and PIL definition of the image origin are the same.
			# TODO: CHECK IF THE NOTE IS TRUE. HAD SOME WEIRD THINGS GOING ON.
			self.device.display(self.quilt_viewer_image, flip_views=False, invert=False)

			# TODO: A free() method needs to be implemented in pyLightIO
			# free this lightfield image
			# self.quilt_viewer_image

			# reset variables
			quiltPixels = None
			self.quilt_viewer_image = None

			# reset state variable to avoid excessive redrawing
			LookingGlassAddon.updateQuiltViewer = False




	# TODO: In this method is room for speed optimization
	# draw the mouse cursor
	def drawCursor3D(self, context, view, view_matrix, projection_matrix, radius, segments):

		start_timer = time.time()
		# Cursor geometry for the view
		# ++++++++++++++++++++++++++++++++++++++
		# location vector
		rot_axis = Vector((0, 0, 1)).cross(self.normal)
		rot_angle = acos(Vector((0, 0, 1)).dot(self.normal))

		# create rotation matrix
		rot_matrix = Matrix.Rotation(rot_angle, 4, rot_axis.normalized())

		# calculate the coordinated of a circle with given radius and segments
		cursor_geometry_coords = []
		for n in range(segments):

			# coordinates
			p1 = cos((1.0 / (segments - 1)) * (2 * pi * n)) * radius
			p2 = sin((1.0 / (segments - 1)) * (2 * pi * n)) * radius

			# location Vector, rotated to lay on the current face
			point = rot_matrix @ Vector((p1, p2, 0))

			# translate to the position of the hit point
			point = Matrix.Translation(self.cursor) @ point

			# project point into camera space taking camera shift etc. into account
			prj = projection_matrix @ view_matrix @ Vector((point[0], point[1], point[2], 1.0))

			# if point is in front of camera
			if prj.w > 0.0:

				width_half = self.qs[self.preset]["view_width"] / self.qs[self.preset]["quilt_width"]
				height_half = self.qs[self.preset]["view_height"] / self.qs[self.preset]["quilt_height"]

				location = Vector((
					width_half + width_half * (prj.x / prj.w),
					height_half + height_half * (prj.y / prj.w),
				))

			else:

				location = Vector((0, 0))

			# add point to the list
			cursor_geometry_coords.append((location[0], location[1]))


		# Draw the custom 3D cursor
		# ++++++++++++++++++++++++++++++++++++++
		shader = gpu.shader.from_builtin('2D_UNIFORM_COLOR')
		batch = batch_for_shader(shader, 'TRI_FAN', {"pos": cursor_geometry_coords})
		shader.bind()
		shader.uniform_float("color", (self.settings.viewport_cursor_color[0], self.settings.viewport_cursor_color[1], self.settings.viewport_cursor_color[2], 1.0))
		batch.draw(shader)

		#print("Cursor time: ", time.time() - start_timer)






# ------------ CAMERA FRUSTUM RENDERING -------------
# Modal operator for rendering a camera frustum reprsenting the Looking Glass
# in Blenders 3D viewport
class LOOKINGGLASS_OT_render_frustum(bpy.types.Operator):
	bl_idname = "render.frustum"
	bl_label = "Looking Glass Frustum Rendering"
	bl_options = {'REGISTER', 'INTERNAL'}

	# variables for the frustum
	frustum_indices_lines = None
	frustum_indices_faces = None
	frustum_indices_focalplane_outline = None
	frustum_indices_focalplane_face = None
	frustum_shader = None



	# Inititalize the camera frustum drawing
	@classmethod
	def __init__(self):

		LookingGlassAddon.FrustumInitialized = True



	# deinititalize the camera frustum drawing
	@classmethod
	def __del__(self):

		# remove the draw handler for the frustum drawing
		if LookingGlassAddon.FrustumDrawHandler:
			bpy.types.SpaceView3D.draw_handler_remove(LookingGlassAddon.FrustumDrawHandler, 'WINDOW')
			LookingGlassAddon.FrustumDrawHandler = None

		# reset variable
		LookingGlassAddon.FrustumInitialized = False




	# poll method
	@classmethod
	def poll(self, context):

		# return True, so the operator is executed
		return True




	# cancel the modal operator
	def cancel(self, context):

		# remove the draw handler for the frustum drawing
		if LookingGlassAddon.FrustumDrawHandler:
			bpy.types.SpaceView3D.draw_handler_remove(LookingGlassAddon.FrustumDrawHandler, 'WINDOW')
			LookingGlassAddon.FrustumDrawHandler = None

		LookingGlassAddon.FrustumInitialized = False

		# return None since this is expected by the operator
		return None




	def invoke(self, context, event):

		# SETUP THE FRUSTUM
		################################################################

		# setup the frustum & shader
		self.setupCameraFrustumShader()




		# REGISTER ALL HANDLERS FOR THE FRUSTUM RENDERING
		################################################################

		# HANDLERS FOR DRAWING PURPOSES
		# ++++++++++++++++++++++++++++++
		# draw handler to display the frustum of the Looking Glass camera
		LookingGlassAddon.FrustumDrawHandler = bpy.types.SpaceView3D.draw_handler_add(self.drawCameraFrustum, (context,), 'WINDOW', 'POST_VIEW')

		# add the modal handler
		context.window_manager.modal_handler_add(self)

		# keep the modal operator running
		return {'RUNNING_MODAL'}



	# modal operator for controlled redrawing of the lightfield
	def modal(self, context, event):

		# pass event through
		return {'PASS_THROUGH'}



	# setup the camera frustum shader
	def setupCameraFrustumShader(self):

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
		if self and context:
			if context.scene.settings.lookingglassCamera:
				if (context.space_data != None and context.space_data.region_3d != None) and context.space_data.region_3d.view_perspective != 'CAMERA':

					# currently selected camera
					camera = context.scene.settings.lookingglassCamera

					# if the camera is visible
					if camera.hide_get() == False:

						# get modelview matrix
						view_matrix = camera.matrix_world.copy()

						# correct for the camera scaling
						view_matrix = view_matrix @ Matrix.Scale(1/camera.scale.x, 4, (1, 0, 0))
						view_matrix = view_matrix @ Matrix.Scale(1/camera.scale.y, 4, (0, 1, 0))
						view_matrix = view_matrix @ Matrix.Scale(1/camera.scale.z, 4, (0, 0, 1))

						# we obtain the viewframe of the camera to calculate the focal and clipping world_clip_planes_calc_clip_distance
						# based on the intercept theorems
						view_frame = camera.data.view_frame(scene=context.scene)
						view_frame_upper_right = view_frame[0]
						view_frame_lower_right = view_frame[1]
						view_frame_lower_left = view_frame[2]
						view_frame_upper_left = view_frame[3]
						view_frame_distance = abs(view_frame_upper_right[2])

						# get the clipping settings
						clipStart = camera.data.clip_start
						clipEnd = camera.data.clip_end
						focalPlane = context.scene.settings.focalPlane

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
										(view_frame_lower_right[0] / view_frame_distance * focalPlane, view_frame_lower_right[1] / view_frame_distance * focalPlane, -focalPlane), (view_frame_lower_left[0] / view_frame_distance * focalPlane, view_frame_lower_left[1] / view_frame_distance * focalPlane, -focalPlane),
										(view_frame_upper_left[0] / view_frame_distance * focalPlane, view_frame_upper_left[1] / view_frame_distance * focalPlane, -focalPlane), (view_frame_upper_right[0] / view_frame_distance * focalPlane, view_frame_upper_right[1] / view_frame_distance * focalPlane, -focalPlane),
										]

						# if the camera fustum shall be drawn
						if context.scene.settings.showFrustum == True:
							batch_lines = batch_for_shader(self.frustum_shader, 'LINES', {"pos": coords_local}, indices=self.frustum_indices_lines)
							batch_faces = batch_for_shader(self.frustum_shader, 'TRIS', {"pos": coords_local}, indices=self.frustum_indices_faces)

						# if the focal plane shall be drawn
						if context.scene.settings.showFocalPlane == True:
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
						if context.scene.settings.showFrustum == True:
							# draw outline
							self.frustum_shader.uniform_float("color", (0.3, 0, 0, 1))
							batch_lines.draw(self.frustum_shader)

						# if the focal plane shall be drawn
						if context.scene.settings.showFocalPlane == True:
							# draw focal plane outline
							self.frustum_shader.uniform_float("color", (1, 1, 1, 1))
							batch_focalplane_outline.draw(self.frustum_shader)

						bgl.glDepthMask(bgl.GL_FALSE)
						bgl.glEnable(bgl.GL_BLEND)

						# if the camera fustum shall be drawn
						if context.scene.settings.showFrustum == True:
							# fill faces
							self.frustum_shader.uniform_float("color", (0.5, 0.5, 0.5, 0.05))
							batch_faces.draw(self.frustum_shader)

						# if the focal plane shall be drawn
						if context.scene.settings.showFocalPlane == True:
							# draw focal plane face
							self.frustum_shader.uniform_float("color", (0.1, 0.1, 0.1, 0.25))
							batch_focalplane_face.draw(self.frustum_shader)

						bgl.glDisable(bgl.GL_DEPTH_TEST)
						bgl.glDisable(bgl.GL_BLEND)

						# reset the matrices to their original state
						gpu.matrix.reset()
						gpu.matrix.load_matrix(viewMatrix)
						gpu.matrix.load_projection_matrix(projectionMatrix)
