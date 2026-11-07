#version 330
uniform sampler2D camera_tex;
uniform vec2 viewport;
uniform vec2 source_size;
uniform vec2 center;
uniform vec2 palm;
uniform vec2 chest;
uniform float shoulder;
uniform float radius;
uniform float time;
uniform float visibility;
uniform float intensity;
uniform float migration;
uniform float mirror_angle;
uniform float effect_gain;
uniform int mode;
uniform int mirrored;
uniform int lightning;
uniform int folded;
uniform int quality;
uniform int slash_count;
uniform vec4 slashes[8];
uniform vec2 slash_data[8];
in vec2 uv;
layout(location=0) out vec4 color;
layout(location=1) out vec4 emission;
const float PI=3.14159265359;
float band(float d,float width) {return exp(-d*d/(width*width));}
float lineDist(vec2 p,vec2 a,vec2 b) {
    vec2 ab=b-a; return length(p-a-clamp(dot(p-a,ab)/max(.001,dot(ab,ab)),0.,1.)*ab);
}
mat2 turn(float a) {return mat2(cos(a),sin(a),-sin(a),cos(a));}
vec3 camera(vec2 p) {return texture(camera_tex,clamp(p/source_size,vec2(0.),vec2(1.))).rgb;}
float sigil(vec2 p,float r,float t) {
    float d=length(p),a=atan(p.y,p.x),v=0.;
    float thin=max(1.4,shoulder*.010);
    v+=band(d-r,thin)*.65;
    v+=band(d-r*.91,thin*.7)*.5;
    v+=band(d-r*.79,thin*.7)*.5;
    float runes=step(.35,sin(a*44.+t)) * step(.1,cos(a*22.+d*.16-t));
    v+=band(d-r*.85,thin*3.3)*runes*.38;
    float star=abs(cos(a*3.+t*.3));
    v+=band(d-r*(.53+.06*star),thin*.7)*.42;
    v+=band(d-r*.64,thin*.55)*step(.6,cos(a*12.-t))*.4;
    v+=band(d-r*.34,thin*.6)*.2;
    v+=band(d-r,thin*5.)*.14;
    // Two counter-facing triangles, twelve radial glyphs and moon nodes.
    for(int i=0;i<6;i++) {
        float b=float(i)*PI/3.+t*.10;
        vec2 u=vec2(cos(b),sin(b))*r*.70;
        vec2 w=vec2(cos(b+2.*PI/3.),sin(b+2.*PI/3.))*r*.70;
        v+=band(lineDist(p,u,w),thin*.65)*.42;
    }
    float sector=mod(a+PI/12.,PI/6.)-PI/12.;
    vec2 local=vec2(cos(sector),sin(sector))*d-vec2(r*.84,0.);
    v+=band(abs(local.x)+abs(local.y)-r*.027,thin*.6)*.65;
    v+=band(d-r*.96,thin*.6)*step(.6,cos(a*72.-t))*.8;
    return v;
}
void main() {
    float fit=min(viewport.x/source_size.x,viewport.y/source_size.y);
    vec2 p=(uv*viewport-(viewport-source_size*fit)*.5)/fit;
    emission=vec4(0.);
    if(any(lessThan(p,vec2(0.)))||any(greaterThan(p,source_size))) {color=vec4(.025,.045,.065,1.);return;}
    if(mirrored==1) p.x=source_size.x-p.x;
    vec3 base=camera(p);
    vec3 silver=lightning==1 ? vec3(.50,.63,1.) : vec3(.60,.87,1.);
    vec3 light=vec3(0.);
    if(mode==0 && visibility>.001) {
        vec2 q=p-center;
        float r=min(radius,min(source_size.x,source_size.y)*.46);
        float v=sigil(turn(time*.07)*q,r,time*.1);
        v+=sigil(turn(-time*.1)*q,r*.70,-time*.17)*.38;
        float central=smoothstep(r*.19,r*.42,length(q));
        float face=smoothstep(shoulder*.23,shoulder*.42,length(p-(chest-vec2(0.,shoulder*.65))));
        float channel=smoothstep(shoulder*.075,shoulder*.17,lineDist(p,chest,palm));
        float backing=smoothstep(r*.45,r*.70,length(q))*(1.-smoothstep(r*.99,r*1.07,length(q)));
        base*=1.-backing*visibility*.40*face;
        light+=silver*v*central*face*mix(.55,1.,channel)*visibility*1.75;
        if(intensity>.002) {
            vec2 energy=p-palm;
            float d=length(energy)/max(shoulder,1.);
            float a=atan(energy.y,energy.x);
            float waves=pow(max(0.,sin(d*28.-time*(7.+intensity*6.))),14.);
            float plume=waves*exp(-d*2.4)*intensity;
            plume+=band(d-.12,.035)*intensity*1.8;
            plume+=band(d,.08)*intensity*.75;
            if(lightning==1) {
                float arc=band(sin(a*8.+d*13.+floor(time*9.)),.07)*exp(-d*1.8);
                plume=arc*intensity*.6;
            }
            light+=silver*plume*visibility*1.45;
        }
        if(migration>.02) {
            for(int i=0;i<3;i++) {
                float k=float(i);
                vec2 offset=vec2(0.,(k-1.)*shoulder*.17);
                light+=silver*sigil(turn(time*(.12+k*.03))* (q-offset),r*(.58+k*.14),time+k)*migration*.80;
            }
            float wave=fract(time*.85);
            light+=silver*band(length(q)-r*(.1+wave*1.1),4.5)*(1.-wave)*intensity*migration*1.5;
            if(lightning==1) {
                for(int j=0;j<12;j++) {
                    float a=float(j)*PI/6.;
                    vec2 node=center+vec2(cos(a),sin(a))*r*.78;
                    vec2 midpoint=mix(node,palm,.5)+vec2(sin(a*3.+floor(time*11.)),cos(a*5.))*shoulder*.09;
                    float pulse=pow(max(0.,sin(time*8.-float(j)*.7)),3.);
                    float network=band(lineDist(p,node,midpoint),1.2)+band(lineDist(p,midpoint,palm),1.2);
                    light+=silver*network*pulse*migration*intensity*.65;
                    light+=silver*band(length(p-node),3.)*migration*.6;
                }
            }
        }
    } else if(mode==1 && visibility>.001) {
        float d=length(p-center);
        light+=vec3(.7,.85,1.)*band(d-radius,2.)*visibility*.7;
    } else if(mode==2 && visibility>.001) {
        vec2 q=turn(-mirror_angle)*(p-center);
        vec2 bounds=vec2(radius,radius*.66);
        vec2 edge=abs(q)-bounds;
        float d=max(edge.x,edge.y);
        if(d<0.) {
            vec2 sampleq=q;
            if(folded==1) {
                float a=atan(q.y,q.x),len=length(q);
                a=abs(mod(a+PI/6.,PI/3.)-PI/6.);
                sampleq=vec2(cos(a),sin(a))*len;
            }
            sampleq.x=-sampleq.x;
            sampleq+=normalize(q+vec2(.001))*sin(length(q)*.035-time*1.8)*2.;
            vec3 reflected=camera(center+sampleq)*vec3(.80,.96,1.08)+vec3(.015,.025,.06);
            base=mix(base,reflected,visibility);
            base+=vec3(.02,.04,.07)*pow(1.-abs(q.y)/max(1.,bounds.y),8.)*visibility;
        }
        light+=vec3(.65,.87,1.)*(band(d,3.)*1.8+band(d,12.)*.28+band(d+7.,1.))*visibility;
        light+=vec3(.65,.87,1.)*band(q.x,1.4)*exp(-abs(q.y)/max(20.,radius*.7))*visibility*float(radius<shoulder*.3);
    }
    for(int i=0;i<8;i++) {
        if(i>=slash_count) break;
        vec2 a=slashes[i].xy,b=slashes[i].zw;
        float age=slash_data[i].x,power=slash_data[i].y;
        vec2 tangent=normalize(b-a+vec2(.001));
        vec2 normal=vec2(-tangent.y,tangent.x);
        float progress=clamp(dot(p-a,b-a)/max(1.,dot(b-a,b-a)),0.,1.);
        vec2 curve=mix(a,b,progress)+normal*sin(progress*PI)*shoulder*.18;
        float d=length(p-curve-tangent*age*shoulder*.7);
        float taper=sin(progress*PI);
        light+=vec3(.68,.86,1.)*(band(d,4.+power*5.)*2.+band(d,20.)*.42)*taper*max(0.,1.-age/.80);
    }
    if(quality>0) light+=min(light,vec3(.5))*.16;
    color=vec4(base+light*effect_gain,1.);
    emission=vec4(max(light*effect_gain-vec3(.3),vec3(0.)),1.);
}
