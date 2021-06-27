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

import platform
import functools
import bpy, bgl
import gpu
import time
from math import *
from mathutils import *
from gpu_extras.batch import batch_for_shader
from gpu_extras.presets import draw_texture_2d
from bpy_extras.view3d_utils import location_3d_to_region_2d, region_2d_to_origin_3d, region_2d_to_vector_3d

# TODO: Is there a better way to share global variables between all addon files and operators?
from .looking_glass_global_variables import *



# --------- TRY TO LOAD SYSTEM API FOR WINDOW CONTROL -----------

# if on macOS
if platform.system() == "Darwin":

	# NOTE: This requires that PyObjC is installed in Blenders Python
	#		- add a button to Preferences wich handles the installation?
	try:

		# The following lines are necessary to use PyObjC to load AppKit
		# from: https://github.com/ronaldoussoren/pyobjc/issues/309
		# User: MaxBelanger
		#	   This means pyobjc always dlopens (via NSBundle) based on the canonical and absolute path of the framework, which works with the cache.
		import objc, objc._dyld

		def __path_for_framework_safe(path: str) -> str:
			return path

		objc._dyld.pathForFramework = __path_for_framework_safe
		objc.pathForFramework = __path_for_framework_safe

		# import AppKit
		import Cocoa
		from AppKit import NSScreen, NSWorkspace, NSWindow, NSApp, NSApplication, NSWindowStyleMaskBorderless, NSApplicationPresentationHideDock, NSApplicationPresentationHideMenuBar
		from Quartz import kCGWindowListOptionOnScreenOnly, kCGNullWindowID, CGWindowListCopyWindowInfo, CGWindowListCreate, kCGWindowNumber

	except:
		#self.report({"WARNING"}, "Could not load PyObjC. Need to position lightfield window manually.")
		pass

# if on 32-bit Windows
elif platform.system() == "Windows":

	# NOTE: Try to use the user32 dll
	try:

		# import ctypes module
		import ctypes
		from ctypes import wintypes

		# load the user32.dll system dll
		user32 = ctypes.windll.user32

	except:
		#self.report({"WARNING"}, "Could not load User32.dll. Need to position lightfield window manually.")
		pass

# if on 32-bit Windows
elif platform.system() == "Linux":

	import subprocess

else:
	#self.report({"ERROR"}, "Unsupported operating system.")
	raise OSError("Unsupported operating system.")






# ------------ LIGHTFIELD RENDERING -------------
# Modal operator for controlled redrawing of the lightfield window.
class LOOKINGGLASS_OT_render_lightfield(bpy.types.Operator):

	bl_idname = "render.lightfield"
	bl_label = "Looking Glass Lightfield Rendering"
	bl_options = {'REGISTER', 'INTERNAL'}

	# ADDON SETTINGS
	settings = None

	# WINDOW RELATED VARIABLES
	window_manager = None
	WindowCheck = False

	# SETTINGS VARIABLES
	preset = 0
	last_preset = 0

	# DRAWING OPERATION VARIABLES
	modal_redraw = True
	updateQuilt = True
	depsgraph_update_time = 0.000
	viewportViewMatrix = None
	activeSpace = None

	# LIGHTFIELD CURSOR
	mouse_click = False
	modified_mouse_x = 0
	modified_mouse_y = 0
	mouse_x = 0
	mouse_y = 0
	cursor = Vector((0, 0, 0))
	normal = Vector((0, 0, 1))

	# HANDLER IDENTIFIERS
	_handle_viewDrawing = []
	_handle_lightfieldDrawing = None
	_handle_trackDepsgraphUpdates = None
	_handle_trackFrameChanges = None
	_handle_trackActiveWindow = None

	# DEBUGING VARIABLES
	start_multi_view = 0




	# inititalize the lightfield window
	@classmethod
	def __init__(self):

		# set global status variable
		LookingGlassAddon.LightfieldWindowInitialized = True



	# deinititalize the lightfield window
	@classmethod
	def __del__(self):

		# set global status variable
		LookingGlassAddon.LightfieldWindowInitialized = False




	# poll method
	@classmethod
	def poll(self, context):

		# if the lightfield window exists
		if LookingGlassAddon.lightfieldWindow != None:

			# return True, so the operator is executed
			return True

		else:

			# return False, so the operator is NOT executed
			return False



	# cancel the modal operator
	def cancel(self, context):

		# stop timer
		context.window_manager.event_timer_remove(self.timerEvent)

		# remove the app handler that checks for depsgraph updates
		bpy.app.handlers.depsgraph_update_post.remove(self.trackDepsgraphUpdates)
		bpy.app.handlers.frame_change_post.remove(self.trackDepsgraphUpdates)

		# remove the handler for the viewport tracking
		if self._handle_trackActiveWindow: bpy.types.SpaceView3D.draw_handler_remove(self._handle_trackActiveWindow, 'WINDOW')

		# remove the draw handlers for all quilt views
		for handle in self._handle_viewDrawing:
			if handle: bpy.types.SpaceView3D.draw_handler_remove(handle, 'WINDOW')

		# clear the list of handles
		self._handle_viewDrawing.clear()

		# remove the draw handler for the lightfield cursor
		if self._handle_lightfieldCursor: bpy.types.SpaceView3D.draw_handler_remove(self._handle_lightfieldCursor, 'WINDOW')

		# remove the draw handler for the lightfield window
		if self._handle_lightfieldDrawing: bpy.types.SpaceView3D.draw_handler_remove(self._handle_lightfieldDrawing, 'WINDOW')

		# iterate through all presets
		for i in range(0, len(LookingGlassAddon.qs), 1):

			# free the GPUOffscreen for the quilt / lightfield
			LookingGlassAddon.qs[i]["quiltOffscreen"].free()

			# iterate through all quilt views
			for view in range(0, LookingGlassAddon.qs[i]["totalViews"], 1):

				# and free the corresponding GPUOffscreen
				LookingGlassAddon.qs[i]["viewOffscreens"][view].free()

			# clear the list
			LookingGlassAddon.qs[i]["viewOffscreens"].clear()

		# set status variables to default state
		LookingGlassAddon.lightfieldWindow = None
		LookingGlassAddon.lightfieldSpace = None
		#LookingGlassAddon.BlenderWindow = None
		LookingGlassAddon.BlenderViewport = None

		# set the button controls for the lightfield window to False
		self.settings.toggleLightfieldWindowFullscreen = False
		self.settings.ShowLightfieldWindow = False
		self.settings.lightfieldWindowIndex = -1


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
					scene.settings.toggleLightfieldWindowFullscreen = LookingGlassAddon.LightfieldWindowInvoker.settings.toggleLightfieldWindowFullscreen
					scene.settings.lightfieldWindowIndex = -1

			# reset global variable
			LookingGlassAddon.LightfieldWindowInvoker = None
			LookingGlassAddon.LightfieldWindowIsFullscreen = False


		# return None since this is expected by the operator
		return None




	def invoke(self, context, event):
		start = time.time()

		# make an internal variable for the window_manager,
		# which can be accessed from methods that have no "context" parameter
		self.settings = context.scene.settings

		# update the variable for the current Looking Glass device
		if int(self.settings.activeDisplay) != -1: self.device = LookingGlassAddon.deviceList[int(self.settings.activeDisplay)]



		# PREPARE THE SHADERS AND LIGHTFIELD RENDERING
		################################################################

		# CREATE OFFSCREENS FOR DRAWING
		# iterate through all presets
		for i in range(0, len(LookingGlassAddon.qs), 1):

			# create a GPUOffscreen for the quilt / lightfield
			LookingGlassAddon.qs[i]["quiltOffscreen"] = gpu.types.GPUOffScreen(LookingGlassAddon.qs[i]["width"], LookingGlassAddon.qs[i]["height"])

			# create a list for the GPUOffscreens of the different views
			for view in range(0, LookingGlassAddon.qs[i]["totalViews"], 1):

				LookingGlassAddon.qs[i]["viewOffscreens"].append(gpu.types.GPUOffScreen(int(LookingGlassAddon.qs[i]["viewWidth"]), int(LookingGlassAddon.qs[i]["viewHeight"])))

		# Load the lightfield shaders
		if self.loadlightFieldShaders() == None:
			self.report({"ERROR"}, "Lightfield shader not compiled")
			raise Exception()

		# Load the specific calibration data of the LG into the shaders
		self.loadCalibrationIntoShader()

		# pass quilt settings to the lightfield shader
		self.passQuiltSettingsToShader(self.preset)



		# PREPARE THE LIGHTFIELD WINDOW AND OVERRIDE CONTEXT
		################################################################

		# # make a temporary variable
		# print("Window: ", LookingGlassAddon.lightfieldWindow)
		# print(" # x: ", LookingGlassAddon.lightfieldWindow.x)
		# print(" # y: ", LookingGlassAddon.lightfieldWindow.y)
		# print(" # width: ", LookingGlassAddon.lightfieldWindow.width)
		# print(" # height: ", LookingGlassAddon.lightfieldWindow.height)

		# get the index of the lightfield window in the list of windows in the WindowManager
		# NOTE: This is required for reloading a blend file in which the lightfield window was open
		self.settings.lightfieldWindowIndex = context.window_manager.windows.values().index(LookingGlassAddon.lightfieldWindow)

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
						LookingGlassAddon.lightfieldRegion = region
						LookingGlassAddon.lightfieldArea = area
						LookingGlassAddon.lightfieldSpace = space

						# create an override context
						self.override = context.copy()

						self.override['area'] = area
						self.override['region'] = region
						self.override['space_data'] = space
						self.override['scene'] = context.scene
						self.override['view_layer'] = context.view_layer

						# ADJUST VIEWPORT SETTINGS
						# lock viewport to local camera
						space.use_local_camera = True
						space.lock_camera = True

						# if a looking glass camera is selected
						if context.scene.settings.lookingglassCamera != None:

							# set space to this camera (automatically None, if none is selected)
							space.camera = context.scene.settings.lookingglassCamera

						# set viewport view location to default
						space.region_3d.view_distance = 15
						space.region_3d.view_matrix = 	(
														(0.41, -0.4017, 0.8188, 0.0),
				               							(0.912, 0.1936, -0.3617, 0.0),
				               							(-0.0133, 0.8959, 0.4458, 0.0),
				               							(0.0, 0.0, -14.9892, 1.0)
														)

						# update view transformation matrices
						space.region_3d.update()

						# set view mode to "CAMERA"
						if space.region_3d.view_perspective != 'CAMERA': bpy.ops.view3d.view_camera(self.override)

						# set FOV to 14° as suggested by the LookingGlassFactory documentation
						# we calculate the field of view from the projection matrix
						self.viewportViewMatrix = space.region_3d.view_matrix.inverted_safe()
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
		self._handle_trackActiveWindow = bpy.types.SpaceView3D.draw_handler_add(self.trackActiveWindow, (context,), 'WINDOW', 'PRE_VIEW')

		# Register app handlers that check if the LookingGlass shall be updated:
		#  (1) Every time something in the scene changed (for camera movement and scene editing)
		#  (2) Every time, the current frame changed (for animations)
		self._handle_trackDepsgraphUpdates = bpy.app.handlers.depsgraph_update_post.append(self.trackDepsgraphUpdates)
		self._handle_trackFrameChanges = bpy.app.handlers.frame_change_post.append(self.trackDepsgraphUpdates)



		# HANDLERS FOR DRAWING PURPOSES
		# ++++++++++++++++++++++++++++++
		# TODO: this needs to be adjusted to enable switching between resolutions with different numbers of views
		# draw handler for rendering the views
		# NOTE: - we use 108 handlers, because this enables rendering of all views at maximum speed (limited by the fps of the Blender viewport)
		for view in range(0, 108, 1):#LookingGlassAddon.qs[self.preset]["totalViews"]):

			self._handle_viewDrawing.append(bpy.types.SpaceView3D.draw_handler_add(self.copyViewToQuilt, (context, view), 'WINDOW', 'POST_PIXEL'))

		# draw callback to draw the lightfield in the window
		self._handle_lightfieldDrawing = bpy.types.SpaceView3D.draw_handler_add(self.drawLightfield, (context,), 'WINDOW', 'POST_PIXEL')

		# draw callback to draw the lightfield cursor
		self._handle_lightfieldCursor = bpy.types.SpaceView3D.draw_handler_add(self.updateLightfieldCursor, (context,), 'WINDOW', 'PRE_VIEW')




		# HANDLERS FOR OPERATOR CONTROL
		# ++++++++++++++++++++++++++++++
		# Create timer event that runs every millisecond to check if the lightfield needs to be updated
		self.timerEvent = context.window_manager.event_timer_add(0.001, window=context.window)

		# add the modal handler
		context.window_manager.modal_handler_add(self)


		# MOVE THE WINDOW TO THE CORRECT SCREEN & TOGGLE FULLSCREEN
		################################################################

		# if on macOS
		if platform.system() == "Darwin":

			# TODO: Add a class function that handles this task for the different
			# operating systems automatically
			try:

				# find the NSScreen representing the Looking Glass
				for screen in NSScreen.screens():

					if screen.localizedName() == LookingGlassAddon.deviceList[int(self.settings.activeDisplay)]['hdmi']:

						# move the window to the Looking Glass Screen and resize it
						NSApp._.windows[-1].setFrame_display_(screen.visibleFrame(), True)

						break


				# set the "toogle fullscreen button" to True
				# NOTE: - via the update function of the boolean property,
				# 		  this already executes the window_fullscreen_toggle button
				self.settings.toggleLightfieldWindowFullscreen = True

			except:
				pass

		# if on Windows
		elif platform.system() == "Windows":

			# TODO: Add a class function that handles this task for the different
			# operating systems automatically
			try:

				# get the handle of the created window
				lightfielfWindow_hWnd = user32.GetActiveWindow()

				# move window to the left
				user32.MoveWindow(lightfielfWindow_hWnd, self.device['x'], self.device['y'], self.device['width'], self.device['height'], True)

				# set the "toogle fullscreen button" to True
				# NOTE: - via the update function of the boolean property,
				# 		  this already executes the window_fullscreen_toggle button
				self.settings.toggleLightfieldWindowFullscreen = True

			except:
				pass

			# we need to remember the scene this operator was invoked on
			# NOTE: - we need this in case the user changes the scene later
			#		- this MUST be called AFTER fullscreen was toggled in this invoke()
			LookingGlassAddon.LightfieldWindowInvoker = context.scene


		# if on linux
		elif platform.system() == "Linux":

			# TODO: Add a class function that handles this task for the different
			# operating systems automatically
			try:

				# TODO: Ugly hack. Should be improved later!
				# check for new window
				bpy.app.timers.register(functools.partial(self.toggleFullscreen, context))

			except:
				pass

		# keep the modal operator running
		return {'RUNNING_MODAL'}


	# make window fullscreen
	def toggleFullscreen(self, context):

		# if on linux, get the currently open windows
		if platform.system() == "Linux":
			LinuxWindowList = list(map(int, str(subprocess.run(['xdotool', 'search', '--name', 'Blender'], check=True, capture_output=True).stdout).replace('b\'','').split('\\n')[:-1]))
			lightfieldWindowID = list(set(LinuxWindowList) - set(LookingGlassAddon.LinuxWindowList))
			if len(lightfieldWindowID) == 1:
				lightfieldWindowID = lightfieldWindowID[0]
				print("New window: ", lightfieldWindowID)

				# Thanks to LoneTech for contributing!
				subprocess.run(['xdotool', 'windowmove', str(lightfieldWindowID), str(self.device['x']), str(self.device['y']), '--sync', ]) #, check=True)

				# set the "toogle fullscreen button" to True
				# NOTE: - via the update function of the boolean property,
				# 		  this already executes the window_fullscreen_toggle button
				self.settings.toggleLightfieldWindowFullscreen = True

				# we need to remember the scene this operator was invoked on
				# NOTE: - we need this in case the user changes the scene later
				#		- this MUST be called AFTER fullscreen was toggled in this invoke()
				LookingGlassAddon.LightfieldWindowInvoker = context.scene

				return None

			else:

				print("Waiting for new window ...")
				return 0.1

	# modal operator for controlled redrawing of the lightfield
	def modal(self, context, event):

		# update the internal variable for the settings, in case the scene has changed
		self.settings = context.scene.settings

		# update the variable for the current Looking Glass device
		if int(self.settings.activeDisplay) != -1: self.device = LookingGlassAddon.deviceList[int(self.settings.activeDisplay)]

		# if this scene was created AFTER the lightfield viewport was
		# invoked, it might not have the correct setting for the lightfield window
		# button
		if self.settings != None and LookingGlassAddon.LightfieldWindowInvoker != None:

			if self.settings.ShowLightfieldWindow != LookingGlassAddon.LightfieldWindowInvoker.settings.ShowLightfieldWindow:

				# adjust the setting
				self.settings.ShowLightfieldWindow = LookingGlassAddon.LightfieldWindowInvoker.settings.ShowLightfieldWindow
				self.settings.toggleLightfieldWindowFullscreen = LookingGlassAddon.LightfieldWindowInvoker.settings.toggleLightfieldWindowFullscreen
				self.settings.lightfieldWindowIndex = LookingGlassAddon.LightfieldWindowInvoker.settings.lightfieldWindowIndex



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




		# Handle the mouse cursor visibility
		################################################################

		# if the mouse cursor is inside the fullscreen lightfield window
		if (LookingGlassAddon.lightfieldWindow.width == self.device['width'] and LookingGlassAddon.lightfieldWindow.height == self.device['height']) and (event.mouse_x < LookingGlassAddon.lightfieldWindow.width and event.mouse_y < LookingGlassAddon.lightfieldWindow.height):

			# make mouse cursor invisible
			LookingGlassAddon.lightfieldWindow.cursor_modal_set('NONE')

		else:

			# make mouse cursor visible again
			LookingGlassAddon.lightfieldWindow.cursor_modal_restore()




		# Control lightfield redrawing in viewport mode
		################################################################

		# if the TIMER event for the lightfield rendering is called AND the automatic render mode is active
		if event.type == 'TIMER' and int(self.settings.renderMode) == 0:

			# if something has changed
			if self.modal_redraw == True or (self.depsgraph_update_time != 0.000 and time.time() - self.depsgraph_update_time > 0.5) or (int(context.scene.settings.lightfieldMode) == 1 and context.scene.settings.viewport_manual_refresh == True):

				if (self.depsgraph_update_time != 0.000 and time.time() - self.depsgraph_update_time > 0.5) or (int(context.scene.settings.lightfieldMode) == 1 and context.scene.settings.viewport_manual_refresh == True):

					# set to the currently chosen quality
					self.preset = int(context.scene.settings.quiltPreset)

 					# set to redraw
					self.modal_redraw = True

					# reset time variable
					self.depsgraph_update_time = 0.000

				# reset status variable for manual refreshes
				context.scene.settings.viewport_manual_refresh = False

				# update the viewport settings
				self.updateViewportSettings(context)

				# running modal
				return {'RUNNING_MODAL'}




		# Control events & lightfield cursor in the viewport
		################################################################
		# if left mouse click was released
		if (event.type == 'LEFTMOUSE' and event.value == 'PRESS'):

			# this is saved because otherwise we cant detect a real click
			self.mouse_click = True

		# if left mouse click was released
		if (event.type == 'LEFTMOUSE' and event.value == 'RELEASE' and self.mouse_click == True) or event.type == 'MOUSEMOVE':

			# save current mouse position
			self.mouse_x = self.modified_mouse_x = event.mouse_x
			self.mouse_y = self.modified_mouse_y = event.mouse_y

			# currently selected camera
			camera = self.settings.lookingglassCamera

			# if the lightfield viewport is attched to a camera
			if camera != None:

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
				view_frame_2D = [location_3d_to_region_2d(LookingGlassAddon.lightfieldRegion, LookingGlassAddon.lightfieldSpace.region_3d, p) for p in view_frame]

				# if all viewframe points were obtained
				if any(p is None for p in view_frame_2D) == False:

					# calculate dimensions in pixels
					view_frame_width = abs(view_frame_2D[2][0] - view_frame_2D[0][0])
					view_frame_height = abs(view_frame_2D[1][1] - view_frame_2D[0][1])

					# remap mouse coordinates in complete window to corresponding coordinates in the camera view frame
					self.modified_mouse_x = int(round(view_frame_2D[2][0] + (event.mouse_x / LookingGlassAddon.lightfieldRegion.width) * view_frame_width))
					self.modified_mouse_y = int(round(view_frame_2D[2][1] + (event.mouse_y / LookingGlassAddon.lightfieldRegion.height) * view_frame_height))

			# force area redraw to draw the cursor
			if context.area:
				context.area.tag_redraw()

			# if the left mouse button was clicked
			if (event.type == 'LEFTMOUSE' and event.value == 'RELEASE' and self.mouse_click == True):

				# select the object
				bpy.ops.view3d.select({'window': LookingGlassAddon.lightfieldWindow, 'region': LookingGlassAddon.lightfieldRegion, 'area': LookingGlassAddon.lightfieldArea}, location=(self.modified_mouse_x, self.modified_mouse_y))

				# reset variable
				self.mouse_click = False

			return {'RUNNING_MODAL'}


		# if manual lightfield update OR the quilt viewer is active
		elif int(self.settings.lightfieldMode) == 1 or int(self.settings.renderMode) == 1:

			# we prevent any event handling by Blender in the lightfield viewport
			return {'RUNNING_MODAL'}

		# pass event through
		return {'PASS_THROUGH'}


	# calculate hit position of a ray cast into the viewport to find the location
	# for the lightfield cursor in the lightfield
	def updateLightfieldCursor(self, context):

		# if this call belongs to the lightfield window
		if context.window == LookingGlassAddon.lightfieldWindow:

			# lightfield cursor is drawn in the Looking Glass viewport
			# because the standard cursor is too small and ... just 2D
			view_direction = region_2d_to_vector_3d(LookingGlassAddon.lightfieldRegion, LookingGlassAddon.lightfieldSpace.region_3d, (self.modified_mouse_x, self.modified_mouse_y))
			ray_start = region_2d_to_origin_3d(LookingGlassAddon.lightfieldRegion, LookingGlassAddon.lightfieldSpace.region_3d, (self.modified_mouse_x, self.modified_mouse_y))

			# calculate the ray end point (10000 is just an arbitrary length)
			ray_end = ray_start + (view_direction * 10000)

			# cast the ray into the scene
			# NOTE: The first parameter ray_cast expects was changed in Blender 2.91
			if bpy.app.version < (2, 91, 0): result, self.cursor, self.normal, index, object, matrix = context.scene.ray_cast(context.view_layer, ray_start, ray_end)
			if bpy.app.version >= (2, 91, 0): result, self.cursor, self.normal, index, object, matrix = context.scene.ray_cast(context.view_layer.depsgraph, ray_start, ray_end)

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

			# adjust the scene and view layer in the lightfield window
			# NOTE: We need this to handle multiple scenes & layers with the Looking Glass
			if LookingGlassAddon.lightfieldWindow != None:
				LookingGlassAddon.lightfieldWindow.scene = scene
				LookingGlassAddon.lightfieldWindow.view_layer = depsgraph.view_layer

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

		# if the space data exists
		if context.space_data != None and context.window != LookingGlassAddon.lightfieldWindow and LookingGlassAddon.BlenderWindow != context.window:

			# in any case, we need to track the active window
			# NOTE: this is important for finding the correct "Scene" and "View Layer"
			LookingGlassAddon.BlenderWindow = context.window



	# pass quilt values to shader
	def passQuiltSettingsToShader(self, preset):

		# Pass quilt settings to the lightfield shader
		self.lightFieldShader.bind()

		try:
			# set viewportion to the full view
			# NOTE: This is always 1 for landscape, but might be different for portait LG?
			self.lightFieldShader.uniform_float("viewPortion", (LookingGlassAddon.qs[self.preset]["viewWidth"] * LookingGlassAddon.qs[self.preset]["columns"] / LookingGlassAddon.qs[self.preset]["width"], LookingGlassAddon.qs[self.preset]["viewHeight"] * LookingGlassAddon.qs[self.preset]["rows"] / LookingGlassAddon.qs[self.preset]["height"]))
			self.lightFieldShader.uniform_int("overscan", 0)
		except ValueError:
			pass  # These uniforms are not used by the free shader

		# number of columns and rows of views
		self.lightFieldShader.uniform_float("tile", (LookingGlassAddon.qs[self.preset]["columns"], LookingGlassAddon.qs[self.preset]["rows"], LookingGlassAddon.qs[self.preset]["totalViews"]))




	# Compile the lightfield shader, which prepares the quilt for display
	# on the LookingGlass as a hologram
	def loadlightFieldShaders(self):

		# NOTE: For some reason, I don't understand
		# 	    we need to change uvz * tile.z to (1 + uvz.z) * tile.z) in the shader
		# 	    in order to get the correct quilt display in Blender 2.83
		#
		#		Since this behavior disappeared in Blender 2.90 it might have
		#		been related to a bug in 2.83 ... I therefore use this hacky solution
		if bpy.app.version < (2, 90, 0):

			# get all lines of the shader
			lines = LookingGlassAddon.lightfieldFragmentShaderSource.splitlines(True)

			# go through all lines
			for i, line in enumerate(lines):

				# if this is the line we want to replace, do it
				if "floor(uvz.z * tile.z)" in line:
					lines[i] = "\tfloat z = floor((1 + uvz.z) * tile.z);\n"
					break

			# write back the modifed shader source to the global variable
			LookingGlassAddon.lightfieldFragmentShaderSource = "".join(lines)

        # Compile lightfield shader via GPU module
		self.lightFieldShader = gpu.types.GPUShader(LookingGlassAddon.lightfieldVertexShaderSource, LookingGlassAddon.lightfieldFragmentShaderSource)

		# prepare a batch used for drawing the lightfield into a texture of correct size
		self.lightFieldShaderBatch = batch_for_shader(
			self.lightFieldShader, 'TRI_FAN',
			{
				"vertPos_data": ((-1, -1), (1, -1), (1, 1), (-1, 1)),
			},
		)

		# return the OpenGL program code
		return self.lightFieldShader



	# Load Looking Glass calibration into the lightfield shader
	def loadCalibrationIntoShader(self):

		# if a Looking Glass is selected
		if int(self.settings.activeDisplay) > -1:

			# obtain information from the connected Looking Glass and
			# load its calibration into the lightfield shader
			self.lightFieldShader.bind()
			self.lightFieldShader.uniform_float("pitch", self.device['pitch'])
			self.lightFieldShader.uniform_float("tilt", self.device['tilt'])
			self.lightFieldShader.uniform_float("center", self.device['center'])
			self.lightFieldShader.uniform_float("subp", self.device['subp'])
			self.lightFieldShader.uniform_int("ri", self.device['ri'])
			self.lightFieldShader.uniform_int("bi", self.device['bi'])
			try:
				self.lightFieldShader.uniform_int("invView", int(self.device['invView']))
				self.lightFieldShader.uniform_int("quiltInvert", 0)
				self.lightFieldShader.uniform_float("displayAspect", self.device['aspectRatio'])
				self.lightFieldShader.uniform_float("quiltAspect", self.device['aspectRatio'])
			except ValueError:
				pass  # These uniforms are not used by the free shader


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
			offsetAngle = (0.5 - view / (LookingGlassAddon.qs[self.preset]["totalViews"] - 1)) * radians(self.device['viewCone'])

			# calculate the offset that the camera should move
			offset = cameraDistance * tan(offsetAngle)

			# translate the view matrix (position) by the calculated offset in x-direction
			viewMatrix = Matrix.Translation((offset, 0, 0)) @ viewMatrix

			# modify the projection matrix, relative to the camera size and aspect ratio
			projectionMatrix[0][2] += offset / (cameraSize * self.device['aspectRatio'])

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
			offsetAngle = (0.5 - view / (LookingGlassAddon.qs[self.preset]["totalViews"] - 1)) * radians(self.device['viewCone'])

			# calculate the offset that the camera should move
			offset = cameraDistance * tan(offsetAngle)

			# translate the view matrix (position) by the calculated offset in x-direction
			viewMatrix = Matrix.Translation((offset, 0, cameraDistance)) @ viewMatrix

			# modify the projection matrix, relative to the camera size and aspect ratio
			projectionMatrix[0][2] += offset / (cameraSize * self.device['aspectRatio'])

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

		# if the low quality quilt settings are active AND the user selected the "SOLID SHADER PREVIEW" option
		if LookingGlassAddon.lightfieldSpace.shading.type == 'RENDERED' and context.engine == 'CYCLES':

			# change the shading type to SOLID
			LookingGlassAddon.lightfieldSpace.shading.type = 'SOLID'

			# notify user
			self.report({"WARNING"}, "Render engine (%s) not supported in lightfield viewport. Switched to SOLID mode." % context.engine)


		# always disable the hdri preview spheres
		self.override['space_data'].overlay.show_look_dev = False





	# Draw function which copies data from the 3D View
	def copyViewToQuilt(self, context, view):

		# if the quilt must be redrawn AND the current image editor belongs to the lightfield window AND the Multiview object exists
		if self.modal_redraw == True and context.area == LookingGlassAddon.lightfieldArea:

			# UPDATE QUILT SETTINGS
			# ++++++++++++++++++++++++++++++++++++++++++++++++

			# if this function call belongs to the first view
			if view == 0:

				self.start_multi_view = time.time()

				# if the quilt and view settings changed
				if self.last_preset != self.preset:

					# update the preset variable
					self.last_preset = self.preset

					# pass quilt settings to the lightfield shader
					self.passQuiltSettingsToShader(self.preset)

			#print("copyViewToQuilt start (view: ", view, ": ", time.time() - self.start_multi_view, (LookingGlassAddon.qs[self.preset]["viewOffscreens"][view].width, LookingGlassAddon.qs[self.preset]["viewOffscreens"][view].height))


			# PREPARE VIEW & PROJECTION MATRIX
			# ++++++++++++++++++++++++++++++++++++++++++++++++
			start_test = time.time()

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
				view_matrix = view_matrix.inverted_safe()

				# get the camera's projection matrix
				projection_matrix = camera.calc_matrix_camera(
						depsgraph=LookingGlassAddon.lightfieldWindow.view_layer.depsgraph,
						x = LookingGlassAddon.qs[self.preset]["viewWidth"],
						y = LookingGlassAddon.qs[self.preset]["viewHeight"],
						scale_x = 1.0,
						scale_y = (LookingGlassAddon.qs[self.preset]["rows"] / LookingGlassAddon.qs[self.preset]["columns"]) / self.device['aspectRatio'],
					)

			# otherwise we take the (lightfield) viewport matrices
			else:

				# get viewports modelview matrix
				view_matrix = LookingGlassAddon.lightfieldSpace.region_3d.view_matrix.copy()

				# get the viewports projection matrix
				projection_matrix = LookingGlassAddon.lightfieldSpace.region_3d.window_matrix.copy()

			print("get matrices: ", time.time() - start_test)

			# calculate the offset-projection of the current view
			view_matrix, projection_matrix = self.setupVirtualCameraForView(camera, view, view_matrix, projection_matrix)

			print("setup camera: ", time.time() - start_test)


			# RENDER THE VIEW INTO THE OFFSCREEN
			# ++++++++++++++++++++++++++++++++++++++++++++++++
			# NOTE: - the draw_view3d method does not apply the color management
			# 		- files bug report (on 2020-12-28): https://developer.blender.org/T84227

			# draw the viewport rendering to the offscreen for the current view
			LookingGlassAddon.qs[self.preset]["viewOffscreens"][view].draw_view3d(
				# we use the "Scene" and the "View Layer" that is active in the Window
				# the user currently works in
				scene=LookingGlassAddon.lightfieldWindow.scene,
				view_layer=LookingGlassAddon.lightfieldWindow.view_layer,
				view3d=self.override['space_data'],
				region=self.override['region'],
				view_matrix=view_matrix,
				projection_matrix=projection_matrix)


			print("draw_view3d (view: ", view, "): ", time.time() - start_test)
			#print("copyViewToQuilt end: ", time.time() - self.start_multi_view)

			# if this was the last view
			if view == LookingGlassAddon.qs[self.preset]["totalViews"] - 1:

				# update the quilt image in the image_editor,
				# which is used for display in the LookingGlass
				self.updateQuilt = True

				# reset draw variable:
				# This is here to prevent excessive redrawing
				self.modal_redraw = False



	# Draw all the views into the quilt, if something has changed
	# and then apply the lightfield shader. Finally, draw the lightfield
	# directly into the SpaceView3D created for the LookingGlass.
	def drawLightfield(self, context):

		# if this call belongs to the lightfield window
		if context.window == LookingGlassAddon.lightfieldWindow and context.area == LookingGlassAddon.lightfieldArea:

			# VIEWPORT MODE
			##################################################################
			if int(self.settings.renderMode) == 0 or (int(self.settings.renderMode) == 1 and context.scene.settings.quiltImage == None):

				start_blit = time.time()

				# if the quilt must be updated
				if self.updateQuilt == True or self.settings.viewport_show_cursor == True:

					# bind the offscreen used for the quilt
					with LookingGlassAddon.qs[self.preset]["quiltOffscreen"].bind():

						start_blit = time.time()
						# for all views
						for view in range(LookingGlassAddon.qs[self.preset]["totalViews"]):

							# push/pop the projection matrices
							with gpu.matrix.push_pop_projection():

								# reset matrices:
								# Use normalized device coordinates [-1, 1]
								gpu.matrix.load_matrix(Matrix.Identity(4))
								gpu.matrix.load_projection_matrix(Matrix.Identity(4))

								# calculate the position of the view
								x = 2 * (view % LookingGlassAddon.qs[self.preset]["columns"]) * LookingGlassAddon.qs[self.preset]["viewWidth"] / LookingGlassAddon.qs[self.preset]["width"] - 1
								y = 2 * int(view / LookingGlassAddon.qs[self.preset]["columns"]) * LookingGlassAddon.qs[self.preset]["viewHeight"] / LookingGlassAddon.qs[self.preset]["height"] - 1

								# Copy the view texture into the quilt texture,
								# but transform the position and dimensions to
								# normalized device coordinates before that
								draw_texture_2d(LookingGlassAddon.qs[self.preset]["viewOffscreens"][view].color_texture, (x, y), 2 * LookingGlassAddon.qs[self.preset]["viewWidth"] / LookingGlassAddon.qs[self.preset]["width"], 2 * LookingGlassAddon.qs[self.preset]["viewHeight"] / LookingGlassAddon.qs[self.preset]["height"])

								# draw the lightfield mouse cursor if desired
								if self.settings.viewport_show_cursor == True:

									# TODO: Maybe there is a better way to check this?
									# but only, if the mouse cursor is inside the fullscreen lightfield window
									if (LookingGlassAddon.lightfieldWindow.width == self.device['width'] and LookingGlassAddon.lightfieldWindow.height == self.device['height']) and (self.mouse_x < LookingGlassAddon.lightfieldWindow.width and self.mouse_y < LookingGlassAddon.lightfieldWindow.height):

										self.drawCursor3D(context, view, x, y, self.settings.viewport_cursor_size, 8)

							#print("Copied view ", view, (x, y), " into the quilt texture. Required time: ", time.time() - start_blit)

						#print("Required total time: ", time.time() - start_blit)


				# Draw the lightfield
				# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
				# bind the quilt texture
				bgl.glActiveTexture(bgl.GL_TEXTURE0)
				bgl.glBindTexture(bgl.GL_TEXTURE_2D, LookingGlassAddon.qs[self.preset]["quiltOffscreen"].color_texture)

				# bind the lightfield shader for drawing operations
				self.lightFieldShader.bind()

				# load the current debug view mode into the shader
				self.lightFieldShader.uniform_int("debug", context.scene.settings.debug_view)

				# draw the quilt texture
				self.lightFieldShaderBatch.draw(self.lightFieldShader)



			# QUILT VIEWER MODE
			##################################################################
			# TODO: Currently only quilts are supported. Maybe implement support
			#		for Multiview images later? (context.scene.settings.quiltImage.is_multiview == True)
			# if the quilt view mode is active AND an image is loaded
			elif int(self.settings.renderMode) == 1 and context.scene.settings.quiltImage != None:

				# default preset is current preset
				preset = self.preset

				# try to find the fitting preset based on quilt size
				# TODO: For the moment checking for the quilt size is okay,
				#		but later we need better checks. Can we access metadata?
				for i in range(len(LookingGlassAddon.qs)):
					if LookingGlassAddon.qs[i]['width'] == context.scene.settings.quiltImage.size[0]:

						# use this preset
						preset = i

						break

				# pass quilt settings to the lightfield shader
				self.passQuiltSettingsToShader(preset)

				# if the texture for the quilt images exists
				if LookingGlassAddon.quiltTextureID != None:

					# bind the quilt texture
					bgl.glActiveTexture(bgl.GL_TEXTURE0)
					bgl.glBindTexture(bgl.GL_TEXTURE_2D, LookingGlassAddon.quiltTextureID.to_list()[0])



				# Draw the lightfield
				# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

				# bind the lightfield shader for drawing operations
				self.lightFieldShader.bind()

				# load the current debug view mode into the shader
				self.lightFieldShader.uniform_int("debug", context.scene.settings.debug_view)

				# draw the quilt texture
				self.lightFieldShaderBatch.draw(self.lightFieldShader)



			# if the quilt was updated
			if self.updateQuilt == True:

				# reset state variable to avoid excessive redrawing
				self.updateQuilt = False




	# TODO: In this method is room for speed optimization
	# draw the mouse cursor
	def drawCursor3D(self, context, view, xoffset, yoffset, radius, segments):

		# if this call belongs to the lightfield window
		if context.window == LookingGlassAddon.lightfieldWindow and context.area == LookingGlassAddon.lightfieldArea:
			start_timer = time.time()
			# current camera object
			camera = self.settings.lookingglassCamera

			# Calculate view & projection matrix
			# ++++++++++++++++++++++++++++++++++++++
			# if a camera is selected
			if camera != None:

				# get camera's modelview matrix
				view_matrix = camera.matrix_world.copy()

				# correct for the camera scaling
				view_matrix = view_matrix @ Matrix.Scale(1/camera.scale.x, 4, (1, 0, 0))
				view_matrix = view_matrix @ Matrix.Scale(1/camera.scale.y, 4, (0, 1, 0))
				view_matrix = view_matrix @ Matrix.Scale(1/camera.scale.z, 4, (0, 0, 1))

				# calculate the inverted view matrix because this is what the draw_view_3D function requires
				view_matrix = view_matrix.inverted_safe()

				# get the camera's projection matrix
				projection_matrix = camera.calc_matrix_camera(
						depsgraph = LookingGlassAddon.lightfieldWindow.view_layer.depsgraph,
						x = LookingGlassAddon.qs[self.preset]["viewWidth"],
						y = LookingGlassAddon.qs[self.preset]["viewHeight"],
						scale_x = 1.0,
						scale_y = (LookingGlassAddon.qs[self.preset]["rows"] / LookingGlassAddon.qs[self.preset]["columns"]) / self.device['aspectRatio'],
					)

			# otherwise we take the (lightfield) viewport matrices
			else:

				# get viewports modelview matrix
				view_matrix = LookingGlassAddon.lightfieldSpace.region_3d.view_matrix.copy()

				# get the viewports projection matrix
				projection_matrix = LookingGlassAddon.lightfieldSpace.region_3d.window_matrix.copy()

			# calculate the offset-projection of the current view
			view_matrix, projection_matrix = self.setupVirtualCameraForView(camera, view, view_matrix, projection_matrix)



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

					width_half = (2 * LookingGlassAddon.qs[self.preset]["viewWidth"] / LookingGlassAddon.qs[self.preset]["width"]) / 2.0
					height_half = (2 * LookingGlassAddon.qs[self.preset]["viewHeight"] / LookingGlassAddon.qs[self.preset]["height"]) / 2.0

					location = Vector((
						width_half + width_half * (prj.x / prj.w),
						height_half + height_half * (prj.y / prj.w),
					))

				else:

					location = Vector((0, 0))

				# add point to the list and add the currect x- & y-offset for the current view
				cursor_geometry_coords.append((xoffset + location[0], yoffset + location[1]))


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

					# get modelview matrix
					view_matrix = camera.matrix_world

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
