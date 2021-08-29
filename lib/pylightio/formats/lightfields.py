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
from enum import Enum

# INTERNAL PACKAGE DEPENDENCIES
###################################################
# NONE

# PREPARE LOGGING
###################################################
import logging

# get the library logger
logger = logging.getLogger('pyLightIO')



# LIGHTFIELD IMAGE CLASSES
###############################################
# the following classes are used to represent, convert, and manipulate a set of
# views using a defined lightfield format
class LightfieldImage(object):

    # POSSIBLE FORMATS OF THE VIEWS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #   Enum definition for the different formats the lightfield image can be
    #   transformed to
    class decoderformat(Enum):
        pil_image = 1           # decode views to a lightfield as Pillow image
        numpyarray = 2          # decode views to a lightfield as numpy array
        bytesio = 3             # decode views to a lightfield as BytesIO object

        @classmethod
        def to_list(cls):
            return list(map(lambda enum: enum, cls))

        @classmethod
        def is_valid(cls, value):
            ''' check if a given value is a member of this class '''
            return (value in cls.to_list())

    # CLASS METHODS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    @classmethod
    def new(cls, type, **kwargs):
        ''' create an empty lightfield image object of specified format '''

        # try to find the class for the specified type, if it exists
        LightfieldImageFormat = [subclass for subclass in BaseLightfieldImageFormat.__subclasses__() if (subclass == type)]
        if LightfieldImageFormat:

            # create the LightfieldImage object of the specified type
            lightfield = LightfieldImageFormat[0](**kwargs)
            return lightfield

        raise TypeError("'%s' is no valid lightfield image type." % type)

    @classmethod
    def open(cls, filepath, type, **kwargs):
        ''' open a lightfield image object file of specified format from disk '''

        # try to find the class for the specified format, if it exists
        LightfieldImageFormat = [subclass for subclass in BaseLightfieldImageFormat.__subclasses__() if (subclass == type)]
        if LightfieldImageFormat:

            # create a new lightfield image instance of the specified format
            lightfield = LightfieldImageFormat[0](**kwargs)

            # load the image
            lightfield.load(filepath)

            # return the lightfield image instance of the specified format
            return lightfield

        raise TypeError("'%s' is no valid lightfield image type." % type)

    @classmethod
    def from_buffer(cls, type, data, width, height, colorchannels, quilt_name = "", **kwargs):
        ''' creat a lightfield image object of specified format from a data block of given format '''

        # try to find the class for the specified format, if it exists
        LightfieldImageFormat = [subclass for subclass in BaseLightfieldImageFormat.__subclasses__() if (subclass == type)]
        if LightfieldImageFormat:

            # create a new lightfield image instance of the specified format
            lightfield = LightfieldImageFormat[0](**kwargs)

            # load the image
            lightfield.from_buffer(data, width, height, colorchannels, quilt_name = quilt_name)

            # return the lightfield image instance of the specified format
            return lightfield

        raise TypeError("'%s' is no valid lightfield image type." % type)

    @classmethod
    def convert(self, lightfield, target_format):
        ''' convert a lightfield image object to another type '''
        pass



# class representing an individual view of a lightfield image
# NOTE: At the moment this class is not too useful, but it might be, if we later
#       want to introduce more view specific calls or some kind of "view streaming"
class LightfieldView(object):

    # POSSIBLE FORMATS OF THE VIEWS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    __format = None                 # format of this LightfieldView instance
    __data = None                   # image data of this view in the specified format



    # POSSIBLE FORMATS OF THE VIEWS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #   Enum definition for the supported image data formats
    class formats(Enum):
        pil_image = 1           # view is a Pillow image
        numpyarray = 2          # view is a numpy array
        bytesio = 3             # view is a BytesIO object

        @classmethod
        def to_list(cls):
            return list(map(lambda enum: enum, cls))

        @classmethod
        def is_valid(cls, value):
            ''' check if a given value is a member of this class '''
            return (value in cls.to_list())



    # CLASS METHODS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    @classmethod
    def is_instance(cls, object):
        ''' verify if a given object is an instance of this class '''
        return isinstance(object, cls)



    # INSTANCE METHODS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    def __init__(self, data, format):
        ''' initialize the view and pass data in '''
        # if a valid format was passed
        if LightfieldView.formats.is_valid(format):

            # store the image data and the format
            self.data = data
            self.format = format

        else:

            raise TypeError("'%s' is no valid view format." % format)



    # CLASS PROPERTIES
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    @property
    def format(self):
        return self.__format

    @format.setter
    def format(self, value):
        self.__format = value

    @property
    def data(self):
        return self.__data

    @data.setter
    def data(self, value):
        self.__data = value


class BaseLightfieldImageFormat(object):

    # PRIVATE MEMBERS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    __views = None              # list of LightfieldView objects belonging to this lightfield in the format {view: LightfieldView instance, updated: Boolean}
    __metadata = None           # metadata of the lightfield format
    __colormode = None          # colormode of the image data
    __colorchannels = None      # number of color channels in the image data


    # INSTANCE METHODS - IMPLEMENTED BY BASE CLASS
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # NOTE: These methods are implemented by the base class but might be overwritten
    #       by subclasses. If they do, these subclasses should still call the
    #       base class method with return super().method() to avoid future conflicts.
    def set_views(self, list, format, index=0):
        ''' store the given list of LightfieldView objects in the internal view list '''
        # if the given index is valid
        if index <= len(self.views):

            # if the format is supported
            if LightfieldView.formats.is_valid(format):

                # if all the elements of the list are no LightfieldView objects
                if all(not LightfieldView.is_instance(view) for view in list):

                    # assume view data was passed
                    list = [LightfieldView(view, format) for view in list]

                    # log a debug message
                    logger.debug('No LightfieldViews instance was passed to LightfieldImage.set_views().')

                # if all views in this list have the same format
                if all((view.format == format) for view in list):

                    # remove all elements from the view list that shall be overwritten
                    for i in range(index, len(list)):
                        if i < len(self.views): self.views.pop(i)

                    # insert the new elements
                    for i, view in enumerate(list):
                        self.views.insert(index+i, {'view': view, 'updated': True})

                    # store the format
                    self.views_format = format

                    # return the list of views
                    return self.views

                raise TypeError("Multiple view formats were passed. All views of a '%s' must have the same format." % self)

            raise TypeError("'%s' is not a valid view format." % format)

        raise ValueError("The given view index is out of bounds. Pass a positive index smaller or equal to %i" % len(self.views))

    def append_view(self, view, format=None):
        ''' append a LightfieldView object to the end of the list of views '''

        # if the passed view is not a LightfieldView object
        if not LightfieldView.is_instance(view):

            # if the passed format is a valid view format
            if LightfieldView.formats.is_valid(format):

                # assume view data was passed and create a LightfieldView instance
                view = LightfieldView(view, format)

                # log a debug message
                logger.debug('No LightfieldViews instance was passed to LightfieldImage.append_views(). Created one from the given view data!')

            else:

                raise TypeError("'%s' is not a valid LightfieldView format." % format)

        # if all views in this list have the same format
        if all((v['view'].format == view.format) for v in self.views):

            # append the new element
            self.views.append({'view': view, 'updated': True})

            # store the format
            self.views_format = view.format

            # return the list of views
            return self.views

        raise TypeError("Multiple view formats were passed. All views of a '%s' must have the same format." % self)

    def insert_view(self, index, view, format=None):
        ''' inserts a LightfieldView object at the given position the list of views '''
        # if all views in this list have the same format
        if all((v['view'].format == view.format) for v in self.views):

            # if the passed view is not a LightfieldView object
            if not LightfieldView.is_instance(view):

                # if the passed format is a valid view format
                if LightfieldView.formats.is_valid(format):

                    # assume view data was passed and create a LightfieldView instance
                    view = LightfieldView(view, format)

                    # log a debug message
                    logger.debug('No LightfieldViews instance was passed to LightfieldImage.insert_views().')

                else:

                    raise TypeError("'%s' is not a valid LightfieldView format." % format)

            # insert the new element
            self.views.insert(index, {'view': view, 'updated': True})

            # store the format
            self.views_format = view.format

            # return the list of views
            return self.views

        raise TypeError("Multiple view formats were passed. All views of a '%s' must have the same format." % self)

    def remove_view(self, index):
        ''' remove a LightfieldView object from the list of views '''
        self.views.pop(index)

        # return the list of views
        return self.views

    def clear_views(self):
        ''' clear the complete list of LightfieldView objects from this LightfieldImage '''

        # remove all views
        for index, view in enumerate(self.views):
            self.remove_view(index)

    def get_view_data(self, updated=None, reset_updated=False):
        ''' return the image data of all views as a list of the views image data '''
        if updated != None: views = [v['view'].data for v in self.views if v['updated'] == updated]
        else:               views = [v['view'].data for v in self.views]

        # if the updated status shall be reset, do that
        if reset_updated == True:
            for v in self.views: v['updated'] = False

        # return the list of view data
        return views




    # INSTANCE METHODS - IMPLEMENTED BY SUBCLASSES
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # NOTE: These methods must be implemented by the subclasses, which represent
    #       the specific lightfield image types.
    def __init__(self, **kwargs):
        ''' create a new and empty lightfield image object of specified type '''
        # NOTE: this method MUST be called from any subclass from the subclasse's
        #      __init__() prior to any further initializations

        # initialize instance properties
        self.views = []
        self.metadata = {}
        self.colormode = 'RGBA'
        self.colorchannels = 4

    def load(self, filepath):
        ''' load the lightfield from a file '''
        pass

    def from_buffer(self, data):
        ''' load the lightfield from a data block '''
        pass

    def save(self, filepath):
        ''' save the lightfield image in its specific format to a disk file '''
        pass

    def delete(self, lightfield):
        ''' delete the given lightfield image object '''
        pass

    def decode(self, format):
        ''' return the image as the lightfield and return it '''
        pass

    def free(self):
        ''' free the image lightfield image '''
        pass

    # CLASS PROPERTIES
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    @property
    def views(self):
        return self.__views

    @views.setter
    def views(self, value):
        self.__views = value

    @property
    def views_format(self):
        return self.__views_format

    @views_format.setter
    def views_format(self, value):
        self.__views_format = value

    @property
    def metadata(self):
        return self.__metadata

    @metadata.setter
    def metadata(self, value):
        self.__metadata = value

    @property
    def colormode(self):
        return self.__colormode

    @colormode.setter
    def colormode(self, value):
        self.__colormode = value

    @property
    def colorchannels(self):
        return self.__colorchannels

    @colorchannels.setter
    def colorchannels(self, value):
        self.__colorchannels = value
