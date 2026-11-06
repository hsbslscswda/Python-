#version 330
uniform vec2 viewport;
uniform vec2 source_size;
uniform vec2 origin;
uniform float age;
uniform int mirrored;
in vec2 in_point;
in vec2 in_uv;
in vec2 in_velocity;
out vec2 tex_uv;
void main(){
    vec2 p=in_point+in_velocity*age+vec2(0.,200.*age*age);
    if(mirrored==1) p.x=source_size.x-p.x;
    float fit=min(viewport.x/source_size.x,viewport.y/source_size.y);
    vec2 pixel=p*fit+(viewport-source_size*fit)*.5;
    gl_Position=vec4(pixel.x/viewport.x*2.-1.,1.-pixel.y/viewport.y*2.,0.,1.);
    tex_uv=in_uv;
}
