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

from pylightio.formats import *
from pylightio.managers import *
from pylightio.lookingglass import *

from pylightio._version import __version__

# logging module
import logging

# THIS CAN BE USED TOO MUTE LIBRARY LOGGER
# OTHERWUSE BY DEFAULT EVENTS WITH LEVEL "WARNING" AND HIGHER WILL BE PRINTED
logging.getLogger('pyLightIO').addHandler(logging.NullHandler())
