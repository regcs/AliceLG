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
import sys, os, platform, shutil, json
import numpy as np
from math import *
from mathutils import *
from pprint import pprint

# TODO: Is there a better way to share global variables between all addon files and operators?
from .globals import *
from .ui import LookingGlassAddonSettings

# append the add-on's path to Blender's python PATH
sys.path.append(LookingGlassAddon.path)
sys.path.append(LookingGlassAddon.libpath)

# TODO: Would be better, if from .lib import pylightio could be called,
#		but for some reason that does not import all modules and throws
#		"AliceLG.lib.pylio has no attribute 'lookingglass'"
import pylightio as pylio

# ---------------- GLOBAL ADDON LOGGER -------------------
import logging
LookingGlassAddonLogger = logging.getLogger('Alice/LG')

# ------------ QUILT RENDERING -------------
# a class whose instances will store the variables required to control the
# internal rendering jobs
class RenderJob:

	def __init__(self, scene, animation):

		# INITIALIZE ATTRIBUTES
		# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
		# general options
		self.init = True
		self.animation = animation
		self.add_suffix = False
		self.scene = scene

		# render job variables
		# NOTE: these variables are required to control the quilt rendering in
		#		the rendering operator
		self.frame = 1
		self.subframe = 0.0
		self.view = 0
		self.seed = None
		self.view_width = None
		self.view_height = None
		self.rows = None
		self.columns = None
		self.total_views = None
		self.quilt_aspect = None
		self.view_cone = None

		# paths
		self.lockfile_path = None
		self.outputpath = None
		self.file_dirname = None
		self.file_basename = None
		self.file_extension = None
		self.file_quilt_suffix = None



		# INITIALIZE OUTPUT PATH ATTRIBUTES
		# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
	    # if a valid scene was given
		if type(self.scene) == bpy.types.Scene:

			# store the suffix option
			self.add_suffix = self.scene.addon_settings.render_add_suffix

			# store the output path in an attribute
			self.outputpath = bpy.path.abspath(bpy.context.scene.render.filepath)

			# try to obtain the basename of the given path
			self.file_dirname, self.file_basename = os.path.split(self.outputpath)
			self.file_basename, self.file_extension = os.path.splitext(self.file_basename)

			# if the basename is not empty
			if self.file_basename:

				# if the extension shall be automatically added AND the user didn't input an extension
				if self.scene.render.use_file_extension and not self.file_extension:

					# add the extension
					self.file_basename = bpy.path.ensure_ext(self.file_basename, bpy.context.scene.render.file_extension)

					# store the filename and the extension in separate variables
					self.file_basename, self.file_extension = os.path.splitext(self.file_basename)

			# if the given path exists AND basename is not empty
			elif not self.file_basename:

				self.file_basename, self.file_extension = ("Quilt Render Result", bpy.context.scene.render.file_extension)



	# return the filename of the quilt file
	def get_quilt_suffix(self):

		# metadata for HoloPlay Studio etc. is stored in the file name as a suffix
		# example of the format convention: quiltfilename_qs5x9a1.6.png
		if self.add_suffix:
			return "_qs" + str(self.columns) + "x" + str(self.rows) + "a" + str(self.quilt_aspect)
		else:
			return ""

	# return the filename of the quilt file
	def quilt_filepath(self, frame=None):

		# if no frame is given
		if frame is None: frame = self.frame

		# if an animation is rendered
		if self.animation:

			return os.path.join(self.file_dirname, self.file_basename + "_f" + str(frame).zfill(len(str(self.scene.frame_end))) + self.get_quilt_suffix() + self.file_extension)

		# if an animation is rendered
		elif not self.animation:

			return os.path.join(self.file_dirname, self.file_basename + self.get_quilt_suffix() + self.file_extension)

	# return the filename of the view file
	def view_filepath(self, view=None, frame=None):

		# if no frame is given
		if view is None: view = self.view
		if frame is None: frame = self.frame

		# if an animation is rendered
		if self.animation:
			return os.path.join(self.file_dirname, self.file_basename + "_f" + str(frame).zfill(len(str(self.scene.frame_end))) + self.get_quilt_suffix() + "_v" + str(view).zfill(len(str(self.total_views - 1))) + self.file_extension)

		# if an animation is rendered
		elif not self.animation:

			return os.path.join(self.file_dirname, self.file_basename + self.get_quilt_suffix() + "_v" + str(view).zfill(len(str(self.total_views - 1))) + self.file_extension)


# a class whose instances will store Blender's RenderSettings attribute
class RenderSettings:

	# currently selected device
	device = None

	# current quilt settings
	qs = None

	# scene which is rendered
	scene = None

	# define some specific "bpy.types.Scene" keys that need to be handled separately
	specific_keys = ['eevee', 'cycles', 'cycles_curves', 'frame_start', 'frame_end', 'frame_step']

	# original bpy.types.RenderSettings object reference
	original = None

	# scene which is rendered
	use_lockfile = None

	# is an animation rendered?
	animation = None

	# scene which is rendered
	job = None


	# initiate the class instance
	def __init__(self, BlenderScene, use_lockfile = False, animation = False):

		# get initialization parameters
		self.scene = BlenderScene
		self.use_lockfile = use_lockfile
		self.animation = animation

		# if a valid scene was given
		if self.scene and type(self.scene) == bpy.types.Scene:

			# INITIALIZATION
			# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

			# make an internal variable for the add-on settings,
			# which can be accessed from methods that have no "context" parameter
			self.addon_settings = self.scene.addon_settings

			# initialize the rendering job variables
			self.job = RenderJob(self.scene, self.animation)

			# copy the attributes of the original bpy.types.RenderSettings object
			for key in dir(self.scene.render):
				# if the attribute is one of the following types: bool, int, float, str, list, dict
				if not "__" in key and isinstance(getattr(self.scene.render, key), (bool, int, float, str, list, dict)):
					setattr(self, key, getattr(self.scene.render, key))



			# SPECIFIC SCENE SETTINGS
			# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
			# NOTE: These are specific keys that are not inside the bpy.types.RenderSettings
			# 		object, but in the bpy.types.Scene object and which are relevant
			#		for the rendering process
			for key in dir(self.scene):
				# if the attribute is one of the following types: bool, int, float, str, list, dict
				if key in self.specific_keys:
					setattr(self, key, getattr(self.scene, key))



			# DEVICE SETTINGS
			# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
			# get active Looking Glass
			if self.addon_settings.render_use_device == True and pylio.DeviceManager.get_active():
				self._device = pylio.DeviceManager.get_active()

			# or the selected emulated device
			elif self.addon_settings.render_use_device == False:
				self._device = pylio.DeviceManager.get_device(key="index", value=int(self.addon_settings.render_device_type))

			# get all quilt presets from pylio
			self._qs = pylio.LookingGlassQuilt.formats.get()



			# PATH SETTINGS
			# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

			# set scene and path settings from current user settings
			self.filepath = self.scene.render.filepath

			# set the lockfile path
			self.job.lockfile_path = bpy.path.abspath(LookingGlassAddon.tmp_path + os.path.basename(bpy.data.filepath) + ".lock")



			# ORIGINAL SETTINGS
			# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

			# store a copy of the original bpy.types.RenderSettings as a
			# dictionary for recovery
			self.original = self.copy()



			# RENDER JOB SETTINGS
			# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
			# if the lockfile shall be used
			if self.use_lockfile == True:

				try:

					# read the settings from the lockfile
					self.read_from_lockfile()

					# make sure the render job will be initalized correctly
					self.job.init = True

				except:

					# reset global and local status variables
					LookingGlassAddon.has_lockfile = False
					self.use_lockfile = False

					# notify user
					LookingGlassAddonLogger.error("Render job can not be continued. Lockfile not found or corrupted.")

					# don't execute operator
					return None


			# if the lockfile shall not be used
			elif self.use_lockfile == False:

				# settings of the current preset
				self.job.view_width = self._qs[int(self.addon_settings.render_quilt_preset)]["view_width"]
				self.job.view_height = self._qs[int(self.addon_settings.render_quilt_preset)]["view_height"]
				self.job.rows = self._qs[int(self.addon_settings.render_quilt_preset)]["rows"]
				self.job.columns = self._qs[int(self.addon_settings.render_quilt_preset)]["columns"]
				self.job.total_views = self._qs[int(self.addon_settings.render_quilt_preset)]["total_views"]

				# if the operator was called with the animation flag set
				if self.animation == True:

					# set the rendering frame variable to the first frame of the scene
					self.job.frame = self.scene.frame_start

				else:

					# set the rendering frame variable to the currently active frame
					self.job.frame = self.scene.frame_current

				# apply device view cone
				self.job.view_cone = self._device.viewCone

				# apply the correct quilt aspect ratio
				self.job.quilt_aspect = self._device.aspect

				# write the lockfile
				self.write_to_lockfile()

		elif self.scene is not None:

			# raise an exception
			raise AttributeError("Could not initialize render settings. The given object '%s' was no bpy.types.Scene object." % self.scene)


	# TODO: Clean this method up and add comments
	# convert the object to a nested dictionary
	# NOTE: This function is largely taken from https://stackoverflow.com/a/1118038
	def to_dict(self, obj, classkey=None):
		if isinstance(obj, dict):
			data = {}
			for (k, v) in obj.items():
				data[k] = self.to_dict(v, classkey)
			return data
		elif isinstance(obj, LookingGlassAddonSettings):
			data = {}
			for key in dir(obj):
				if not callable(getattr(obj, key)) and not key.startswith('_'):
					if key not in ['bl_rna', 'rna_type', 'blender_view3d']:
						value = self.to_dict(getattr(obj, key))
						data[key] = value
			return data
		elif isinstance(obj, type(self.scene.eevee)) or isinstance(obj, type(self.scene.cycles)) or isinstance(obj, type(self.scene.cycles_curves)):
			data = {}
			for key in dir(obj):
				if not callable(getattr(obj, key)) and not key.startswith('_'):
					if key not in ['bl_rna', 'rna_type']:
						value = self.to_dict(getattr(obj, key))
						data[key] = value
			return data
		elif hasattr(obj, "_ast"):
			return self.to_dict(obj._ast())
		elif hasattr(obj, "__iter__") and not isinstance(obj, str):
			try:
				return [self.to_dict(v, classkey) for v in obj]
			except:
				LookingGlassAddonLogger.error("Could not serialize object:", obj)
		elif hasattr(obj, "__dict__"):
			data = dict([(key, self.to_dict(value, classkey))
			for key, value in obj.__dict__.items()
			if not callable(value) and not key.startswith('_')])
			if classkey is not None and hasattr(obj, "__class__"):
				data[classkey] = obj.__class__.__name__
			return data
		elif hasattr(obj, "_asdict"):
			return to_dict(obj._asdict())
		elif hasattr(obj, "name"):
			return obj.name
		elif isinstance(obj, (bool, int, float, str, list)):
			return obj
		else:
			return None

	# read the settings from a dict
	def from_dict(self, object, dictionary):

		# read the settings
		for key, value in dictionary.items():

			# if this is the scene object
			if key == "scene" and value is not None:

				# read the
				setattr(object, key, bpy.data.scenes[value])

			# if this is the quiltImage object
			elif key == "quiltImage" and value is not None:

				# read the
				setattr(object, key, bpy.data.images[value])

			# if this is the lookingglassCamera object
			elif key == "lookingglassCamera" and value is not None:

				# read the
				setattr(object, key, bpy.data.objects[value])

			# if this key contains a dictionary AND the original value is not a dictionary
			elif isinstance(value, dict) and not isinstance(getattr(object, key), dict):

				# read the data recursively
				self.from_dict(getattr(object, key), value)

			# if this is one of the standard types
			elif isinstance(value, (bool, int, float, str, list, dict)):

				try:

					# read the
					setattr(object, key, value)

				except:

					LookingGlassAddonLogger.warning("Could not set key '%s'. Instead using value '%s'" % (key, str(getattr(object, key))))

	# write the render settings to the lockfile
	def write_to_lockfile(self):

		# if the current blender session has a file
		if bpy.data.filepath != "":

			# if no temp directory exists in the add-on path, create one
			if os.path.exists(LookingGlassAddon.tmp_path) == False:
				os.mkdir(LookingGlassAddon.tmp_path)

			# if the temp directory exists now
			if os.path.exists(LookingGlassAddon.tmp_path) == True:

				# create the lockfile there
				lockfile = open(self.job.lockfile_path, 'wt')
				if lockfile != None:

					# get dictionary of settings
					settings_dict = self.to_dict(self)

					# add some custom values to the dict
					settings_dict['blend_file'] = bpy.data.filepath
					#pprint(settings_dict)

					# write the date to the lock file
					lockfile.write(json.dumps(settings_dict))

					# close file
					lockfile.close()

				else:

					# log warning
					LookingGlassAddon.warning("Could not create lockfile. Quilt render continuation is turned off for this rendering process.")

			else:

				# log warning
				LookingGlassAddon.warning("Could not find/create temporary folder in add-on directory. Quilt render continuation is turned off for this rendering process.")

		else:

			# log warning
			LookingGlassAddon.warning("No blender file exists. Quilt render continuation is turned off for this rendering process.")


	# read the render settings from the lockfile
	def read_from_lockfile(self):

		# read the lockfile data
		lockfile = open(self.job.lockfile_path, 'rt')
		if lockfile != None:

			# read the data from the obtained dictionary
			self.from_dict(self, json.load(lockfile))

			# apply loaded settings to the scene
			self.apply_to_scene(self.scene)

			# close file
			lockfile.close()

			return True

		else:

			# log warning
			LookingGlassAddon.error("Could not open lockfile.")

			return False


	# apply this RenderSettings to the given scene
	def apply_to_scene(self, BlenderScene):

		# if a valid scene object was given
		if type(BlenderScene) == bpy.types.Scene:

			# set the attributes of the given scene
			for key in dir(self):

				# GENERAL RENDER SETTINGS
				# +++++++++++++++++++++++++++++++
				# if the attribute is one of the following types: bool, int, float, str, list, dict
				if not ("__" in key or key == "job" or key in self.specific_keys) and isinstance(getattr(self, key), (bool, int, float, str, list, dict)):
					try:
						setattr(BlenderScene.render, key, getattr(self, key))
					except:
						pass

				# SPECIFIC SETTINGS
				# +++++++++++++++++++++++++++++++
				# for EEVEE
				elif key in self.specific_keys:
					try:
						setattr(BlenderScene, key, getattr(self, key))
					except:
						pass

	# apply this RenderSettings to the given scene
	def copy(self):

		# return a copy
		return self.to_dict(self)

	# restore the original values of the copied bpy.types.RenderSettings attributes
	def restore_original(self):

		# load the original settings into the calling RenderSettings object
		self.from_dict(self, self.original)

		# apply these settings to the scene
		self.apply_to_scene(self.scene)


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

	# render settings
	render_settings = None

	# camera settings
	camera_temp_name = '_quilt_render_cam'
	camera_temp = None
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

	# CALLBACK FUNCTIONS:
	# +++++++++++++++++++++++++++++++++++++++++++++++
	def init_render(self, Scene, depsgraph):

		# reset the operator state to IDLE
		if self.operator_state != "CANCEL_RENDER": self.operator_state = "INIT_RENDER"

		LookingGlassAddonLogger.info("Rendering job initialized.")


		# GET THE PIXEL DATA OF THE RENDERED VIEWS
		# ++++++++++++++++++++++++++++++++++++++++++++
		# if the lockfile shall be used AND this is the first render
		if (self.use_lockfile == True and self.render_settings.job.init == True):

			# set current frame
			frame = self.render_settings.job.frame

			# iterate through all views
			for view in range(0, self.render_settings.job.total_views):

				# if this view was already rendered
				if view <= self.render_settings.job.view:

					# if the file exists
					if os.path.exists(self.render_settings.job.view_filepath(view)):

						# load the view image
						self.viewImage = bpy.data.images.load(self.render_settings.job.view_filepath(view))

						# store the pixel data in an numpy array
						# NOTE: we use foreach_get, since this is significantly faster
						tmp_pixels = np.empty(len(self.viewImage.pixels), np.float32)
						self.viewImage.pixels.foreach_get(tmp_pixels)

						# append the pixel data to the list of views
						self.viewImagesPixels.append(tmp_pixels)

						# if this was the last view
						if self.render_settings.job.view == (self.render_settings.job.total_views - 1):

							# NOTE: Creating a new image via the dedicated operators and methods
							# 		didn't apply the correct image formats and settings
							#		and therefore, we use the created image
							self.viewImage.scale(self.render_settings.scene.render.resolution_x * self.render_settings.job.columns, self.render_settings.scene.render.resolution_y * self.render_settings.job.rows)

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

			# reset status variable
			self.use_lockfile = False

		# Some status infos
		# if a single frame shall be rendered
		if self.animation == False:

			# notify user
			self.report({"INFO"},"Rendering view " + str(self.render_settings.job.view + 1) + "/" + str(self.render_settings.job.total_views) + " ...")

		# if an animation shall be rendered
		elif self.animation == True:

			# notify user
			self.report({"INFO"},"Rendering view " + str(self.render_settings.job.view + 1) + "/" + str(self.render_settings.job.total_views) + " of frame " + str(self.render_settings.job.frame) +  " ...")


	# function that is called before rendering starts
	def pre_render(self, Scene, depsgraph):

		# reset the operator state to PRE_RENDER
		if self.operator_state != "CANCEL_RENDER": self.operator_state = "PRE_RENDER"

		LookingGlassAddonLogger.info("Rendering view is going to be prepared.")

		# output current status
		LookingGlassAddonLogger.info(" [#] active camera: %s" % self.camera_active)
		LookingGlassAddonLogger.info(" [#] current frame: %s" % self.render_settings.job.frame)
		LookingGlassAddonLogger.info(" [#] current subframe: %s" % self.render_settings.job.subframe)
		LookingGlassAddonLogger.info(" [#] current view: %s" % self.render_settings.job.view)
		LookingGlassAddonLogger.info(" [#] current quilt file: %s" % self.render_settings.job.quilt_filepath())
		LookingGlassAddonLogger.info(" [#] current view file: %s" % self.render_settings.job.view_filepath())


	# function that is called after rendering finished
	def post_render(self, Scene, depsgraph):

		# reset the operator state to PRE_RENDER
		if self.operator_state != "CANCEL_RENDER": self.operator_state = "POST_RENDER"

		LookingGlassAddonLogger.info("Saving view file: %s" % self.render_settings.job.view_filepath())

		# STORE THE PIXEL DATA OF THE RENDERED IMAGE
		# ++++++++++++++++++++++++++++++++++++++++++++
		# save the rendered image in a file
		bpy.data.images["Render Result"].save_render(filepath=self.render_settings.job.view_filepath(), scene=self.render_settings.scene)

		# load the view image
		self.viewImage = bpy.data.images.load(filepath=self.render_settings.job.view_filepath())

		# TODO: Would be good to implement the quilt assembly via pyLightIO
		#
		# store the pixel data in an numpy array
		# NOTE: we use foreach_get, since this is significantly faster
		tmp_pixels = np.empty(len(self.viewImage.pixels), np.float32)
		self.viewImage.pixels.foreach_get(tmp_pixels)

		# append the pixel data to the list of views
		self.viewImagesPixels.append(tmp_pixels)

		# delete the Blender image of this view
		bpy.data.images.remove(self.viewImage)

	# function that is called when the renderjob is completed
	def completed_render(self, Scene, depsgraph):

		# reset the operator state to COMPLETE_RENDER
		if self.operator_state != "CANCEL_RENDER": self.operator_state = "COMPLETE_RENDER"

		# the initialization step was done
		self.render_settings.job.init = False

	# function that is called if rendering was cancelled
	def cancel_render(self, Scene, depsgraph):

		# set operator state to CANCEL
		self.operator_state = "CANCEL_RENDER"

		LookingGlassAddonLogger.info("Rendering job was cancelled.")




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




	# OPERATOR:
	# +++++++++++++++++++++++++++++++++++++++++++++++
	# check if everything is correctly set up for the quilt rendering
	@classmethod
	def poll(self, context):

		# # if a device is active
		# if pylio.DeviceManager.get_active():

		# return True, so the operator is executed
		return True

		# else:
		#
		# 	# notify user
		# 	self.report({"ERROR"}, "Cannot determine proper render settings, if no device is selected.")
		#
		# 	# return False, so the operator is executed
		# 	return False



	# delete the files
	def delete_files(self, frame=None):

		# for all views of the given frame
		for view in range(0, self.render_settings.job.total_views):

			# delete this file, if it exists
			if os.path.isfile(self.render_settings.job.view_filepath(view, frame)):
				os.remove(self.render_settings.job.view_filepath(view, frame))

		# delete the quilt file, if the user initially specified no file name
		# NOTE: This is done, because this is Blenders behavior for normal renders
		#		if no filename is specifed
		file_dirname, file_basename = os.path.split(self.render_settings.job.outputpath)
		if not file_basename:

			# delete this file, if it exists
			if os.path.isfile(self.render_settings.job.quilt_filepath(frame)):
				os.remove(self.render_settings.job.quilt_filepath(frame))


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
		if ((self.render_settings.addon_settings.render_output == '1' or (not ((self.animation == False and ("Quilt Render Result" in self.render_settings.job.file_basename) == False) or self.animation == True))) and self.force_keep == False) or self.discard_lockfile == True:

			LookingGlassAddonLogger.info("Cleaning up the disk files.")

			# if it was an animation
			if self.animation == True:

				# for all frames of the animation
				for frame in range(self.render_settings.scene.frame_start, self.render_settings.scene.frame_end + self.render_settings.frame_step):

					# delete views
					self.delete_files(frame)

			# if it was a still image
			elif self.animation == False:

				#  delete its views
				self.delete_files()



		# RESTORE USER SETTINGS
		# +++++++++++++++++++++++++
		# if this call was not just invoked to discard an incomplete render job
		if self.discard_lockfile == False:

			# CAMERA
			# delete the temporarily created camera
			bpy.data.objects.remove(bpy.data.objects[self.camera_temp_name], do_unlink=True, do_id_user=True, do_ui_user=True)

			# restore the original active camera
			self.render_settings.scene.camera = self.camera_original


			# RENDER SETTINGS
			# restore original render settings
			self.render_settings.restore_original()



		# DELETE LOCKFILE
		# ++++++++++++++++++++++++++++++++++
		# if a lockfile exists, delete it
		if os.path.exists(self.render_settings.job.lockfile_path) == True:
			os.remove(self.render_settings.job.lockfile_path)

		# reset global and local status variables
		LookingGlassAddon.has_lockfile = False
		self.use_lockfile = False



		# RESET STATUS VARIABLES FOR PROGRESSBAR
		# ++++++++++++++++++++++++++++++++++
		self.render_settings.addon_settings.render_progress = 0.0
		LookingGlassAddon.RenderInvoked = False
		LookingGlassAddon.RenderAnimation = None

		# return None since this is expected by the operator
		return None



	# invoke the modal operator
	def invoke(self, context, event):

		# RENDER SETTINGS
		################################################################
		# we handle the render settings in a separate class
		# NOTE: This class also stores the original settings and provides a
		#		restore_original() method to restore the scenes original render
		#		settings after the render job is done
		self.render_settings = RenderSettings(bpy.context.scene, self.use_lockfile, self.animation)

		# if a lockfile should be loaded
		if self.use_lockfile:
			if self.render_settings is None:

				# notify user
				self.report({"ERROR"}, "Render job can not be continued. Lockfile not found or corrupted.")

				# cancel the operator
				# NOTE: - this includes deleting all view files
				self.cancel(context)

				# don't execute operator
				return {'CANCELLED'}

			else:

				# apply the animation flag of the RenderSettings
				# NOTE: This is done, since the lockfile's "animation" flag should be used
				self.animation = self.render_settings.animation



		# VALIDATE PATH AND FILENAME
		################################################################

		# check if a valid path is given in output settings
		if self.render_settings.use_file_extension == True:

			if not os.path.exists(os.path.dirname(self.render_settings.job.quilt_filepath())):

				# notify user
				self.report({"ERROR"}, "Output path " + self.render_settings.job.quilt_filepath() + " is not a valid path. Please change the output path in the render settings.")

				# don't execute operator
				return {'FINISHED'}

			# if the file already exists and should not be overwritten
			elif not self.render_settings.use_overwrite and os.path.exists(self.render_settings.job.quilt_filepath()):

				# notify user
				self.report({"ERROR"}, "Specified file '" + self.render_settings.job.quilt_filepath() + "' already exists. Please change the output path in the render settings.")

				# don't execute operator
				return {'FINISHED'}

			# if a file extension was given and does not fit to the expected extension
			elif self.render_settings.job.file_extension and self.render_settings.file_extension != self.render_settings.job.file_extension:

				# notify user
				self.report({"ERROR"}, "Specified file extension '" + self.render_settings.job.file_extension + "' does not fit to expected one. Please change the output path in the render settings.")

				# don't execute operator
				return {'FINISHED'}

		elif self.render_settings.use_file_extension == False:

			# was a file extension entered by the user?
			if not self.render_settings.job.file_extension:

				# if not, notify user
				self.report({"ERROR"}, "Output path '" + self.render_settings.job.quilt_filepath() + "' is missing a valid file extension.")

				# don't execute operator
				return {'FINISHED'}

			# if a file extension was given and does not fit to the expected extension
			elif self.render_settings.job.file_extension and self.render_settings.file_extension != self.render_settings.job.file_extension:

				# notify user
				self.report({"ERROR"}, "Specified file extension '" + self.render_settings.job.file_extension + "' does not fit to expected one. Please change the output path in the render settings.")

				# don't execute operator
				return {'FINISHED'}

			else:

				# is a valid directory path given?
				if not os.path.exists(os.path.dirname(self.render_settings.job.quilt_filepath())):

					# if not, notify user
					self.report({"ERROR"}, "Output path '" + self.render_settings.job.quilt_filepath() + "' is not a valid path. Please change the output path in the render settings.")

					# don't execute operator
					return {'FINISHED'}

				# if the file already exists and should not be overwritten
				elif not self.render_settings.use_overwrite and os.path.exists(self.render_settings.job.quilt_filepath()):

					# notify user
					self.report({"ERROR"}, "Specified file '" + self.render_settings.job.quilt_filepath() + "' already exists. Please change the output path in the render settings.")

					# don't execute operator
					return {'FINISHED'}


		# check if the directory is accessible
		# NOTE: One could use os.access, but with regard to documentation,
		#		the following is more pythonic and more reliable
		try:

			# try to create the file
			test_file = open(self.render_settings.job.quilt_filepath(), 'w')
			test_file.close()

			# remove the file again
			os.remove(self.render_settings.job.quilt_filepath())

		except IOError:

			# if not, notify user
			self.report({"ERROR"}, "Cannot write to '" + self.render_settings.job.file_dirname + "'. Please change the output path in the render settings.")

			# don't execute operator
			return {'FINISHED'}



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

		# TODO: Maybe shift this to the RenderSettings class and change the
		#		self.resolution_x variables etc. and apply them to the scene
		#		-> might be more congruent with the rest of the code?
		# VIEW RESOLUTION SETTINGS
		# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
		# apply the render resolution to Blender render settings
		self.render_settings.scene.render.resolution_x = self.render_settings.job.view_width
		self.render_settings.scene.render.resolution_y = self.render_settings.job.view_height

		# set the render percentage to 100%
		self.render_settings.scene.render.resolution_percentage = 100

		# for landscape formatted devices
		if (self.render_settings.scene.render.resolution_x / self.render_settings.scene.render.resolution_y) / self.render_settings._device.aspect > 1:

			# apply the correct aspect ratio
			self.render_settings.scene.render.pixel_aspect_x = 1.0
			self.render_settings.scene.render.pixel_aspect_y = self.render_settings.scene.render.resolution_x / (self.render_settings.scene.render.resolution_y * self.render_settings._device.aspect)

		# for portrait formatted devices
		else:

			# apply the correct aspect ratio
			self.render_settings.scene.render.pixel_aspect_x = (self.render_settings.scene.render.resolution_y * self.render_settings._device.aspect) / self.render_settings.scene.render.resolution_x
			self.render_settings.scene.render.pixel_aspect_y = 1.0

		# keep the modal operator running
		return {'RUNNING_MODAL'}



	# modal operator for controlled redrawing of the lightfield
	def modal(self, context, event):

		LookingGlassAddonLogger.debug("Current operator state: %s" % self.operator_state)

		# if the TIMER event for the quilt rendering is called
		if event.type == 'TIMER':

			# INVOKE NEW RENDER JOB
			# ++++++++++++++++++++++++++++++++++
			if self.operator_state == "INVOKE_RENDER":

				# make sure the interface is not locked
				# otherwise the renderjob won't be excecuted properly.
				# Unclear why, but maybe because the camera settings will not
				# be applied properly then. Solved issue:
				# https://github.com/regcs/AliceLG-beta/issues/9
				self.render_settings.use_lock_interface = False

				# log debug info
				LookingGlassAddonLogger.debug("Invoking new render job.")

				# FRAME AND VIEW
				# ++++++++++++++++++++++
				# set the current frame to be rendered
				self.render_settings.scene.frame_set(self.render_settings.job.frame, subframe=self.render_settings.job.subframe)

				# get the subframe, that will be rendered
				self.render_settings.job.subframe = self.render_settings.scene.frame_subframe

				# CYCLES: RANDOMIZE SEED
				# ++++++++++++++++++++++
				# NOTE: This randomizes the noise pattern from view to view.
				#		In theory, this enables a higher quilt quality at lower
				#		render sampling rates due to the overlap of views in the
				#		Looking Glass.
				if self.render_settings.engine == "CYCLES":

					# if this is the first view of the current frame
					if self.render_settings.job.view == 0:

						# use the user setting as seed basis
						self.render_settings.job.seed = self.render_settings.scene.cycles.seed

					# if the "use_animated_seed" option is active,
					if self.render_settings.scene.cycles.use_animated_seed:

						# increment the seed value with th frame number AND the view number
						self.render_settings.scene.cycles.seed = self.render_settings.job.seed + self.render_settings.job.frame + self.render_settings.job.view

					else:

						# increment the seed value only with the view number
						self.render_settings.scene.cycles.seed = self.render_settings.job.seed + self.render_settings.job.view

				# STORE USER CAMERA SETTINGS
				# ++++++++++++++++++++++++++++++++++

				# if this is the first view of this render job
				# NOTE: - we do it this way in case the camera is animated and its position changes each frame
				if self.render_settings.job.init == True:

					# use the camera selected by the user for the Looking Glass
					self.camera_active = self.render_settings.addon_settings.lookingglassCamera

					# remember the origingally active camera of the scene
					self.camera_original = self.render_settings.scene.camera

					# CAMERA SETTINGS: GET VIEW & PROJECTION MATRICES
					# +++++++++++++++++++++++++++++++++++++++++++++++

					# get camera's modelview matrix
					self.view_matrix = self.camera_active.matrix_world.copy()

					# correct for the camera scaling
					self.view_matrix = self.view_matrix @ Matrix.Scale(1/self.camera_active.scale.x, 4, (1, 0, 0))
					self.view_matrix = self.view_matrix @ Matrix.Scale(1/self.camera_active.scale.y, 4, (0, 1, 0))
					self.view_matrix = self.view_matrix @ Matrix.Scale(1/self.camera_active.scale.z, 4, (0, 0, 1))

					# calculate the inverted view matrix because this is what the draw_view_3D function requires
					self.view_matrix_inv = self.view_matrix.inverted_safe()

					# remember the original settings of the Looking Glass camera
					self.camera_original_location = self.view_matrix.decompose()[0]# self.camera_active.location.copy()
					self.camera_original_shift_x = self.camera_active.data.shift_x
					self.camera_original_sensor_fit = self.camera_active.data.sensor_fit

					# COPY CAMERA
					# +++++++++++++++++++++++++++++++++++++++++++++++
					# create a new, temporary camera using a copy of the
					# originals camera data
					self.camera_temp = bpy.data.objects.new(self.camera_temp_name, self.camera_active.data.copy())

					# NOTE: It seems not to be required. Rendering still works,
					#		which is nice, because the camera remains invisible
					# # add this camera to the master collection of the scene
					# self.render_settings.scene.collection.objects.link(self.camera_temp)

					# use this camera for rendering
					self.camera_active = self.camera_temp

					# apply same location and perspective like the original camera
					self.camera_active.matrix_world = self.view_matrix.copy()

					# set the scenes active camera to this temporary camera
					self.render_settings.scene.camera = self.camera_active


				# CAMERA SETTINGS: APPLY POSITION AND SHIFT
				# +++++++++++++++++++++++++++++++++++++++++++++++
				# adjust the camera settings to the correct view point
				# The field of view set by the camera
				# NOTE 1: - the Looking Glass Factory documentation suggests to use a FOV of 14°. We use the focal length of the Blender camera instead.
				fov = self.camera_active.data.angle

				# calculate cameraSize from its distance to the focal plane and the FOV
				cameraDistance = self.render_settings.addon_settings.focalPlane
				cameraSize = cameraDistance * tan(fov / 2)

				# start at view_cone * 0.5 and go up to -view_cone * 0.5
				offsetAngle = (0.5 - self.render_settings.job.view / (self.render_settings.job.total_views - 1)) * radians(self.render_settings.job.view_cone)

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




			# COMPLETE-RENDER STEP
			# ++++++++++++++++++++++++++++++++++

			# if nothing is rendering, but the last view is not yet rendered
			elif self.operator_state == "COMPLETE_RENDER":

				# QUILT ASSEMBLY
				# ++++++++++++++++++++++++++++++++++++++++++++
				# if this was the last view
				if self.render_settings.job.view == (self.render_settings.job.total_views - 1):
					start = time.time()

					# TODO: Would be good to implement the quilt assembly via pyLightIO
					#
					# then assemble the quilt from the views
					verticalStack = []
					horizontalStack = []
					for row in range(0, self.render_settings.job.rows, 1):
						for column in range(0, self.render_settings.job.columns, 1):

							# get pixel data and reshape into a reasonable format for stacking
							viewPixels = self.viewImagesPixels[row * self.render_settings.job.columns + column]
							viewPixels = viewPixels.reshape((self.render_settings.scene.render.resolution_y, self.render_settings.scene.render.resolution_x, 4))

							# append the pixel data to the current horizontal stack
							horizontalStack.append(viewPixels)

						# append the complete horizontal stack to the vertical stacks
						verticalStack.append(np.hstack(horizontalStack.copy()))

						# clear this horizontal stack
						horizontalStack.clear()

					# reshape the pixel data of all images into the quilt shape
					quiltPixels = np.vstack(verticalStack.copy())
					quiltPixels = np.reshape(quiltPixels, (self.render_settings.job.columns * self.render_settings.job.rows * (self.render_settings.scene.render.resolution_x * self.render_settings.scene.render.resolution_y * 4)))


					# copy the viewfile
					shutil.copy(self.render_settings.job.view_filepath(), self.render_settings.job.quilt_filepath())

					# load the view image
					self.quiltImage = bpy.data.images.load(filepath=self.render_settings.job.quilt_filepath())

					# NOTE: Creating a new image via the dedicated operators and methods
					# 		didn't apply the correct image formats and settings
					#		and therefore, we use the created image
					self.quiltImage.scale(self.render_settings.scene.render.resolution_x * self.render_settings.job.columns, self.render_settings.scene.render.resolution_y * self.render_settings.job.rows)

					# apply the assembled quilt pixel data
					self.quiltImage.pixels.foreach_set(quiltPixels)

					# set "view as render" based on the image format
					if self.quiltImage.file_format == 'OPEN_EXR_MULTILAYER' or self.quiltImage.file_format == 'OPEN_EXR':
						self.quiltImage.use_view_as_render = True
					else:
						self.quiltImage.use_view_as_render = False

					# save the quilt in a file
					self.quiltImage.save() #scene=self.render_settings.scene)

					# log debug info
					LookingGlassAddonLogger.debug("Saved quilt file to: " + self.quiltImage.filepath)



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

											break



				# UPDATE PROGRESS BAR
				# +++++++++++++++++++++++++++++++++++++++++++
				# if a single frame shall be rendered
				if self.animation == False:
					self.render_settings.addon_settings.render_progress = int(self.render_settings.job.view / ((self.render_settings.job.total_views - 1)) * 100)
				else:
					self.render_settings.addon_settings.render_progress = int(((self.render_settings.job.frame - self.render_settings.scene.frame_start) * (self.render_settings.job.total_views - 1) + self.render_settings.job.view) / ((self.render_settings.job.total_views - 1) * (self.render_settings.scene.frame_end - self.render_settings.scene.frame_start + 1)) * 100)



				# UPDATE LOCKFILE
				# +++++++++++++++++++++++++++++++++++++++++++
				# if the lockfile exists
				if self.render_settings.job.lockfile_path != None and os.path.exists(self.render_settings.job.lockfile_path) == True:

					# open the lockfile and read it
					self.render_settings.write_to_lockfile()



				# VIEW & FRAME RENDERING
				# ++++++++++++++++++++++++++++++++++++++++++++
				# if a single frame shall be rendered
				if self.animation == False:

					# if this was not the last view
					if self.render_settings.job.view < (self.render_settings.job.total_views - 1):

						# increase view count
						self.render_settings.job.view += 1

						# reset the operator state to IDLE
						self.operator_state = "INVOKE_RENDER"

					# if this was the last view
					else:

						# cancel the operator
						self.operator_state = "CANCEL_RENDER"

						# notify user
						self.cancel_sign = "INFO"
						self.cancel_message = "Complete quilt rendered."

				# if an animation shall be rendered
				elif self.animation == True:

					# if this was not the last view
					if self.render_settings.job.view < (self.render_settings.job.total_views - 1):

						# increase view count
						self.render_settings.job.view += 1

						# reset the operator state to IDLE
						self.operator_state = "INVOKE_RENDER"

					# if this was the last view
					elif self.render_settings.job.view == (self.render_settings.job.total_views - 1):

						# but if this was not the last frame
						if self.render_settings.job.frame < self.render_settings.scene.frame_end:

							# if the view files shall not be kept
							if ((self.render_settings.addon_settings.render_output == '1') and self.force_keep == False):

								# delete views of the rendered frame
								self.delete_files(self.render_settings.job.frame)

							# delete the temporarily created camera
							bpy.data.objects.remove(bpy.data.objects[self.camera_temp_name], do_unlink=True, do_id_user=True, do_ui_user=True)

							# restore the original active camera
							self.render_settings.scene.camera = self.camera_original

							# reset the initialization step variable
							self.render_settings.job.init = True

							# reset the rendering view variable
							self.render_settings.job.view = 0

							# increase frame count
							self.render_settings.job.frame = self.render_settings.job.frame + self.render_settings.frame_step

							# clear the pixel data
							self.viewImagesPixels.clear()

							# CYCLES SPECIFIC
							if self.render_settings.engine == "CYCLES":

								# restore seed setting
								self.render_settings.scene.cycles.seed = self.render_settings.job.seed

							# reset the operator state to IDLE
							self.operator_state = "INVOKE_RENDER"

						# if this was the last frame
						else:

							# cancel the operator
							self.operator_state = "CANCEL_RENDER"

							# notify user
							self.cancel_sign = "INFO"
							self.cancel_message = "Complete animation quilt rendered."

				# log debug info
				LookingGlassAddonLogger.debug("Render job completed.")


			# CANCEl-RENDER STEP
			# ++++++++++++++++++++++++++++++++++

			# if nothing is rendering, but the last view is not yet rendered
			elif self.operator_state == "CANCEL_RENDER":

				# log debug info
				LookingGlassAddonLogger.debug("Render job cancelled.")

				# cancel the operator
				# NOTE: - this includes recovering all original user settings
				self.cancel(context)

				# notify user
				self.report({self.cancel_sign}, self.cancel_message)
				return {"CANCELLED"}



		# pass event through
		return {'PASS_THROUGH'}
