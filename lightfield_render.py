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
# This includes everything that is related the quilt rendering

# ------------------ INTERNAL MODULES --------------------
from .globals import *
from .ui import LookingGlassAddonSettings

# ------------------- EXTERNAL MODULES -------------------
import bpy
import time
import sys, os, platform, shutil, json
import numpy as np
from math import *
from mathutils import *

# append the add-on's path to Blender's python PATH
sys.path.insert(0, LookingGlassAddon.path)
sys.path.insert(0, LookingGlassAddon.libpath)

# TODO: Would be better, if from .lib import pylightio could be called,
#		but for some reason that does not import all modules and throws
#		"AliceLG.lib.pylio has no attribute 'lookingglass'"
import pylightio as pylio

# ---------------- GLOBAL ADDON LOGGER -------------------
import logging
LookingGlassAddonLogger = logging.getLogger('Alice/LG')

# ------------------ QUILT RENDERING --------------------
# a class whose instances will store the variables required to control the
# internal rendering jobs
class RenderJob:

	def __init__(self, scene, animation, use_lockfile, use_multiview, blocking):

		# INITIALIZE ATTRIBUTES
		# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
		# NOTE: Attributes with a leading "_" won't be saved in the lockfile

		# general attributes
		self.init = True
		self.add_suffix = False
		self.scene = scene
		self.animation = animation
		self._use_lockfile = use_lockfile
		self.use_multiview = use_multiview
		self.blocking = blocking

		# render job control attributes
		self._state = 'INVOKE_RENDER' # possible states: 'INVOKE_RENDER', 'INIT_RENDER', 'PRE_RENDER', 'POST_RENDER', 'COMPLETE_RENDER', 'CANCEL_RENDER''IDLE'
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

		# path attributes
		self.lockfile_path = None
		self.outputpath = None
		self.file_use_temp = False
		self.file_temp_name = "Quilt Render Result"
		self.file_dirname = None
		self.file_basename = None
		self.file_extension = None
		self.file_quilt_suffix = None
		self.file_force_keep = False

		# camera attributes
		self._camera_temp_basename = '_quilt_render_cam'
		self._camera_temp = []
		self._camera_active = None
		self._camera_original = None
		self._multiview_view_basename = 'quilt_v'
		self._view_matrix = None
		self._view_matrix_inv = None

		# image attributes
		self._view_image = None
		self._view_images_pixels = []
		self._quilt_image = None

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

				# use temporary files
				self.file_use_temp = True
				self.file_basename, self.file_extension = (self.file_temp_name, bpy.context.scene.render.file_extension)


	# FILE PATH HANDLING
	# ++++++++++++++++++++++++++++++++++
	# return the filename of the quilt file
	def get_quilt_suffix(self):

		# metadata for HoloPlay Studio etc. is stored in the file name as a suffix
		# example of the format convention: quiltfilename_qs5x9a1.6.png
		if self.add_suffix:
			if len(str(self.quilt_aspect)) > 3:
				return f'_qs{self.columns}x{self.rows}a{self.quilt_aspect:.2f}'
			else:
				return f'_qs{self.columns}x{self.rows}a{self.quilt_aspect}'
		else:
			return ''

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


	# RENDER JOB HANDLING
	# ++++++++++++++++++++++++++++++++++
	# invoke a new render job
	def invoke(self):

		# if this is the first view of this render job
		# NOTE: - we do it this way in case the camera is animated and its position changes each frame
		if self.init:

			# log debug info
			LookingGlassAddonLogger.debug("Invoking new render job.")

			# FRAME AND VIEW
			# ++++++++++++++++++++++
			# set the current frame to be rendered
			self.scene.frame_set(self.frame, subframe=self.subframe)

			# get the subframe, that will be rendered
			self.subframe = self.scene.frame_subframe

		# CYCLES: RANDOMIZE SEED
		# ++++++++++++++++++++++
		# NOTE: This randomizes the noise pattern from view to view.
		#		In theory, this enables a higher quilt quality at lower
		#		render sampling rates due to the overlap of views in the
		#		Looking Glass.
		if self.scene.render.engine == "CYCLES":

			# if this is the first view of the current frame
			if self.view == 0:

				# use the user setting as seed basis
				self.seed = self.scene.cycles.seed

			# if the "use_animated_seed" option is active,
			if self.scene.cycles.use_animated_seed:

				# increment the seed value with th frame number AND the view number
				self.scene.cycles.seed = self.seed + self.frame + self.view

			else:

				# increment the seed value only with the view number
				self.scene.cycles.seed = self.seed + self.view

		# FILEPATH
		# ++++++++++++++++++++++

		# SINGLE-CAMERA RENDERING
		if not self.use_multiview:

			# set the current quilt filepath
			bpy.context.scene.render.filepath = self.view_filepath()

		# SINGLE-CAMERA RENDERING
		elif self.use_multiview:

			# set the current quilt filepath
			bpy.context.scene.render.filepath = self.quilt_filepath()


		# CAMERA SETUP
		# ++++++++++++++++++++++
		self.setup_camera()

		# update status variable
		self.init = False

	# setup the camera (system) for rendering
	def setup_camera(self):

		# SINGLE-CAMERA RENDERING
		# ++++++++++++++++++++++++++++++++++
		if not self.use_multiview:

			# if this is the first view of this render job
			# NOTE: - we do it this way in case the camera is animated and its position changes each frame
			if self.init:

				# use the camera selected by the user for the Looking Glass
				self._camera_active = self.scene.addon_settings.lookingglassCamera

				# remember the origingally active camera of the scene
				self._camera_original = self._camera_active

				# CAMERA SETTINGS: GET VIEW & PROJECTION MATRICES
				# +++++++++++++++++++++++++++++++++++++++++++++++

				# get camera's modelview matrix
				self._view_matrix = self._camera_active.matrix_world.copy()

				# correct for the camera scaling
				self._view_matrix = self._view_matrix @ Matrix.Scale(1/self._camera_active.scale.x, 4, (1, 0, 0))
				self._view_matrix = self._view_matrix @ Matrix.Scale(1/self._camera_active.scale.y, 4, (0, 1, 0))
				self._view_matrix = self._view_matrix @ Matrix.Scale(1/self._camera_active.scale.z, 4, (0, 0, 1))

				# calculate the inverted view matrix because this is what the draw_view_3D function requires
				self._view_matrix_inv = self._view_matrix.inverted_safe()

				# COPY CAMERA
				# +++++++++++++++++++++++++++++++++++++++++++++++
				# create a new, temporary camera using a copy of the
				# originals camera data, if it not already exists
				if not self._camera_temp: self._camera_temp.append(bpy.data.objects.new(self._camera_temp_basename, self._camera_active.data.copy()))

				# use this new camera for rendering
				self._camera_active = self._camera_temp[-1]

				# apply location and perspective of the original camera
				self._camera_active.matrix_world = self._view_matrix.copy()

				# set the scenes active camera to this temporary camera
				self.scene.camera = self._camera_active

				# NOTE: In contrast to multiview rendering, linking is not
				#		required for single cameras. Rendering still works,
				#		which is nice, because the camera remains invisible.
				#		Leave this here for debugging purposes.
				# # add this camera to the master collection of the scene
				# self.scene.collection.objects.link(self._camera_active)


			# CAMERA SETTINGS: APPLY POSITION AND SHIFT
			# +++++++++++++++++++++++++++++++++++++++++++++++
			# adjust the camera settings to the correct view point
			# The field of view set by the camera
			# NOTE 1: - the Looking Glass Factory documentation suggests to use a FOV of 14°. We use the focal length of the Blender camera instead.
			fov = self._camera_active.data.angle

			# calculate cameraSize from its distance to the focal plane and the FOV
			cameraDistance = self.scene.addon_settings.focalPlane
			cameraSize = cameraDistance * tan(fov / 2)

			# start at view_cone * 0.5 and go up to -view_cone * 0.5
			offsetAngle = (0.5 - self.view / (self.total_views - 1)) * radians(self.view_cone)

			# calculate the offset that the camera should move
			offset = cameraDistance * tan(offsetAngle)

			# translate the camera by the calculated offset in x-direction
			# NOTE: the matrix multiplications first transform the camera location into camera coordinates,
			#		then we apply the offset and transform back to world coordinates
			self._camera_active.matrix_world = self._view_matrix @ (Matrix.Translation((-offset, 0, 0)) @ (self._view_matrix_inv @ self._camera_original.matrix_world.copy()))

			# modify the projection matrix, relative to the camera size
			self._camera_active.data.shift_x = self._camera_original.data.shift_x + 0.5 * offset / cameraSize



		# MULTIVIEW CAMERA RENDERING
		# ++++++++++++++++++++++++++++++++++
		elif self.use_multiview:

			# if this is the first view of this render job
			# NOTE: - we do it this way in case the camera is animated and its position changes each frame
			if self.init:

				# set to view format to
				self.scene.render.views_format = 'MULTIVIEW'
				self.scene.render.image_settings.views_format = "INDIVIDUAL"

				# deactivate 'left' and 'right' view
				self.scene.render.views['left'].use = False
				self.scene.render.views['right'].use = False

				# use the camera selected by the user for the Looking Glass
				self._camera_active = self.scene.addon_settings.lookingglassCamera

				# remember the origingally active camera of the scene
				self._camera_original = self._camera_active

				# CAMERA SETTINGS: GET VIEW & PROJECTION MATRICES
				# +++++++++++++++++++++++++++++++++++++++++++++++

				# get camera's modelview matrix
				self._view_matrix = self._camera_active.matrix_world.copy()

				# correct for the camera scaling
				self._view_matrix = self._view_matrix @ Matrix.Scale(1/self._camera_active.scale.x, 4, (1, 0, 0))
				self._view_matrix = self._view_matrix @ Matrix.Scale(1/self._camera_active.scale.y, 4, (0, 1, 0))
				self._view_matrix = self._view_matrix @ Matrix.Scale(1/self._camera_active.scale.z, 4, (0, 0, 1))

				# calculate the inverted view matrix because this is what the draw_view_3D function requires
				self._view_matrix_inv = self._view_matrix.inverted_safe()

				# loop through all views
				for view in range(0, self.total_views):

					# COPY CAMERA
					# +++++++++++++++++++++++++++++++++++++++++++++++

					# if the cameras not already exist
					if not len(self._camera_temp) == self.total_views:

						# create a new, temporary camera using a copy of the original camera
						self._camera_temp.append(bpy.data.objects.new(self._camera_temp_basename + "_v" + str(view).zfill(len(str(self.total_views - 1))), self._camera_active.data.copy()))

						# set up view
						render_view = self.scene.render.views.new(self._multiview_view_basename + str(view).zfill(len(str(self.total_views - 1))))
						render_view.camera_suffix = '_v' + str(view).zfill(len(str(self.total_views - 1)))
						render_view.use = True

						# add this camera to the master collection of the scene
						self.scene.collection.objects.link(self._camera_temp[view])


					# use this camera for rendering
					self._camera_active = self._camera_temp[view]

					# apply same location and perspective like the original camera
					self._camera_active.matrix_world = self._view_matrix.copy()

					# set the scenes active camera to this temporary camera
					self.scene.camera = self._camera_active

					# CAMERA SETTINGS: APPLY POSITION AND SHIFT
					# +++++++++++++++++++++++++++++++++++++++++++++++
					# adjust the camera settings to the correct view point
					# The field of view set by the camera
					# NOTE 1: - the Looking Glass Factory documentation suggests to use a FOV of 14°. We use the focal length of the Blender camera instead.
					fov = self._camera_active.data.angle

					# calculate cameraSize from its distance to the focal plane and the FOV
					cameraDistance = self.scene.addon_settings.focalPlane
					cameraSize = cameraDistance * tan(fov / 2)

					# start at view_cone * 0.5 and go up to -view_cone * 0.5
					offsetAngle = (0.5 - view / (self.total_views - 1)) * radians(self.view_cone)

					# calculate the offset that the camera should move
					offset = cameraDistance * tan(offsetAngle)

					# translate the camera by the calculated offset in x-direction
					# NOTE: the matrix multiplications first transform the camera location into camera coordinates,
					#		then we apply the offset and transform back to world coordinates
					self._camera_active.matrix_world = self._view_matrix @ (Matrix.Translation((-offset, 0, 0)) @ (self._view_matrix_inv @ self._camera_original.matrix_world.copy()))

					# modify the projection matrix, relative to the camera size
					self._camera_active.data.shift_x = self._camera_original.data.shift_x + 0.5 * offset / cameraSize

	# assemble quilt
	def assemble_quilt(self):

		LookingGlassAddonLogger.info("Assembling the quilt from the rendered views:")

		# GET THE PIXEL DATA OF THE RENDERED VIEWS
		# ++++++++++++++++++++++++++++++++++++++++++++
		# clear the quilt pixel data for the (next) quilt
		self._view_images_pixels.clear()

		# iterate through all views
		for view in range(0, self.total_views):

			# if the file exists
			if os.path.exists(self.view_filepath(view)):

				LookingGlassAddonLogger.debug(" [#] Loading file for view %i: %s" % (view, self.view_filepath(view)))

				# load the view image
				self._view_image = bpy.data.images.load(self.view_filepath(view))

				# store the pixel data in an numpy array
				tmp_pixels = np.empty(len(self._view_image.pixels), np.float32)
				self._view_image.pixels.foreach_get(tmp_pixels)

				# append the pixel data to the list of views
				self._view_images_pixels.append(tmp_pixels)

				# delete the Blender image of this view
				bpy.data.images.remove(self._view_image)

			# if the file does not exist
			else:

				LookingGlassAddonLogger.debug(" [#] Could not find file for view %i: %s" % (view, self.view_filepath(view)))
				LookingGlassAddonLogger.debug(" [#] Cancel render job continuation.")

				# cancel the operator
				self._state = "CANCEL_RENDER"

				return None

		LookingGlassAddonLogger.info(" [#] Loaded all views into memory.")


		# ASSEMBLE THE QUILT
		# ++++++++++++++++++++++++++++++++++++++++++++
		# TODO: Would be good to implement the quilt assembly via pyLightIO
		#
		# then assemble the quilt from the views
		verticalStack = []
		horizontalStack = []
		for row in range(0, self.rows):
			for column in range(0, self.columns):

				# get pixel data and reshape into a reasonable format for stacking
				viewPixels = self._view_images_pixels[row * self.columns + column]
				viewPixels = viewPixels.reshape((self.scene.render.resolution_y, self.scene.render.resolution_x, 4))

				# append the pixel data to the current horizontal stack
				horizontalStack.append(viewPixels)

				# log info
				LookingGlassAddonLogger.debug(" [#] Stacking view %i with shape %s." % (row * self.columns + column, viewPixels.shape))

			# append the complete horizontal stack to the vertical stacks
			verticalStack.append(np.hstack(horizontalStack.copy()))

			# clear this horizontal stack
			horizontalStack.clear()

		# reshape the pixel data of all images into the quilt shape
		quiltPixels = np.vstack(verticalStack.copy())
		quiltPixels = np.reshape(quiltPixels, (self.columns * self.rows * (self.scene.render.resolution_x * self.scene.render.resolution_y * 4)))

		# log info
		LookingGlassAddonLogger.info(" [#] Assembled quilt in memory.")

		# copy the viewfile
		shutil.copy(self.view_filepath(), self.quilt_filepath())

		# delete the current image data block of the quilt render result
		# NOTE: This is required to prevent image data block accumulation
		if bpy.data.images.find(os.path.basename(self.quilt_filepath())) != -1:
			bpy.data.images.remove(bpy.data.images[os.path.basename(self.quilt_filepath())], do_unlink=True, do_id_user=True, do_ui_user=True)

		elif bpy.data.images.find(self.file_temp_name) != -1:
			bpy.data.images.remove(bpy.data.images[self.file_temp_name], do_unlink=True, do_id_user=True, do_ui_user=True)

		# load the view image
		self._quilt_image = bpy.data.images.load(filepath=self.quilt_filepath())

		# log debug info
		LookingGlassAddonLogger.info(" [#] Saved quilt file to: " + self._quilt_image.filepath)

		# NOTE: Creating a new image via the dedicated operators and methods
		# 		didn't apply the correct image formats and settings
		#		and therefore, we use the created image
		self._quilt_image.scale(self.scene.render.resolution_x * self.columns, self.scene.render.resolution_y * self.rows)

		# log info
		LookingGlassAddonLogger.info(" [#] Reading quilt pixel data into the image data block.")

		# apply the assembled quilt pixel data
		self._quilt_image.pixels.foreach_set(quiltPixels)

		# set "view as render" based on the image format
		if self._quilt_image.file_format == 'OPEN_EXR_MULTILAYER' or self._quilt_image.file_format == 'OPEN_EXR':
			self._quilt_image.use_view_as_render = True
		else:
			self._quilt_image.use_view_as_render = False

		# save the quilt in a file
		self._quilt_image.save()

		# give the result image the temporary quilt file name
		self._quilt_image.name = self.file_temp_name

		# log info
		LookingGlassAddonLogger.info(" [#] Done.")

		# return the quilt image
		return self._quilt_image

	# delete the files
	def delete_files(self, frame=None):

		# for all views of the given frame
		for view in range(0, self.total_views):

			# delete this file, if it exists
			if os.path.isfile(self.view_filepath(view, frame)):
				os.remove(self.view_filepath(view, frame))

		# delete the quilt file, if the user initially specified no file name
		# AND this is not an animation
		# NOTE: This is done, because this is Blenders behavior for normal renders
		#		if no filename is specifed
		file_dirname, file_basename = os.path.split(self.outputpath)
		if not file_basename and not self.animation:

			# delete the quilt file, if it exists
			if os.path.isfile(self.quilt_filepath(frame)):
				os.remove(self.quilt_filepath(frame))

		# clear the pixel data
		self._view_images_pixels.clear()

	# setup the camera system for rendering
	def clean_up(self):

		LookingGlassAddonLogger.info("Cleaning up camera setup.")

		# SINGLE-CAMERA RENDERING
		# ++++++++++++++++++++++++++++++++++
		if not self.use_multiview:

			# restore the original active camera
			self.scene.camera = self._camera_original

			# delete the temporarily created camera data block
			if bpy.data.objects.find(self._camera_temp_basename) != -1:

				LookingGlassAddonLogger.info(" [#] Delete temporary camera: %s" % (bpy.data.objects[self._camera_temp_basename]))

				# remove the data blocks
				bpy.data.cameras.remove(bpy.data.objects[self._camera_temp_basename].data, do_unlink=True, do_id_user=True, do_ui_user=True)

				# clear the list
				self._camera_temp.clear()

			LookingGlassAddonLogger.info(" [#] Setting scene camera to the original camera: %s" % (self._camera_original))

		# MULTIVIEW CAMERA RENDERING
		# ++++++++++++++++++++++++++++++++++
		elif self.use_multiview:

			# restore the original active camera
			self.scene.camera = self._camera_original

			# loop through all views
			for view, camera in enumerate(self._camera_temp):

				# delete the temporarily created camera data block
				LookingGlassAddonLogger.info(" [#] Delete temporary camera: %s" % (camera))
				bpy.data.cameras.remove(camera.data, do_unlink=True, do_id_user=True, do_ui_user=True)

				# remove the corresponding temporary multiview data block
				if self.scene.render.views.find(self._multiview_view_basename + str(view).zfill(len(str(self.total_views - 1)))) != -1:
					LookingGlassAddonLogger.info(" [#] Delete render view: %s" % (self.scene.render.views[self._multiview_view_basename + str(view).zfill(len(str(self.total_views - 1)))]))
					self.scene.render.views.remove(self.scene.render.views[self._multiview_view_basename + str(view).zfill(len(str(self.total_views - 1)))])

			# clear the list
			self._camera_temp.clear()

			LookingGlassAddonLogger.info(" [#] Setting scene camera to the original camera: %s" % (self._camera_original))
			LookingGlassAddonLogger.info(" [#] Remaining Cameras: %i" % len(self._camera_temp))

			# set to view format to
			self.scene.render.views_format = 'STEREO_3D'

			# deactivate 'left' and 'right' view
			self.scene.render.views['left'].use = True
			self.scene.render.views['right'].use = True


	# update the progress bar
	def update_progress(self):

		# get the curre

		# SINGLE-CAMERA RENDERING
		# ++++++++++++++++++++++++++++++++++
		if not self.use_multiview:

			# if a single frame shall be rendered
			if self.animation == False:
				return int(self.view / ((self.total_views - 1)) * 100)

			# for animations
			else:
				return int(((self.frame - self.scene.frame_start) * (self.total_views - 1) + self.view) / ((self.total_views - 1) * (self.scene.frame_end - self.scene.frame_start + 1)) * 100)

		# MULTIVIEW CAMERA RENDERING
		# ++++++++++++++++++++++++++++++++++
		elif self.use_multiview:

			# if a single frame shall be rendered
			if self.animation == False:
				return int(self.view / ((self.total_views - 1)) * 100)

			# for animations
			else:
				return int(((self.frame - self.scene.frame_start) * (self.total_views - 1) + self.view) / ((self.total_views - 1) * (self.scene.frame_end - self.scene.frame_start + 1)) * 100)

	# CALLBACK FUNCTIONS / APPLICATION HANDLERS
	# +++++++++++++++++++++++++++++++++++++++++++++++
	def init_render(self, Scene, depsgraph):

		# update operator state
		self._state = "INIT_RENDER"

		# log info
		LookingGlassAddonLogger.info("Rendering job initialized. (lockfile: %s, init: %s)" % (self._use_lockfile, self.init))

	# function that is called before rendering starts
	def pre_render(self, Scene, depsgraph):

		# update operator state
		self._state = "PRE_RENDER"

		# SINGLE-CAMERA RENDERING
		# ++++++++++++++++++++++++++++++++++
		if not self.use_multiview:

			# output current status
			LookingGlassAddonLogger.info("Rendering view is going to be prepared.")
			LookingGlassAddonLogger.info(" [#] active camera: %s" % self._camera_active)
			LookingGlassAddonLogger.info(" [#] current frame: %s" % self.frame)
			LookingGlassAddonLogger.info(" [#] current subframe: %s" % self.subframe)
			LookingGlassAddonLogger.info(" [#] current view: %s" % self.view)
			LookingGlassAddonLogger.info(" [#] current quilt file: %s" % self.quilt_filepath())
			LookingGlassAddonLogger.info(" [#] current view file: %s" % self.view_filepath())

		# MULTIVIEW CAMERA RENDERING
		# ++++++++++++++++++++++++++++++++++
		elif self.use_multiview:

			# output current status
			LookingGlassAddonLogger.info("Rendering multiview is going to be prepared.")
			LookingGlassAddonLogger.info(" [#] active camera: %s" % self._camera_active)
			LookingGlassAddonLogger.info(" [#] current frame: %s" % self.frame)
			LookingGlassAddonLogger.info(" [#] current subframe: %s" % self.subframe)
			LookingGlassAddonLogger.info(" [#] current view: all (multiview)")
			LookingGlassAddonLogger.info(" [#] current quilt file: %s" % self.quilt_filepath())
			LookingGlassAddonLogger.info(" [#] current view file: %s" % self.view_filepath())

	# function that is called after rendering finished
	def post_render(self, Scene, depsgraph):

		# update operator state
		self._state = "POST_RENDER"

		LookingGlassAddonLogger.info("Saving view file: %s" % self.view_filepath())

			# save the rendered image in a file
			#bpy.data.images["Render Result"].save_render(filepath=self.view_filepath(), scene=self.scene)


	# function that is called when the renderjob is completed
	def completed_render(self, Scene, depsgraph):

		# update operator state
		self._state = "COMPLETE_RENDER"

	# function that is called if rendering was cancelled
	def cancel_render(self, Scene, depsgraph):

		# set render job state to CANCEL
		self._state = "CANCEL_RENDER"
		self.scene.addon_settings.render_stop = True

		LookingGlassAddonLogger.info("Rendering job was cancelled.")

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
	def __init__(self, BlenderScene, animation, use_lockfile, use_multiview, blocking):

		# get initialization parameters
		self.scene = BlenderScene
		self.animation = animation
		self._use_lockfile = use_lockfile
		self.use_multiview = use_multiview
		self.blocking = blocking

		# if a valid scene was given
		if self.scene and type(self.scene) == bpy.types.Scene:

			# COMMAND LINE ARGUMENTS
			# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

			# check if Blender is run in background mode
			if LookingGlassAddon.background:

				# if an output path was specified
				if "-o" in LookingGlassAddon.addon_arguments or "--render-output" in LookingGlassAddon.addon_arguments:

					# get the file name position
					try:
						index = LookingGlassAddon.addon_arguments.index("-o") + 1
					except ValueError:
						index = LookingGlassAddon.addon_arguments.index("--render-output") + 1

					# set the file name
					self.scene.render.filepath = LookingGlassAddon.addon_arguments[index]

					# deactivate the "Add Metadata option"
					self.scene.addon_settings.render_add_suffix = False

				# if an starting frame was specified
				if "-s" in LookingGlassAddon.addon_arguments or "--frame-start" in LookingGlassAddon.addon_arguments:

					# get the file name position
					try:
						index = LookingGlassAddon.addon_arguments.index("-s") + 1
					except ValueError:
						index = LookingGlassAddon.addon_arguments.index("--frame-start") + 1

					# set the frame start
					self.scene.frame_start = int(LookingGlassAddon.addon_arguments[index])

				# if an end frame was specified
				if "-e" in LookingGlassAddon.addon_arguments or "--frame-end" in LookingGlassAddon.addon_arguments:

					# get the file name position
					try:
						index = LookingGlassAddon.addon_arguments.index("-e") + 1
					except ValueError:
						index = LookingGlassAddon.addon_arguments.index("--frame-end") + 1

					# set the end frame
					self.scene.frame_end = int(LookingGlassAddon.addon_arguments[index])

				# if a frame step was specified
				if "-j" in LookingGlassAddon.addon_arguments or "--frame-jump" in LookingGlassAddon.addon_arguments:

					# get the file name position
					try:
						index = LookingGlassAddon.addon_arguments.index("-j") + 1
					except ValueError:
						index = LookingGlassAddon.addon_arguments.index("--frame-jump") + 1

					# set the frame step
					self.scene.frame_step = int(LookingGlassAddon.addon_arguments[index])

				# if a rendering frame was specified
				if "-f" in LookingGlassAddon.addon_arguments or "--render-frame" in LookingGlassAddon.addon_arguments:

					# get the file name position
					try:
						index = LookingGlassAddon.addon_arguments.index("-f") + 1
					except ValueError:
						index = LookingGlassAddon.addon_arguments.index("--render-frame") + 1

					# if a relative frame number is given
					if LookingGlassAddon.addon_arguments[index][0] == "+":

						# set the current frame
						self.scene.frame_current += int(LookingGlassAddon.addon_arguments[index])

					# if a relative frame number is given
					elif LookingGlassAddon.addon_arguments[index][0] == "-":

						# set the current frame
						self.scene.frame_current += int(LookingGlassAddon.addon_arguments[index])

					else:

						# set the current frame
						self.scene.frame_current = int(LookingGlassAddon.addon_arguments[index])

			# INITIALIZATION
			# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

			# make an internal variable for the add-on settings,
			# which can be accessed from methods that have no "context" parameter
			self.addon_settings = self.scene.addon_settings

			# initialize the rendering job variables
			self.job = RenderJob(self.scene, self.animation, self._use_lockfile, self.use_multiview, self.blocking)

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
			if not self.blocking and (self.addon_settings.render_use_device == True and pylio.DeviceManager.get_active()):
				self._device = pylio.DeviceManager.get_active()
				self._quilt_preset = self.addon_settings.quiltPreset

			# or the selected emulated device
			elif self.blocking or self.addon_settings.render_use_device == False:
				self._device = pylio.DeviceManager.get_device(key="index", value=int(self.addon_settings.render_device_type))
				self._quilt_preset = self.addon_settings.render_quilt_preset

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
			if self._use_lockfile == True:

				try:

					# read the settings from the lockfile
					self.read_from_lockfile()

					# make sure the render job will be initalized correctly
					self.job.init = True

				except:

					# reset global and local status variables
					LookingGlassAddon.has_lockfile = False
					self._use_lockfile = False

					# notify user
					LookingGlassAddonLogger.error("Render job can not be continued. Lockfile not found or corrupted.")

					# don't execute operator
					return None


			# if the lockfile shall not be used
			elif not self._use_lockfile:

				# settings of the current preset
				self.job.view_width = self._qs[int(self._quilt_preset)]["view_width"]
				self.job.view_height = self._qs[int(self._quilt_preset)]["view_height"]
				self.job.rows = self._qs[int(self._quilt_preset)]["rows"]
				self.job.columns = self._qs[int(self._quilt_preset)]["columns"]
				self.job.total_views = self._qs[int(self._quilt_preset)]["total_views"]

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



	# convert the object to a nested dictionary
	# NOTE: This function is largely taken from https://stackoverflow.com/a/1118038
	def to_dict(self, obj, classkey=None):

		# if this is an dictionary
		if isinstance(obj, dict):
			data = {}
			for (k, v) in obj.items():
				data[k] = self.to_dict(v, classkey)
			return data

		# if this is the addon settings
		elif isinstance(obj, LookingGlassAddonSettings):
			data = {}
			for key in dir(obj):
				if not callable(getattr(obj, key)) and not key.startswith('_'):
					if key not in ['bl_rna', 'rna_type', 'blender_view3d']:
						value = self.to_dict(getattr(obj, key))
						data[key] = value
			return data

		# if this are EEVEE or Cycles settings
		elif isinstance(obj, type(self.scene.eevee)) or isinstance(obj, type(self.scene.cycles)) or isinstance(obj, type(self.scene.cycles_curves)):
			data = {}
			for key in dir(obj):
				if not callable(getattr(obj, key)) and not key.startswith('_'):
					if key not in ['bl_rna', 'rna_type']:
						value = self.to_dict(getattr(obj, key))
						data[key] = value
			return data

		# if this is one of the class methods
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

		# if this is an object name
		elif hasattr(obj, "name"):
			return obj.name

		# if this is one of the standard types
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

					# write the date to the lock file
					lockfile.write(json.dumps(settings_dict))

					# close file
					lockfile.close()

				else:

					# log warning
					LookingGlassAddonLogger.warning("Could not create lockfile. Quilt render continuation is turned off for this rendering process.")

			else:

				# log warning
				LookingGlassAddonLogger.warning("Could not find/create temporary folder in add-on directory. Quilt render continuation is turned off for this rendering process.")

		else:

			# log warning
			LookingGlassAddonLogger.warning("No blender file exists. Quilt render continuation is turned off for this rendering process.")


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
	use_multiview: bpy.props.BoolProperty(default = False)		# use the multiview rendering
	blocking: bpy.props.BoolProperty(default = False)			# start rendering in blocking mode (for renderfarms & command line calls)

	# render settings
	render_settings = None

	# event and app handler ids
	_handle_event_timer = None	# modal timer event

	# define cancel standard messages
	cancel_sign = "INFO"
	cancel_message = "Quilt rendering was cancelled."




	# OPERATOR:
	# +++++++++++++++++++++++++++++++++++++++++++++++
	# check if everything is correctly set up for the quilt rendering
	@classmethod
	def poll(self, context):

		# return True, so the operator is executed
		return True


	# cancel modal operator
	# NOTE: - this includes deleting all view files
	#		- this includes recovering all original user settings
	def cancel(self, context):

		# REMOVE APP HANDLERS
		# +++++++++++++++++++++++++
		# if this call was not just invoked to discard an incomplete render job
		if not self.discard_lockfile:

			# remove render app handlers
			bpy.app.handlers.render_init.remove(self.render_settings.job.init_render)
			bpy.app.handlers.render_pre.remove(self.render_settings.job.pre_render)
			bpy.app.handlers.render_post.remove(self.render_settings.job.post_render)
			bpy.app.handlers.render_cancel.remove(self.render_settings.job.cancel_render)
			bpy.app.handlers.render_complete.remove(self.render_settings.job.completed_render)

			# remove event timer
			if self._handle_event_timer: context.window_manager.event_timer_remove(self._handle_event_timer)

			LookingGlassAddonLogger.info("Removing application handlers.")



		# CLEAR IMAGE & PIXEL DATA
		# +++++++++++++++++++++++++
		self.render_settings.job._view_image = None
		self.render_settings.job._quilt_image = None
		self.render_settings.job._view_images_pixels.clear()



		# CLEAN-UP FILES
		# +++++++++++++++++++++++++++++++++++++++++++
		# if the view files shall not be kept OR (still was rendered AND no filename was specfied) OR the file keeping is forced OR the incomplete render job was discarded
		if ((self.render_settings.addon_settings.render_output == '1' or (not ((self.render_settings.job.animation == False and not self.render_settings.job.file_use_temp) or self.animation == True))) and self.render_settings.job.file_force_keep == False) or self.discard_lockfile == True:

			LookingGlassAddonLogger.info("Cleaning up the disk files.")

			# if it was an animation
			if self.render_settings.job.animation:

				# for all frames of the animation
				for frame in range(self.render_settings.job.scene.frame_start, self.render_settings.job.scene.frame_end + self.render_settings.frame_step):

					# delete views
					self.render_settings.job.delete_files(frame)

			# if it was a still image
			elif not self.render_settings.job.animation:

				#  delete its views
				self.render_settings.job.delete_files()



		# RESTORE USER SETTINGS
		# +++++++++++++++++++++++++
		# if this call was not just invoked to discard an incomplete render job
		if not self.discard_lockfile:

			# clean up the render job (e.g., the temporary cameras etc.)
			self.render_settings.job.clean_up()

			# restore original render settings
			self.render_settings.restore_original()



		# DELETE LOCKFILE
		# ++++++++++++++++++++++++++++++++++
		# if a lockfile exists, delete it
		if os.path.exists(self.render_settings.job.lockfile_path):
			os.remove(self.render_settings.job.lockfile_path)

		# reset global and local status variables
		LookingGlassAddon.has_lockfile = False
		self.use_lockfile = False



		# RESET STATUS VARIABLES FOR PROGRESSBAR AND CANCEL BUTTON
		# ++++++++++++++++++++++++++++++++++
		self.render_settings.addon_settings.render_progress = 0.0
		LookingGlassAddon.RenderInvoked = False
		LookingGlassAddon.RenderAnimation = None
		self.render_settings.addon_settings.render_stop = False

		# log debug info
		LookingGlassAddonLogger.debug("Render job stopped.")

		# return None since this is expected by the operator
		return None



	# invoke the modal operator
	def execute(self, context):
		return self.invoke(context, None)


	# invoke the modal operator
	def invoke(self, context, event):

		# RENDER SETTINGS
		################################################################

		# we handle the render settings in a separate class
		# NOTE: This class also stores the original settings and provides a
		#		restore_original() method to restore the scenes original render
		#		settings after the render job is done
		self.render_settings = RenderSettings(bpy.context.scene, self.animation, self.use_lockfile, self.use_multiview, self.blocking)

		# if a lockfile should be loaded
		if self.use_lockfile:
			if self.render_settings is None:

				# notify user
				self.report({"ERROR"}, "Render job can not be continued. Lockfile not found or corrupted.")

				# cancel the operator
				self.cancel(context)

				# don't execute operator
				return {'CANCELLED'}



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
			self.cancel(context)

			# notify user
			self.report({"INFO"}, "Render job discarded.")
			return {"CANCELLED"}



		# REGISTER ALL HANDLERS FOR THE QUILT RENDERING
		# OR EXECUTE A MULTIVIEW RENDERING
		################################################################

		# TODO: Maybe shift this to the RenderSettings class and change the
		#		self.resolution_x variables etc. and apply them to the scene
		#		-> might be more congruent with the rest of the code?
		# VIEW RESOLUTION SETTINGS
		# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
		# apply the render resolution to Blender render settings
		self.render_settings.job.scene.render.resolution_x = self.render_settings.job.view_width
		self.render_settings.job.scene.render.resolution_y = self.render_settings.job.view_height

		# set the render percentage to 100%
		self.render_settings.job.scene.render.resolution_percentage = 100

		# for landscape formatted devices
		if (self.render_settings.job.scene.render.resolution_x / self.render_settings.job.scene.render.resolution_y) / self.render_settings._device.aspect > 1:

			# apply the correct aspect ratio
			self.render_settings.job.scene.render.pixel_aspect_x = 1.0
			self.render_settings.job.scene.render.pixel_aspect_y = self.render_settings.job.scene.render.resolution_x / (self.render_settings.job.scene.render.resolution_y * self.render_settings._device.aspect)

		# for portrait formatted devices
		else:

			# apply the correct aspect ratio
			self.render_settings.job.scene.render.pixel_aspect_x = (self.render_settings.job.scene.render.resolution_y * self.render_settings._device.aspect) / self.render_settings.job.scene.render.resolution_x
			self.render_settings.job.scene.render.pixel_aspect_y = 1.0

		# MULTIVIEW SETTINGS
		# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

		# set the multiview mode of the scene
		self.render_settings.job.scene.render.use_multiview = self.use_multiview

		# HANDLERS FOR THE RENDERING PROCESS
		# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
		bpy.app.handlers.render_init.append(self.render_settings.job.init_render)
		bpy.app.handlers.render_pre.append(self.render_settings.job.pre_render)
		bpy.app.handlers.render_post.append(self.render_settings.job.post_render)
		bpy.app.handlers.render_cancel.append(self.render_settings.job.cancel_render)
		bpy.app.handlers.render_complete.append(self.render_settings.job.completed_render)

		LookingGlassAddon.RenderInvoked = True
		LookingGlassAddon.RenderAnimation = self.render_settings.job.animation

		# START RENDERING IN MODAL OR BLOCKING MODE
		# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
		# if operator was called in non-blocking mode
		if not self.blocking:

			# HANDLER FOR EVENT TIMER
			# ++++++++++++++++++++++++++++++++++
			# Create timer event that runs every 1 ms to check the rendering process
			self._handle_event_timer = context.window_manager.event_timer_add(0.001, window=context.window)

			# add the modal operator handler
			context.window_manager.modal_handler_add(self)

			# keep the modal operator running
			return {'RUNNING_MODAL'}

		else:

			# render the quilt in blocking mode until it is finished
			while (self.modal(context, None) == {'PASS_THROUGH'}):
				time.sleep(0.001)

			# finish operator
			return {'FINISHED'}

	# modal operator for controlled redrawing of the lightfield
	def modal(self, context, event):

		# LookingGlassAddonLogger.debug("Current render job state: %s (stop state: %s)" % (self.render_settings.job._state, self.render_settings.addon_settings.render_stop))

		# UPDATE PROGRESS BAR
		# +++++++++++++++++++++++++++++++++++++++++++
		self.render_settings.addon_settings.render_progress = self.render_settings.job.update_progress()



		# PROCESS MODAL EVENTS
		# +++++++++++++++++++++++++++++++++++++++++++
		# if the ESC key was pressed
		if not event is None and event.type == 'ESC':

			# update state variables
			self.render_settings.addon_settings.render_stop = True

			# pass event through
			return {'PASS_THROUGH'}

		# if the TIMER event for the quilt rendering is called
		elif event is None or (not event is None and event.type == 'TIMER'):

			# INVOKE NEW RENDER JOB
			# ++++++++++++++++++++++++++++++++++
			if self.render_settings.job._state == "INVOKE_RENDER" and not self.render_settings.addon_settings.render_stop:

				# make sure the interface is not locked
				# otherwise the renderjob won't be excecuted properly.
				# Unclear why, but maybe because the camera settings will not
				# be applied properly then. Solved issue:
				# https://github.com/regcs/AliceLG-beta/issues/9
				self.render_settings.job.scene.render.use_lock_interface = False

				# invoke the new render job
				self.render_settings.job.invoke()

				# start rendering
				result = bpy.ops.render.render("INVOKE_DEFAULT", animation=False, write_still=True)
				if result != {'CANCELLED'}:

					self.render_settings.job.scene.render.use_lock_interface = True

 					# set render job state to IDLE, if operator not in blocking mode
					if not self.blocking: self.render_settings.job._state = "IDLE"

					# Some status infos for the user if this is not a multiview render:
					if not self.use_multiview:

						# if a single frame shall be rendered
						if self.render_settings.job.animation == False:

							# notify user
							self.report({"INFO"},"Rendering view " + str(self.render_settings.job.view + 1) + "/" + str(self.render_settings.job.total_views) + " ..")

						# if an animation shall be rendered
						elif self.render_settings.job.animation == True:

							# notify user
							self.report({"INFO"},"Rendering view " + str(self.render_settings.job.view + 1) + "/" + str(self.render_settings.job.total_views) + " of frame " + str(self.render_settings.job.frame) +  " ..")

				# pass event through
				return {'PASS_THROUGH'}



			# COMPLETE-RENDER STEP
			# ++++++++++++++++++++++++++++++++++

			# if nothing is rendering, but the last view is not yet rendered
			elif self.render_settings.job._state == "COMPLETE_RENDER" and not self.render_settings.addon_settings.render_stop:

				# QUILT ASSEMBLY
				# ++++++++++++++++++++++++++++++++++++++++++++
				# if this was the last view OR a multiview render
				if self.render_settings.job.view == (self.render_settings.job.total_views - 1) or self.use_multiview:
					start = time.time()

					# assemble the quilt from the view data
					if not self.render_settings.job.assemble_quilt():

						# cancel the operator
						self.render_settings.addon_settings.render_stop = True

						# force the operator to keep the view Files
						self.file_force_keep = True

						# notify user
						self.cancel_sign = "ERROR"
						self.cancel_message = "Render job can not be continued. Missing view file(s) of the previously failed render job."


					# QUILT DISPLAY AS RENDER RESULT
					# ++++++++++++++++++++++++++++++++++++++++++++
					for window in context.window_manager.windows:
						for area in window.screen.areas:

							if area.type == 'IMAGE_EDITOR':

								if area.spaces.active != None:

									if area.spaces.active.image != None:

										if area.spaces.active.image.name == "Render Result":

											# and change the active image shown here to the quilt
											area.spaces.active.image = self.render_settings.job._quilt_image

											# fit the zoom factor in this window to show the complete quilt
											# bpy.ops.image.view_all({'window': window, 'screen': window.screen, 'area': area})

											break


				# UPDATE LOCKFILE
				# +++++++++++++++++++++++++++++++++++++++++++
				# if the lockfile exists
				if self.render_settings.job.lockfile_path != None and os.path.exists(self.render_settings.job.lockfile_path) == True:

					# open the lockfile and read it
					self.render_settings.write_to_lockfile()



				# VIEW & FRAME RENDERING
				# ++++++++++++++++++++++++++++++++++++++++++++

				# if a single frame shall be rendered
				if self.render_settings.job.animation == False:

					# if this was not the last view AND the multiview mechanism is NOT used
					if self.render_settings.job.view < (self.render_settings.job.total_views - 1) and not self.use_multiview:

						# increase view count
						self.render_settings.job.view += 1

						# reset the render job state to IDLE
						self.render_settings.job._state = "INVOKE_RENDER"

					# if this was the last view
					else:

						# notify user
						self.cancel_sign = "INFO"
						self.cancel_message = "Complete quilt rendered."

						# stop the operator
						self.render_settings.addon_settings.render_stop = True


				# if an animation shall be rendered
				elif self.render_settings.job.animation == True:

					# if this was not the last view AND the multiview mechanism is NOT used
					if self.render_settings.job.view < (self.render_settings.job.total_views - 1) and not self.use_multiview:

						# increase view count
						self.render_settings.job.view += 1

						# reset the render job state to IDLE
						self.render_settings.job._state = "INVOKE_RENDER"

					# if this was the last view OR the multiview mechanism is used
					elif self.render_settings.job.view == (self.render_settings.job.total_views - 1) or self.use_multiview:

						# but if this was not the last frame
						if self.render_settings.job.frame < self.render_settings.job.scene.frame_end:

							# CYCLES SPECIFIC
							if self.render_settings.engine == "CYCLES":

								# restore seed setting
								self.render_settings.job.scene.cycles.seed = self.render_settings.job.seed

							# if the view files shall not be kept
							if ((self.render_settings.addon_settings.render_output == '1') and self.render_settings.job.file_force_keep == False):

								# delete views of the rendered frame
								self.render_settings.job.delete_files(self.render_settings.job.frame)

							# delete the temporarily created camera
							# self.render_settings.job.clean_up()

							# reset the initialization step variable for the render job
							self.render_settings.job.init = True

							# reset the rendering view variable
							self.render_settings.job.view = 0

							# increase frame count
							self.render_settings.job.frame = self.render_settings.job.frame + self.render_settings.frame_step

							# reset the render job state to IDLE
							self.render_settings.job._state = "INVOKE_RENDER"

						# if this was the last frame
						else:

							# cancel the operator
							self.render_settings.addon_settings.render_stop = True

							# notify user
							self.cancel_sign = "INFO"
							self.cancel_message = "Complete animation quilt rendered."

				# log debug info
				LookingGlassAddonLogger.debug("Render job completed.")

				# pass event through
				return {'PASS_THROUGH'}


		# CANCEl-RENDER STEP
		# ++++++++++++++++++++++++++++++++++

		# if nothing is rendering, but the last view is not yet rendered
		if (self.render_settings.job._state == "INVOKE_RENDER" or self.render_settings.job._state == "COMPLETE_RENDER" or self.render_settings.job._state == "CANCEL_RENDER") and self.render_settings.addon_settings.render_stop:

			# cancel the operator
			self.cancel(context)

			# notify user
			self.report({self.cancel_sign}, self.cancel_message)
			return {"CANCELLED"}

		# pass event through
		return {'PASS_THROUGH'}
