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

import bpy
import time
import os, platform
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
	bl_options = {'REGISTER', 'INTERNAL'}

	# OPERATOR ARGUMENTS
	animation: bpy.props.BoolProperty(default = False)
	use_lockfile: bpy.props.BoolProperty(default = False)
	discard_lockfile: bpy.props.BoolProperty(default = False)	# trigger discarding lockfile
	force_keep: bpy.props.BoolProperty(default = False)			# only used for lockfile rendering

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

	# lock file
	lockfile = None
	lockfile_path = None
	lockfile_data = None
	lockfile_start_frame = None
	lockfile_start_view = None

	# render settings
	render_setting_original_engine = None
	render_setting_original_width = None
	render_setting_original_height = None
	render_setting_original_aspect_x = None
	render_setting_original_aspect_y = None
	render_setting_scene = None

	# render variables
	rendering_frame = 1	    	# the frame that is currently rendered
	rendering_subframe = 0.0	# the subframe that is currently rendered
	rendering_view = 0	  		# the view of the frame that is currently rendered

	rendering_deviceType = None
	rendering_viewWidth = None
	rendering_viewHeight = None
	rendering_rows = None
	rendering_columns = None
	rendering_totalViews = None
	rendering_viewCone = None
	rendering_filepath = None
	rendering_view_filepath = None

	# camera settings
	camera_active = None
	camera_original = None
	camera_original_location = None
	camera_original_shift_x = None
	camera_original_sensor_fit = None
	view_matrix = None
	view_matrix_inv = None

	# Blender images & pixel data
	viewImage = None
	quiltImage = None
	viewImagesPixels = []

	# event and app handler ids
	_handle_event_timer = None	# modal timer event

	# define cancel standard messages
	cancel_sign = "INFO"
	cancel_message = "Quilt rendering was cancelled."

	# callback functions:
	# NOTE: - we only use this callbacks to enter the correct state. The actual
	#		  is executed in the modal operator, because Blender doesn't allow
	# 		  object manipulation from application handlers.

	def init_render(self, Scene, unknown_param):

		# reset the operator state to IDLE
		if self.operator_state != "CANCEL_RENDER": self.operator_state = "INIT_RENDER"

		# wait a few milliseconds until the operator processed the step
		while self.operator_state != "IDLE" and self.operator_state != "CANCEL_RENDER":
			time.sleep(0.001)
			#print("[", self.operator_state, "] WAITING")

	# function that is called before rendering starts
	def pre_render(self, Scene, unknown_param):

		# reset the operator state to PRE_RENDER
		if self.operator_state != "CANCEL_RENDER": self.operator_state = "PRE_RENDER"

		# wait a few milliseconds until the operator processed the step
		while self.operator_state != "IDLE" and self.operator_state != "CANCEL_RENDER":
			time.sleep(0.001)
			#print("[", self.operator_state, "] WAITING")

	# function that is called after rendering finished
	def post_render(self, Scene, unknown_param):

		# reset the operator state to PRE_RENDER
		if self.operator_state != "CANCEL_RENDER": self.operator_state = "POST_RENDER"

		# wait a few milliseconds until the operator processed the step
		while self.operator_state != "IDLE" and self.operator_state != "CANCEL_RENDER":
			time.sleep(0.001)
			#print("[", self.operator_state, "] WAITING")

	# function that is called when the renderjob is completed
	def completed_render(self, Scene, unknown_param):

		# reset the operator state to COMPLETE_RENDER
		if self.operator_state != "CANCEL_RENDER": self.operator_state = "COMPLETE_RENDER"

		# print("######################################")
		# # wait a few milliseconds until the operator processed the step
		# while self.operator_state != "INVOKE_RENDER" and self.operator_state != "IDLE":
		# 	time.sleep(0.001)
		# 	print("[", self.operator_state, "] WAITING")

	# function that is called if rendering was cancelled
	def cancel_render(self, Scene, unknown_param):

		# set operator state to CANCEL
		self.operator_state = "CANCEL_RENDER"




	# # inititalize the quilt rendering
	# @classmethod
	# def __init__(self):
	#
	# 	print("Initializing the quilt rendering operator ...")
	#
	#
	#
	# # clean up
	# @classmethod
	# def __del__(self):
	#
	# 	print("Stopped quilt rendering operator ...")




	# check if everything is correctly set up for the quilt rendering
	@classmethod
	def poll(self, context):

		# return True, so the operator is executed
		return True



	# cancel modal operator
	def cancel(self, context):

		# REMOVE APP HANDLERS
		# +++++++++++++++++++++++++
		try:

			# remove render app handlers
			bpy.app.handlers.render_init.remove(self.init_render)
			bpy.app.handlers.render_pre.remove(self.pre_render)
			bpy.app.handlers.render_post.remove(self.post_render)
			bpy.app.handlers.render_cancel.remove(self.cancel_render)
			bpy.app.handlers.render_complete.remove(self.completed_render)

			# remove event timer
			if self._handle_event_timer != None: context.window_manager.event_timer_remove(self._handle_event_timer)

		except:
			pass



		# CLEAR IMAGE & PIXEL DATA
		# +++++++++++++++++++++++++
		self.viewImage = None
		self.quiltImage = None
		self.viewImagesPixels.clear()



		# CLEAN-UP FILES
		# +++++++++++++++++++++++++++++++++++++++++++
		# if the view files shall not be kept OR (still was rendered AND no filename was specfied) OR the file keeping is forced OR the incomplete render job was discarded
		if ((self.settings.render_output == '1' or (not ((self.animation == False and ("Quilt Render Result" in self.rendering_filepath) == False) or self.animation == True))) and self.force_keep == False) or self.discard_lockfile == True:

			# if it was an animation
			if self.animation == True:

				# for all frames and views
				for frame in range(self.render_setting_scene.frame_start, self.render_setting_scene.frame_end + 1):

					for view in range(0, self.rendering_totalViews):

						# get the file or directory path
						filepath, extension = os.path.splitext(os.path.abspath(self.render_setting_filepath))

						# if this path is a valid directory path AND not a filename
						if os.path.isdir(filepath) == True or os.path.basename(filepath + self.render_setting_scene.render.file_extension) == self.render_setting_scene.render.file_extension:

							# include the frame number in the temporary filename
							filepath = os.path.abspath(filepath + "/Quilt Render Result")

						# if no extension is in the filename use Blender's
						if extension == "":
							extension = self.render_setting_scene.render.file_extension

						# append the frame number
						filepath = filepath + "_f" + str(frame).zfill(len(str(self.render_setting_scene.frame_end)))

						# append the view number
						filepath = filepath + "_v" + str(view).zfill(len(str(self.rendering_totalViews - 1))) + extension

						# delete this file, if it exists
						if os.path.isfile(filepath) == True: os.remove(filepath)

			# if it was a still image
			elif self.animation == False:

				# for all views
				for view in range(0, self.rendering_totalViews):

					# get the file or directory path
					filepath, extension = os.path.splitext(os.path.abspath(self.render_setting_filepath))

					# if this path is a valid directory path AND not a filename
					if os.path.isdir(filepath) == True or os.path.basename(filepath + self.render_setting_scene.render.file_extension) == self.render_setting_scene.render.file_extension:

						# use a temporary filename
						filepath = os.path.abspath(filepath + "/Quilt Render Result")

					# if no extension is in the filename use Blender's
					if extension == "":
						extension = self.render_setting_scene.render.file_extension

					# adjust the file name for current view and frame:
					# used format: FILENAME_fXXX_vXXX.EXTENSION
					filepath = filepath + "_v" + str(view).zfill(len(str(self.rendering_totalViews - 1))) + extension

					# delete this file, if it exists
					if os.path.isfile(filepath) == True: os.remove(filepath)



		# RESTORE USER SETTINGS
		# +++++++++++++++++++++++++
		# if this call was not just invoked to discard an incomplete render job
		if self.discard_lockfile == False:

			# CAMERA
			# if a active camera exists
			if self.camera_active != None and self.camera_active.type == 'CAMERA':

				# restore original camera settings
				self.camera_active.location = self.camera_original_location.copy()
				self.camera_active.data.shift_x = self.camera_original_shift_x
				self.camera_active.data.sensor_fit = self.camera_original_sensor_fit

			# restore the origingal active camera
			self.render_setting_scene.camera = self.camera_original


			# RENDER SETTINGS
			# restore original file path
			self.render_setting_scene.render.filepath = self.render_setting_filepath

			# restore engine and image settings
			self.render_setting_scene.render.engine = self.render_setting_original_engine
			self.render_setting_scene.render.resolution_x = self.render_setting_original_width
			self.render_setting_scene.render.resolution_y = self.render_setting_original_height
			self.render_setting_scene.render.pixel_aspect_x = self.render_setting_original_aspect_x
			self.render_setting_scene.render.pixel_aspect_y = self.render_setting_original_aspect_y


		# DELETE LOCKFILE
		# ++++++++++++++++++++++++++++++++++
		# if a lockfile exists, delete it
		if os.path.exists(self.lockfile_path) == True: os.remove(self.lockfile_path)

		# reset global and local status variables
		LookingGlassAddon.has_lockfile = False
		self.use_lockfile = False



		# RESET STATUS VARIABLES FOR PROGRESSBAR
		# ++++++++++++++++++++++++++++++++++
		self.settings.render_progress = 0.0
		LookingGlassAddon.RenderInvoked = False
		LookingGlassAddon.RenderAnimation = None

		# return None since this is expected by the operator
		return None



	# invoke the modal operator
	def invoke(self, context, event):

		# make an internal variable for the window_manager,
		# which can be accessed from methods that have no "context" parameter
		self.settings = context.scene.settings

		# get the calibration data of the selected Looking Glass from the deviceList
		if int(self.settings.activeDisplay) != -1: self.device = LookingGlassAddon.deviceList[int(self.settings.activeDisplay)]

		# RENDER SETTINGS
		################################################################

		# STORE ORIGINAL SETTINGS
		# ++++++++++++++++++++++++
		# we need to restore these at the end
		self.render_setting_original_engine = context.scene.render.engine
		self.render_setting_original_width = context.scene.render.resolution_x
		self.render_setting_original_height = context.scene.render.resolution_y
		self.render_setting_original_aspect_x = context.scene.render.pixel_aspect_x
		self.render_setting_original_aspect_y = context.scene.render.pixel_aspect_y



		# SCENE AND PATH SETTINGS
		# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

		# set the lockfile path
		self.lockfile_path = os.path.abspath(LookingGlassAddon.tmp_path + "/" + os.path.basename(bpy.data.filepath) + ".lock")

		# if the lockfile shall be used
		if self.use_lockfile == True:

			# check if the lockfile still exists and otherwise start a new render job
			try:

				# READ LOCKFILE DATA
				# ++++++++++++++++++++++++++++++++++++++++++++
				self.lockfile = open(self.lockfile_path, 'rt')
				if self.lockfile != None:

					# read all lines
					self.lockfile_data = self.lockfile.readlines()

					# strip all line breaks
					self.lockfile_data = [line.replace("\n", "") for line in self.lockfile_data]

					# close file
					self.lockfile.close()

			except:

				# reset global and local status variables
				LookingGlassAddon.has_lockfile = False
				self.use_lockfile = False

				# notify user
				self.report({"ERROR"}, "Render job can not be continued. Lockfile not found or corrupted.")

				# don't execute operator
				return {'FINISHED'}



		# if the lockfile shall be used
		if self.use_lockfile == True:

			# try to apply the render engine
			try:

				context.scene.render.engine = self.lockfile_data[1]

			except:

				# if this does not work, notify user
				self.report({"ERROR"}, "Render job can not be continued. Could not find the previously used render engine: " + self.lockfile_data[1] + ".")

				# don't execute operator
				return {'FINISHED'}

			# get scene and path settings
			self.render_setting_scene = bpy.data.scenes[self.lockfile_data[2]]
			self.render_setting_filepath = self.lockfile_data[3]
			self.rendering_filepath = self.lockfile_data[4]

		else:

			# set scene and path settings from current user settings
			self.render_setting_scene = context.scene
			self.render_setting_filepath = context.scene.render.filepath
			self.rendering_filepath = os.path.abspath(context.scene.render.filepath)




		# get file and extension part of the string
		filepath, extension = os.path.splitext(self.rendering_filepath)

		# check if a valid path is given in output settings
		if self.render_setting_scene.render.use_file_extension == True:

			if os.path.exists(os.path.dirname(self.rendering_filepath + self.render_setting_scene.render.file_extension)) == False:

				# notify user
				self.report({"ERROR"}, "Output path " + self.rendering_filepath + " is not a valid path. Please change the output path in the render settings.")

				# don't execute operator
				return {'FINISHED'}

			# if the file already exists and should not be overwritten
			elif  self.render_setting_scene.render.use_overwrite == False and os.path.exists(self.rendering_filepath + self.render_setting_scene.render.file_extension) == True:

				# notify user
				self.report({"ERROR"}, "Specified file " + self.rendering_filepath + self.render_setting_scene.render.file_extension + " already exists. Please change the output path in the render settings.")

				# don't execute operator
				return {'FINISHED'}

			# if a file extension was given and does not fit to the expected extension
			elif extension != '' and self.render_setting_scene.render.file_extension != extension:

				# notify user
				self.report({"ERROR"}, "Specified file extension " + extension + " does not fit to expected one. Please change the output path in the render settings.")

				# don't execute operator
				return {'FINISHED'}

		elif self.render_setting_scene.render.use_file_extension == False:

			# was a file extension entered by the user?
			if extension == '':

				# if not, notify user
				self.report({"ERROR"}, "Output path " + self.rendering_filepath + " is missing a valid file extension.")

				# don't execute operator
				return {'FINISHED'}

			# if a file extension was given and does not fit to the expected extension
			elif extension != '' and self.render_setting_scene.render.file_extension != extension:

				# notify user
				self.report({"ERROR"}, "Specified file extension " + extension + " does not fit to expected one. Please change the output path in the render settings.")

				# don't execute operator
				return {'FINISHED'}

			else:

				# is a valid directory path given?
				if os.path.exists(os.path.dirname(self.rendering_filepath)) == False:

					# if not, notify user
					self.report({"ERROR"}, "Output path " + self.rendering_filepath + " is not a valid path. Please change the output path in the render settings.")

					# don't execute operator
					return {'FINISHED'}

				# if the file already exists and should not be overwritten
				elif  self.render_setting_scene.render.use_overwrite == False and os.path.exists(self.rendering_filepath) == True:

					# notify user
					self.report({"ERROR"}, "Specified file " + self.rendering_filepath + " already exists. Please change the output path in the render settings.")

					# don't execute operator
					return {'FINISHED'}


		# check if the directory is accessible
		# NOTE: One could use os.access, but with regard to documentation,
		#		the following is more pythonic and more reliable
		try:

			# set the file path to the current render path
			test_path = os.path.abspath(self.render_setting_filepath)

			# if this path is a directory and not a file
			if os.path.isdir(test_path) == True or os.path.basename(test_path + self.render_setting_scene.render.file_extension) == self.render_setting_scene.render.file_extension:

				# use a temporary filename
				test_path = os.path.abspath(test_path + "/Quilt Render Result" + self.render_setting_scene.render.file_extension)

			# if this path + extension is a file
			elif os.path.basename(self.rendering_filepath + self.render_setting_scene.render.file_extension) != self.render_setting_scene.render.file_extension:

				# add the file file_extension, only if option is selected
				if self.render_setting_scene.render.use_file_extension == True:
					test_path = test_path + self.render_setting_scene.render.file_extension

			# try to create the file
			test_file = open(test_path, 'w')
			test_file.close()

			# remove the file again
			os.remove(test_path)

		except IOError:

			# if not, notify user
			self.report({"ERROR"}, "Cannot write to " + self.rendering_filepath + ". Please change the output path in the render settings.")

			# don't execute operator
			return {'FINISHED'}



		# GET RENDER SETTINGS
		# ++++++++++++++++++++++++

		# if the lockfile shall be used
		if self.use_lockfile == True:

			# render settings
			self.rendering_deviceType = self.lockfile_data[5]
			self.rendering_viewWidth = int(self.lockfile_data[6])
			self.rendering_viewHeight = int(self.lockfile_data[7])
			self.rendering_rows = int(self.lockfile_data[8])
			self.rendering_columns = int(self.lockfile_data[9])
			self.rendering_totalViews = int(self.lockfile_data[10])

			# animation settings
			self.animation = (self.lockfile_data[11] == "True")
			self.render_setting_scene.frame_start = int(self.lockfile_data[12])
			self.render_setting_scene.frame_end = int(self.lockfile_data[13])

			# frame and view
			self.rendering_frame = self.lockfile_start_frame = int(self.lockfile_data[14].split(";")[0])
			self.rendering_view = self.lockfile_start_view = int(self.lockfile_data[14].split(";")[1])

		else:

			# settings of the current preset
			# if the settings are to be taken from device selection
			if self.settings.render_use_device == True:

				self.rendering_deviceType = self.device['type']
				self.rendering_viewWidth = LookingGlassAddon.qs[int(self.settings.quiltPreset)]["viewWidth"]
				self.rendering_viewHeight = LookingGlassAddon.qs[int(self.settings.quiltPreset)]["viewHeight"]
				self.rendering_rows = LookingGlassAddon.qs[int(self.settings.quiltPreset)]["rows"]
				self.rendering_columns = LookingGlassAddon.qs[int(self.settings.quiltPreset)]["columns"]
				self.rendering_totalViews = LookingGlassAddon.qs[int(self.settings.quiltPreset)]["totalViews"]

			# else, if the settings were specified separately
			else:

				self.rendering_deviceType = self.render_setting_scene.settings.render_device_type
				self.rendering_viewWidth = LookingGlassAddon.qs[int(self.settings.render_quilt_preset)]["viewWidth"]
				self.rendering_viewHeight = LookingGlassAddon.qs[int(self.settings.render_quilt_preset)]["viewHeight"]
				self.rendering_rows = LookingGlassAddon.qs[int(self.settings.render_quilt_preset)]["rows"]
				self.rendering_columns = LookingGlassAddon.qs[int(self.settings.render_quilt_preset)]["columns"]
				self.rendering_totalViews = LookingGlassAddon.qs[int(self.settings.render_quilt_preset)]["totalViews"]

			# if the operator was called with the animation flag set
			if self.animation == True:

				# set the rendering frame variable to the first frame of the scene
				self.rendering_frame = self.render_setting_scene.frame_start

			else:

				# set the rendering frame variable to the currently active frame
				self.rendering_frame = self.render_setting_scene.frame_current


			# CREATE NEW LOCKFILE
			# ++++++++++++++++++++++++++++++++++

			# if the current blender session has a file
			if bpy.data.filepath != "":

				# if no temp directory exists in the add-on path, create one
				if os.path.exists(LookingGlassAddon.tmp_path) == False:
					os.mkdir(LookingGlassAddon.tmp_path)


				# if the temp directory exists now
				if os.path.exists(LookingGlassAddon.tmp_path) == True:

					# set the lockfile path
					self.lockfile_path = os.path.abspath(LookingGlassAddon.tmp_path + "/" + os.path.basename(bpy.data.filepath) + ".lock")

					# create the lockfile there
					self.lockfile = open(self.lockfile_path, 'a')
					if self.lockfile != None:

						# WRITE INFORMATION ABOUT THE RENDER JOB
						# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
						# blend-file name
						self.lockfile.write(bpy.data.filepath + "\n")

						# render settings
						self.lockfile.write(self.render_setting_scene.render.engine + "\n")
						self.lockfile.write(self.render_setting_scene.name + "\n")
						self.lockfile.write(self.render_setting_filepath + "\n")
						self.lockfile.write(self.rendering_filepath + "\n")
						self.lockfile.write(str(self.rendering_deviceType) + "\n")
						self.lockfile.write(str(self.rendering_viewWidth) + "\n")
						self.lockfile.write(str(self.rendering_viewHeight) + "\n")
						self.lockfile.write(str(self.rendering_rows) + "\n")
						self.lockfile.write(str(self.rendering_columns) + "\n")
						self.lockfile.write(str(self.rendering_totalViews) + "\n")

						# animation settings
						self.lockfile.write(str(self.animation) + "\n")
						self.lockfile.write(str(self.render_setting_scene.frame_start) + "\n")
						self.lockfile.write(str(self.render_setting_scene.frame_end) + "\n")

						# IMPORTANT: THIS LAST LINE WILL CONTAIN THE CURRENT
						# FRAME AND VIEW THAT IS RENDERED AND WILL BE UPDATED
						# DURING RENDERING
						self.lockfile.write(str(self.rendering_frame) + ";" + str(self.rendering_view))

						# close file
						self.lockfile.close()



		# APPLY RENDER SETTINGS
		# ++++++++++++++++++++++++

		# apply the render resolution to Blender render settings
		self.render_setting_scene.render.resolution_x = self.rendering_viewWidth
		self.render_setting_scene.render.resolution_y = self.rendering_viewHeight

		# TODO: At the moment this is hardcoded.
		# 		May make sense to use the Blender preset mechanisms instead ("preset_add", "execute_preset", etc.)
		#		This would be more future proof and allow users to add presets manually.
		# if for Looking Glass Portrait
		if self.rendering_deviceType == 'portrait':

			# set the correct view cone
			self.rendering_viewCone = 58.0

			# apply the correct aspect ratio
			self.render_setting_scene.render.pixel_aspect_x = 1.0
			self.render_setting_scene.render.pixel_aspect_y = (self.render_setting_scene.render.resolution_x / self.render_setting_scene.render.resolution_y) / 0.75

		# if for Looking Glass 8.9''
		elif self.rendering_deviceType == 'standard':

			# set the correct view cone
			self.rendering_viewCone = 40.0

			# apply the correct aspect ratio
			self.render_setting_scene.render.pixel_aspect_x = 1.0
			self.render_setting_scene.render.pixel_aspect_y = (self.render_setting_scene.render.resolution_x / self.render_setting_scene.render.resolution_y) / 1.6

		# if for Looking Glass 15.6'' or 8k
		elif self.rendering_deviceType == 'large' or self.rendering_deviceType == '8k':

			# set the correct view cone
			self.rendering_viewCone = 50.0

			# apply the correct aspect ratio
			self.render_setting_scene.render.pixel_aspect_x = 1.0
			self.render_setting_scene.render.pixel_aspect_y = (self.render_setting_scene.render.resolution_x / self.render_setting_scene.render.resolution_y) / 1.777777777



		# CHECK IF USER OPTED TO DISCARD AN INCOMPLETE RENDER JOB
		################################################################
		# if the lockfile shall be discarded
		if self.discard_lockfile == True:

			# cancel the operator
			# NOTE: - this includes deleting all view files
			self.cancel(context)

			# notify user
			self.report({"INFO"}, "Render job discarded.")
			return {"CANCELLED"}



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
		# add the modal operator handler
		context.window_manager.modal_handler_add(self)

		# SET STATUS VARIABLES FOR PROGRESSBAR
		# ++++++++++++++++++++++++++++++++++
		LookingGlassAddon.RenderInvoked = True
		LookingGlassAddon.RenderAnimation = self.animation

		# keep the modal operator running
		return {'RUNNING_MODAL'}



	# modal operator for controlled redrawing of the lightfield
	def modal(self, context, event):

		#print("[INFO] Operator state: ", self.operator_state)

		# if the TIMER event for the quilt rendering is called
		if event.type == 'TIMER':

			# INVOKE NEW RENDER JOB
			# ++++++++++++++++++++++++++++++++++
			if self.operator_state == "INVOKE_RENDER":

				# print("[INFO] Invoking new render job.")

				# FRAME AND VIEW
				# ++++++++++++++++++++++
				# set the current frame to be rendered
				self.render_setting_scene.frame_set(self.rendering_frame, subframe=self.rendering_subframe)

				# get the subframe, that will be rendered
				self.rendering_subframe = self.render_setting_scene.frame_subframe



				# STORE USER CAMERA SETTINGS
				# ++++++++++++++++++++++++++++++++++

				# if this is the first view of the current frame OR the first view of the lockfile
				# NOTE: - we do it this way in case the camera is animated and its position changes each frame
				if self.rendering_view == 0 or (self.use_lockfile == True and (self.rendering_frame == self.lockfile_start_frame and self.rendering_view == self.lockfile_start_view)):

					# NOTE: - we do this here, since each frame could contain a different
					#		 camera setting
					# if a camera is selected in the add-on settings
					if self.settings.lookingglassCamera != None:

						# use the selected camera
						self.camera_active = self.settings.lookingglassCamera

					else:

						# use the active camera of the scene
						self.camera_active = self.render_setting_scene.camera

					# remember the origingally active camera
					self.camera_original = self.render_setting_scene.camera

					# remember current camera settings
					self.camera_original_location = self.camera_active.location.copy()
					self.camera_original_shift_x = self.camera_active.data.shift_x
					self.camera_original_sensor_fit = self.camera_active.data.sensor_fit

					# CAMERA SETTINGS: GET VIEW & PROJECTION MATRICES
					# +++++++++++++++++++++++++++++++++++++++++++++++

					# set the scenes active camera to this camera
					self.render_setting_scene.camera = self.camera_active

					# get camera's modelview matrix
					self.view_matrix = self.camera_active.matrix_world.copy()

					# correct for the camera scaling
					self.view_matrix = self.view_matrix @ Matrix.Scale(1/self.camera_active.scale.x, 4, (1, 0, 0))
					self.view_matrix = self.view_matrix @ Matrix.Scale(1/self.camera_active.scale.y, 4, (0, 1, 0))
					self.view_matrix = self.view_matrix @ Matrix.Scale(1/self.camera_active.scale.z, 4, (0, 0, 1))

					# calculate the inverted view matrix because this is what the draw_view_3D function requires
					self.view_matrix_inv = self.view_matrix.inverted_safe()



				# CAMERA SETTINGS: APPLY POSITION AND SHIFT
				# +++++++++++++++++++++++++++++++++++++++++++++++
				# adjust the camera settings to the correct view point
				# The field of view set by the camera
				# NOTE 1: - the Looking Glass Factory documentation suggests to use a FOV of 14°. We use the focal length of the Blender camera instead.
				fov = self.camera_active.data.angle

				# calculate cameraSize from its distance to the focal plane and the FOV
				cameraDistance = self.settings.focalPlane
				cameraSize = cameraDistance * tan(fov / 2)

				# start at viewCone * 0.5 and go up to -viewCone * 0.5
				offsetAngle = (0.5 - self.rendering_view / (self.rendering_totalViews - 1)) * radians(self.rendering_viewCone)

				# calculate the offset that the camera should move
				offset = cameraDistance * tan(offsetAngle)

				# translate the camera by the calculated offset in x-direction
				# NOTE: the matrix multiplications first transform the camera location into camera coordinates,
				#		then we apply the offset and transform back to world coordinates
				self.camera_active.location = self.view_matrix @ (Matrix.Translation((-offset, 0, 0)) @ (self.view_matrix_inv @ self.camera_original_location.copy()))

				# modify the projection matrix, relative to the camera size
				self.camera_active.data.shift_x = self.camera_original_shift_x + 0.5 * offset / cameraSize




				# start rendering
				# NOTE: Not using write_still because we save the images manually
				bpy.ops.render.render("INVOKE_DEFAULT", animation=False)#, write_still=True)



			# INIT STEP
			# ++++++++++++++++++++++++++++++++++
			elif self.operator_state == "INIT_RENDER":

				#print("[INFO] Rendering job initialized.")

				# get the file or directory path
				filepath, extension = os.path.splitext(os.path.abspath(self.render_setting_filepath))

				# if an animation shall be rendered
				if self.animation == True:

					# if this path is a valid directory path AND not a filename
					if os.path.isdir(filepath) == True or os.path.basename(filepath + self.render_setting_scene.render.file_extension) == self.render_setting_scene.render.file_extension:

						# include the frame number in the temporary filename
						self.rendering_filepath = os.path.abspath(filepath + "/Quilt Render Result" + "_f" + str(self.rendering_frame).zfill(len(str(self.render_setting_scene.frame_end))) + self.render_setting_scene.render.file_extension)

					# if this path + extension is a filename
					elif os.path.basename(filepath + self.render_setting_scene.render.file_extension) != self.render_setting_scene.render.file_extension:

						# if no extension is in the filename use Blender's
						if extension == "":
							extension = self.render_setting_scene.render.file_extension

						# include the frame number in the temporary filename
						self.rendering_filepath = filepath + "_f" + str(self.rendering_frame).zfill(len(str(self.render_setting_scene.frame_end))) + extension

				# if a single frame shall be rendered
				elif self.animation == False:

					# if this path is a valid directory path AND not a filename
					if os.path.isdir(filepath) == True or os.path.basename(filepath + self.render_setting_scene.render.file_extension) == self.render_setting_scene.render.file_extension:

						# use a temporary filename
						self.rendering_filepath = os.path.abspath(filepath + "/Quilt Render Result" + self.render_setting_scene.render.file_extension)

					# if this path + extension is a filename
					elif os.path.basename(filepath + self.render_setting_scene.render.file_extension) != self.render_setting_scene.render.file_extension:

						# if no extension is in the filename use Blender's
						if extension == "":
							extension = self.render_setting_scene.render.file_extension

						# add the file extension
						self.rendering_filepath = filepath + extension


				# GET THE PIXEL DATA OF THE RENDERED VIEWS
				# ++++++++++++++++++++++++++++++++++++++++++++
				# if the lockfile shall be used AND this is the first render
				if (self.use_lockfile == True and (self.rendering_frame == self.lockfile_start_frame and self.rendering_view == self.lockfile_start_view)):

					# set current frame
					frame = self.rendering_frame

					# iterate through all views
					for view in range(0, self.rendering_totalViews):

						# if this view was already rendered
						if view <= self.lockfile_start_view:

							# adjust the file name for current view:
							# used format: FILENAME_fXXX_vXXX.EXTENSION
							self.rendering_view_filepath, extension = os.path.splitext(self.rendering_filepath)
							self.rendering_view_filepath = self.rendering_view_filepath.replace("_f" + str(self.rendering_frame).zfill(len(str(self.render_setting_scene.frame_end))), "")

							# append frame number, if a animation is rendered
							if self.animation == True: self.rendering_view_filepath = self.rendering_view_filepath + "_f" + str(frame).zfill(len(str(self.render_setting_scene.frame_end)))

							# append view number
							self.rendering_view_filepath = self.rendering_view_filepath + "_v" + str(view).zfill(len(str(self.rendering_totalViews - 1))) + extension

							# if the file exists
							if os.path.exists(self.rendering_view_filepath):

								# load the view image
								self.viewImage = bpy.data.images.load(filepath=self.rendering_view_filepath)

								# store the pixel data in an numpy array
								# NOTE: we use foreach_get, since this is significantly faster
								tmp_pixels = np.empty(len(self.viewImage.pixels), np.float32)
								self.viewImage.pixels.foreach_get(tmp_pixels)

								# append the pixel data to the list of views
								self.viewImagesPixels.append(tmp_pixels)

								# if this was the last view
								if self.rendering_view == (self.rendering_totalViews - 1):

									# NOTE: Creating a new image via the dedicated operators and methods
									# 		didn't apply the correct image formats and settings
									#		and therefore, we use the created image
									self.viewImage.scale(self.render_setting_scene.render.resolution_x * self.rendering_columns, self.render_setting_scene.render.resolution_y * self.rendering_rows)
									self.quiltImage = self.viewImage

								else:

									# delete the Blender image of this view
									bpy.data.images.remove(self.viewImage)

							# if the file does not exist
							else:

								# cancel the operator
								self.operator_state = "CANCEL_RENDER"

								# force the operator to keep the view Files
								self.force_keep = True

								# notify user
								self.cancel_sign = "ERROR"
								self.cancel_message = "Render job can not be continued. Missing view file(s) of the previous render job."

								return {"PASS_THROUGH"}


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

				# print("[INFO] Rendering view is going to be prepared.")
				#
				# # output current status
				# print(" # active camera: ", self.camera_active)
				# print(" # current frame: ", self.rendering_frame)
				# print(" # current subframe: ", self.rendering_subframe)
				# print(" # current view: ", self.rendering_view)
				# print(" # current file: ", self.rendering_filepath)

				# reset the operator state to IDLE
				self.operator_state = "IDLE"



			# POST-RENDER STEP
			# ++++++++++++++++++++++++++++++++++

			# if nothing is rendering, but the last view is not yet rendered
			elif self.operator_state == "POST_RENDER":

				# print("[INFO] Saving file in ", self.rendering_filepath)

				# STORE THE PIXEL DATA OF THE RENDERED IMAGE
				# ++++++++++++++++++++++++++++++++++++++++++++
				# adjust the file name for current view:
				# # used format: FILENAME_fXXX_vXXX.EXTENSION
				self.rendering_view_filepath, extension = os.path.splitext(self.rendering_filepath)
				self.rendering_view_filepath = self.rendering_view_filepath + "_v" + str(self.rendering_view).zfill(len(str(self.rendering_totalViews - 1))) + extension

				# save the rendered image in a file
				bpy.data.images["Render Result"].save_render(filepath=self.rendering_view_filepath, scene=self.render_setting_scene)

				# load the view image
				self.viewImage = bpy.data.images.load(filepath=self.rendering_view_filepath)

				# store the pixel data in an numpy array
				# NOTE: we use foreach_get, since this is significantly faster
				tmp_pixels = np.empty(len(self.viewImage.pixels), np.float32)
				self.viewImage.pixels.foreach_get(tmp_pixels)

				# append the pixel data to the list of views
				self.viewImagesPixels.append(tmp_pixels)

				# if this was the last view
				if self.rendering_view == (self.rendering_totalViews - 1):

					# NOTE: Creating a new image via the dedicated operators and methods
					# 		didn't apply the correct image formats and settings
					#		and therefore, we use the created image
					self.viewImage.scale(self.render_setting_scene.render.resolution_x * self.rendering_columns, self.render_setting_scene.render.resolution_y * self.rendering_rows)
					self.quiltImage = self.viewImage

				else:
					# delete the Blender image of this view
					bpy.data.images.remove(self.viewImage)

				# reset the operator state to IDLE
				self.operator_state = "IDLE"



			# COMPLETE-RENDER STEP
			# ++++++++++++++++++++++++++++++++++

			# if nothing is rendering, but the last view is not yet rendered
			elif self.operator_state == "COMPLETE_RENDER":

				# print("[INFO] Render job completed.")

				# QUILT ASSEMBLY
				# ++++++++++++++++++++++++++++++++++++++++++++
				# if this was the last view
				if self.rendering_view == (self.rendering_totalViews - 1):
					start = time.time()

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

					# apply the assembled quilt pixel data
					self.quiltImage.pixels.foreach_set(quiltPixels)

					# set "view as render" based on the image format
					if self.quiltImage.file_format == 'OPEN_EXR_MULTILAYER' or self.quiltImage.file_format == 'OPEN_EXR':
						self.quiltImage.use_view_as_render = True
					else:
						self.quiltImage.use_view_as_render = False

					# save the quilt in a file
					self.quiltImage.save()#filepath=self.rendering_filepath, scene=self.render_setting_scene)

					# if no filename was specified and no animation is to be rendered
					if not ((self.animation == False and ("Quilt Render Result" in self.rendering_filepath) == False) or self.animation == True):

						# if a single frame shall be rendered
						if self.animation == False:

							# rename the Blender image to "Quilt Render Result"
							bpy.data.images[os.path.basename(self.rendering_view_filepath)].name = "Quilt Render Result"

						else:

							# rename the Blender image to "Quilt Render Result (f: XXX)" where XXX is the frame number
							bpy.data.images[os.path.basename(self.rendering_view_filepath)].name = "Quilt Render Result (f: " + str(self.rendering_frame).zfill(len(str(self.render_setting_scene.frame_end))) + ")"


						# remove the file
						if os.path.isfile(self.rendering_filepath) == True: os.remove(self.rendering_filepath)

					else:

						# rename the file
						os.rename(os.path.abspath(self.rendering_view_filepath), os.path.abspath(self.rendering_filepath))

						# update path in the image data
						self.quiltImage.filepath_raw = self.quiltImage.filepath = os.path.abspath(self.rendering_filepath)

						# rename the Blender image to the file's name
						bpy.data.images[os.path.basename(self.rendering_view_filepath)].name = os.path.basename(self.rendering_filepath)


					# QUILT DISPLAY AS RENDER RESULT
					# ++++++++++++++++++++++++++++++++++++++++++++
					for window in context.window_manager.windows:
						for area in window.screen.areas:

							if area.type == 'IMAGE_EDITOR':

								if area.spaces.active != None:

									if area.spaces.active.image != None:

										if area.spaces.active.image.name == "Render Result":

											# and change the active image shown here to the quilt
											area.spaces.active.image = self.quiltImage

											# fit the zoom factor in this window to show the complete quilt
											# bpy.ops.image.view_all({'window': window, 'screen': window.screen, 'area': area})

											# remove the render result image
											#bpy.data.images.remove(bpy.data.images["Render Result"])

											break



				# UPDATE PROGRESS BAR
				# +++++++++++++++++++++++++++++++++++++++++++
				# if a single frame shall be rendered
				if self.animation == False:
					self.settings.render_progress = int(self.rendering_view / ((self.rendering_totalViews - 1)) * 100)
				else:
					self.settings.render_progress = int(((self.rendering_frame - self.render_setting_scene.frame_start) * (self.rendering_totalViews - 1) + self.rendering_view) / ((self.rendering_totalViews - 1) * (self.render_setting_scene.frame_end - self.render_setting_scene.frame_start + 1)) * 100)




				# UPDATE LOCKFILE
				# +++++++++++++++++++++++++++++++++++++++++++
				# if the lockfile exists
				if self.lockfile_path != None and os.path.exists(self.lockfile_path) == True:

					# open the lockfile and read it
					self.lockfile = open(self.lockfile_path, 'rt')
					if self.lockfile != None:

						# read all lines but the last
						lines = self.lockfile.readlines()[:-1]

						# close file
						self.lockfile.close()

					# open the lockfile and write it with the updated line
					self.lockfile = open(self.lockfile_path, 'wt')
					if self.lockfile != None:

						# write the file content
						self.lockfile.write(''.join(lines))

						# updated line
						self.lockfile.write(str(self.rendering_frame) + ";" + str(self.rendering_view))

						# close file
						self.lockfile.close()



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

						# # cancel the operator
						# # NOTE: - this includes recovering all original user settings
						# # reset the operator state to IDLE
						# self.cancel(context)
						#
						# # notify user
						# self.report({"INFO"},"Complete quilt rendered.")
						# return {"CANCELLED"}

						# cancel the operator
						self.operator_state = "CANCEL_RENDER"

						# notify user
						self.cancel_sign = "INFO"
						self.cancel_message = "Complete quilt rendered."

						return {"PASS_THROUGH"}

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

							# # cancel the operator
							# # NOTE: - this includes recovering all original user settings
							# self.cancel(context)
							#
							# # notify user
							# self.report({"INFO"},"Complete animation quilt rendered.")
							# return {"CANCELLED"}

							# cancel the operator
							self.operator_state = "CANCEL_RENDER"

							# notify user
							self.cancel_sign = "INFO"
							self.cancel_message = "Complete animation quilt rendered."

							return {"PASS_THROUGH"}




			# CANCEl-RENDER STEP
			# ++++++++++++++++++++++++++++++++++

			# if nothing is rendering, but the last view is not yet rendered
			elif self.operator_state == "CANCEL_RENDER":

				# print("[INFO] Render job cancelled.")

				# cancel the operator
				# NOTE: - this includes recovering all original user settings
				self.cancel(context)

				# notify user
				self.report({self.cancel_sign}, self.cancel_message)
				return {"CANCELLED"}



		# pass event through
		return {'PASS_THROUGH'}
