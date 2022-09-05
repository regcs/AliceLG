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




# ------------ CONTEXT OVERRIDE -------------
# Class for managing a SpaceView3D context override for offscreen rendering
class ContextOverride:

	# ADDON SETTING DATA
	__addon_settings = None

	# CONTEXT DATA
	__context = None
	__override = None

	# CONTEXT DATA BACKUP
	__shading_restore_backup = {}
	__overlay_restore_backup = {}

    # Inititalize the context override
	def __init__(self, context):

		# get the current settings of this scene
		self.__context = context

		# get the current settings of this scene
		self.__addon_settings = context.scene.addon_settings

		# create an override context from the invoking context
		self.__override = context.copy()


	# set a new context
	def set_context(self, context):

		# get the current settings of this scene
		self.__context = context


	# set up the camera for each view and the shader of the rendering object
	def setupVirtualCameraForView(self, view, total_views, view_cone, aspect, viewMatrix, projectionMatrix):

		# The field of view set by the camera
		# NOTE 1: - the Looking Glass Factory documentation suggests to use a FOV of 14°. We use the focal length of the Blender camera instead.
		# NOTE 2: - we take the angle directly from the projection matrix
		fov = 2.0 * atan(1 / projectionMatrix[1][1])

		# calculate cameraSize from its distance to the focal plane and the FOV
		# NOTE: - we take an arbitrary distance of 5 m (we could also use the focal distance of the camera, but might be confusing)
		cameraDistance = self.__addon_settings.focalPlane
		cameraSize = cameraDistance * tan(fov / 2)

		# start at viewCone * 0.5 and go up to -viewCone * 0.5
		offsetAngle = (0.5 - view / (total_views - 1)) * radians(view_cone)

		# calculate the offset that the camera should move
		offset = cameraDistance * tan(offsetAngle)

		# translate the view matrix (position) by the calculated offset in x-direction
		viewMatrix = Matrix.Translation((offset, 0, 0)) @ viewMatrix

		# modify the projection matrix, relative to the camera size and aspect ratio
		projectionMatrix[0][2] += offset / (cameraSize * aspect)

		# return the projection matrix
		return viewMatrix, projectionMatrix



	# Save the viewport settings
	def saveViewportSettings(self):

		# SHADING ATTRIBUTES
		# define some exceptions that must not be taken into
		attributeExceptions = ["__doc__", "__module__", "__slots__", "bl_rna", "rna_type", "color_type", "studio_light"]

		# use the "space data" of the selected viewport
		attributeList = dir(self.__override['space_data'].shading)
		for attr in attributeList:

			if not attr in attributeExceptions and hasattr(self.__override['space_data'].shading, attr):
				#print("[SHADING]", attr, " = ", getattr(LookingGlassAddon.BlenderViewport.shading, attr))

				try:
					self.__shading_restore_backup[attr] = getattr(self.__override['space_data'].shading, attr)
				except Exception as e:
					#print(" # ", e)
					pass

		attributeList = dir(self.__override['space_data'].overlay)
		for attr in attributeList:

			if not attr in attributeExceptions and hasattr(self.__override['space_data'].overlay, attr):
				#print("[OVERLAY]", attr, " = ", getattr(self.__override['space_data'].overlay, attr))

				try:
					self.__overlay_restore_backup[attr] = getattr(self.__override['space_data'].overlay, attr)
				except Exception as e:
					#print(" # ", e)
					pass


	# Update the viewport settings
	def updateViewportSettings(self, space_data=None, force_context_data=False):

		# get the space data into the override
		if space_data:
			self.__override['space_data'] = space_data

		# save all shading & overlay settings
		self.saveViewportSettings()


		# APPLY CUSTOM SETTINGS IF REQUIRED
		####################################################################

		# if the custom settings shall be used OR the given space data is invalid
		if (self.__addon_settings.viewportMode == 'CUSTOM' and force_context_data == False) or space_data == None:

			# SHADING ATTRIBUTES
			self.__override['space_data'].shading.type = self.__addon_settings.shadingMode
			self.__override['space_data'].shading.show_xray = bool(self.__addon_settings.viewport_show_xray)
			self.__override['space_data'].shading.xray_alpha = float(self.__addon_settings.viewport_xray_alpha)
			self.__override['space_data'].shading.use_dof = bool(int(self.__addon_settings.viewport_use_dof))

			# OVERLAY ATTRIBUTES: Guides
			self.__override['space_data'].overlay.show_floor = bool(int(self.__addon_settings.viewport_show_floor))
			self.__override['space_data'].overlay.show_axis_x = bool(int(self.__addon_settings.viewport_show_axes[0]))
			self.__override['space_data'].overlay.show_axis_y = bool(int(self.__addon_settings.viewport_show_axes[1]))
			self.__override['space_data'].overlay.show_axis_z = bool(int(self.__addon_settings.viewport_show_axes[2]))
			self.__override['space_data'].overlay.grid_scale = float(self.__addon_settings.viewport_grid_scale)
			# OVERLAY ATTRIBUTES: Objects
			self.__override['space_data'].overlay.show_extras = bool(int(self.__addon_settings.viewport_show_extras))
			self.__override['space_data'].overlay.show_relationship_lines = bool(int(self.__addon_settings.viewport_show_relationship_lines))
			self.__override['space_data'].overlay.show_outline_selected = bool(int(self.__addon_settings.viewport_show_outline_selected))
			self.__override['space_data'].overlay.show_bones = bool(int(self.__addon_settings.viewport_show_bones))
			self.__override['space_data'].overlay.show_motion_paths = bool(int(self.__addon_settings.viewport_show_motion_paths))
			self.__override['space_data'].overlay.show_object_origins = bool(int(self.__addon_settings.viewport_show_origins))
			self.__override['space_data'].overlay.show_object_origins_all = bool(int(self.__addon_settings.viewport_show_origins_all))
			# OVERLAY ATTRIBUTES: Geometry
			self.__override['space_data'].overlay.show_wireframes = bool(int(self.__addon_settings.viewport_show_wireframes))
			self.__override['space_data'].overlay.show_face_orientation = bool(int(self.__addon_settings.viewport_show_face_orientation))

		# if the settings rely on a specific viewport / SpaceView3D
		elif (self.__addon_settings.viewportMode != 'CUSTOM' or force_context_data == True) and space_data != None:

			# if CYCLES is activated in the current viewport
			if space_data.shading.type == 'RENDERED' and self.__context.engine == 'CYCLES':

				# change the shading type to SOLID
				self.__override['space_data'].shading.type = 'SOLID'

				# notify user
				self.report({"WARNING"}, "Render engine (%s) not supported in lightfield previews. Switched to SOLID mode." % self.__context.engine)

		# always disable the hdri preview spheres
		self.__override['space_data'].overlay.show_look_dev = False

	# Restore the viewport settings
	def restoreViewportSettings(self):

		# SHADING ATTRIBUTES
		# define some exceptions that must not be taken into
		attributeExceptions = ["__doc__", "__module__", "__slots__", "bl_rna", "rna_type", "color_type", "studio_light", "type"]

		# use the "space data" of the selected viewport
		attributeList = dir(self.__override['space_data'].shading)
		for attr in attributeList:

			if not attr in attributeExceptions and hasattr(self.__override['space_data'].shading, attr):
				if getattr(self.__override['space_data'].shading, attr) != self.__shading_restore_backup[attr]:
				#print("[SHADING]", attr, " = ", self.__shading_restore_backup[attr])

					try:
						setattr(self.__override['space_data'].shading, attr, self.__shading_restore_backup[attr])
					except Exception as e:
						#print(" # ", e)
						pass

		attributeList = dir(self.__override['space_data'].overlay)
		for attr in attributeList:

			if not attr in attributeExceptions and hasattr(self.__override['space_data'].overlay, attr):
				if getattr(self.__override['space_data'].overlay, attr) != self.__overlay_restore_backup[attr]:
				# print("[OVERLAY]", attr, " = ", self.__overlay_restore_backup[attr])

					try:
						setattr(self.__override['space_data'].overlay, attr, self.__overlay_restore_backup[attr])
					except Exception as e:
						#print(" # ", e)
						pass

    # CLASS PROPERTIES
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # (A) context override properties
	@property
	def space_data(self):
		return self.__override['space_data']

	@space_data.setter
	def space_data(self, value):
		pass

	@property
	def region(self):
		return self.__override['region']

	@region.setter
	def region(self, value):
		pass

	@property
	def shading_to_dict(self):
		return self.__shading_restore_backup

	@shading_to_dict.setter
	def shading_to_dict(self, value):
		pass

	@property
	def overlay_to_dict(self):
		return self.__overlay_restore_backup

	@overlay_to_dict.setter
	def overlay_to_dict(self, value):
		pass



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
		self._override = ContextOverride(context)

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
	def setupVirtualCameraForView(self, view, viewMatrix, projectionMatrix):

		# use the context override class method
		return self._override.setupVirtualCameraForView(view, self.qs[self.preset]["total_views"], self.device.viewCone, self.device.aspect, viewMatrix, projectionMatrix)


	# Save the viewport settings
	def saveViewportSettings(self):

		# use the context override class method
		return self._override.saveViewportSettings()


	# Update the viewport settings
	def updateViewportSettings(self, context):

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

				# set the context
				self._override.set_context(context)

				# assign the selected viewport
				return self._override.updateViewportSettings(LookingGlassAddon.BlenderViewport)

			else:

				# reset the global variable and fall back to custom settings
				LookingGlassAddon.BlenderViewport = None

				# set the context
				self._override.set_context(context)

				# assign the selected viewport
				return self._override.updateViewportSettings(LookingGlassAddon.BlenderViewport)


	# Restore the viewport settings
	def restoreViewportSettings(self):

		# use the context override class method
		return self._override.restoreViewportSettings()


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
						view_matrix, projection_matrix = self.setupVirtualCameraForView(view, camera_view_matrix.copy(), camera_projection_matrix.copy())

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
								view3d=self._override.space_data,
								region=self._override.region,
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
        LookingGlassAddonLogger.info("Camera frustum drawing handler stopped.")

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
        LookingGlassAddonLogger.info("Camera frustum drawing handler started.")

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

        # the texture of an image in the image editor
        self.image_texture = None

        # quilt presets
        self.qs = pylio.LookingGlassQuilt.formats.get()
        self.preset = None
        self.device = None

        # block parameters
        self.active = False
        self.x = x
        self.y = y
        self.width = int(width * bpy.context.scene.addon_settings.viewport_block_scaling_factor)
        self.height = int(height * bpy.context.scene.addon_settings.viewport_block_scaling_factor)
        self.border_width = 0.000
        self.border_color = (0.0086, 0.0086, 0.0086, 1.0)
        self.aspect = self.width / self.height
        self.angle = 0
        self.view = 0
        self.view_cone = 40
        self.shading_type = 'SOLID'

        # GPU and rendering
        self.changed = True
        self.camera = None
        self.view_matrix = None
        self.projection_matrix = None
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
            uniform vec2 dimensions;
            uniform float alpha;

            in vec2 texCoord;
            out vec4 FragColor;

			float roundedBoxSDF(vec2 CenterPosition, vec2 Size, float Radius)
			{
			    return length(max(abs(CenterPosition)-Size+Radius,0.0))-Radius;
			}

            void main()
            {
			    // Input info
			    vec2 boxPos; // The position of the center of the box (in normalized coordinates)
			    vec2 boxBnd; // The half-bounds (radii) of the box (in normalzied coordinates)
			    float radius;// Radius


			   	boxPos = vec2(0.5, 0.5);	// center of the screen
			    boxBnd = vec2(0.5, 0.5);  // half of the area
			    radius = 0.04;

			    // Normalize the pixel coordinates (this is "passTexCoords" in your case)
			    vec2 uv = texCoord;
			    vec2 aspectRatio = vec2(dimensions.x/dimensions.y, 1.0);

			    // In order to make sure visual distances are preserved, we multiply everything by aspectRatio
			    uv *= aspectRatio;
			    boxPos *= aspectRatio;
			    boxBnd *= aspectRatio;

			    // Output to screen
			    float a = length(max(abs(uv - boxPos) - boxBnd + radius, 0.0)) - radius;

				// Shadertoy doesn't have an alpha in this case
			    if(a <= 0.0){
			    	FragColor = texture(view_texture, texCoord);
	                FragColor.a = alpha;
			    }else{
			        FragColor = vec4(0.0, 0.0, 0.0, 0.0);
			    }

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
    def __projection_matrix(self, x, y, scale_x, scale_y):

        # set camera parameters that we require for the block rendering
        camera_lens = 50.0
        camera_sensor_width = 36.0
        camera_sensor_height = 24.0
        camera_shift_x = 0
        camera_shift_y = 0
        camera_clip_start = 0.001
        camera_clip_end = 100

        def view_plane(winx, winy, xasp, yasp):

            #/* fields rendering */
            ycor = yasp / xasp

            #/* perspective camera */
            pixsize = (camera_sensor_width * 0.001) / camera_lens

            # for landscape devices
            if (self.aspect >= 1):
              viewfac = winx

            # for portrait devices
            else:
              viewfac = ycor * winy

            pixsize /= viewfac

            #/* extra zoom factor */
            pixsize *= 1

            #/* compute view plane:
            # * fully centered, zbuffer fills in jittered between -.5 and +.5 */
            xmin = -0.5 * winx
            ymin = -0.5 * ycor * winy
            xmax =  0.5 * winx
            ymax =  0.5 * ycor * winy

            #/* lens shift and offset */
            dx = camera_shift_x * viewfac
            dy = camera_shift_y * viewfac

            xmin += dx
            ymin += dy
            xmax += dx
            ymax += dy

            #/* the window matrix is used for clipping, and not changed during OSA steps */
            #/* using an offset of +0.5 here would give clip errors on edges */
            xmin *= pixsize
            xmax *= pixsize
            ymin *= pixsize
            ymax *= pixsize

            return xmin, xmax, ymin, ymax

        left, right, bottom, top = view_plane(x, y, scale_x, scale_y)

        farClip, nearClip = camera_clip_end, camera_clip_start

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

        # calculate the inverted view matrix because this is what the draw_view_3D function requires
        self.view_matrix = self.__matrix_look_at(Vector((sin(radians(self.angle)) * 3.1, 0, cos(radians(self.angle)) * 3.1)), Vector((0, 0, 0)), Vector((0, 1, 0)))

        # get the camera's projection matrix
        self.projection_matrix = self.__projection_matrix(
                x = self.qs[self.preset]['view_width'],
                y = self.qs[self.preset]['view_height'],
                scale_x = 1.0,
                scale_y = (self.qs[self.preset]['rows'] / self.qs[self.preset]['columns']) / self.aspect,
            )

    # test if mouse is hovering over the block
    def is_mouse_over(self, context):
        if context is None or context.space_data is None:
            return False

        # for 3D viewports
        if context.space_data.type == 'VIEW_3D':
            # for left positioned blocks
            if context.scene.addon_settings.viewport_block_alignment == 'left':
                if (LookingGlassAddon.mouse_region_x > self.x and LookingGlassAddon.mouse_region_x < self.x + self.width) and (LookingGlassAddon.mouse_region_y > self.y and LookingGlassAddon.mouse_region_y < self.y + self.height):
                    return True

            # for right positioned blocks
            if context.scene.addon_settings.viewport_block_alignment == 'right':
                if (LookingGlassAddon.mouse_region_x > context.area.width - self.width - self.x - 50 and LookingGlassAddon.mouse_region_x < context.area.width - self.width - self.x - 50 + self.width) and (LookingGlassAddon.mouse_region_y > self.y and LookingGlassAddon.mouse_region_y < self.y + self.height):
                    return True

        # for image editors
        elif context.space_data.type == 'IMAGE_EDITOR':

            if (LookingGlassAddon.mouse_region_x > self.x and LookingGlassAddon.mouse_region_x < self.x + self.width) and (LookingGlassAddon.mouse_region_y > self.y and LookingGlassAddon.mouse_region_y < self.y + self.height):
                return True

	# check if block has changed
    def has_changed(self, context):
        if self.changed or self.shading_type != context.space_data.shading.type:
            return True

    # store lightfield image in the block data
    def set_lightfield_image(self, lightfield_image):
        if  not (lightfield_image is None or self.lightfield_image == lightfield_image):
            self.lightfield_image = lightfield_image

            # block has changed
            self.changed = True

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

            # block has changed
            self.changed = True

    # set the device type for this Block
    def set_device(self, device):

        if not (device is None or self.device == device):
            self.device = device

            # set the aspect and view cone
            self.aspect = device.aspect
            self.view_cone = device.viewCone

            # update shaders to include the new aspect ratio
            self.__update_shaders()

            # block has changed
            self.changed = True

    # set the quilt preset for this Block
    def set_preset(self, preset):

        if not (preset is None or self.preset == preset):
            self.preset = preset

            # get list of formats
            self.qs = pylio.LookingGlassQuilt.formats.get()

            # free offscreen
            if self.offscreen_view: self.offscreen_view.free()

            # create a new offscreen the view is drawn to
            self.offscreen_view = gpu.types.GPUOffScreen(self.qs[self.preset]['view_width'], self.qs[self.preset]['view_height'])

            # update shaders to include the new aspect ratio
            self.__update_shaders()

            # block has changed
            self.changed = True

    # store view in the block data
    def set_view(self, view):
        if not (view is None or self.view == view):
            self.view = view

            # block has changed
            self.changed = True

    # store view cone in the block data
    def set_view_cone(self, view_cone):
        if not (view_cone is None or self.view_cone == view_cone):
            self.view_cone = view_cone

            # block has changed
            self.changed = True

    # store angle in the block data
    def set_angle(self, angle):
        if not (angle is None or self.angle == angle):
            self.angle = angle

            # block has changed
            self.changed = True

    # store activity value in the block data
    def set_active(self, active):
        if not (active is None or self.active == active):
            self.active = active

            # block has changed
            self.changed = True

    # store aspect ratio of the views in the block data
    def set_aspect(self, aspect):
        if not (aspect is None or self.aspect == aspect):
            self.aspect = aspect

            # update shaders to include the new aspect ratio
            self.__update_shaders()

            # block has changed
            self.changed = True

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

			# update shading type variable
            if hasattr(context.space_data, 'shading'): self.shading_type = context.space_data.shading.type

            # start drawing into the preview offscreen
            with self.offscreen_canvas.bind():

                # get active frame buffer
                framebuffer = gpu.state.active_framebuffer_get()

                # clear the framebuffer
                framebuffer.clear(color=(0.0, 0.0, 0.0, 0.0))

                # update shader uniforms
                from struct import pack
                self.shader.bind()
                self.shader.uniform_float("modelMatrix", self.view_matrix)
                self.shader.uniform_float("viewProjectionMatrix", self.projection_matrix)
                #self.shader.uniform_float("aspect", self.aspect)
                self.shader.uniform_vector_float(self.shader.uniform_from_name("dimensions"), pack("2f", self.width, self.height), 2)
                #self.shader.uniform_float("border_width", self.border_width)
                #self.shader.uniform_float("border_color", self.border_color)
                if context.space_data.type == 'VIEW_3D':
                    if self.active: self.shader.uniform_float("alpha", 1.0)
                    if not self.active: self.shader.uniform_float("alpha", context.scene.addon_settings.viewport_block_alpha)
                if context.space_data.type == 'IMAGE_EDITOR':
                    self.shader.uniform_float("alpha", 1.0)
                self.shader.uniform_sampler("view_texture", self.offscreen_view.texture_color)

                # draw the block image
                self.batch.draw(self.shader)

	# free the block and all its resources
    def free(self):

        # make sure the block is not drawn
        self.changed = False

		# free shader and batch
        del self.shader, self.batch

		# free offscreens
        if self.offscreen_view: self.offscreen_view.free()
        if self.offscreen_canvas: self.offscreen_canvas.free()


# Class for rendering a Looking Glass Block in Blenders 3D viewport for live preview
class BlockRenderer:

    # ------------ KEYMAP OPERATOR FOR BLOCK RENDERER UPDATES -------------
    class LOOKINGGLASS_OT_update_block_renderer(bpy.types.Operator):
        """ This operator updates the block renderer"""
        bl_idname = "wm.update_block_renderer"
        bl_label = "Alice/LG: Block Renderer Update"

        def invoke(self, context, event):

            if (context is None) or (event is None) or (not context is None and context.area is None) or not hasattr(context.scene, "addon_settings"):
                return {'PASS_THROUGH'}

            # if the block preview is not active
            if context.space_data.type == "VIEW_3D" and not context.scene.addon_settings.viewport_block_show:
                return {'PASS_THROUGH'}

            # if the block preview is not active
            if context.space_data.type == 'IMAGE_EDITOR' and not context.scene.addon_settings.imageeditor_block_show:
                return {'PASS_THROUGH'}

            # mouse position in window
            LookingGlassAddon.mouse_window_x = event.mouse_x
            LookingGlassAddon.mouse_window_y = event.mouse_y

            # if the mouse is not in this area
            if not ((LookingGlassAddon.mouse_window_x >= context.area.x and LookingGlassAddon.mouse_window_x <= context.area.x + context.area.width) and (LookingGlassAddon.mouse_window_y >= context.area.y and LookingGlassAddon.mouse_window_y <= context.area.y + context.area.height)):
                return {'PASS_THROUGH'}

            # mouse position in current context region
            LookingGlassAddon.mouse_region_x = event.mouse_x - context.region.x
            LookingGlassAddon.mouse_region_y = event.mouse_y - context.region.y

            # for 3D viewports
            if context.space_data.type == "VIEW_3D":

                # if the settings are to be taken from device selection AND a device is active
                if context.scene.addon_settings.render_use_device == True and pylio.DeviceManager.get_active() is not None:

                    # currently selected device
                    device = pylio.DeviceManager.get_active()

                else:

                    # make the emulated device the active device, if one was found
                    device = pylio.DeviceManager.get_device(key='index', value=int(context.scene.addon_settings.render_device_type))

                # get the viewport block
                block = LookingGlassAddon.ViewportBlockRenderer.get_viewport_block()
                if block and device:

                    # infer the current view
                    if context.region.type != 'HEADER' and block.is_mouse_over(context):

                        # for left positioned blocks
                        if context.scene.addon_settings.viewport_block_alignment == 'left':
                            # calculate the view number and angle
                            view = floor(block.qs[block.preset]["total_views"] * (1 - (LookingGlassAddon.mouse_region_x - block.x) / block.width))
                            angle = -floor(device.viewCone * ((LookingGlassAddon.mouse_region_x - block.x) / block.width - 0.5))

                        # for right positioned blocks
                        elif context.scene.addon_settings.viewport_block_alignment == 'right':

                            # calculate the view number and angle
                            view = floor(block.qs[block.preset]["total_views"] * (1 - (LookingGlassAddon.mouse_region_x - (context.area.width - block.width - block.x)) / block.width))
                            angle = -floor(device.viewCone * ((LookingGlassAddon.mouse_region_x - (context.area.width - block.width - block.x - 50)) / block.width - 0.5))

                        # update state variables
                        block.set_active(True)
                        block.set_device(device)
                        block.set_view(view)
                        block.set_angle(angle)

                        # redraw region
                        context.area.tag_redraw()

                        return {'PASS_THROUGH'}

            # for Image Editors
            elif context.space_data.type == "IMAGE_EDITOR":

                # get the selected device
                device = pylio.DeviceManager.get_device(key='index', value=int(context.scene.addon_settings.imageeditor_block_device_type))

                # get the image
                image = context.space_data.image

                # get the image editor block
                block = LookingGlassAddon.ImageBlockRenderer.get_imageeditor_block()
                if block and device and image:

                    # get image name
                    image_name = image.name
                    preset, quilt_format = LookingGlassAddon.ImageBlockRenderer.detect_from_quilt_suffix(context, image_name)
                    if preset:

                        # set the preset
                        block.set_preset(preset)

                        # update dimensions
                        block.set_dimensions(int(device.width * context.space_data.zoom[0]), int(device.height * context.space_data.zoom[1]))

                        # infer the current view
                        if context.region.type != 'HEADER' and block.is_mouse_over(context):

                            # calculate the view number and angle
                            view = floor(block.qs[preset]["total_views"] * (1 - (LookingGlassAddon.mouse_region_x - block.x) / block.width))
                            angle = -floor(device.viewCone * ((LookingGlassAddon.mouse_region_x - block.x) / block.width - 0.5))

                            # update state variables
                            block.set_device(device)
                            block.set_view(view)
                            block.set_angle(angle)

                            # redraw region
                            context.area.tag_redraw()

                            return {'PASS_THROUGH'}

            # otherwise show centered view as default
            if block and device and block.preset:

                # if the mouse is outside the area use the center view
                view = floor(block.qs[block.preset]["total_views"] / 2)
                angle = floor(0)

                # update state variables
                block.set_active(False)
                block.set_device(device)
                block.set_view(view)
                block.set_angle(angle)

                # redraw region
                context.area.tag_redraw()

            return {'PASS_THROUGH'}



    # ------------ BLOCK RENDERER -------------
    # Inititalize the block renderer
    def __init__(self):

	    # renderer type and state
	    self.__type = None
	    self.__is_running = False

	    # drawing handlers
	    self.__block_draw_view_view3d_handler = None
	    self.__block_draw_block_view3d_handler = None
	    self.__block_depsgraph_handler = None
	    self.__block_frame_change_handler = None
	    self.__block_draw_view_imageeditor_handler = None
	    self.__block_draw_block_imageeditor_handler = None
	    self.__block_imageeditor_autodetected = False

	    # private class properties
	    self.__blocks = {}
	    self.__last_id = 0

	    # active blocks
	    self.__viewport3d_block = None
	    self.__imageeditor_block = None

	    # active presets
	    self.__viewport3d_preset = 0
	    self.__imageeditor_preset = 0

	    # context override
	    self.__override = None



    # deinititalize the block renderer
    def __del__(self):

		# if this is for the viewport
        if self.__type == 'VIEW_3D':

	        # remove the draw handlers
	        if self.__block_draw_view_view3d_handler:
	            bpy.types.SpaceView3D.draw_handler_remove(self.__block_draw_view_view3d_handler, 'WINDOW')
	            self.__block_draw_view_view3d_handler = None

	        if self.__block_draw_block_view3d_handler:
	            bpy.types.SpaceView3D.draw_handler_remove(self.__block_draw_block_view3d_handler, 'WINDOW')
	            self.__block_draw_block_view3d_handler = None

		# if this is for the viewport
        if self.__type == 'IMAGE_EDITOR':

	        # remove the draw handlers
	        if self.__block_draw_view_imageeditor_handler:
	            bpy.types.SpaceImageEditor.draw_handler_remove(self.__block_draw_view_imageeditor_handler, 'WINDOW')
	            self.__block_draw_view_imageeditor_handler = None

	        if self.__block_draw_block_imageeditor_handler:
	            bpy.types.SpaceImageEditor.draw_handler_remove(self.__block_draw_block_imageeditor_handler, 'WINDOW')
	            self.__block_draw_block_imageeditor_handler = None

        # free all blocks
        for id, block in self.__blocks.items():
            block.free()



    # status of the block renderer
    def is_running(self):
        return self.__is_running



    # start the block renderer
    def start(self, context):

        # if the renderer is NOT running
        if not self.is_running():

			# renderer type
            self.__type = context.space_data.type

            # create a context override
            self.__override = ContextOverride(context)

			# if this is for the viewport
            if self.__type == 'VIEW_3D':

	            # setup the viewport block
	            self.add_block(0, 10, 10, 420, 560)
	            self.set_viewport_block(0)

	            # add depsgraph update handler to react to scene changes
	            self.__block_depsgraph_handler = bpy.app.handlers.depsgraph_update_post.append(self.__depsgraph_changes)

	            # add update handler to react to frame changes
	            self.__block_frame_change_handler = bpy.app.handlers.frame_change_post.append(self.__depsgraph_changes)

	            # add draw handler to display the frustum of the Looking Glass camera
	            # after everything else has been drawn in the view
	            self.__block_draw_view_view3d_handler = bpy.types.SpaceView3D.draw_handler_add(self.__viewport_render_view, (context,), 'WINDOW', 'POST_PIXEL')
	            self.__block_draw_block_view3d_handler = bpy.types.SpaceView3D.draw_handler_add(self.__viewport_render_block, (context,), 'WINDOW', 'POST_PIXEL')

			# if this is for the viewport
            if self.__type == 'IMAGE_EDITOR':

	            # setup the image editor block
	            self.add_block(0, 0, 0, 420, 560)
	            self.set_imageeditor_block(0)

	            # add draw handler to display the frustum of the Looking Glass camera
	            # after everything else has been drawn in the view
	            self.__block_draw_view_imageeditor_handler = bpy.types.SpaceImageEditor.draw_handler_add(self.__imageeditor_render_view, (context,), 'WINDOW', 'PRE_VIEW')
	            self.__block_draw_block_imageeditor_handler = bpy.types.SpaceImageEditor.draw_handler_add(self.__imageeditor_render_block, (context,), 'WINDOW', 'POST_PIXEL')

            # update status
            self.__is_running = True

            # log info
            LookingGlassAddonLogger.info("Block preview started.")

        # keep the modal operator running
        return (self.__block_draw_block_view3d_handler, self.__block_draw_view_imageeditor_handler, self.__block_draw_block_imageeditor_handler)

    # stop the block renderer
    def stop(self):

        # if the renderer is running
        if self.is_running():

            # free all blocks
            for id, block in self.__blocks.items():
                block.free()

			# if this is for the viewport
            if self.__type == 'VIEW_3D':

	            # remove the draw handlers
	            if self.__block_draw_view_view3d_handler:
	                bpy.types.SpaceView3D.draw_handler_remove(self.__block_draw_view_view3d_handler, 'WINDOW')
	                self.__block_draw_view_view3d_handler = None

	            # remove the draw handlers
	            if self.__block_draw_block_view3d_handler:
	                bpy.types.SpaceView3D.draw_handler_remove(self.__block_draw_block_view3d_handler, 'WINDOW')
	                self.__block_draw_block_view3d_handler = None

			# if this is for the viewport
            if self.__type == 'IMAGE_EDITOR':

	            if self.__block_draw_view_imageeditor_handler:
	                bpy.types.SpaceImageEditor.draw_handler_remove(self.__block_draw_view_imageeditor_handler, 'WINDOW')
	                self.__block_draw_view_imageeditor_handler = None

	            if self.__block_draw_block_imageeditor_handler:
	                bpy.types.SpaceImageEditor.draw_handler_remove(self.__block_draw_block_imageeditor_handler, 'WINDOW')
	                self.__block_draw_block_imageeditor_handler = None

            # update status
            self.__is_running = False

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

		# get the block
        block = self.get_viewport_block()

        # if the settings are to be taken from device selection AND a device is active
        if bpy.context.scene.addon_settings.render_use_device == True and pylio.DeviceManager.get_active() is not None:

            # currently selected device
            block.set_device(pylio.DeviceManager.get_active())

            # set selected preset for this block
            block.set_preset(int(bpy.context.scene.addon_settings.quiltPreset))

        else:

            # set the selected emulated device as device for this block
            block.set_device(pylio.DeviceManager.get_device(key='index', value=int(bpy.context.scene.addon_settings.render_device_type)))

            # set selected preset for this block
            block.set_preset(int(bpy.context.scene.addon_settings.render_quilt_preset))

    # get the block to be rendered in the Blender viewport
    def get_viewport_block(self):
        if not self.__viewport3d_block is None:
            return self.__blocks[self.__viewport3d_block]

    # set the block to be rendered in the image editor
    def set_imageeditor_block(self, id):

        # set the active IMAGE_EDITOR block
        self.__imageeditor_block = id

        # if the settings are to be taken from device selection AND a device is active
        if bpy.context.scene.addon_settings.render_use_device == True and pylio.DeviceManager.get_active() is not None:

            # currently selected device
            self.__blocks[self.__imageeditor_block].set_device(pylio.DeviceManager.get_active())

        else:

            # set the selected emulated device as device for this block
            self.__blocks[self.__imageeditor_block].set_device(pylio.DeviceManager.get_device(key='index', value=int(bpy.context.scene.addon_settings.render_device_type)))

    # get the block to be rendered in the image editor
    def get_imageeditor_block(self):
        if not self.__imageeditor_block is None:
            return self.__blocks[self.__imageeditor_block]

    # check if the quilt and device format for the image editor have been
    # automatically detected
    def is_imageeditor_detected(self):
        if not self.__imageeditor_block is None:
            return self.__block_imageeditor_autodetected


    # Application handler that continously checks for changes of the depsgraph
    def __depsgraph_changes(self, scene, depsgraph):

        # if the block renderer is actively rendering
        if scene.addon_settings.viewport_block_show:

            # if something in the scene has changed
            if len(depsgraph.updates.values()) > 0:

                # select current viewport block
                block = self.get_viewport_block()
                if block is None or block.preset is None or block.offscreen_view is None:
                    return

                # update the blocks status variable
                block.changed = True


    # render the view for the block
    def __viewport_render_view(self, context):

        # if a camera is selected AND the space is not in camera mode AND
        # the block viewport preview shall be drawn
        if self and context:
            if hasattr(context.scene, "addon_settings") and context.scene.addon_settings.lookingglassCamera in [obj for obj in context.view_layer.objects] and context.scene.addon_settings.viewport_block_show:
                if (context.space_data != None):

                    # if the cycles render engine is active in this viewport
                    if context.space_data.shading.type == 'RENDERED' and context.engine == 'CYCLES':
                        return

                    # select correct block
                    block = self.get_viewport_block()
                    if block is None or block.preset is None or block.offscreen_view is None:
                        return

                    # currently selected device
                    device = block.device

                    # if the device exists
                    if device:

                        # update dimensions
                        if device.aspect < 1: block.set_dimensions(int(sqrt(context.area.width * context.area.height) * context.scene.addon_settings.viewport_block_scaling_factor * device.aspect), int(sqrt(context.area.width * context.area.height) * context.scene.addon_settings.viewport_block_scaling_factor))
                        if device.aspect >= 1: block.set_dimensions(int(sqrt(context.area.width * context.area.height) * context.scene.addon_settings.viewport_block_scaling_factor), int(sqrt(context.area.width * context.area.height) * context.scene.addon_settings.viewport_block_scaling_factor / device.aspect))

                    # if the block changed
                    if block.has_changed(context):

                        # select camera that belongs to the view
                        camera = context.scene.addon_settings.lookingglassCamera

                        # PREPARE THE MODELVIEW AND PROJECTION MATRICES
                        # if a camera is selected
                        if camera != None:

                            # copy context
                            context_copy = context.copy()

                            # set the context for the override
                            self.__override.set_context(context)

                            # update all viewport shading and overlay settings
                            self.__override.updateViewportSettings(context_copy['space_data'], force_context_data=True)

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
                                view_matrix, projection_matrix = self.__override.setupVirtualCameraForView(block.view, block.qs[block.preset]["total_views"], block.view_cone, block.aspect, camera_view_matrix.copy(), camera_projection_matrix.copy())

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
                        self.__override.restoreViewportSettings()

                        # reset status variable
                        block.changed = False



    # render the block into the viewport
    def __viewport_render_block(self, context):

        # if a camera is selected AND the space is not in camera mode AND
        # the block viewport preview shall be drawn
        if self and context:
            if hasattr(context.scene, "addon_settings") and context.scene.addon_settings.lookingglassCamera in [obj for obj in context.view_layer.objects] and context.scene.addon_settings.viewport_block_show:
                if (context.space_data != None):

                    # if the cycles render engine is active in this viewport
                    if context.space_data.shading.type == 'RENDERED' and context.engine == 'CYCLES':
                        return

                    # select correct block
                    block = self.get_viewport_block()
                    if block is None or block.preset is None or block.offscreen_view is None:
                        return

                    # update the block
                    block.update(context)

                    #gpu.state.depth_test_set('LESS_EQUAL')
                    gpu.state.depth_mask_set(True)
                    gpu.state.blend_set('ALPHA')

                    # if the block is drawn in a SpaceView3D
                    if context.space_data.type == 'VIEW_3D' and context.space_data.region_3d != None:

                        if context.scene.addon_settings.viewport_block_alignment == 'left': draw_texture_2d(block.offscreen_canvas.texture_color, (block.x, block.y), block.width, block.height)
                        if context.scene.addon_settings.viewport_block_alignment == 'right': draw_texture_2d(block.offscreen_canvas.texture_color, (context.area.width - block.width - block.x - 50, block.y), block.width, block.height)

                    gpu.state.depth_mask_set(False)
                    gpu.state.blend_set('NONE')
                    #print("blend_set")


    def detect_from_quilt_suffix(self, context, quilt_name):
        import re

        # select correct block
        block = self.get_imageeditor_block()

        # values from the metadata
        columns = None
        rows = None
        aspect = None

        # if a quilt name was given
        if quilt_name:

            # try to extract some metadata information from the quiltname
            try:

                columns = int(re.search('_qs(\d+)x(\d+)a(\d+.?\d*)', quilt_name).group(1))
                rows = int(re.search('_qs(\d+)x(\d+)a(\d+.?\d*)', quilt_name).group(2))
                aspect = float(re.search('_qs(\d+)x(\d+)a(\d+.?\d*)', quilt_name).group(3))

            except AttributeError:

                try:

                    columns = int(re.search('_qs(\d+)x(\d+).', quilt_name).group(1))
                    rows = int(re.search('_qs(\d+)x(\d+).', quilt_name).group(2))

                except AttributeError:

                    pass

            # for each supported quilt format
            for preset, qf in pylio.LookingGlassQuilt.formats.get().items():

                # if the quilt
                if not (columns is None or rows is None or aspect is None) and columns == qf['columns'] and rows == qf['rows']:

					# update status variable
                    self.__block_imageeditor_autodetected = True

					# update UI
                    if context.scene.addon_settings.imageeditor_block_quilt_preset != str(preset):
                        context.scene.addon_settings.imageeditor_block_quilt_preset = str(preset)

                    return preset, qf

		# return preset and format from the settings
        self.__block_imageeditor_autodetected = False
        return int(context.scene.addon_settings.imageeditor_block_quilt_preset), block.qs[int(context.scene.addon_settings.imageeditor_block_quilt_preset)]


    # render the view into the offscreen
    def __imageeditor_render_view(self, context):

        # if a camera is selected AND the space is not in camera mode
        if self and context:
            if hasattr(context.scene, "addon_settings"):
                if (context.space_data != None and context.space_data.type == 'IMAGE_EDITOR'):

                    # get the image loaded in the image editor
                    image = context.space_data.image
                    if not image is None and image.type != "RENDER_RESULT":

	    	            # select correct block
                        block = self.get_imageeditor_block()

                        # get the selected device
                        device = pylio.DeviceManager.get_device(key='index', value=int(context.scene.addon_settings.imageeditor_block_device_type))

                        # get quilt preset and format parameters
                        preset, quilt_format = self.detect_from_quilt_suffix(context, image.name)
                        if quilt_format:

	                        # update dimensions
	                        block.set_dimensions(int(device.width * context.space_data.zoom[0]), int(device.height * context.space_data.zoom[1]))

						# if the block mode is activated
                        if context.scene.addon_settings.imageeditor_block_show:

	                        # if the block changed
	                        if block.changed and block.offscreen_view:

	                            # create a texture from the image
	                            #if not block.image_texture:
	                            block.image_texture = gpu.texture.from_image(image)

	                            # if the texture was created
	                            if block.image_texture:

	                                # calculate view grid indices in the quilt
	                                view_ix = block.view % block.qs[block.preset]['columns']
	                                view_iy = floor(block.view / block.qs[block.preset]['columns'])

	                                # RENDER THE VIEW
	                                # ++++++++++++++++++++++++++++++++++++++++++++++++
	                                with block.offscreen_view.bind():

	                                    # get the current projection matrix
	                                    viewMatrix = gpu.matrix.get_model_view_matrix()
	                                    projectionMatrix = gpu.matrix.get_projection_matrix()

	                                    with gpu.matrix.push_pop():

	                                        # reset matrices -> use normalized device coordinates [-1, 1]
	                                        gpu.matrix.load_matrix(Matrix.Identity(4))
	                                        gpu.matrix.load_projection_matrix(Matrix.Identity(4))

	                                        gpu.state.depth_test_set('GREATER_EQUAL')
	                                        gpu.state.depth_mask_set(True)
	                                        gpu.state.blend_set('ALPHA')

	                                        # draw the viewport rendering to the offscreen for the current view
	                                        draw_texture_2d(block.image_texture, (-1 - 2 * view_ix, -1 - 2 * view_iy), 2 * block.qs[block.preset]['columns'], 2 * block.qs[block.preset]['rows'])

	                                        gpu.state.blend_set('NONE')
	                                        gpu.state.depth_mask_set(False)
	                                        gpu.state.depth_test_set('NONE')

	                                        # reload original matrices
	                                        gpu.matrix.load_matrix(viewMatrix)
	                                        gpu.matrix.load_projection_matrix(projectionMatrix)

	                            # reset status variable
	                            block.changed = False

						        # update the block
	                            block.update(context)

	                        # convert view2d coordinates of the image center to
	                        # region corrdinates
	                        view_2d_x, view_2d_y = context.region.view2d.view_to_region(0.5, 0.5)

	                        # center the block
	                        block.x = view_2d_x - block.width / 2
	                        block.y = view_2d_y - block.height / 2

    # render the block into the image editor
    def __imageeditor_render_block(self, context):

        # if a camera is selected AND the space is not in camera mode
        if self and context:
	        if hasattr(context.scene, "addon_settings") and context.scene.addon_settings.imageeditor_block_show:
	        	if not context.space_data is None:

	        		# get the image loaded in the image editor
	        		image = context.space_data.image
	        		if not image is None and image.type != "RENDER_RESULT":

	        			# select correct block
	        			block = self.get_imageeditor_block()
	        			if block:

							# get active frame buffer
					        framebuffer = gpu.state.active_framebuffer_get()
					        with framebuffer.bind():

						        # clear the framebuffer
						        c = context.preferences.themes[0].image_editor.grid
						        framebuffer.clear(color=(c[0] * 0.15, c[1] * 0.15, c[2] * 0.15, c[3]))

						        gpu.state.depth_test_set('GREATER_EQUAL')
						        gpu.state.depth_mask_set(True)
						        gpu.state.blend_set('ALPHA')

		                        # draw the block
						        draw_texture_2d(block.offscreen_canvas.texture_color, (block.x, block.y), block.width, block.height)

						        gpu.state.blend_set('NONE')
						        gpu.state.depth_mask_set(False)
						        gpu.state.depth_test_set('NONE')
