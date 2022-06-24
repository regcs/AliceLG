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
# This includes everything that is related the "live view"

# ------------------ INTERNAL MODULES --------------------
from .globals import *

# ------------------- EXTERNAL MODULES -------------------
import sys, platform
import bpy, bgl
import gpu
import time, timeit
from math import *
from mathutils import *
from gpu_extras.batch import batch_for_shader
from gpu_extras.presets import draw_texture_2d, draw_circle_2d
from bpy_extras.view3d_utils import location_3d_to_region_2d, region_2d_to_origin_3d, region_2d_to_vector_3d
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




# ------------ LIGHTFIELD RENDERING -------------
# Modal operator for controlled redrawing of the lightfield window.
class LOOKINGGLASS_OT_render_viewport(bpy.types.Operator):

	bl_idname = "render.viewport"
	bl_label = "Looking Glass Lightfield Viewport rendering"
	bl_options = {'REGISTER', 'INTERNAL'}


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
	depsgraph_update_time = 0
	skip_views = 1
	restricted_viewcone_limit = 0

	# DEBUGING VARIABLES
	start_multi_view = 0

	# PROTECTED CLASS MEMBERS
	# ++++++++++++++++++++++++++++++++++++++++++++++++++

	# HANDLER IDENTIFIERS
	_handle_trackDepsgraphUpdates = None
	_handle_trackFrameChanges = None
	_handle_trackActiveWindow = None

	# CONTEXT OVERRIDE
	_override = None

	# SETTINGS BACKUP
	_shading_restore_backup = {}
	_overlay_restore_backup = {}

	# METHODS
	# ++++++++++++++++++++++++++++++++++++++++++++++++++
	# poll method
	@classmethod
	def poll(self, context):

		# check if the context is invalid
		if not context:
			LookingGlassAddonLogger.error("Could not open Lightfield Window. Operator was called from invalid context.")
			return False

		# return True, so the operator is executed
		return True



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

		# iterate through all presets
		for i, preset in self.qs.items():

			# loop through all required views
			#for view in range(int((self.qs[self.preset]["total_views"] + 1) / 3), self.qs[self.preset]["total_views"] - int((self.qs[self.preset]["total_views"] + 1) / 3)):
			for view in range(0, self.qs[i]["total_views"]):

				# free the GPUOffscreen for the view rendering
				self.qs[i]["viewOffscreen"][view].free()

			# delete the list of offscreen objects
			self.qs[i]["viewOffscreen"].clear()

		# log info
		LookingGlassAddonLogger.info(" [#] Freed GPUOffscreens of the lightfield views.")

		# set status variables to default state
		#LookingGlassAddon.BlenderWindow = None
		LookingGlassAddon.BlenderViewport = None

		# set the button controls for the lightfield window to False
		self.addon_settings.ShowLightfieldWindow = False

		# SCENE UPDATES
		# ++++++++++++++++++++++++++
		if context != None:

			# iterate through all scenes
			for scene in bpy.data.scenes:
				if scene != None and scene.addon_settings != None:

					# update the status variables
					scene.addon_settings.ShowLightfieldWindow = False

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
		self.addon_settings = context.scene.addon_settings

		# update the variable for the current Looking Glass device
		if int(self.addon_settings.activeDisplay) != -1: self.device = pylio.DeviceManager.get_active()



		# PREPARE THE OFFSCREEN RENDERING
		################################################################

		# set to the currently chosen quality
		self.preset = self.last_preset = int(context.scene.addon_settings.quiltPreset)

		# get all quilt presets from pylio
		self.qs = pylio.LookingGlassQuilt.formats.get()

		# iterate through all presets
		for i, preset in self.qs.items():

			# create a list of offscreen objects for this preset
			self.qs[i]["viewOffscreen"] = []

			# loop through all required views
			#for view in range(int((self.qs[self.preset]["total_views"] + 1) / 3), self.qs[self.preset]["total_views"] - int((self.qs[self.preset]["total_views"] + 1) / 3)):
			for view in range(0, self.qs[i]["total_views"]):

				# create a GPUOffscreen for the views
				self.qs[i]["viewOffscreen"].append(gpu.types.GPUOffScreen(int(self.qs[i]["view_width"]), int(self.qs[i]["view_height"])))

		# log info
		LookingGlassAddonLogger.info(" [#] Prepared GPUOffscreens for view rendering.")


		# PREPARE THE OVERRIDE CONTEXT THAT CONTAINS THE RENDER SETTINGS
		################################################################

		# create an override context from the invoking context
		self._override = context.copy()

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

		# if the active scene was changed
		if context.scene.addon_settings != self.addon_settings:

			# make sure the "lightfield window" button is set correctly
			context.scene.addon_settings.ShowLightfieldWindow = self.addon_settings.ShowLightfieldWindow

			# update the internal variable for the settings
			self.addon_settings = context.scene.addon_settings

			# update the lightfield window
			# Lightfield Viewport
			if int(self.addon_settings.renderMode) == 0:
				context.scene.addon_settings.viewport_manual_refresh = True
			# Quilt Viewer
			elif int(self.addon_settings.renderMode) == 1:
				LookingGlassAddon.update_lightfield_window(int(self.addon_settings.renderMode), LookingGlassAddon.quiltViewerLightfieldImage)

		# cancel the operator, if the lightfield viewport was deactivated
		if not self.addon_settings.ShowLightfieldWindow:
			self.cancel(context)
			return {'FINISHED'}

		# update the variable for the current Looking Glass device
		if int(self.addon_settings.activeDisplay) != -1: self.device = pylio.DeviceManager.get_active()


		# Control lightfield redrawing in viewport mode
		################################################################

		# if the TIMER event for the lightfield rendering is called AND the automatic render mode is active
		if event.type == 'TIMER':

			# if something has changed OR the user requested a manual redrawing
			if self.modal_redraw or (not self.modal_redraw and ((self.depsgraph_update_time > 0 and time.time() - self.depsgraph_update_time > LookingGlassAddon.low_resolution_preview_timout) or context.scene.addon_settings.viewport_manual_refresh == True)):

				# update the viewport settings
				self.updateViewportSettings(context)

				if (not self.modal_redraw and ((self.depsgraph_update_time > 0 and time.time() - self.depsgraph_update_time > LookingGlassAddon.low_resolution_preview_timout) or context.scene.addon_settings.viewport_manual_refresh == True)):

					# reset time of last depsgraph update
					self.depsgraph_update_time = 0

					# reset status variable for manual refreshes
					context.scene.addon_settings.viewport_manual_refresh = False

					# set to the currently chosen quality
					self.preset = int(context.scene.addon_settings.quiltPreset)

					# dont skip any views
					self.skip_views = 1
					self.restricted_viewcone_limit = 0

 					# set to redraw
					self.modal_redraw = True

				# render the views
				self.render_view(context)

				# Lightfield Viewport
				if int(self.addon_settings.renderMode) == 0 and self.lightfield_image:

					# update the lightfield displayed on the device
					LookingGlassAddon.update_lightfield_window(int(self.addon_settings.renderMode), self.lightfield_image)

				# Quilt Viewer
				elif int(self.addon_settings.renderMode) == 1 and LookingGlassAddon.quiltViewerLightfieldImage:

					# update the lightfield displayed on the device
					LookingGlassAddon.update_lightfield_window(int(self.addon_settings.renderMode), LookingGlassAddon.quiltViewerLightfieldImage)

				else:

					# update the lightfield displayed on the device: show the demo quilt
					LookingGlassAddon.update_lightfield_window(-1, None)

				# running modal
				return {'RUNNING_MODAL'}

		# pass event through
		return {'PASS_THROUGH'}

	# Application handler that continously checks for changes of the depsgraph
	def trackDepsgraphUpdates(self, scene, depsgraph):

		# if no quilt rendering is currently Running
		if not LookingGlassAddon.RenderInvoked:

			# if automatic live view is activated AND something in the scene has changed
			if (int(self.addon_settings.renderMode) == 0 and int(self.addon_settings.lightfieldMode) == 0) and len(depsgraph.updates.values()) > 0:
				# print("DEPSGRAPH UPDATE: ", depsgraph.updates.values())

				# remember time of last depsgraph update
				self.depsgraph_update_time = time.time()

				# allow an update of the Looking Glass viewport
				self.modal_redraw = True

				# if the "no preview" is activated
				if self.addon_settings.viewport_use_preview_mode and self.addon_settings.lightfield_preview_mode == '0':

					# don't allow an update of the Looking Glass viewport
					self.modal_redraw = False

					# we don't redraw, because changes are only updated after the user interaction finished
					pass

				# if the "low resolution preview" is activated
				elif self.addon_settings.viewport_use_preview_mode and self.addon_settings.lightfield_preview_mode == '1':

					# activate them
					self.preset = int(list(pylio.LookingGlassQuilt.formats.get().keys())[-1])

				# if the "skip views preview I" is activated
				elif self.addon_settings.viewport_use_preview_mode and self.addon_settings.lightfield_preview_mode == '2':

					# skip every second view during rendering
					self.skip_views = 2

				# if the "skip views preview II" is activated
				elif self.addon_settings.viewport_use_preview_mode and self.addon_settings.lightfield_preview_mode == '3':

					# skip every third view during rendering
					self.skip_views = 3

				# if the "restricted viewcone preview" is activated
				elif self.addon_settings.viewport_use_preview_mode and self.addon_settings.lightfield_preview_mode == '4':

					# only show the center 33% of all views
					self.restricted_viewcone_limit = int(self.qs[self.preset]["total_views"] / 3)

				else:

					# set to the currently chosen quality
					self.preset = int(scene.addon_settings.quiltPreset)
					self.skip_views = 1

			# if quilt viewer is active AND an image is selected
			elif int(self.addon_settings.renderMode) == 1 and scene.addon_settings.quiltImage != None:

				# set status variable
				changed = False

				# set to the currently chosen quality
				self.preset = int(scene.addon_settings.quiltPreset)

				# TODO: Hacky, but this identifies color management changes
				# go through the updates
				for DepsgraphUpdate in depsgraph.updates.values():
					#print(" # ", DepsgraphUpdate.is_updated_geometry, DepsgraphUpdate.is_updated_shading, DepsgraphUpdate.is_updated_transform, DepsgraphUpdate.id.name)

					if DepsgraphUpdate.is_updated_geometry == True and DepsgraphUpdate.is_updated_shading == True and DepsgraphUpdate.is_updated_transform == True:

						# update status variable
						changed = False

						break

				# are there any changes in the image or color management settings?
				if LookingGlassAddon.quiltViewAsRender != scene.addon_settings.quiltImage.use_view_as_render or LookingGlassAddon.quiltImageColorSpaceSetting.name != scene.addon_settings.quiltImage.colorspace_settings.name:

					# update status variable
					changed = True

				# update the quilt image, if something had changed
				if changed == True: scene.addon_settings.quiltImage = scene.addon_settings.quiltImage


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
			cameraDistance = self.addon_settings.focalPlane
			cameraSize = cameraDistance * tan(fov / 2)

			# start at viewCone * 0.5 and go up to -viewCone * 0.5
			offsetAngle = (0.5 - view / (self.qs[self.preset]["total_views"] - 1)) * radians(self.device.viewCone)

			# calculate the offset that the camera should move
			offset = cameraDistance * tan(offsetAngle)

			# translate the view matrix (position) by the calculated offset in x-direction
			viewMatrix = Matrix.Translation((offset, 0, 0)) @ viewMatrix

			# modify the projection matrix, relative to the camera size and aspect ratio
			projectionMatrix[0][2] += offset / (cameraSize * self.device.aspect)

		else:

			LookingGlassAddonLogger.warning("Could not calculate the matrices for the lightfield viewport. '%s' is not a valid camera." % camera)

		# return the projection matrix
		return viewMatrix, projectionMatrix



	# Save the viewport settings
	def saveViewportSettings(self):

		# SHADING ATTRIBUTES
		# define some exceptions that must not be taken into
		attributeExceptions = ["__doc__", "__module__", "__slots__", "bl_rna", "rna_type"]

		# use the "space data" of the selected viewport
		attributeList = dir(self._override['space_data'].shading)
		for attr in attributeList:

			if not attr in attributeExceptions:
				#print("[SHADING]", attr, " = ", getattr(LookingGlassAddon.BlenderViewport.shading, attr))

				try:
					self._shading_restore_backup[attr] = getattr(self._override['space_data'].shading, attr)
				except Exception as e:
					#print(" # ", e)
					pass

		attributeList = dir(self._override['space_data'].overlay)
		for attr in attributeList:

			if not attr in attributeExceptions:
				#print("[OVERLAY]", attr, " = ", getattr(LookingGlassAddon.BlenderViewport.overlay, attr))

				try:
					self._overlay_restore_backup[attr] = getattr(self._override['space_data'].overlay, attr)
				except Exception as e:
					#print(" # ", e)
					pass


	# Update the viewport settings
	def updateViewportSettings(self, context):

		# CHECK FOR SELECTED VIEWPORT
		######################################################

		# if the settings shall be taken from a Blender viewport
		if self.addon_settings.viewportMode == 'BLENDER':

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

				# assign the selected viewport
				self._override['space_data'] = LookingGlassAddon.BlenderViewport

			else:

				# reset the global variable and fall back to custom settings
				LookingGlassAddon.BlenderViewport = None


		# SAVE ALL SHADING & OVERLAY SETTINGS
		####################################################################
		self.saveViewportSettings()


		# APPLY CUSTOM SETTINGS IF REQUIRED
		####################################################################

		# if the custom settings shall be used OR the chosen Blender Viewport is invalid
		if self.addon_settings.viewportMode == 'CUSTOM' or LookingGlassAddon.BlenderViewport == None:

			# SHADING ATTRIBUTES
			self._override['space_data'].shading.type = self.addon_settings.shadingMode
			self._override['space_data'].shading.show_xray = bool(self.addon_settings.viewport_show_xray)
			self._override['space_data'].shading.xray_alpha = float(self.addon_settings.viewport_xray_alpha)
			self._override['space_data'].shading.use_dof = bool(int(self.addon_settings.viewport_use_dof))

			# OVERLAY ATTRIBUTES: Guides
			self._override['space_data'].overlay.show_floor = bool(int(self.addon_settings.viewport_show_floor))
			self._override['space_data'].overlay.show_axis_x = bool(int(self.addon_settings.viewport_show_axes[0]))
			self._override['space_data'].overlay.show_axis_y = bool(int(self.addon_settings.viewport_show_axes[1]))
			self._override['space_data'].overlay.show_axis_z = bool(int(self.addon_settings.viewport_show_axes[2]))
			self._override['space_data'].overlay.grid_scale = float(self.addon_settings.viewport_grid_scale)
			# OVERLAY ATTRIBUTES: Objects
			self._override['space_data'].overlay.show_extras = bool(int(self.addon_settings.viewport_show_extras))
			self._override['space_data'].overlay.show_relationship_lines = bool(int(self.addon_settings.viewport_show_relationship_lines))
			self._override['space_data'].overlay.show_outline_selected = bool(int(self.addon_settings.viewport_show_outline_selected))
			self._override['space_data'].overlay.show_bones = bool(int(self.addon_settings.viewport_show_bones))
			self._override['space_data'].overlay.show_motion_paths = bool(int(self.addon_settings.viewport_show_motion_paths))
			self._override['space_data'].overlay.show_object_origins = bool(int(self.addon_settings.viewport_show_origins))
			self._override['space_data'].overlay.show_object_origins_all = bool(int(self.addon_settings.viewport_show_origins_all))
			# OVERLAY ATTRIBUTES: Geometry
			self._override['space_data'].overlay.show_wireframes = bool(int(self.addon_settings.viewport_show_wireframes))
			self._override['space_data'].overlay.show_face_orientation = bool(int(self.addon_settings.viewport_show_face_orientation))

		# if the settings rely on a specific viewport / SpaceView3D
		elif self.addon_settings.viewportMode != 'CUSTOM' and LookingGlassAddon.BlenderViewport != None:

			# if CYCLES is activated in the current viewport
			if LookingGlassAddon.BlenderViewport.shading.type == 'RENDERED' and context.engine == 'CYCLES':

				# change the shading type to SOLID
				self._override['space_data'].shading.type = 'SOLID'

				# notify user
				self.report({"WARNING"}, "Render engine (%s) not supported in lightfield viewport. Switched to SOLID mode." % context.engine)

		# always disable the hdri preview spheres
		self._override['space_data'].overlay.show_look_dev = False

	# Restore the viewport settings
	def restoreViewportSettings(self):

		# SHADING ATTRIBUTES
		# define some exceptions that must not be taken into
		attributeExceptions = ["__doc__", "__module__", "__slots__", "bl_rna", "rna_type"]

		# use the "space data" of the selected viewport
		attributeList = dir(self._override['space_data'].shading)
		for attr in attributeList:

			if not attr in attributeExceptions:
				#print("[SHADING]", attr, " = ", getattr(LookingGlassAddon.BlenderViewport.shading, attr))

				try:
					setattr(self._override['space_data'].shading, attr, self._shading_restore_backup[attr])
				except Exception as e:
					#print(" # ", e)
					pass

		attributeList = dir(self._override['space_data'].overlay)
		for attr in attributeList:

			if not attr in attributeExceptions:
				#print("[OVERLAY]", attr, " = ", getattr(LookingGlassAddon.BlenderViewport.overlay, attr))

				try:
					setattr(self._override['space_data'].overlay, attr, self._overlay_restore_backup[attr])
				except Exception as e:
					#print(" # ", e)
					pass


	@staticmethod
	def from_texture_to_numpy_array(offscreen, array):
		"""copy the current texture to a numpy array"""

		with offscreen.bind():

			# TODO: IN LATER VERSIONS OF ALICE/LG THAT DO NOT SUPPORT 2.93
			#		 ANYMORE, THE bgl.* CALLS SHOULD BE REMOVED
			# for Blender versions earlier than 3.0 (prior to the major BGL changes)
			if bpy.app.version < (3, 0, 0):

				# activate the texture
				bgl.glActiveTexture(bgl.GL_TEXTURE0)
				bgl.glBindTexture(bgl.GL_TEXTURE_2D, offscreen.color_texture)

				# then we pass the numpy array to the bgl.Buffer as template,
				# which causes Blender to write the buffer data into the numpy array directly
				buffer = bgl.Buffer(bgl.GL_BYTE, array.shape, array)

				# set correct colormode
				if array.shape[2] == 3: colormode = bgl.GL_RGB
				if array.shape[2] == 4: colormode = bgl.GL_RGBA

				# write pixel data from texture into the buffer (numpy array)
				bgl.glGetTexImage(bgl.GL_TEXTURE_2D, 0, colormode, bgl.GL_UNSIGNED_BYTE, buffer)
				bgl.glBindTexture(bgl.GL_TEXTURE_2D, 0)

			# for Blender versions later than 3.0 (after the major BGL changes)
			else:

				# then we pass the numpy array to the gpu.types.Buffer as template,
				# which causes Blender to write the buffer data into the numpy array directly
				buffer = gpu.types.Buffer('UBYTE', array.shape, array)

				# get the active framebuffer
				framebuffer = gpu.state.active_framebuffer_get()

				# write pixel data from texture into the buffer (numpy array)
				framebuffer.read_color(0, 0, array.shape[1], array.shape[0], array.shape[2], 0, 'UBYTE', data=buffer)

	# Draw function which copies data from the 3D View
	def render_view(self, context):

		# if the quilt must be redrawn
		if (self.addon_settings.lookingglassCamera or LookingGlassAddon.BlenderViewport):

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

                # TODO: Actually we would use "RGB" and a numpy array with 3
				#		color channels, because that would be more efficient.
				#		But we can't read in RGB mode to gpu.types.Buffer
                #       due to Blender's default OpenGL settings:
				#
                #       https://developer.blender.org/T91828
				#
				#		If we don't so it that way, it causes crashes:
				#
				#		https://github.com/regcs/AliceLG/issues/59
				#
				#		The Blender behaviour was fixed for v.3.0+. At the
				#		point when Alice/LG does not support 2.93 anymore,
				#		we can change this. (because the Blender fix is not)

				# create a pylio LightfieldImage
				self.lightfield_image = pylio.LightfieldImage.new(pylio.LookingGlassQuilt, id=self.preset, colormode='RGBA')

				# create a new set of LightfieldViews
				self.lightfield_image.set_views([pylio.LightfieldView(np.empty((self.qs[self.preset]["view_height"], self.qs[self.preset]["view_width"], 4), dtype=np.uint8), pylio.LightfieldView.formats.numpyarray) for view in range(0, self.qs[self.preset]["total_views"])], pylio.LightfieldView.formats.numpyarray)

			LookingGlassAddonLogger.debug("Start rendering lightfield views ...")
			LookingGlassAddonLogger.debug(" [#] View dimensions: %i x %i" % (self.qs[self.preset]["view_width"], self.qs[self.preset]["view_height"]))
			LookingGlassAddonLogger.debug(" [#] LightfieldImage views: %i" % len(self.lightfield_image.get_view_data()))
			LookingGlassAddonLogger.debug(" [#] Using quilt preset: %i (%s, %i x %i)" % (self.preset, self.qs[self.preset]['description'], self.lightfield_image.metadata['quilt_width'], self.lightfield_image.metadata['quilt_height']))
			LookingGlassAddonLogger.debug(" [#] Preview mode: %s (selected: %s)" % (self.addon_settings.viewport_use_preview_mode, self.addon_settings.lightfield_preview_mode))


			# PREPARE VIEW & PROJECTION MATRIX
			# ++++++++++++++++++++++++++++++++++++++++++++++++

			# select camera that belongs to the view
			camera = self.addon_settings.lookingglassCamera

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

				LookingGlassAddonLogger.debug(" [#] Geting view & projection matrices took %.6f s" % (time.time() - self.start_multi_view))


				# RENDER THE VIEWS
				# ++++++++++++++++++++++++++++++++++++++++++++++++

				# loop through all required views
				for view in range(0, self.qs[self.preset]["total_views"]):

					with self.qs[self.preset]["viewOffscreen"][view].bind():

						start_test = time.time()
						# calculate the offset-projection of the current view
						view_matrix, projection_matrix = self.setupVirtualCameraForView(camera, view, camera_view_matrix.copy(), camera_projection_matrix.copy())

						LookingGlassAddonLogger.debug(" [#] [%i] Setting up view camera took %.3f ms" % (view, (time.time() - start_test) * 1000))
						start_test = time.time()

						# if the "skip views preview" is activated AND this view shall be skipped
						if (self.addon_settings.viewport_use_preview_mode and (self.addon_settings.lightfield_preview_mode == '2' or self.addon_settings.lightfield_preview_mode == '3')) and view % self.skip_views:

							# clear LightfieldView array's color data (so it appears black)
							self.lightfield_image.views[view]['view'].data[:] = 0

							LookingGlassAddonLogger.debug(" [#] [%i] Clearing skipped view's numpy array took %.3f ms" % (view, (time.time() - start_test) * 1000))

						# if the "Restricted viewcone preview" is activated AND this view shall be skipped
						elif (self.addon_settings.viewport_use_preview_mode and self.addon_settings.lightfield_preview_mode == '4') and (view < self.restricted_viewcone_limit or view > self.qs[self.preset]["total_views"] - self.restricted_viewcone_limit):

							# clear LightfieldView array's color data (so it appears black)
							self.lightfield_image.views[view]['view'].data[:] = 0

							LookingGlassAddonLogger.debug(" [#] [%i] Clearing skipped view's numpy array took %.3f ms" % (view, (time.time() - start_test) * 1000))

						else:

							# draw the viewport rendering to the offscreen for the current view
							self.qs[self.preset]["viewOffscreen"][view].draw_view3d(
								# we use the "Scene" and the "View Layer" that is active in the Window
								# the user currently works in
								scene=context.scene,
								view_layer=context.view_layer,
								view3d=self._override['space_data'],
								region=self._override['region'],
								view_matrix=view_matrix,
								projection_matrix=projection_matrix,
								do_color_management = True)

							LookingGlassAddonLogger.debug(" [#] [%i] Drawing view into offscreen took %.3f ms" % (view, (time.time() - start_test) * 1000))

				# restore all viewport shading and overlay settings
				self.restoreViewportSettings()

				LookingGlassAddonLogger.debug("-----------------------------")
				LookingGlassAddonLogger.debug("Rendering all views took in total %.3f ms" % ((time.time() - self.start_multi_view) * 1000))
				LookingGlassAddonLogger.debug("-----------------------------")


				# COPY THE VIEWS INTO A BUFFER
				# NOTE: We do this in a separate loop, because for an unknown
				#		reason (probably something Blender internal), it is faster.
				# ++++++++++++++++++++++++++++++++++++++++++++++++

				self.start_multi_view = time.time()

				# loop through all required views
				for view in range(0, self.qs[self.preset]["total_views"]):

					# if the "skip views preview" is activated AND this view shall be skipped
					if (self.addon_settings.viewport_use_preview_mode and (self.addon_settings.lightfield_preview_mode == '2' or self.addon_settings.lightfield_preview_mode == '3')) and view % self.skip_views:

						continue
					# if the "Restricted viewcone preview" is activated AND this view shall be skipped
					elif (self.addon_settings.viewport_use_preview_mode and self.addon_settings.lightfield_preview_mode == '4') and (view < self.restricted_viewcone_limit or view > self.qs[self.preset]["total_views"] - self.restricted_viewcone_limit):

						continue
					else:

						start_test = time.time()

						# copy texture into LightfieldView array
						self.from_texture_to_numpy_array(self.qs[self.preset]["viewOffscreen"][view], self.lightfield_image.views[view]['view'].data[:])

						LookingGlassAddonLogger.debug(" [#] [%i] Copying texture to numpy array took %.3f ms" % (view, (time.time() - start_test) * 1000))

				LookingGlassAddonLogger.debug("-----------------------------")
				LookingGlassAddonLogger.debug("Copying all views took in total %.3f ms" % ((time.time() - self.start_multi_view) * 1000))
				LookingGlassAddonLogger.debug("-----------------------------")

			# reset draw variable:
			# This is here to prevent excessive redrawing
			self.modal_redraw = False



# ------------ CAMERA FRUSTUM RENDERING -------------
# Class for rendering a camera frustum reprsenting the Looking Glass
# in Blenders 3D viewport
class FrustumRenderer:

    # Inititalize the camera frustum drawing
    def __init__(self):

        # Blender draw handler for the frustum
        self.frustum_draw_handler = None

        # variables for the frustum
        self.frustum_indices_lines = None
        self.frustum_indices_faces = None
        self.frustum_indices_focalplane_outline = None
        self.frustum_indices_focalplane_face = None
        self.frustum_shader = None

        # notify addon that frustum is activated
        LookingGlassAddon.FrustumInitialized = True



    # deinititalize the camera frustum drawing
    @classmethod
    def __del__(self):

        # remove the draw handler for the frustum drawing
        if self.frustum_draw_handler:
            bpy.types.SpaceView3D.draw_handler_remove(self.frustum_draw_handler, 'WINDOW')
            self.frustum_draw_handler = None

        # notify addon that frustum is deactivated
        LookingGlassAddon.FrustumInitialized = False



    # cancel frustum drawing
    def stop(self):

        # remove the draw handler for the frustum drawing
        if self.frustum_draw_handler:
            bpy.types.SpaceView3D.draw_handler_remove(self.frustum_draw_handler, 'WINDOW')
            self.frustum_draw_handler = None

        LookingGlassAddon.FrustumInitialized = False

        # log info
        LookingGlassAddonLogger.info("Camera frustum drawing handler started.")

        # return None since this is expected by the operator
        return None



    # start the frustum drawing
    def start(self, context):

        # setup the camera frustum & shader
        self.setupCameraFrustumShader()

        # add draw handler to display the frustum of the Looking Glass camera
        # after everything else has been drawn in the view
        self.frustum_draw_handler = bpy.types.SpaceView3D.draw_handler_add(self.drawCameraFrustum, (context,), 'WINDOW', 'POST_VIEW')

        # log info
        LookingGlassAddonLogger.info("Camera frustum drawing handler stopped.")

        # keep the modal operator running
        return self.frustum_draw_handler



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
            if hasattr(context.scene, "addon_settings") and context.scene.addon_settings.lookingglassCamera in [obj for obj in context.view_layer.objects]:
                if (context.space_data != None and context.space_data.region_3d != None) and context.space_data.region_3d.view_perspective != 'CAMERA':

                    # currently selected camera
                    camera = context.scene.addon_settings.lookingglassCamera

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
                        focalPlane = context.scene.addon_settings.focalPlane

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
                        if context.scene.addon_settings.showFrustum == True:
                            batch_lines = batch_for_shader(self.frustum_shader, 'LINES', {"pos": coords_local}, indices=self.frustum_indices_lines)
                            batch_faces = batch_for_shader(self.frustum_shader, 'TRIS', {"pos": coords_local}, indices=self.frustum_indices_faces)

                        # if the focal plane shall be drawn
                        if context.scene.addon_settings.showFocalPlane == True:
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

                        gpu.state.depth_test_set('LESS_EQUAL')
                        gpu.state.depth_mask_set(True)

                        # if the camera fustum shall be drawn
                        if context.scene.addon_settings.showFrustum == True:
                            # draw outline
                            self.frustum_shader.uniform_float("color", (0.3, 0, 0, 1))
                            batch_lines.draw(self.frustum_shader)

                        # if the focal plane shall be drawn
                        if context.scene.addon_settings.showFocalPlane == True:
                            # draw focal plane outline
                            self.frustum_shader.uniform_float("color", (1, 1, 1, 1))
                            batch_focalplane_outline.draw(self.frustum_shader)

                        gpu.state.depth_mask_set(False)
                        gpu.state.blend_set('ALPHA')

                        # if the camera fustum shall be drawn
                        if context.scene.addon_settings.showFrustum == True:
                            # fill faces
                            self.frustum_shader.uniform_float("color", (0.5, 0.5, 0.5, 0.05))
                            batch_faces.draw(self.frustum_shader)

                        # if the focal plane shall be drawn
                        if context.scene.addon_settings.showFocalPlane == True:
                            # draw focal plane face
                            self.frustum_shader.uniform_float("color", (0.1, 0.1, 0.1, 0.25))
                            batch_focalplane_face.draw(self.frustum_shader)

                        gpu.state.depth_test_set('NONE')
                        gpu.state.blend_set('NONE')

                        # reset the matrices to their original state
                        gpu.matrix.reset()
                        gpu.matrix.load_matrix(viewMatrix)
                        gpu.matrix.load_projection_matrix(projectionMatrix)



# ------------ BLOCKS PREVIEW RENDERING -------------
# Class for blocks. Instances store all the data of a Block.
class Block:

    # Inititalize the block
    def __init__(self, x, y, width, height):

        # the lightfield image of the block
        self.lightfield_image = None

        # quilt presets
        self.qs = pylio.LookingGlassQuilt.formats.get()
        self.preset = bpy.context.scene.addon_settings.quiltPreset

        # block parameters
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.border_width = 0.015
        self.border_color = (0.0086, 0.0086, 0.0086, 1.0)
        self.alpha = 1.0
        self.size_factor = 0.25
        self.aspect = self.width / self.height
        self.angle = 0
        self.view = 0
        self.view_cone = 40

        # GPU parameters
        self.camera = None
        self.view_matrix = None
        self.projection_matrix = None

        # create the offscreen this block is drawn in
        self.offscreen_canvas = gpu.types.GPUOffScreen(self.width, self.height)
        self.offscreen_view = None

        # create shaders
        self.__update_shaders()



    # create a view matrix from a virtual camera position, target vector, and up
    # vector
    def __update_shaders(self):

        # define shaders
        self.vertex_shader = '''
            uniform mat4 modelMatrix;
            uniform mat4 viewProjectionMatrix;

            in vec2 position;
            in vec2 uv;

            out vec2 texCoord;

            void main()
            {
                texCoord = uv;
                gl_Position = viewProjectionMatrix * modelMatrix * vec4(position, 0.0, 1.0);
            }
        '''

        self.fragment_shader = '''
            uniform sampler2D view_texture;
            uniform vec4 border_color;
            uniform float border_width;
            uniform float aspect;  // ratio of width to height
            uniform float alpha;

            in vec2 texCoord;
            out vec4 FragColor;

            void main()
            {
                float border_width = border_width;
                float maxX = 1.0 - border_width / aspect;
                float minX = border_width / aspect;
                float maxY = 1.0 - border_width;
                float minY = border_width;
                float a = aspect;

                if (texCoord.x < maxX && texCoord.x > minX &&
                   texCoord.y < maxY && texCoord.y > minY) {
                 FragColor = texture(view_texture, texCoord);
                } else {
                 FragColor = border_color;
                }

                // set alpha value
                FragColor.a = alpha;
            }
        '''

        # for portrait orientations
        if self.aspect < 1:
            position_vertices = ((-self.aspect, -1), (self.aspect, -1), (self.aspect, 1), (-self.aspect, 1))

        # for portrait orientations
        elif self.aspect >= 1:
            position_vertices = ((-1, -1/self.aspect), (1, -1/self.aspect), (1, 1/self.aspect), (-1, 1/self.aspect))

        # compile block shader
        self.shader = gpu.types.GPUShader(self.vertex_shader, self.fragment_shader)
        self.batch = batch_for_shader(
            self.shader, 'TRI_FAN',
            {
                "position": position_vertices,
                "uv": ((0, 0), (1, 0), (1, 1), (0, 1)),
            },
        )

    # this is widely based on the following stackexchange thread:
    # https://blender.stackexchange.com/questions/16472/how-can-i-get-the-cameras-projection-matrix/86570#86570
    # which is a python translation of Blenders internal projection matrix calculations
    def __projection_matrix(self, camera, x, y, scale_x, scale_y):

        def BKE_camera_sensor_size(p_sensor_fit, sensor_x, sensor_y):
            #/* sensor size used to fit to. for auto, sensor_x is both x and y. */
            if (p_sensor_fit == 'VERTICAL'):
                return sensor_y;

            return sensor_x;

        #/* determine sensor fit */
        def BKE_camera_sensor_fit(p_sensor_fit, sizex, sizey):
            if (p_sensor_fit == 'AUTO'):
                if (sizex >= sizey):
                    return 'HORIZONTAL'
                else:
                    return 'VERTICAL'

            return p_sensor_fit

        def view_plane(camera, winx, winy, xasp, yasp):
            #/* fields rendering */
            ycor = yasp / xasp
            use_fields = False
            if (use_fields):
              ycor *= 2

            if (camera.type == 'ORTHO'):
              #/* orthographic camera */
              #/* scale == 1.0 means exact 1 to 1 mapping */
              pixsize = camera.ortho_scale
            else:
              #/* perspective camera */
              sensor_size = BKE_camera_sensor_size(camera.sensor_fit, camera.sensor_width, camera.sensor_height)
              pixsize = (sensor_size * 0.001) / camera.lens

            sensor_fit = BKE_camera_sensor_fit(camera.sensor_fit, xasp * winx, yasp * winy)

            if (sensor_fit == 'HORIZONTAL'):
              viewfac = winx
            else:
              viewfac = ycor * winy

            pixsize /= viewfac

            #/* extra zoom factor */
            pixsize *= 1 #params->zoom

            #/* compute view plane:
            # * fully centered, zbuffer fills in jittered between -.5 and +.5 */
            xmin = -0.5 * winx
            ymin = -0.5 * ycor * winy
            xmax =  0.5 * winx
            ymax =  0.5 * ycor * winy

            #/* lens shift and offset */
            dx = camera.shift_x * viewfac # + winx * params->offsetx
            dy = camera.shift_y * viewfac # + winy * params->offsety

            xmin += dx
            ymin += dy
            xmax += dx
            ymax += dy

            #/* fields offset */
            #if (params->field_second):
            #    if (params->field_odd):
            #        ymin -= 0.5 * ycor
            #        ymax -= 0.5 * ycor
            #    else:
            #        ymin += 0.5 * ycor
            #        ymax += 0.5 * ycor

            #/* the window matrix is used for clipping, and not changed during OSA steps */
            #/* using an offset of +0.5 here would give clip errors on edges */
            xmin *= pixsize
            xmax *= pixsize
            ymin *= pixsize
            ymax *= pixsize

            return xmin, xmax, ymin, ymax

        left, right, bottom, top = view_plane(camera, x, y, scale_x, scale_y)

        farClip, nearClip = 100, 0.001#camera.clip_end, camera.clip_start

        Xdelta = right - left
        Ydelta = top - bottom
        Zdelta = farClip - nearClip

        mat = [[0]*4 for i in range(4)]

        mat[0][0] = nearClip * 2 / Xdelta
        mat[1][1] = nearClip * 2 / Ydelta
        mat[2][0] = (right + left) / Xdelta #/* note: negate Z  */
        mat[2][1] = (top + bottom) / Ydelta
        mat[2][2] = -(farClip + nearClip) / Zdelta
        mat[2][3] = -1
        mat[3][2] = (-2 * nearClip * farClip) / Zdelta

        return sum([c for c in mat], [])

    # create a view matrix from a virtual camera position, target vector, and up
    # vector
    def __matrix_look_at(self, camera_location, camera_target, camera_up):

        # calculate coordinate vectors
        camera_direction = (camera_location - camera_target).normalized()
        camera_right = camera_up.cross(camera_direction).normalized()
        camera_up = camera_direction.cross(camera_right).normalized()

        # rotation matrix
        matrix_rotation = Matrix()
        matrix_rotation[0][:3] = camera_right[:]
        matrix_rotation[1][:3] = camera_up[:]
        matrix_rotation[2][:3] = camera_direction[:]

        # translation matrix
        matrix_translation = Matrix.Translation(-camera_location)

        # calculate and return view matrix ("lookat" matrix)
        return matrix_rotation @ matrix_translation

    # update the view and perspective matrices
    def __update_matrices(self, context):

        if context.space_data is None:
            return None

        # select camera that belongs to the view
        camera = context.scene.addon_settings.lookingglassCamera

        if camera != None:

            # calculate the inverted view matrix because this is what the draw_view_3D function requires
            self.view_matrix = self.__matrix_look_at(Vector((sin(radians(self.angle)) * 3.1, 0, cos(radians(self.angle)) * 3.1)), Vector((0, 0, 0)), Vector((0, 1, 0)))

            # get the camera's projection matrix
            self.projection_matrix = self.__projection_matrix(
                    camera.data,
                    x = self.qs[self.preset]['view_width'],
                    y = self.qs[self.preset]['view_height'],
                    scale_x = 1.0,
                    scale_y = (self.qs[self.preset]['rows'] / self.qs[self.preset]['columns']) / self.aspect,
                )


    # store camera for block rendering in the block data
    def set_camera(self, camera):
        if not camera is None:
            self.camera = camera

    # store lightfield image in the block data
    def set_lightfield_image(self, lightfield_image):
        if not lightfield_image is None:
            self.lightfield_image = lightfield_image

    # store dimensions in the block data
    def set_dimensions(self, width, height):

        if (not width is None and width != self.width) or (not height is None and height != self.height):

            if not width is None:
                self.width = int(width)

            if not height is None:
                self.height = int(height)

            # free the offscreen object
            if self.offscreen_canvas: self.offscreen_canvas.free()

            # create a new offscreen block is drawn in
            self.offscreen_canvas = gpu.types.GPUOffScreen(self.width, self.height)

    # set the quilt preset for this Block
    def set_preset(self, preset):

        if not (preset is None or self.preset == preset):
            self.preset = preset

            # free offscreen
            if self.offscreen_view: self.offscreen_view.free()

            # create a new offscreen the view is drawn to
            self.offscreen_view = gpu.types.GPUOffScreen(self.qs[self.preset]['view_width'], self.qs[self.preset]['view_height'])

            # update shaders to include the new aspect ratio
            self.__update_shaders()

    # store view in the block data
    def set_view(self, view):
        if not view is None:
            self.view = view

    # store view cone in the block data
    def set_view_cone(self, view_cone):
        if not view_cone is None:
            self.view_cone = view_cone

    # store angle in the block data
    def set_angle(self, angle):
        if not angle is None:
            self.angle = angle

    # store alpha value in the block data
    def set_alpha(self, alpha):
        if not alpha is None:
            self.alpha = alpha

    # store aspect ratio of the views in the block data
    def set_aspect(self, aspect):
        if not (aspect is None or self.aspect == aspect):
            self.aspect = aspect

            # update shaders to include the new aspect ratio
            self.__update_shaders()

    # store border_width value in the block data
    def set_border_width(self, border_width):
        if not border_width is None:
            self.border_width = border_width

    # store border_color value in the block data
    def set_border_color(self, border_color):
        if not border_color is None:
            self.border_color = border_color

    # update the block by rendering it in its own offscreen
    def update(self, context):

        # if the block has a view texture
        if self.offscreen_view:

            # update matrices
            self.__update_matrices(context)

            # start drawing into the preview offscreen
            with self.offscreen_canvas.bind():

                # get active frame buffer
                framebuffer = gpu.state.active_framebuffer_get()

                # clear the framebuffer
                framebuffer.clear(color=(1.0, 0.0, 0.0, 0.0))

                # update shader uniforms
                self.shader.bind()
                self.shader.uniform_float("modelMatrix", self.view_matrix)
                self.shader.uniform_float("viewProjectionMatrix", self.projection_matrix)
                self.shader.uniform_float("aspect", self.aspect)
                self.shader.uniform_float("border_width", self.border_width)
                self.shader.uniform_float("border_color", self.border_color)
                if context.space_data.type == 'VIEW_3D': self.shader.uniform_float("alpha", self.alpha)
                if context.space_data.type == 'IMAGE_EDITOR': self.shader.uniform_float("alpha", 1.0)
                self.shader.uniform_sampler("view_texture", self.offscreen_view.texture_color)

                # draw the block image
                self.batch.draw(self.shader)




# Class for rendering a Looking Glass Block in Blenders 3D viewport for live preview
class BlockRenderer:

    # drawing handlers
    __block_draw_view3d_handler = None
    __block_draw_imageeditor_handler = None

    # private class properties
    __blocks = {}
    __last_id = 0

    # active blocks
    __viewport3d_block = None
    __imageeditor_block = None

    # active presets
    __viewport3d_preset = 0
    __imageeditor_preset = 0

    # camera for block rendering
    block_renderer_camera = None

    # ------------ KEYMAP OPERATOR FOR BLOCK RENDERER UPDATES -------------
    class LOOKINGGLASS_OT_update_block_renderer(bpy.types.Operator):
        """ This operator updates the block renderer"""
        bl_idname = "wm.update_block_renderer"
        bl_label = "Alice/LG: Block Renderer"

        def invoke(self, context, event):

            if (context is None) or (event is None) or (not context is None and context.region is None):
                return {'PASS_THROUGH'}

            # if the block preview is active
            if not context.scene.addon_settings.ShowBlockPreview:
                return {'PASS_THROUGH'}

            # mouse position in window
            LookingGlassAddon.mouse_window_x = event.mouse_x
            LookingGlassAddon.mouse_window_y = event.mouse_y

            # mouse position in current context region
            LookingGlassAddon.mouse_region_x = event.mouse_x - context.region.x
            LookingGlassAddon.mouse_region_y = event.mouse_y - context.region.y


            # update the variable for the current Looking Glass device
            if int(bpy.context.scene.addon_settings.activeDisplay) != -1: device = pylio.DeviceManager.get_active()

            # get the viewport block
            block = LookingGlassAddon.BlockRenderer.get_viewport_block()
            if block and device:

                # update dimensions
                if device.aspect < 1: block.set_dimensions(int(sqrt(context.area.width * context.area.height) * block.size_factor * device.aspect), int(sqrt(context.area.width * context.area.height) * block.size_factor))
                if device.aspect >= 1: block.set_dimensions(int(sqrt(context.area.width * context.area.height) * block.size_factor), int(sqrt(context.area.width * context.area.height) * block.size_factor / device.aspect))

                # infer the current view
                if (LookingGlassAddon.mouse_region_x > block.x and LookingGlassAddon.mouse_region_x < block.x + block.width) and (LookingGlassAddon.mouse_region_y > block.y and LookingGlassAddon.mouse_region_y < block.y + block.height):

                    # calculate the view number and angle
                    view = floor(block.qs[block.preset]["total_views"] * (1 - (LookingGlassAddon.mouse_region_x - block.x) / block.width))
                    angle = -floor(device.viewCone * ((LookingGlassAddon.mouse_region_x - block.x) / block.width - 0.5))

                    # update state variables
                    block.set_aspect(device.aspect)
                    block.set_view_cone(device.viewCone)
                    block.set_view(view)
                    block.set_angle(angle)
                    block.set_alpha(1.0)

                    # redraw region
                    context.region.tag_redraw()

                    return {'PASS_THROUGH'}

                # has some of the parameters changed
                if block.aspect != device.aspect or block.view_cone != device.viewCone or block.alpha != 0.3:

                    # if the mouse is outside the area use the center view
                    #view = floor(block.qs[block.preset]["total_views"] / 2)
                    #angle = floor(0)

                    # update state variables
                    block.set_aspect(device.aspect)
                    block.set_view_cone(device.viewCone)
                    block.set_alpha(0.3)

                    # redraw region
                    bpy.context.region.tag_redraw()

            return {'PASS_THROUGH'}



    # ------------ BLOCK RENDERER -------------
    # Inititalize the block renderer
    def __init__(self):

        # notify addon that block is activated
        LookingGlassAddon.BlockInitialized = True



    # deinititalize the block renderer
    @classmethod
    def __del__(self):

        # if it was successfully initialized
        if LookingGlassAddon.BlockInitialized:

            # delete the temporary camera again
            if self.block_renderer_camera: bpy.data.objects.remove(self.block_renderer_camera)

            # remove the draw handler for the frustum drawing
            if self.__block_draw_view3d_handler:
                bpy.types.SpaceView3D.draw_handler_remove(self.__block_draw_view3d_handler, 'WINDOW')
                self.__block_draw_view3d_handler = None

            if self.__block_draw_imageeditor_handler:
                bpy.types.SpaceImageEditor.draw_handler_remove(self.__block_draw_imageeditor_handler, 'WINDOW')
                self.__block_draw_imageeditor_handler = None

            # notify addon that frustum is deactivated
            LookingGlassAddon.BlockInitialized = False



    # start the block renderer
    def start(self, context):

        # # set border volor to Blenders default background color
        # self.block_border_color = context.preferences.themes[0].user_interface.editor_outline
        # print(self.block_border_color[0], self.block_border_color[1], self.block_border_color[2])
        # self.block_border_color = (self.block_border_color[0], self.block_border_color[1], self.block_border_color[2], 1.0)

        # add draw handler to display the frustum of the Looking Glass camera
        # after everything else has been drawn in the view
        self.__block_draw_view3d_handler = bpy.types.SpaceView3D.draw_handler_add(self.__viewport_render, (context,), 'WINDOW', 'POST_PIXEL')
        self.__block_draw_imageeditor_handler = 0#bpy.types.SpaceImageEditor.draw_handler_add(self.__imageeditor_render, (context,), 'WINDOW', 'POST_PIXEL')

        # log info
        LookingGlassAddonLogger.info("Block preview started.")

        # keep the modal operator running
        return (self.__block_draw_view3d_handler, self.__block_draw_imageeditor_handler)



    # stop the block renderer
    def stop(self):

        # if it was successfully initialized
        if LookingGlassAddon.BlockInitialized:

            # remove the draw handler for the frustum drawing
            if self.__block_draw_view3d_handler:
                bpy.types.SpaceView3D.draw_handler_remove(self.__block_draw_view3d_handler, 'WINDOW')
                self.__block_draw_view3d_handler = None

            if self.__block_draw_imageeditor_handler:
                bpy.types.SpaceImageEditor.draw_handler_remove(self.__block_draw_imageeditor_handler, 'WINDOW')
                self.__block_draw_imageeditor_handler = None

            # notify addon that frustum is deactivated
            LookingGlassAddon.BlockInitialized = False

        # log info
        LookingGlassAddonLogger.info("Block preview stopped.")

        # return None since this is expected by the operator
        return None



    # add a block to the block renderer
    def add_block(self, id, x, y, width, height):

        # add the block to the dictionary
        self.__blocks[id] = Block(x, y, width, height)

    # set the block to be rendered in the Blender viewport
    def set_viewport_block(self, id):

        # set the active VIEW3D block
        self.__viewport3d_block = id

    # get the block to be rendered in the Blender viewport
    def get_viewport_block(self):
        if not self.__viewport3d_block is None:
            return self.__blocks[self.__viewport3d_block]

    # set the block to be rendered in the image editor
    def set_imageeditor_block(self, id):

        # set the active IMAGE_EDITOR block
        self.__imageeditor_block = id

    # get the block to be rendered in the image editor
    def get_imageeditor_block(self):
        if not self.__imageeditor_block is None:
            return self.__blocks[self.__imageeditor_block]

    # set up the camera for each view and the shader of the rendering object
    def __setupVirtualCameraForView(self, context, block, camera, viewMatrix, projectionMatrix):

        # if a camera is used for the Looking Glass
        if camera != None:

            # The field of view set by the camera
            # NOTE 1: - the Looking Glass Factory documentation suggests to use a FOV of 14°. We use the focal length of the Blender camera instead.
            # NOTE 2: - we take the angle directly from the projection matrix
            fov = 2.0 * atan(1 / projectionMatrix[1][1])

            # calculate cameraSize from its distance to the focal plane and the FOV
            # NOTE: - we take an arbitrary distance of 5 m (we could also use the focal distance of the camera, but might be confusing)
            cameraDistance = context.scene.addon_settings.focalPlane
            cameraSize = cameraDistance * tan(fov / 2)

            # start at viewCone * 0.5 and go up to -viewCone * 0.5
            offsetAngle = (0.5 - block.view / (block.qs[block.preset]["total_views"] - 1)) * radians(block.view_cone)

            # calculate the offset that the camera should move
            offset = cameraDistance * tan(offsetAngle)

            # translate the view matrix (position) by the calculated offset in x-direction
            viewMatrix = Matrix.Translation((offset, 0, 0)) @ viewMatrix

            # modify the projection matrix, relative to the camera size and aspect ratio
            projectionMatrix[0][2] += offset / (cameraSize * block.aspect)

        else:

            LookingGlassAddonLogger.warning("Could not calculate the matrices for the lightfield viewport. '%s' is not a valid camera." % camera)

        # return the projection matrix
        return viewMatrix, projectionMatrix

    # render the block into the viewport
    def __viewport_render(self, context):

        # if a camera is selected AND the space is not in camera mode AND
        # the block viewport preview shall be drawn
        if self and context:
            if hasattr(context.scene, "addon_settings") and context.scene.addon_settings.lookingglassCamera in [obj for obj in context.view_layer.objects] and context.scene.addon_settings.ShowBlockPreview:
                if (context.space_data != None):

                    # select correct block
                    block = self.__blocks[self.__viewport3d_block]
                    if block is None or block.preset is None or block.offscreen_view is None:
                        return

                    # PREPARE VIEW & PROJECTION MATRIX
                    # ++++++++++++++++++++++++++++++++++++++++++++++++

                    # select camera that belongs to the view
                    camera = context.scene.addon_settings.lookingglassCamera

                    # PREPARE THE MODELVIEW AND PROJECTION MATRICES
                    # if a camera is selected
                    if camera != None:
                        #
                        # # if noc camera exists create it
                        # if not self.block_renderer_camera:
                        #     self.block_renderer_camera = bpy.data.objects.new("alicelg_blocks_cam", camera.data.copy())
                        #     self.block_renderer_camera.data.clip_start = 0
                        #
                        #     # set the block camera
                        #     block.set_camera(self.block_renderer_camera)
                        #
                        # else:
                        #
                        #     # set the block camera
                        #     block.set_camera(self.block_renderer_camera)
                        #
                        #     # copy selected Looking Glass camera data
                        #     block.camera.data = camera.data.copy()

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
                                x = block.qs[block.preset]["view_width"],
                                y = block.qs[block.preset]["view_height"],
                                scale_x = 1.0,
                                scale_y = (block.qs[block.preset]["rows"] / block.qs[block.preset]["columns"]) / block.aspect,
                            )


                        # RENDER THE VIEW
                        # ++++++++++++++++++++++++++++++++++++++++++++++++
                        with block.offscreen_view.bind():

                            # calculate the offset-projection of the current view
                            view_matrix, projection_matrix = self.__setupVirtualCameraForView(context, block, camera, camera_view_matrix.copy(), camera_projection_matrix.copy())

                            # draw the viewport rendering to the offscreen for the current view
                            block.offscreen_view.draw_view3d(
                                # we use the "Scene" and the "View Layer" that is active in the Window
                                # the user currently works in
                                scene=context.scene,
                                view_layer=context.view_layer,
                                view3d=context.space_data,
                                region=context.region,
                                view_matrix=view_matrix,
                                projection_matrix=projection_matrix,
                                do_color_management = False)

                        # restore all viewport shading and overlay settings
                        #self.restoreViewportSettings()

                    # update the block
                    block.update(context)

                    #gpu.state.depth_test_set('LESS_EQUAL')
                    gpu.state.depth_mask_set(True)
                    gpu.state.blend_set('ALPHA')

                    # if the block is drawn in a SpaceView3D
                    if context.space_data.type == 'VIEW_3D' and context.space_data.region_3d != None:
                        draw_texture_2d(block.offscreen_canvas.texture_color, (block.x, block.y), block.width, block.height)

                    gpu.state.depth_mask_set(False)
                    gpu.state.blend_set('NONE')



    # render the block into the image editor
    def __imageeditor_render(self, context):

        # if a camera is selected AND the space is not in camera mode
        if self and context:
            if hasattr(context.scene, "addon_settings") and context.scene.addon_settings.lookingglassCamera in [obj for obj in context.view_layer.objects]:
                if (context.space_data != None and context.space_data.type == 'IMAGE_EDITOR'):

                    # if the image is a quilt
                    if context.space_data.image != None:
                        print("image", context.space_data.image.name)
                        #draw_texture_2d(block.offscreen_canvas.texture_color, ((context.area.width - block.width) / 2, (context.area.height - block.height) / 2), block.width, block.height)

                        # select correct block
                        block = self.__blocks[self.__imageeditor_block]

                        # update the block
                        block.update(context)

                        #gpu.state.depth_test_set('LESS_EQUAL')
                        gpu.state.depth_mask_set(True)
                        gpu.state.blend_set('ALPHA')

                        # if the block is drawn in a SpaceView3D
                        if context.space_data.type == 'VIEW_3D' and context.space_data.region_3d != None:
                            draw_texture_2d(block.offscreen_canvas.texture_color, (block.x, block.y), block.width, block.height)

                        gpu.state.depth_mask_set(False)
                        #gpu.state.depth_test_set('NONE')
                        gpu.state.blend_set('NONE')
