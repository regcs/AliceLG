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

	# event and app handler ids
	_handle_event_timer = None	# modal timer event

	# modal operator state
	operator_state: bpy.props.EnumProperty(
											items = [
													('IDLE', '', ''),
													('INIT_RENDER', '', ''),
													('PRE_RENDER', '', ''),
												 	('POST_RENDER', '', ''),
													('COMPLETE_RENDER', '', ''),
													('CANCEL_RENDER', '', '')
													],
											default='IDLE'
											)

	# callback functions:
	# NOTE: - we only use this callbacks to enter the correct state. The actual
	#		  is executed in the modal operator, because Blender doesn't allow
	# 		  object manipulation from application handlers.

	def init_render(self, Scene, unknown_param):

		# change the operator state
		self.operator_state = "INIT_RENDER"

		# since we need to know the scene through the job, we store it in an internal variable
		self.render_setting_scene = Scene

		# wait a few milliseconds until the operator processed the step
		while self.operator_state != "IDLE":
			time.sleep(0.001)
			print("[", self.operator_state, "] WAITING")

	# function that is called when the renderjob is completed
	def completed_render(self, Scene, unknown_param):

		# change the operator state
		self.operator_state = "COMPLETE_RENDER"

		# wait a few milliseconds until the operator processed the step
		while self.operator_state != "IDLE":
			time.sleep(0.001)
			print("[", self.operator_state, "] WAITING")

	# function that is called before rendering starts
	def pre_render(self, Scene, unknown_param):

		# change the operator state
		self.operator_state = "PRE_RENDER"

		# wait a few milliseconds until the operator processed the step
		while self.operator_state != "IDLE":
			time.sleep(0.001)
			print("[", self.operator_state, "] WAITING")

	# function that is called after rendering finished
	def post_render(self, Scene, unknown_param):

		# change the operator state
		self.operator_state = "POST_RENDER"

		# wait a few milliseconds until the operator processed the step
		while self.operator_state != "IDLE":
			time.sleep(0.001)
			print("[", self.operator_state, "] WAITING")

	# function that is called if rendering was cancelled
	def cancel_render(self, Scene, unknown_param):

		# change the operator state
		self.operator_state = "CANCEL_RENDER"

		# wait a few milliseconds until the operator processed the step
		while self.operator_state != "IDLE":
			time.sleep(0.001)
			print("[", self.operator_state, "] WAITING")




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
		# Create timer event that runs every 1 ms to check the rendering process
		self._handle_event_timer = context.window_manager.event_timer_add(0.001, window=context.window)

		# START THE MODAL OPERATOR
		# ++++++++++++++++++++++++++++++++++
		# add the modal operator handler
		context.window_manager.modal_handler_add(self)

		print("Invoked modal operator: ", self.operator_state)

		# start the rendering job
		#bpy.ops.render.render("INVOKE_DEFAULT", write_still=True)

		# keep the modal operator running
		return {'RUNNING_MODAL'}



	# modal operator for controlled redrawing of the lightfield
	def modal(self, context, event):

		# if the TIMER event for the quilt rendering is called
		if event.type == 'TIMER':

			# INIT STEP
			# ++++++++++++++++++++++++++++++++++
			if self.operator_state == "INIT_RENDER":

				print("[INFO] Rendering job initialized.")

				# set the rendering frame variable to the first frame
				self.rendering_frame = self.render_setting_scene.frame_start

				# remember active camera as well as its original location and shift value
				self.camera_active = self.render_setting_scene.camera


				# reset the operator state to IDLE
				self.operator_state = "IDLE"


			# PRE-RENDER STEP
			# ++++++++++++++++++++++++++++++++++

			# if nothing is rendering, but the last view is not yet rendered
			elif self.operator_state == "PRE_RENDER":

				print("[INFO] Rendering view is going to be prepared.")

				# FRAME AND VIEW
				# ++++++++++++++++++++++

				# set the current frame to be rendered
				self.render_setting_scene.frame_set(self.rendering_frame, subframe=self.rendering_subframe)

				# get the subframe, that will be rendered
				self.rendering_subframe = self.render_setting_scene.frame_subframe

				# set the filepath so that the filename adheres to:
				# filepath + "_view_XX_YYYY"
				self.render_setting_scene.render.frame_path(frame=self.rendering_frame)



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





				# output current status
				print(" # active camera: ", self.camera_active)
				print(" # current frame: ", self.rendering_frame)
				print(" # current subframe: ", self.rendering_subframe)
				print(" # current view: ", self.rendering_view)

				# reset the operator state to IDLE
				self.operator_state = "IDLE"



			# POST-RENDER STEP
			# ++++++++++++++++++++++++++++++++++

			# if nothing is rendering, but the last view is not yet rendered
			elif self.operator_state == "POST_RENDER":

				print("[INFO] View ", self.rendering_view, " rendered.")

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
					self.rendering_frame = self.render_setting_scene.frame_current + 1

					# restore original camera settings of this frame
					self.camera_active.location = self.camera_original_location
					self.camera_active.data.shift_x = self.camera_original_shift_x
					self.camera_active.data.sensor_fit = self.camera_original_sensor_fit

				else:

					# only update the rendering view and stay in the current frame
					self.rendering_view += 1

				# free the interface again
				self.render_setting_scene.render.use_lock_interface = False

				# reset the operator state to IDLE
				self.operator_state = "IDLE"



			# COMPLETE-RENDER STEP
			# ++++++++++++++++++++++++++++++++++

			# if nothing is rendering, but the last view is not yet rendered
			elif self.operator_state == "COMPLETE_RENDER":

				print("[INFO] Render job completed.")

				# cancel the operator
				# NOTE: - this includes recovering all original user settings
				self.cancel(bpy.context)

				# reset the operator state to IDLE
				self.operator_state = "IDLE"

				# notify user
				self.report({"INFO"},"Quilt sucessfully rendered.")
				return {"FINISHED"}



			# CANCEl-RENDER STEP
			# ++++++++++++++++++++++++++++++++++

			# if nothing is rendering, but the last view is not yet rendered
			elif self.operator_state == "CANCEL_RENDER":

				print("[INFO] Render job cancelled.")

				# cancel the operator
				# NOTE: - this includes recovering all original user settings
				self.cancel(bpy.context)

				# reset the operator state to IDLE
				self.operator_state = "IDLE"

				# notify user
				self.report({"INFO"},"Quilt rendering was cancelled.")
				return {"CANCELLED"}



		# pass event through
		return {'PASS_THROUGH'}
