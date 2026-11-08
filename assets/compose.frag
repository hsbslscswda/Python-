#version 330
uniform sampler2D scene_tex;
uniform sampler2D bloom_tex;
uniform float gain;
in vec2 uv;
out vec4 color;
void main(){vec2 p=vec2(uv.x,1.-uv.y);color=vec4(texture(scene_tex,p).rgb+texture(bloom_tex,p).rgb*gain,1.);}
