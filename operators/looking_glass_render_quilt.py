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

import bpy, bgl
import gpu
import json
import subprocess
import logging
import time
import os, sys
import ctypes
from gpu_extras.batch import batch_for_shader
from gpu_extras.presets import draw_texture_2d, draw_circle_2d
from bpy_extras.view3d_utils import location_3d_to_region_2d

from bgl import *
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
	bl_label = "Looking Glass Quilt Rendering"
	bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

	# status variables
	rendering_status = None		# rendering status
	rendering_cancelled = None	# was render cancelled by user
	rendering_frame = None	  # the view of the current frame that is currently rendered
	rendering_view = None	  	# the view of the current frame that is currently rendered

	# event and app handler ids
	_handle_event_timer = None	# modal timer event



	# callback functions
	def pre_render(self, dummy):

		print("[INFO] Render started")
		# set status variable:
		# notify the modal operator that a rendering task is started
		self.rendering_status = True

	def post_render(self, dummy):

		print("[INFO] Render finished")
		# set status variable:
		# notify the modal operator that the rendering task is finished
		self.rendering_status = True

	def cancel_render(self, dummy):
		print("[INFO] Render cancelled")

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



	# cancel the modal operator
	def cancel(self, context):

		print("Everything is done.")

		# return None since this is expected by the operator
		return None




	def invoke(self, context, event):

		# PREPARE STUFF ?
		################################################################


		# REGISTER ALL HANDLERS FOR THE QUILT RENDERING
		################################################################

		# HANDLERS FOR THE RENDERING PROCESS
		# +++++++++++++++++++++++++++++++++++
		bpy.app.handlers.render_pre.append(self.pre_render)
		bpy.app.handlers.render_post.append(self.post_render)
		bpy.app.handlers.render_cancel.append(self.cancel_render)

		# HANDLER FOR EVENT TIMER
		# ++++++++++++++++++++++++++++++++++
		# Create timer event that runs every second to check the rendering process
		self._handle_event_timer = context.window_manager.event_timer_add(1, window=context.window)

		# START THE MODAL OPERATOR
		# ++++++++++++++++++++++++++++++++++
		# add the modal operator handler
		context.window_manager.modal_handler_add(self)

		print("Invoked modal operator")

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

				# remove render app handlers
				bpy.app.handlers.render_pre.remove(self.pre_render)
				bpy.app.handlers.render_post.remove(self.post_render)
				bpy.app.handlers.render_cancel.remove(self.cancel_render)

				# remove event timer
				context.window_manager.event_timer_remove(self._handle_event_timer)

				self.report({"INFO"},"QUILT RENDER FINISHED")
				return {"FINISHED"}




			# RENDERING WAS CANCELLED
			# ++++++++++++++++++++++++++++++++++
			elif self.rendering_status == True and self.rendering_cancelled == True:

				# remove render app handlers
				bpy.app.handlers.render_pre.remove(self.pre_render)
				bpy.app.handlers.render_post.remove(self.post_render)
				bpy.app.handlers.render_cancel.remove(self.cancel_render)

				# remove event timer
				context.window_manager.event_timer_remove(self._handle_event_timer)

				self.report({"INFO"},"QUILT RENDER CANCELLED")
				return {"CANCELLED"}

		# pass event through
		return {'PASS_THROUGH'}
