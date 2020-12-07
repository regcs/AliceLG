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
import os
import numpy as np
from math import *
from mathutils import *

# TODO: Is there a better way to share global variables between all addon files and operators?
from .looking_glass_global_variables import *


# ------------ QUILT RENDERING -------------
# Modal operator for handling rendering of a quilt out of Blender
class LOOKINGGLASS_OT_render_quilt(bpy.types.Operator):

	bl_idname = "render.quilt"
	bl_label = "Render"
	bl_description = "Render a quilt (animation) using the current scene and active camera."
	bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

	# OPERATOR ARGUMENTS
	animation: bpy.props.BoolProperty(default = False)

	# OPERATOR STATE
	# this is used for handling different rendering steps
	operator_state: bpy.props.EnumProperty(items = [
													('INVOKE_RENDER', '', ''),
													('INIT_RENDER', '', ''),
													('PRE_RENDER', '', ''),
												 	('POST_RENDER', '', ''),
													('COMPLETE_RENDER', '', ''),
													('CANCEL_RENDER', '', ''),
													('IDLE', '', '')
													],
											default='INVOKE_RENDER'
											)


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

	rendering_viewWidth = None	# rendering width of the view
	rendering_viewHeight = None	# rendering height of the view
	rendering_rows = None	# rendering width of the view
	rendering_columns = None	# rendering height of the view
	rendering_totalViews = None	# rendering height of the view
	rendering_aspectRatio = 1.0	# aspect ratio of the view
	rendering_filepath = None	# aspect ratio of the view

	# camera settings
	camera_active = None
	camera_original_location = None
	camera_original_shift_x = None
	camera_original_sensor_fit = None

	# Blender images
	viewImagesPixels = []

	# event and app handler ids
	_handle_event_timer = None	# modal timer event


	# callback functions:
	# NOTE: - we only use this callbacks to enter the correct state. The actual
	#		  is executed in the modal operator, because Blender doesn't allow
	# 		  object manipulation from application handlers.

	def init_render(self, Scene, unknown_param):

		# reset the operator state to IDLE
		self.operator_state = "INIT_RENDER"

		# since we need to know the scene through the job, we store it in an internal variable
		self.render_setting_scene = Scene

		# wait a few milliseconds until the operator processed the step
		while self.operator_state != "IDLE" and self.operator_state != "CANCEL_RENDER":
			time.sleep(0.001)
			#print("[", self.operator_state, "] WAITING")

	# function that is called before rendering starts
	def pre_render(self, Scene, unknown_param):

		# reset the operator state to PRE_RENDER
		self.operator_state = "PRE_RENDER"

		# wait a few milliseconds until the operator processed the step
		while self.operator_state != "IDLE" and self.operator_state != "CANCEL_RENDER":
			time.sleep(0.001)
			#print("[", self.operator_state, "] WAITING")

	# function that is called after rendering finished
	def post_render(self, Scene, unknown_param):

		# reset the operator state to PRE_RENDER
		self.operator_state = "POST_RENDER"

		# wait a few milliseconds until the operator processed the step
		while self.operator_state != "IDLE" and self.operator_state != "CANCEL_RENDER":
			time.sleep(0.001)
			#print("[", self.operator_state, "] WAITING")

	# function that is called when the renderjob is completed
	def completed_render(self, Scene, unknown_param):

		# reset the operator state to COMPLETE_RENDER
		self.operator_state = "COMPLETE_RENDER"

		print("######################################")
		# # wait a few milliseconds until the operator processed the step
		# while self.operator_state != "INVOKE_RENDER" and self.operator_state != "IDLE":
		# 	time.sleep(0.001)
		# 	print("[", self.operator_state, "] WAITING")

	# function that is called if rendering was cancelled
	def cancel_render(self, Scene, unknown_param):

		# set operator state to CANCEL
		self.operator_state = "CANCEL_RENDER"




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

		# return True, so the operator is executed
		return True



	# cancel modal operator
	def cancel(self, context):

		print("[INFO] Rendering operator clean-up.")

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
			self.camera_active.location = self.camera_original_location.copy()
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
		self.settings = context.scene.settings

		# get the calibration data of the selected Looking Glass from the deviceList
		self.device_current = LookingGlassAddon.deviceList[int(self.settings.activeDisplay)]


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
		# settings of the current preset
		self.rendering_viewWidth = LookingGlassAddon.qs[int(context.scene.settings.viewResolution)]["viewWidth"]
		self.rendering_viewHeight = LookingGlassAddon.qs[int(context.scene.settings.viewResolution)]["viewHeight"]
		self.rendering_rows = LookingGlassAddon.qs[int(context.scene.settings.viewResolution)]["rows"]
		self.rendering_columns = LookingGlassAddon.qs[int(context.scene.settings.viewResolution)]["columns"]
		self.rendering_totalViews = LookingGlassAddon.qs[int(context.scene.settings.viewResolution)]["totalViews"]

		# apply aspect ratio of the Looking Glass
		self.rendering_aspectRatio = self.device_current['aspectRatio'] / (self.rendering_rows / self.rendering_columns)
		self.render_setting_scene.render.resolution_x = self.rendering_viewWidth
		self.render_setting_scene.render.resolution_y = self.rendering_viewHeight

		if self.rendering_aspectRatio > 1:
			self.render_setting_scene.render.pixel_aspect_x = self.rendering_aspectRatio
			self.render_setting_scene.render.pixel_aspect_y = 1
		else:
			self.render_setting_scene.render.pixel_aspect_x = 1
			self.render_setting_scene.render.pixel_aspect_y = 1 / self.rendering_aspectRatio


		# if the operator was called with the animation flag set
		if self.animation == True:

			# set the rendering frame variable to the first frame of the scene
			self.rendering_frame = self.render_setting_scene.frame_start

		else:

			# set the rendering frame variable to the currently active frame
			self.rendering_frame = self.render_setting_scene.frame_current



		# REGISTER ALL HANDLERS FOR THE QUILT RENDERING
		################################################################

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
		# set the INVOKE_RENDER state to directly start the rendering_view
		self.operator_state == "INVOKE_RENDER"

		# add the modal operator handler
		context.window_manager.modal_handler_add(self)


		# keep the modal operator running
		return {'RUNNING_MODAL'}



	# modal operator for controlled redrawing of the lightfield
	def modal(self, context, event):

		print("[INFO] Operator state: ", self.operator_state)

		# if the TIMER event for the quilt rendering is called
		if event.type == 'TIMER':

			# INVOKE NEW RENDER JOB
			# ++++++++++++++++++++++++++++++++++
			if self.operator_state == "INVOKE_RENDER":

				print("[INFO] Invoking new render job.")

				# FRAME AND VIEW
				# ++++++++++++++++++++++
				# set the current frame to be rendered
				self.render_setting_scene.frame_set(self.rendering_frame, subframe=self.rendering_subframe)

				# get the subframe, that will be rendered
				self.rendering_subframe = self.render_setting_scene.frame_subframe

				# set the filepath so that the filename adheres to:
				# filepath + "_view_XX_YYYY"
				self.rendering_filepath



				# STORE USER CAMERA SETTINGS
				# ++++++++++++++++++++++++++++++++++
				# NOTE: - we do this here, since each frame could contain a different
				#		 camera setting
				# remember active camera as well as its original location and shift value
				self.camera_active = self.render_setting_scene.camera

				# if this is the first view of the current frame
				# NOTE: - we do it this way in case the camera is animated and its position changes each frame
				if self.rendering_view == 0:

					# remember current camera settings
					self.camera_original_location = self.camera_active.location.copy()
					self.camera_original_shift_x = self.camera_active.data.shift_x
					self.camera_original_sensor_fit = self.camera_active.data.sensor_fit



				# CAMERA SETTINGS: GET VIEW & PROJECTION MATRICES
				# +++++++++++++++++++++++++++++++++++++++++++++++

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
				cameraDistance = self.settings.focalPlane#self.camera_active.data.dof.focus_distance
				cameraSize = cameraDistance * tan(fov / 2)

				# start at viewCone * 0.5 and go up to -viewCone * 0.5
				# TODO: The Looking Glass Factory dicumentation suggests to use a viewcone of 35°, but the device calibration has 40° by default.
				#		Which one should we take?
				offsetAngle = (0.5 - self.rendering_view / (self.rendering_totalViews - 1)) * radians(self.device_current['viewCone'])

				# calculate the offset that the camera should move
				offset = cameraDistance * tan(offsetAngle)

				# translate the camera by the calculated offset in x-direction
				# NOTE: the matrix multiplications first transform the camera location into camera coordinates,
				#		then we apply the offset and transform back to the normal world coordinates
				self.camera_active.location = view_matrix @ (Matrix.Translation((-offset, 0, 0)) @ (view_matrix_inv @ self.camera_original_location.copy()))

				# modify the projection matrix, relative to the camera size.
				# NOTE: - we need to take into account the view aspect ratio and the pixel aspect ratio
				self.camera_active.data.shift_x = self.camera_original_shift_x + offset / (cameraSize * self.rendering_viewWidth / self.rendering_viewHeight * self.render_setting_scene.render.pixel_aspect_x * self.render_setting_scene.render.pixel_aspect_y)

				print("view_matrix: ", view_matrix)
				print("view_matrix_inv: ", view_matrix_inv)
				print("camera_location: ", self.camera_active.location)
				print("camera_original_location: ", self.camera_original_location)



				# start rendering
				bpy.ops.render.render("INVOKE_DEFAULT", animation=False, write_still=True, use_viewport=True)


			# INIT STEP
			# ++++++++++++++++++++++++++++++++++
			elif self.operator_state == "INIT_RENDER":

				print("[INFO] Rendering job initialized.")

				# if an animation shall be rendered
				if self.animation == True:

					# set the file path to the current frame path
					self.rendering_filepath = self.render_setting_scene.render.frame_path(frame=self.rendering_frame)

				# if a single frame shall be rendered
				elif self.animation == False:

					# set the file path to the current render path
					self.rendering_filepath = self.render_setting_filepath

					# if this path is a directory and not a file
					if os.path.isdir(self.rendering_filepath) == True or os.path.basename(self.rendering_filepath + self.render_setting_scene.render.file_extension) == self.render_setting_scene.render.file_extension:

						# define the frame number as the filename
						self.render_setting_scene.render.filepath = self.rendering_filepath + "####"
						self.rendering_filepath = self.render_setting_scene.render.frame_path(frame=self.rendering_frame)

					# if this path + extension is a file
					elif os.path.basename(self.rendering_filepath + self.render_setting_scene.render.file_extension) != self.render_setting_scene.render.file_extension:

						# add the file file_extension
						self.rendering_filepath = self.rendering_filepath + self.render_setting_scene.render.file_extension



				# Some status infos
				# if a single frame shall be rendered
				if self.animation == False:

					# notify user
					self.report({"INFO"},"Rendering view " + str(self.rendering_view + 1) + "/" + str(self.rendering_totalViews) + " ...")

				# if an animation shall be rendered
				elif self.animation == True:

					# notify user
					self.report({"INFO"},"Rendering view " + str(self.rendering_view + 1) + "/" + str(self.rendering_totalViews) + " of frame " + str(self.rendering_frame) +  " ...")



				# reset the operator state to IDLE
				self.operator_state = "IDLE"


			# PRE-RENDER STEP
			# ++++++++++++++++++++++++++++++++++

			# if nothing is rendering, but the last view is not yet rendered
			elif self.operator_state == "PRE_RENDER":

				print("[INFO] Rendering view is going to be prepared.")

				# output current status
				print(" # active camera: ", self.camera_active)
				print(" # current frame: ", self.rendering_frame)
				print(" # current subframe: ", self.rendering_subframe)
				print(" # current view: ", self.rendering_view)
				print(" # current file: ", self.rendering_filepath)

				# reset the operator state to IDLE
				self.operator_state = "IDLE"



			# POST-RENDER STEP
			# ++++++++++++++++++++++++++++++++++

			# if nothing is rendering, but the last view is not yet rendered
			elif self.operator_state == "POST_RENDER":

				print("[INFO] Saving file in ", self.rendering_filepath)
				print(bpy.data.images["Render Result"].pixels)


				# STORE THE PIXEL DATA OF THE RENDERED IMAGE
				# ++++++++++++++++++++++++++++++++++++++++++++
				# save the rendered image in a file
				bpy.data.images["Render Result"].save_render(filepath=self.rendering_filepath, scene=self.render_setting_scene)

				# append the loaded image to the list
				viewImage = bpy.data.images.load(filepath=self.rendering_filepath)

				# store the pixel data in an numpy array
				self.viewImagesPixels.append(np.array(viewImage.pixels[:]).copy())

				# delete the Blender image of this view
				bpy.data.images.remove(viewImage)



				# reset the operator state to IDLE
				self.operator_state = "IDLE"





			# COMPLETE-RENDER STEP
			# ++++++++++++++++++++++++++++++++++

			# if nothing is rendering, but the last view is not yet rendered
			elif self.operator_state == "COMPLETE_RENDER":

				print("[INFO] Render job completed.")

				# QUILT ASSEMBLY
				# ++++++++++++++++++++++++++++++++++++++++++++
				# if this was the last view
				if self.rendering_view == (self.rendering_totalViews - 1):

					# then assemble the quilt from the views
					verticalStack = []
					horizontalStack = []
					for row in range(0, self.rendering_rows, 1):
						for column in range(0, self.rendering_columns, 1):

							# get pixel data and reshape into a reasonable format for stacking
							viewPixels = self.viewImagesPixels[row * self.rendering_columns + column]
							viewPixels = viewPixels.reshape((self.render_setting_scene.render.resolution_y, self.render_setting_scene.render.resolution_x, 4))

							# append the pixel data to the current horizontal stack
							horizontalStack.append(viewPixels)

						# append the complete horizontal stack to the vertical stacks
						verticalStack.append(np.hstack(horizontalStack.copy()))

						# clear this horizontal stack
						horizontalStack.clear()

					# reshape the pixel data of all images into the quilt shape
					quiltPixels = np.vstack(verticalStack.copy())
					quiltPixels = np.reshape(quiltPixels, (self.rendering_columns * self.rendering_rows * (self.render_setting_scene.render.resolution_x * self.render_setting_scene.render.resolution_y * 4)))

					# create a Blender image with the obtained pixeö data
					quiltImage = bpy.data.images.new(os.path.basename(self.rendering_filepath), self.render_setting_scene.render.resolution_x * self.rendering_columns, self.render_setting_scene.render.resolution_y * self.rendering_rows)
					quiltImage.pixels = quiltPixels

					# save the quilt in a file
					quiltImage.save_render(filepath=self.rendering_filepath)

					# QUILT DISPLAY AS RENDER RESULT
					# ++++++++++++++++++++++++++++++++++++++++++++
					for window in context.window_manager.windows:
						for area in window.screen.areas:

							if area.type == 'IMAGE_EDITOR':
								if area.spaces.active.image.name == "Render Result":

									# and change the active image shown here to the quilt
									area.spaces.active.image = quiltImage

									# fit the zoom factor in this window to show the complete quilt
									bpy.ops.image.view_all({'window': window, 'screen': window.screen, 'area': area})

									# remove the render result image
									bpy.data.images.remove(bpy.data.images["Render Result"])

									break






				# VIEW & FRAME RENDERING
				# ++++++++++++++++++++++++++++++++++++++++++++
				# if a single frame shall be rendered
				if self.animation == False:

					# if this was not the last view
					if self.rendering_view < (self.rendering_totalViews - 1):

						# increase view count
						self.rendering_view += 1

						# reset the operator state to IDLE
						self.operator_state = "INVOKE_RENDER"

						return {'RUNNING_MODAL'}

					# if this was the last view
					else:

						# cancel the operator
						# NOTE: - this includes recovering all original user settings
						# reset the operator state to IDLE
						self.cancel(context)

						# notify user
						self.report({"INFO"},"Complete quilt rendered.")
						return {"CANCELLED"}

				# if an animation shall be rendered
				elif self.animation == True:

					# if this was not the last view
					if self.rendering_view < (self.rendering_totalViews - 1):

						# increase view count
						self.rendering_view += 1

						# reset the operator state to IDLE
						self.operator_state = "INVOKE_RENDER"

						return {'RUNNING_MODAL'}

					# if this was the last view
					elif self.rendering_view == (self.rendering_totalViews - 1):

						# but if this was not the last frame
						if self.rendering_frame < self.render_setting_scene.frame_end:

							# restore original camera settings of this frame
							self.camera_active.location = self.camera_original_location.copy()
							self.camera_active.data.shift_x = self.camera_original_shift_x
							self.camera_active.data.sensor_fit = self.camera_original_sensor_fit

							# reset the rendering view variable
							self.rendering_view = 0

							# increase frame count
							self.rendering_frame = self.rendering_frame + 1

							# clear the pixel data
							self.viewImagesPixels.clear()

							# reset the operator state to IDLE
							self.operator_state = "INVOKE_RENDER"

							return {'RUNNING_MODAL'}

						# if this was the last frame
						else:

							# cancel the operator
							# NOTE: - this includes recovering all original user settings
							self.cancel(context)

							# notify user
							self.report({"INFO"},"Complete animation quilt rendered.")
							return {"CANCELLED"}





			# CANCEl-RENDER STEP
			# ++++++++++++++++++++++++++++++++++

			# if nothing is rendering, but the last view is not yet rendered
			elif self.operator_state == "CANCEL_RENDER":

				print("[INFO] Render job cancelled.")

				# cancel the operator
				# NOTE: - this includes recovering all original user settings
				self.cancel(context)

				# notify user
				self.report({"INFO"},"Quilt rendering was cancelled.")
				return {"CANCELLED"}



		# pass event through
		return {'PASS_THROUGH'}
