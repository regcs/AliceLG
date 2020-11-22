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

import bpy
import time
import os, sys
import numpy as np
from math import *
from mathutils import *
from bpy.types import AddonPreferences, PropertyGroup
from bpy.props import FloatProperty, PointerProperty

# TODO: Is there a better way to share global variables between all addon files and operators?
from .looking_glass_global_variables import *


# ------------ QUILT RENDERING -------------
# Modal operator for handling rendering of a quilt out of Blender
class LOOKINGGLASS_OT_render_quilt(bpy.types.Operator):

	bl_idname = "render.quilt"
	bl_label = "Render a quilt using the current scene and active camera."
	bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

	# override context for operator calls in the app handlers
	override = None

	# filepath
	render_setting_filepath = None

	# render settings
	render_setting_original_width = None
	render_setting_original_height = None
	render_setting_original_aspect_x = None
	render_setting_original_aspect_y = None
	render_setting_scene = None

	# render variables
	rendering_status = None		# rendering status
	rendering_cancelled = None	# was render cancelled by user
	rendering_frame = 1	    	# the frame that is currently rendered
	rendering_subframe = 0.0	# the subframe that is currently rendered
	rendering_view = 0	  		# the view of the frame that is currently rendered

	rendering_viewWidth = 819	# rendering width of the view
	rendering_viewHeight = 455	# rendering height of the view
	rendering_aspectRatio = 1.0	# aspect ratio of the view

	# camera settings
	camera_active = None
	camera_original_location = None
	camera_original_shift_x = None
	camera_original_sensor_fit = None

	# Blender images
	viewImagesPixels = []
	viewImagePixels = []

	# event and app handler ids
	_handle_event_timer = None	# modal timer event

	# callback functions:
	# TODO: find out, what the second parameter is, that the handler expects (in first test it was always None)
	# function that is called when the renderjob is initialized
	def init_render(self, Scene, unknown_param):

		print("[INFO] Rendering job initialized.")

		# set the rendering frame variable to the first frame
		self.rendering_frame = Scene.frame_start

		# remember active camera as well as its original location and shift value
		self.camera_active = Scene.camera

	# function that is called when the renderjob is completed
	def completed_render(self, Scene, unknown_param):

		# cancel the operator - this includes recovering the original camera settings
		self.cancel(bpy.context)


	# function that is called before rendering starts
	def pre_render(self, Scene, unknown_param):

		# FRAME AND VIEW
		# ++++++++++++++++++++++

		# set the current frame to be rendered
		Scene.frame_set(self.rendering_frame, subframe=self.rendering_subframe)

		# get the subframe, that will be rendered
		self.rendering_subframe = Scene.frame_subframe

		# set the filepath so that the filename adheres to:
		# filepath + "_view_XX_YYYY"
		Scene.render.frame_path(frame=self.rendering_frame)



		# CAMERA SETTINGS: GET VIEW & PROJECTION MATRICES
		# +++++++++++++++++++++++++++++++++++++++++++++++

		# if this is the first view of the current frame
		# NOTE: - we do it this way in case the camera is animated and its position changes each frame
		if self.rendering_view == 0:

			# remember current camera settings
			self.camera_original_location = self.camera_active.location.copy()
			self.camera_original_shift_x = self.camera_active.data.shift_x
			self.camera_original_sensor_fit = self.camera_active.data.sensor_fit

		# set sensor fit to Vertical
		#self.camera_active.data.sensor_fit = 'VERTICAL'

		# get camera's modelview matrix
		view_matrix = self.camera_active.matrix_world.copy()

		# correct for the camera scaling
		view_matrix = view_matrix @ Matrix.Scale(1/self.camera_active.scale.x, 4, (1, 0, 0))
		view_matrix = view_matrix @ Matrix.Scale(1/self.camera_active.scale.y, 4, (0, 1, 0))
		view_matrix = view_matrix @ Matrix.Scale(1/self.camera_active.scale.z, 4, (0, 0, 1))

		# calculate the inverted view matrix because this is what the draw_view_3D function requires
		view_matrix_inv = view_matrix.inverted()

		# # get the camera's projection matrix
		# projection_matrix = self.camera_active.calc_matrix_camera(
		# 		bpy.context.view_layer.depsgraph,
		# 		x = self.render_setting_scene.render.resolution_x,
		# 		y = self.render_setting_scene.render.resolution_y,
		# 		scale_x = self.render_setting_scene.render.pixel_aspect_x,
		# 		scale_y = self.render_setting_scene.render.pixel_aspect_y,
		# 	)


		# CAMERA SETTINGS: APPLY POSITION AND SHIFT
		# +++++++++++++++++++++++++++++++++++++++++++++++
		# adjust the camera settings to the correct view point
		# The field of view set by the camera
		# NOTE 1: - the Looking Glass Factory documentation suggests to use a FOV of 14°. We use the focal length of the Blender camera instead.
		fov = self.camera_active.data.angle

		# calculate cameraSize from its distance to the focal plane and the FOV
		# NOTE: - we take an arbitrary distance of 5 m (we could also use the focal distance of the camera, but might be confusing)
		cameraDistance = self.window_manager.focalPlane#self.camera_active.data.dof.focus_distance
		cameraSize = cameraDistance * tan(fov / 2)

		# start at viewCone * 0.5 and go up to -viewCone * 0.5
		# TODO: The Looking Glass Factory dicumentation suggests to use a viewcone of 35°, but the device calibration has 40° by default.
		#		Which one should we take?
		offsetAngle = (0.5 - self.rendering_view / (45 - 1)) * radians(self.device_current['viewCone'])

		# calculate the offset that the camera should move
		offset = cameraDistance * tan(offsetAngle)

		# translate the camera by the calculated offset in x-direction
		# NOTE: the matrix multiplications first transform the camera location into camera coordinates,
		#		then we apply the offset and transform back to the normal world coordinates
		self.camera_active.location = view_matrix @ (Matrix.Translation((-offset, 0, 0)) @ (view_matrix_inv @ self.camera_original_location))

		# modify the projection matrix, relative to the camera size.
		# NOTE: - we need to take into account the view aspect ratio and the pixel aspect ratio
		self.camera_active.data.shift_x = self.camera_original_shift_x + offset / (cameraSize * self.rendering_viewWidth / self.rendering_viewHeight * self.render_setting_scene.render.pixel_aspect_x * self.render_setting_scene.render.pixel_aspect_y)



		# set status variable:
		# notify the modal operator that a rendering task is started
		self.rendering_status = True

		# output current status
		print(" # active camera: ", self.camera_active)
		print(" # current frame: ", self.rendering_frame)
		print(" # current subframe: ", self.rendering_subframe)
		print(" # current view: ", self.rendering_view)

	# function that is called after rendering finished
	def post_render(self, Scene, unknown_param):

		print("[INFO] View ", self.rendering_view, " rendered.")
		print(" # file was saved to: ", Scene.render.filepath)

		# MAKE A QUILT IMAGE OUT OF THE RENDERED VIEWS
		# ++++++++++++++++++++++++++++++++++++++++++++
		# append the loaded image to the list
		viewImage = bpy.data.images.load(filepath=self.render_setting_scene.render.frame_path(frame=self.rendering_frame))

		# store the pixel data in an numpy array
		self.viewImagesPixels.append(np.array(viewImage.pixels[:]).copy())

		# delete the Blender image
		bpy.data.images.remove(viewImage)

		# if this was the last view of the frame_set
		if self.rendering_view == 44:

			# # SIMPLE EXAMPLE
			# import bpy
			# import numpy as np
			#
			# a = range(1, 17)
			# b = range(17, 33)
			# c = range(33, 49)
			# d = range(49, 65)
			#
			# viewImagesPixels = [a, b, c, d]
			#
			# verticalStack = []
			# horizontalStack = []
			# for row in range(0, 2, 1):
			#     for column in range(0, 2, 1):
			#
			#
			#         # get pixel data and reshape into a reasonable format for stacking
			#         viewPixels = np.array(viewImagesPixels[row * 2 + column], copy=False)
			#         viewPixels = viewPixels.reshape((2, 2, 4))
			#
			#         # append the pixel data to the current horizontal stack
			#         horizontalStack.append([viewPixels])
			#
			#     #
			#     #print(horizontalStack)
			#
			#     # append the complete horizontal stack to the vertical stacks
			#     verticalStack.append([horizontalStack.copy()])
			#
			#     # clear this rows
			#     horizontalStack.clear()
			#
			# print(verticalStack)
			#
			# pixels = np.block(verticalStack)
			# pixels = pixels.reshape((1 * 2 * 2 * 2 * 2 * 4))
			# print(pixels)


			# MAKE A SINGLE QUILT IMAGE
			# ++++++++++++++++++++++++++++++++++++++++++++
			verticalStack = []
			horizontalStack = []
			for row in range(0, 9, 1):
				for column in range(0, 5, 1):

					# get pixel data and reshape into a reasonable format for stacking
					viewPixels = self.viewImagesPixels[row * 5 + column]
					viewPixels = viewPixels.reshape((self.render_setting_scene.render.resolution_y, self.render_setting_scene.render.resolution_x, 4))

					# append the pixel data to the current horizontal stack
					horizontalStack.append(viewPixels)

				# append the complete horizontal stack to the vertical stacks
				verticalStack.append(np.hstack(horizontalStack.copy()))

				# clear this horizontal stack
				horizontalStack.clear()

			# reshape the pixel data of all images into the quilt shape
			quiltPixels = np.vstack(verticalStack.copy())
			quiltPixels = np.reshape(quiltPixels, (5 * 9 * (self.render_setting_scene.render.resolution_x * self.render_setting_scene.render.resolution_y * 4)))

			# create a Blender image with the obtained pixeö data
			quiltImage = bpy.data.images.new("quilt_frame_" + str(self.rendering_frame).zfill(4), self.render_setting_scene.render.resolution_x * 5, self.render_setting_scene.render.resolution_y * 9)
			quiltImage.pixels = quiltPixels




			# PREPARE RENDERING OF THE NEXT FRAME
			# ++++++++++++++++++++++++++++++++++++++++++++

			# reset the rendering view variable
			self.rendering_view = 0

			# go to the next frame
			self.rendering_frame = Scene.frame_current + 1

			# restore original camera settings of this frame
			self.camera_active.location = self.camera_original_location
			self.camera_active.data.shift_x = self.camera_original_shift_x
			self.camera_active.data.sensor_fit = self.camera_original_sensor_fit

		else:

			# only update the rendering view and stay in the current frame
			self.rendering_view += 1

		# set status variable:
		# notify the modal operator that the rendering task is finished
		self.rendering_status = False

	# function that is called if rendering was cancelled
	def cancel_render(self, Scene, unknown_param):
		print("[INFO] Render cancelled", Scene)

		# cancel the operator - this includes recovering the original camera settings
		self.cancel(bpy.context)

		# set status variable to notify the modal operator that the user started a rendering task
		self.rendering_cancelled = True



	# inititalize the quilt rendering
	@classmethod
	def __init__(self):

		print("Initializing the quilt rendering operator ...")



	# clean up
	@classmethod
	def __del__(self):

		print("Stopped quilt rendering operator ...")




	# check if everything is correctly set up for the quilt rendering
	@classmethod
	def poll(self, context):

		print("POLLING: ", LookingGlassAddon.lightfieldWindow)

		# if the lightfield window exists
		if LookingGlassAddon.lightfieldWindow != None:

			# return True, so the operator is executed
			return True

		else:

			# return False, so the operator is NOT executed
			return False



	# cancel modal operator
	def cancel(self, context):

		# REMOVE APP HANDLERS
		# +++++++++++++++++++++++++
		# remove render app handlers
		bpy.app.handlers.render_init.remove(self.init_render)
		bpy.app.handlers.render_pre.remove(self.pre_render)
		bpy.app.handlers.render_post.remove(self.post_render)
		bpy.app.handlers.render_cancel.remove(self.cancel_render)
		bpy.app.handlers.render_complete.remove(self.completed_render)

		# remove event timer
		context.window_manager.event_timer_remove(self._handle_event_timer)


		# CLEAR PIXEL DATA
		# +++++++++++++++++++++++++
		self.viewImagesPixels.clear()


		# RESTORE USER SETTINGS
		# +++++++++++++++++++++++++
		# CAMERA
		# if a active camera exists
		if self.camera_active != None and self.camera_active.type == 'CAMERA':

			# restore original camera settings
			self.camera_active.location = self.camera_original_location
			self.camera_active.data.shift_x = self.camera_original_shift_x
			self.camera_active.data.sensor_fit = self.camera_original_sensor_fit


		# RENDER SETTINGS
		# restore original file path
		self.render_setting_scene.render.filepath = self.render_setting_filepath
		# restore image settings
		self.render_setting_scene.render.resolution_x = self.render_setting_original_width
		self.render_setting_scene.render.resolution_y = self.render_setting_original_height
		self.render_setting_scene.render.pixel_aspect_x = self.render_setting_original_aspect_x
		self.render_setting_scene.render.pixel_aspect_y = self.render_setting_original_aspect_y

		print("Everything is done.")

		# return None since this is expected by the operator
		return None



	# invoke the modal operator
	def invoke(self, context, event):

		# make an internal variable for the window_manager,
		# which can be accessed from methods that have no "context" parameter
		self.window_manager = context.window_manager

		# get the calibration data of the selected Looking Glass from the deviceList
		for device in LookingGlassAddon.deviceList:

			if device['index'] == int(self.window_manager.activeDisplay):

				# store the current device calibration data for later access
				self.device_current = device


		# RENDER SETTINGS
		################################################################

		# STORE ORIGINAL SETTINGS
		# ++++++++++++++++++++++++
		# we need to restore these at the end
		self.render_setting_original_width = context.scene.render.resolution_x
		self.render_setting_original_height = context.scene.render.resolution_y
		self.render_setting_original_aspect_x = context.scene.render.pixel_aspect_x
		self.render_setting_original_aspect_y = context.scene.render.pixel_aspect_y
		self.render_setting_scene = context.scene
		self.render_setting_filepath = context.scene.render.filepath


		# SET RENDER SETTINGS
		# ++++++++++++++++++++++++
		# apply aspect ratio of the Looking Glass
		self.rendering_aspectRatio = self.device_current['aspectRatio'] / (9 / 5)
		print("Calculated aspect ratio: ", self.device_current['aspectRatio'], self.rendering_aspectRatio)

		# TODO: set the correct aspect ratio
		self.render_setting_scene.render.resolution_x = self.rendering_viewWidth
		self.render_setting_scene.render.resolution_y = self.rendering_viewHeight

		if self.rendering_aspectRatio > 1:
			self.render_setting_scene.render.pixel_aspect_x = self.rendering_aspectRatio
			self.render_setting_scene.render.pixel_aspect_y = 1
		else:
			self.render_setting_scene.render.pixel_aspect_x = 1
			self.render_setting_scene.render.pixel_aspect_y = 1 / self.rendering_aspectRatio

		print("Applied aspect ratio: ", self.render_setting_scene.render.pixel_aspect_x, self.render_setting_scene.render.pixel_aspect_y)

		# file path
		self.render_setting_scene.render.filepath = self.render_setting_filepath + "_frame_####" + self.render_setting_scene.render.file_extension


		# REGISTER ALL HANDLERS FOR THE QUILT RENDERING
		################################################################
		# CREATE OVERRIDE CONTEXT
		# +++++++++++++++++++++++++++++++++++
		self.override = context.copy()

		# HANDLERS FOR THE RENDERING PROCESS
		# +++++++++++++++++++++++++++++++++++
		bpy.app.handlers.render_init.append(self.init_render)
		bpy.app.handlers.render_pre.append(self.pre_render)
		bpy.app.handlers.render_post.append(self.post_render)
		bpy.app.handlers.render_cancel.append(self.cancel_render)
		bpy.app.handlers.render_complete.append(self.completed_render)

		# HANDLER FOR EVENT TIMER
		# ++++++++++++++++++++++++++++++++++
		# Create timer event that runs every 100 ms to check the rendering process
		self._handle_event_timer = context.window_manager.event_timer_add(0.1, window=context.window)

		# START THE MODAL OPERATOR
		# ++++++++++++++++++++++++++++++++++
		# add the modal operator handler
		context.window_manager.modal_handler_add(self)

		print("Invoked modal operator")

		# start the rendering job
		#bpy.ops.render.render("INVOKE_DEFAULT", write_still=True)

		# keep the modal operator running
		return {'RUNNING_MODAL'}



	# modal operator for controlled redrawing of the lightfield
	def modal(self, context, event):

		# if the TIMER event for the quilt rendering is called
		if event.type == 'TIMER':

			# RENDER NEXT VIEW
			# ++++++++++++++++++++++++++++++++++

			# if nothing is rendering, but the last view is not yet rendered
			if self.rendering_status is False:

				# start the rendering process
				# bpy.ops.render.render("INVOKE_DEFAULT", write_still=True)
				print("Go on with next view!")




			# RENDERING IS FINISHED
			# ++++++++++++++++++++++++++++++++++

			# if all rendering is done
			elif self.rendering_status == True and self.rendering_view == 45:

				self.report({"INFO"},"QUILT RENDER FINISHED")
				return {"FINISHED"}




			# RENDERING WAS CANCELLED
			# ++++++++++++++++++++++++++++++++++
			elif self.rendering_status == True and self.rendering_cancelled == True:

				self.report({"INFO"},"QUILT RENDER CANCELLED")
				return {"CANCELLED"}

		# pass event through
		return {'PASS_THROUGH'}
