# ###################### BEGIN LICENSE BLOCK ###########################
#
# Copyright © 2021 Christian Stolze
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# ####################### END LICENSE BLOCK ############################

# EXTERNAL PACKAGE DEPENDENCIES
###################################################
import io, os
import numpy as np
from PIL import Image

# debuging
import timeit

# INTERNAL PACKAGE DEPENDENCIES
###################################################
from pylightio.formats import *

# PREPARE LOGGING
###################################################
import logging

# get the library logger
logger = logging.getLogger('pyLightIO')



# LIGHTFIELD IMAGE TYPES FOR LOOKING GLASS DEVICES
###################################################
# the following classes are used to represent, convert, and manipulate a set of
# views for Looking Glass devices
class LookingGlassQuilt(BaseLightfieldImageFormat):

    # PRIVATE ATTRIBUTES
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    __merged_numpy = None   # a numpy array which holds all the view data


    # DEFINE PUBLIC CLASS ATTRIBUTES
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # supported quilt formats
    class formats:

        __dict = {

            # first gen devices
            1: {'description': "2k Quilt, 32 Views", 'quilt_width': 2048, 'quilt_height': 2048, 'view_width': 512, 'view_height': 256, 'columns': 4, 'rows': 8, 'total_views': 32, 'hidden': False },
            2: {'description': "4k Quilt, 45 Views", 'quilt_width': 4096, 'quilt_height': 4096, 'view_width': 819, 'view_height': 455, 'columns': 5, 'rows': 9, 'total_views': 45, 'hidden': False },
            3: {'description': "8k Quilt, 45 Views", 'quilt_width': 8192, 'quilt_height': 8192, 'view_width': 1638, 'view_height': 910, 'columns': 5, 'rows': 9, 'total_views': 45, 'hidden': False },

            #Looking Glass Portrait
            4: {'description': "Portrait, 48 Views", 'quilt_width': 3360, 'quilt_height': 3360, 'view_width': 420, 'view_height': 560, 'columns': 8, 'rows': 6, 'total_views': 48, 'hidden': False },

        }

        @classmethod
        def add(cls, values):
            ''' add a new format by passing a dict '''
            cls.__dict[len(cls.__dict) + 1] = values
            return len(cls.__dict)

        @classmethod
        def remove(cls, id):
            ''' remove an existing format '''
            cls.__dict.pop(id, None)

        @classmethod
        def get(cls, id=None):
            ''' return the complete dictionary or the dictionary of a specific format '''
            if not id: return cls.__dict
            else:      return cls.__dict[id]

        @classmethod
        def set(cls, id, values):
            ''' modify an existing format by passing a dict '''
            if id in cls.__dict.keys(): cls.__dict[id] = values

        @classmethod
        def count(cls):
            ''' get number of formats '''
            if id in cls.__dict.keys(): return len(cls.__dict)

        # NOTE: the following is useful for applications where the formats are
        #       exposed in an UI to the user, but if not all formats shall be exposed
        @classmethod
        def hide(cls, id, value):
            ''' set the 'hidden' flag on this format '''
            if id in cls.__dict.keys(): cls.__dict[id]['hidden'] = value

        @classmethod
        def is_hidden(cls, id):
            ''' returns True if the quilt format is a private one '''
            if id in cls.__dict.keys(): return cls.__dict[id]['hidden']


    # INSTANCE METHODS - IMPLEMENTED BY SUBCLASS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    def __init__(self, id=None, colormode='RGBA'):
        ''' create a new and empty lightfield image object of type LookingGlassQuilt '''

        # first make the mandatory call to the __init__ method of the base class
        super().__init__()

        # if no quilt format id was passed
        if not id:

            # store color information
            self.colormode = colormode
            self.colorchannels = len(colormode)

            # store quilt metadata
            self.metadata['quilt_width'] = 0
            self.metadata['quilt_height'] = 0
            self.metadata['view_width'] = 0
            self.metadata['view_height'] = 0
            self.metadata['rows'] = 0
            self.metadata['columns'] = 0
            self.metadata['count'] = 0

        # if a valid id was passed
        elif id in LookingGlassQuilt.formats.get().keys():

            # TODO: Implement this as arguments in a reasonable way
            # store color information
            self.colormode = colormode
            self.colorchannels = len(colormode)

            # store quilt metadata
            self.metadata['quilt_width'] = LookingGlassQuilt.formats.get(id)['quilt_width']
            self.metadata['quilt_height'] = LookingGlassQuilt.formats.get(id)['quilt_height']
            self.metadata['view_width'] = LookingGlassQuilt.formats.get(id)['view_width']
            self.metadata['view_height'] = LookingGlassQuilt.formats.get(id)['view_height']
            self.metadata['rows'] = LookingGlassQuilt.formats.get(id)['rows']
            self.metadata['columns'] = LookingGlassQuilt.formats.get(id)['columns']
            self.metadata['count'] = LookingGlassQuilt.formats.get(id)['total_views']

        else:

            raise TypeError("There is no quilt format with the id '%i'. Please choose one of the following: %s" % (id, LookingGlassQuilt.formats.get()))

    def load(self, filepath):
        ''' load the quilt file from the given path and convert to numpy views '''
        if os.path.exists(filepath):

            start = timeit.default_timer()
            # use PIL to load the image from disk
            # NOTE: This makes nearly all of the execution time of the load() method
            quilt_image = Image.open(filepath)
            if quilt_image:

                # reset state variable
                found = False

                # for each supported quilt format
                for qf in LookingGlassQuilt.formats.get().values():

                    # if the image dimensions matches one of the quilt formats
                    # NOTE: We allow a difference of +/-1 px in width and height
                    #       to accomodate for rounding errors in view width/height
                    if quilt_image.width in range(qf['quilt_width'] - 1, qf['quilt_width'] + 1) and quilt_image.height in range(qf['quilt_height'] - 1, qf['quilt_height'] + 1):

                        # store new row and column number in the metadata
                        self.metadata['rows'] = qf['rows']
                        self.metadata['columns'] = qf['columns']
                        self.metadata['count'] = qf['rows'] * qf['columns']
                        self.metadata['view_width'] = qf['view_width']
                        self.metadata['view_height'] = qf['view_height']

                        # update state variable
                        found = True

                # if no fitting quilt format was found
                if not found: raise TypeError("The loaded image is not in a supported format. Please check the image dimensions.")

                # TODO: This takes 0.5 to 1.5 s ... is there a faster way?
                # convert it to a numpy array
                quilt_np = np.asarray(quilt_image, dtype=np.uint8)
                # crop the image in case, the size is incorrect due to rounding
                # errors
                quilt_np = quilt_np[0:(self.metadata['rows'] * self.metadata['view_height']), 0:(self.metadata['columns'] * self.metadata['view_width']), :]

                # store the colormode
                self.colormode = quilt_image.mode

                # store the size and color depth in the meta data of the instance
                self.metadata['quilt_height'], self.metadata['quilt_width'], self.colorchannels = quilt_np.shape

                # then we reshape the quilt into the array of individual views ...
                views = np.flip(quilt_np.reshape(self.metadata['rows'], self.metadata['view_height'], self.metadata['columns'], self.metadata['view_width'], self.colorchannels).swapaxes(1, 2), 0).reshape(self.metadata['count'], self.metadata['view_height'], self.metadata['view_width'], self.colorchannels)

                # add each view image data array as a numpyarray view to the LookingGlassQuilt
                for data in views:
                    view = self.append_view(data, LightfieldView.formats.numpyarray)

                return True

            raise TypeError("The quilt image was found but could not be opened. The image format is not supported.")

        raise FileNotFoundError("The quilt image was not found: %s" % filepath)

    def from_buffer(self, data, width, height, colorchannels):
        ''' load the quilt from the given data block and convert to numpy views '''

        # if this is a numpy array
        if type(data) == np.ndarray:

            start = timeit.default_timer()

            # status variable for the quilt format
            found = False

            # for each supported quilt format
            for qf in LookingGlassQuilt.formats.get().values():

                # if the image dimensions matches one of the quilt formats
                # NOTE: We allow a difference of +/-1 px in width and height
                #       to accomodate for rounding errors in view width/height
                if data.shape[0] in range((qf['quilt_width'] - 1) * (qf['quilt_height'] - 1) * 4, (qf['quilt_width'] + 1) * (qf['quilt_height'] + 1) * 4):

                    # store new row and column number in the metadata
                    self.metadata['rows'] = qf['rows']
                    self.metadata['columns'] = qf['columns']
                    self.metadata['count'] = qf['rows'] * qf['columns']
                    self.metadata['view_width'] = qf['view_width']
                    self.metadata['view_height'] = qf['view_height']

                    # update state variable
                    found = True

            # if no fitting quilt format was found
            if not found: raise TypeError("The loaded image is not in a supported format. Please check the image dimensions.")

            # convert it to a numpy array
            quilt_np = data.reshape(height, width, colorchannels)

            # crop the image in case, the size is incorrect due to rounding
            # errors
            quilt_np = np.flip(quilt_np[0:(self.metadata['rows'] * self.metadata['view_height']), 0:(self.metadata['columns'] * self.metadata['view_width']), :], 0)

            # store the colormode
            self.colormode = 'RGBA'

            # store the size and color depth in the meta data of the instance
            self.metadata['quilt_height'], self.metadata['quilt_width'], self.colorchannels = quilt_np.shape

            # then we reshape the quilt into the array of individual views ...
            views = np.flip(quilt_np.reshape(self.metadata['rows'], self.metadata['view_height'], self.metadata['columns'], self.metadata['view_width'], self.colorchannels).swapaxes(1, 2), 0).reshape(self.metadata['count'], self.metadata['view_height'], self.metadata['view_width'], self.colorchannels)

            # add each view image data array as a numpyarray view to the LookingGlassQuilt
            for data in views:

                view = self.append_view(data, LightfieldView.formats.numpyarray)

            return True

        raise FileNotFoundError("The data block needs to be of type '%s'" % np.ndarray)

    def save(self, filepath, format):
        ''' save the lightfield image in its specific format to a disk file '''

        pass

    def delete(self, lightfield):
        ''' delete the given lightfield image object '''
        pass

    def set_views(self, list, format):
        ''' store the list of LightfieldViews and their format in the quilt '''

        # we override the base class function to introduce an additional check:
        # if the given list has the correct length for this quilt
        if len(list) == self.metadata['count']:

            # and then call the base class function
            return super().set_views(list, format)

        raise ValueError("Invalid view set. %i views were passed, but %i were required." % (len(list), self.metadata['count']))

    def decode(self, format, flip_views=False, custom_decoder = None):
        ''' return the lightfield image object in a specific format '''

        # get the view data
        views = self.get_view_data()
        views_format = self.views_format

        # if a custom decoder function is passed
        if custom_decoder:

            # call this function
            quilt = custom_decoder(views, views_format, format)

            # return the bytesio of the quilt
            return quilt


        # TODO: HERE IS THE PLACE TO DEFINE STANDARD CONVERSIONS THAT CAN BE
        #       USED IN MULTIPLE PROGRAMMS

        # if the image shall be returned as
        if format == LightfieldImage.decoderformat.bytesio:

            # if the views are in a numpy array format
            if views_format == LightfieldView.formats.numpyarray:

                # create a numpy quilt from numpy views
                quilt_numpy = self.__from_views_to_quilt_numpy(flip_views=flip_views)

                # convert to bytesio
                quilt_bytesio = self.__from_numpyarray_to_bytesio(quilt_numpy)

                # return the bytesio of the quilt
                return quilt_bytesio

            # otherwise raise exception
            raise TypeError("The given views format '%s' is not supported." % views_format)

        # otherwise raise exception
        raise TypeError("The requested lightfield format '%s' is not supported." % format)


    # PRIVATE INSTANCE METHODS: VIEWS TO QUILTS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # NOTE: this function is based on https://stackoverflow.com/questions/42040747/more-idiomatic-way-to-display-images-in-a-grid-with-numpy
    # NOTE: This call takes 15 to 30 ms -> can this be optimized?
    def __from_views_to_quilt_numpy(self, flip_views=False, dtype = np.uint8):
        ''' convert views given as numpy arrays to a quilt as a numpy array '''

        start = timeit.default_timer()

        # if no merged numpy array exists
        if self.__merged_numpy is None:

            # get the views
            views = self.get_view_data()
            views_format = self.views_format

            # create a numpy array from the list of views
            self.__merged_numpy = np.asarray(views)

            # step 1: get an array of shape (rows, columns, view_height, view_width)
            self.__merged_numpy = self.__merged_numpy.reshape(self.metadata['rows'], self.metadata['columns'], self.metadata['view_height'], self.metadata['view_width'], self.colorchannels)

            # then we reshape the numpy array to the quilt shape:

            # step 2: get a reverted view into the numpy array
            # NOTE: image origins are in the top left of the image and therefore the
            #       row 0 starts with the leftmost camera perspective. But for the
            #       quilt we need this row to be at the bottom. Therefore, revert order.
            self.__merged_numpy = self.__merged_numpy[::-1, :, :]

            # step 3: swap the "columns" and "view_height" axis, so that we get an
            #         array of shape (rows, view_height, columns, view_width, colorchannels)
            self.__merged_numpy = self.__merged_numpy.swapaxes(1, 2)

            # re-assign the numpy arrays for all underlying LightfieldView-objects
            # as (memory)views into the __merged_numpy array
            # NOTE: This step speeds up the quilt creation by some tens of milliseconds
            #       since the next time the LightfieldView pixel data is updated
            #       it directly updates the pixel data in the __merged_numpy array.
            i_x = i_y = 0
            for i, view in enumerate(self.views):

                # create subarray view into the quilt pixel data
                view['view'].data = self.__merged_numpy[self.metadata['rows'] - 1 - i_y, :, i_x, :, :]

                # choose column and row
                if (i + 1) % self.metadata['columns'] == 0 and i > 0:
                    i_x = 0
                    i_y += 1
                else:
                    i_x += 1

        # step 4: flip the individual views vertically, if required
        if flip_views: quilt_np = self.__merged_numpy[::, ::-1, ::, ::, ::]

        # step 5: reshape to the final quilt (rows * view_height, columns * view_width)
        quilt_np = quilt_np.reshape(self.metadata['quilt_height'], self.metadata['quilt_width'], self.colorchannels)

        # log info
        logger.debug(" [#] Created quilt as numpy array in %.3f ms." % ((timeit.default_timer() - start) * 1000))

        # output the views
        return quilt_np


    # PRIVATE INSTANCE METHODS: CONVERT BETWEEN DECODERFORMATS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    def __from_numpyarray_to_bytesio(self, data):
        ''' convert pixel data from numpy array to BytesIO object '''

        start = timeit.default_timer()
        # create a PIL image from the numpy
        quilt_image = Image.fromarray(data)
        logger.debug(" [#] Converted numpy array to pillow image in %.3f ms." % ((timeit.default_timer() - start) * 1000))

        # create a BytesIO object and save the numpy image data therein
        start = timeit.default_timer()
        bytesio = io.BytesIO()
        quilt_image.save(bytesio, 'BMP')
        logger.debug(" [#] Saved image data in %.3f ms." % ((timeit.default_timer() - start) * 1000))

        # return the bytesio object
        return bytesio

    # CLASS PROPERTIES
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # @property                   # read-only property
    # def formats(self):
    #     return self.__formats

    # @presets.setter
    # def presets(self, value):
    #     self.__formats = value
