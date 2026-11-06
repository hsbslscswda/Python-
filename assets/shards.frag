#version 330
uniform sampler2D frozen_tex;
uniform float age;
in vec2 tex_uv;
out vec4 color;
void main(){color=vec4(texture(frozen_tex,tex_uv).rgb*vec3(.86,.96,1.08),max(0.,1.-age/.85));}
