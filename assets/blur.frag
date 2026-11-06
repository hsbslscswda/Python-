#version 330
uniform sampler2D input_tex;
uniform vec2 step_uv;
in vec2 uv;
out vec4 color;
void main(){
    // Textures rendered by OpenGL have a bottom-left origin.
    vec2 p=vec2(uv.x,1.-uv.y);
    vec3 c=texture(input_tex,p).rgb*.227027;
    c+=texture(input_tex,p+step_uv*1.384615).rgb*.316216;
    c+=texture(input_tex,p-step_uv*1.384615).rgb*.316216;
    c+=texture(input_tex,p+step_uv*3.230769).rgb*.070270;
    c+=texture(input_tex,p-step_uv*3.230769).rgb*.070270;
    color=vec4(c,1.);
}
