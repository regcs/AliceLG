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

# debuging
import time

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

            # third gen devices
            5: {'description': "Go, 66 Views", 'quilt_width': 4092, 'quilt_height': 4092, 'view_width': 372, 'view_height': 682, 'columns': 11, 'rows': 6, 'total_views': 66, 'hidden': False },
            6: {'description': "16 Landscape, 49 Views", 'quilt_width': 5999, 'quilt_height': 5999, 'view_width': 857, 'view_height': 857, 'columns': 7, 'rows': 7, 'total_views': 49, 'hidden': False },
            7: {'description': "16 Portrait, 66 Views", 'quilt_width': 5995, 'quilt_height': 6000, 'view_width': 545, 'view_height': 1000, 'columns': 11, 'rows': 6, 'total_views': 66, 'hidden': False },
            8: {'description': "32 Landscape, 49 Views", 'quilt_width': 8190, 'quilt_height': 8190, 'view_width': 1170, 'view_height': 1170, 'columns': 7, 'rows': 7, 'total_views': 49, 'hidden': False },
            9: {'description': "32 Portrait, 66 Views", 'quilt_width': 8184, 'quilt_height': 8184, 'view_width': 744, 'view_height': 1364, 'columns': 11, 'rows': 6, 'total_views': 66, 'hidden': False },
            10: {'description': "65, 72 views", 'quilt_width': 8192, 'quilt_height': 8190, 'view_width': 1024, 'view_height': 910, 'columns': 8, 'rows': 9, 'total_views': 72, 'hidden': False },

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
        def find(cls, width, height, rows, columns):
            ''' try to find a format id based on the given parameters '''
            for id, format in cls.__dict.items():
                if (format['quilt_width'], format['quilt_height'], format['rows'], format['columns']) == (width, height, rows, columns):
                    return id

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
            self.metadata['quilt_width'] = LookingGlassQuilt.formats.get(id)['view_width'] * LookingGlassQuilt.formats.get(id)['columns']
            self.metadata['quilt_height'] = LookingGlassQuilt.formats.get(id)['view_height'] * LookingGlassQuilt.formats.get(id)['rows']
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

            start = time.time()
            # use PIL to load the image from disk
            # NOTE: This makes nearly all of the execution time of the load() method
            # ToDo: replace PIL with OpenCV call, since we don't need both
            quilt_image = Image.open(filepath)
            if quilt_image:

                # try to detect quilt from quilt name
                found = self.__detect_from_quilt_suffix(os.path.basename(filepath))
                if not found:
                    # otherwise try to detect it from the quilt dimensions
                    found = self.__detect_from_quilt_dimensions(quilt_width = quilt_image.width, quilt_height = quilt_image.height)

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

    def from_buffer(self, data, width, height, colorchannels, quilt_name = ""):
        ''' load the quilt from the given data block and convert to numpy views '''

        # if this is a numpy array
        if type(data) == np.ndarray:

            start = time.time()

            # try to detect quilt from quilt name
            found = self.__detect_from_quilt_suffix(quilt_name)
            if not found:
                # otherwise try to detect it from the quilt dimensions
                found = self.__detect_from_quilt_dimensions(quilt_pixels = data.shape[0])

            # if no fitting quilt format was found
            if not found: raise TypeError("The loaded image is not in a supported format. Please check the image dimensions.")

            # convert it to a numpy array
            quilt_np = data.reshape(height, width, colorchannels)

            # crop the image in case, the size is incorrect due to rounding
            # errors
            quilt_np = np.flip(quilt_np[0:(self.metadata['rows'] * self.metadata['view_height']), 0:(self.metadata['columns'] * self.metadata['view_width']), :], 0)

            # store the colormode
            if colorchannels == 3: self.colormode = 'RGB'
            if colorchannels == 4: self.colormode = 'RGBA'

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

        # if a custom decoder function is passed
        if custom_decoder:

            # get the view data
            views = self.get_view_data()

            # call this function
            quilt = custom_decoder(views, views_format, format)

            # return the quilt data
            return quilt


        # TODO: HERE IS THE PLACE TO DEFINE STANDARD CONVERSIONS THAT CAN BE
        #       USED IN MULTIPLE PROGRAMMS

        # if the image shall be returned as numpy array
        if format == LightfieldImage.decoderformat.numpyarray:

            # if the views are in a numpy array format
            if self.views_format == LightfieldView.formats.numpyarray:

                # create a numpy quilt from numpy views
                quilt_numpy = self.__from_views_to_quilt_numpy(flip_views=flip_views)

                # return the numpy array of the quilt
                return quilt_numpy

            # otherwise raise exception
            raise TypeError("The given views format '%s' is not supported." % self.views_format)

        # otherwise raise exception
        raise TypeError("The requested lightfield format '%s' is not supported." % format)


    # PRIVATE INSTANCE METHODS: CONVERT BETWEEN DECODERFORMATS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    def __detect_from_quilt_suffix(self, quilt_name):
        import re

        # values from the metadata
        columns = None
        rows = None
        aspect = None

        # if a quilt name was given
        if quilt_name:

            # try to extract some metadata information from the quiltname
            try:

                rows = int(re.search('_qs(\d+)x(\d+)a(\d+.?\d*)', quilt_name).group(1))
                columns = int(re.search('_qs(\d+)x(\d+)a(\d+.?\d*)', quilt_name).group(2))
                aspect = float(re.search('_qs(\d+)x(\d+)a(\d+.?\d*)', quilt_name).group(3))

            except AttributeError:

                try:

                    rows = int(re.search('_qs(\d+)x(\d+).', quilt_name).group(1))
                    columns = int(re.search('_qs(\d+)x(\d+).', quilt_name).group(2))

                except AttributeError:

                    pass

            # for each supported quilt format
            for qf in LookingGlassQuilt.formats.get().values():

                # if the image dimensions matches one of the quilt formats
                # NOTE: We allow a difference of +/-1 px in width and height
                #       to accomodate for rounding errors in view width/height
                if not (columns is None or rows is None) and columns == qf['columns'] and rows == qf['rows']:

                    # store new row and column number in the metadata
                    self.metadata['rows'] = qf['rows']
                    self.metadata['columns'] = qf['columns']
                    self.metadata['count'] = qf['rows'] * qf['columns']
                    self.metadata['view_width'] = qf['view_width']
                    self.metadata['view_height'] = qf['view_height']

                    logger.info("Detected quilt format from name.")

                    return True

        return False

    def __detect_from_quilt_dimensions(self, quilt_width = None, quilt_height = None, quilt_pixels = None, quilt_name = ""):

        # for each supported quilt format
        for qf in LookingGlassQuilt.formats.get().values():

            # if the image dimensions matches one of the quilt formats
            # NOTE: We allow a difference of +/-1 px in width and height
            #       to accomodate for rounding errors in view width/height
            if not quilt_pixels is None and quilt_pixels in range((qf['quilt_width'] - 1) * (qf['quilt_height'] - 1) * 4, (qf['quilt_width'] + 1) * (qf['quilt_height'] + 1) * 4):

                # store new row and column number in the metadata
                self.metadata['rows'] = qf['rows']
                self.metadata['columns'] = qf['columns']
                self.metadata['count'] = qf['rows'] * qf['columns']
                self.metadata['view_width'] = qf['view_width']
                self.metadata['view_height'] = qf['view_height']

                logger.info("Detected quilt format from pixel count.")

                return True

            # if the image dimensions matches one of the quilt formats
            # NOTE: We allow a difference of +/-1 px in width and height
            #       to accomodate for rounding errors in view width/height
            if not (quilt_width is None or quilt_height is None) and quilt_width in range(qf['quilt_width'] - 1, qf['quilt_width'] + 1) and quilt_height in range(qf['quilt_height'] - 1, qf['quilt_height'] + 1):

                # store new row and column number in the metadata
                self.metadata['rows'] = qf['rows']
                self.metadata['columns'] = qf['columns']
                self.metadata['count'] = qf['rows'] * qf['columns']
                self.metadata['view_width'] = qf['view_width']
                self.metadata['view_height'] = qf['view_height']

                logger.info("Detected quilt format from width and height.")

                return True

        return False

    # PRIVATE INSTANCE METHODS: VIEWS TO QUILTS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    # NOTE: this function is based on https://stackoverflow.com/questions/42040747/more-idiomatic-way-to-display-images-in-a-grid-with-numpy
    # NOTE: This call takes 15 to 30 ms -> can this be optimized?
    def __from_views_to_quilt_numpy(self, flip_views=False):
        ''' convert views given as numpy arrays to a quilt as a numpy array '''

        start = time.time()

        # if no merged numpy array exists
        if self.__merged_numpy is None:

            # get the views
            views = self.get_view_data()
            views_format = self.views_format

            # create numpy array from the BytesIO buffer object
            self.__merged_numpy = np.asarray(views, dtype=np.uint8)

            # log info
            logger.debug(" [#] Prepared numpy array of shape %s in %.3f ms." % (self.__merged_numpy.shape, (time.time() - start) * 1000))

            # step 1: get an array of shape (rows, columns, view_height, view_width)
            self.__merged_numpy = self.__merged_numpy.reshape(self.metadata['rows'], self.metadata['columns'], self.metadata['view_height'], self.metadata['view_width'], self.colorchannels)

            # step 2: swap the "columns" and "view_height" axis, so that we get an
            #         array of shape (rows, view_height, columns, view_width, colorchannels)
            self.__merged_numpy = self.__merged_numpy.swapaxes(1, 2)

            # step 3: re-assign the numpy arrays for all underlying LightfieldView-objects
            # as (memory)views into the __merged_numpy array
            # NOTE: This step speeds up the quilt creation by some tens of milliseconds
            #       since the next time the LightfieldView pixel data is updated
            #       it directly updates the pixel data in the __merged_numpy array.
            i_x = i_y = 0
            for i, view in enumerate(self.views):

                # create subarray view into the quilt pixel data
                view['view'].data = self.__merged_numpy[i_y, :, i_x, :, :]

                # choose column and row
                if (i + 1) % self.metadata['columns'] == 0 and i > 0:
                    i_x = 0
                    i_y += 1
                else:
                    i_x += 1

            # log info
            logger.debug(" [#] Prepeared quilt as numpy array in %.3f ms." % ((time.time() - start) * 1000))

        # output the views
        return self.__merged_numpy



    # PRIVATE INSTANCE METHODS: CONVERT BETWEEN DECODERFORMATS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


    # CLASS PROPERTIES
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    @property                   # read-only property
    def merged_numpy(self):
        return self.__merged_numpy

    @merged_numpy.setter
    def merged_numpy(self, value):
        pass
