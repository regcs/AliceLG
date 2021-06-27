# ############################## LICENSE BLOCK ###############################
#
#                      freeHPC - Free HoloPlay Core API
#                      ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
# MIT License
#
# Copyright © 2021 Yann Vernier, Christian Stolze
# All rights reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
# ############################################################################

# NOTE: this is just here since we need Yann's shaders until the new live view
#       is implemented

class freeHoloPlayCoreAPI:

    # LIGHTFIELD SHADERS
    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Vertex shader
    LightfieldVertShaderGLSL = '''
        // INPUT AND OUTPUT VARIABLES
        layout (location = 0)
        in vec2 vertPos_data;
        out vec2 texCoords;

        // VERTEX SHADER
        void main()
        {
        	gl_Position = vec4(vertPos_data.xy, 0.0, 1.0);
        	texCoords = (vertPos_data.xy + 1.0) * 0.5;
        }
    '''

    # Fragment shader
    LightfieldFragShaderGLSL = '''
        in vec2 texCoords;
        out vec4 fragColor;

        // CALIBRATION VALUES
        uniform float pitch;
        uniform float tilt;
        uniform float center;
        uniform int invView;
        uniform float subp;
        uniform float displayAspect;
        uniform int ri;
        uniform int bi;

        // QUILT SETTINGS
        uniform vec3 tile;
        uniform vec2 viewPortion;
        uniform int debug;

        // QUILT TEXTURE
        uniform sampler2D screenTex;

        // GET CORRECT VIEW
        vec2 quilt_map(vec2 pos, float a) {

            // Tile ordering
            vec2 tile2 = vec2(tile.x - 1, tile.y - 1), dir=vec2(-1, -1);

            a = fract(a) * tile.y;
            tile2.y += dir.y * floor(a);
            a = fract(a) * tile.x;
            tile2.x += dir.x * floor(a);
            return (tile2 + pos) / tile.xy;

        }

        // SHADER
        void main()
        {

            float a;
            vec4 res;

            a = (-texCoords.x - texCoords.y * tilt) * pitch - center;
            res.r = texture(screenTex, quilt_map(texCoords.xy, a-ri*subp)).r;
            res.g = texture(screenTex, quilt_map(texCoords.xy, a-   subp)).g;
            res.b = texture(screenTex, quilt_map(texCoords.xy, a-bi*subp)).b;

            if (debug == 1) {
                // use quilt texture
                res = texture(screenTex, texCoords.xy);
            }
            else if (debug == 2) {
                // Mark center line only in central view
                res.r = res.r * 0.001 + (texCoords.x>0.49 && texCoords.x<0.51 && fract(a)>0.48&&fract(a)<0.51 ?1.0:0.0);
                res.g = res.g * 0.001 + texCoords.x;
                res.b = res.b * 0.001 + texCoords.y;
            }

            res.a = 1.0;
            fragColor = res;

        }
    '''
