#version 330
uniform sampler2D camera_tex;
uniform vec2 viewport;
uniform vec2 source_size;
uniform vec2 center;
uniform vec2 palm;
uniform vec2 chest;
uniform float shoulder;
uniform float radius;
uniform float body_yaw;
uniform float mirror_time;
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

const float PI = 3.14159265359;

float band(float d, float width) {
    return exp(-d * d / max(0.0001, width * width));
}

float lineDist(vec2 p, vec2 a, vec2 b) {
    vec2 ab = b - a;
    return length(p - a - clamp(dot(p - a, ab) / max(0.001, dot(ab, ab)), 0.0, 1.0) * ab);
}

mat2 turn(float a) {
    float c = cos(a), s = sin(a);
    return mat2(c, s, -s, c);
}

vec3 camera(vec2 p) {
    return texture(camera_tex, clamp(p / source_size, vec2(0.0), vec2(1.0))).rgb;
}

// 2.5D Perspective projection helper: tilts the magic circle plane toward the caster's aim vector
vec2 projectPlane(vec2 q, vec2 tilt, float layerDepth, float sh) {
    vec2 shifted = q - tilt * layerDepth * sh * 0.28;
    float tiltMag = clamp(length(tilt), 0.0, 0.62);
    if (tiltMag < 0.01) return shifted;
    vec2 dir = tilt / max(length(tilt), 0.001);
    vec2 ortho = vec2(-dir.y, dir.x);
    float parallel = dot(shifted, dir) / (1.0 - tiltMag * 0.42);
    float perp = dot(shifted, ortho);
    return dir * parallel + ortho * perp;
}

float hash11(float p) {
    p = fract(p * 0.1031);
    p *= p + 33.33;
    p *= p + p;
    return fract(p);
}

float sigilLayer(vec2 p, float r, float t, float sh, int style) {
    float d = length(p);
    float a = atan(p.y, p.x);
    float thin = max(1.6, sh * 0.011);
    float v = 0.0;

    // Outer double celestial rim + glow
    v += band(d - r, thin * 1.15) * 1.15;
    v += band(d - r * 0.92, thin * 0.85) * 0.85;
    v += band(d - r * 0.78, thin * 0.75) * 0.70;
    v += band(d - r, thin * 6.5) * 0.28;

    // Crisp astrolabe tick marks & rune ring
    float ticks = smoothstep(0.45, 0.85, cos(a * 36.0 - t * 1.4));
    v += band(d - r * 0.96, thin * 1.4) * ticks * 0.95;

    float runes = step(0.15, sin(a * 24.0 + t * 0.8)) * smoothstep(-0.2, 0.6, cos(a * 12.0 + d * 0.22 - t));
    v += band(d - r * 0.85, thin * 3.2) * runes * 0.75;

    if (style == 0) {
        // Moon phase crescent & intersecting twelve-point star geometry
        for (int i = 0; i < 6; i++) {
            float b = float(i) * PI / 3.0 + t * 0.15;
            vec2 u = vec2(cos(b), sin(b)) * r * 0.76;
            vec2 w = vec2(cos(b + 2.0 * PI / 3.0), sin(b + 2.0 * PI / 3.0)) * r * 0.76;
            v += band(lineDist(p, u, w), thin * 0.85) * 0.62;
        }
        // Embedded crescent moons at cardinal nodes
        float sector = mod(a + PI / 4.0, PI / 2.0) - PI / 4.0;
        vec2 moonPos = vec2(cos(sector), sin(sector)) * d - vec2(r * 0.62, 0.0);
        float m1 = length(moonPos) - r * 0.075;
        float m2 = length(moonPos - vec2(r * 0.028, 0.0)) - r * 0.068;
        v += band(max(m1, -m2), thin * 0.9) * 0.95;
    } else {
        // Thunder octagonal array & sharp zig-zag circuit rings
        float oct = cos(floor(0.5 + a / (PI / 4.0)) * (PI / 4.0) - a) * d;
        v += band(oct - r * 0.68, thin * 1.1) * 0.95;
        float jag = sin(a * 16.0 + floor(time * 12.0)) * r * 0.025;
        v += band(d - (r * 0.52 + jag), thin * 0.95) * 0.85;
    }

    // Inner core ring
    v += band(d - r * 0.32, thin * 1.1) * 0.75;
    return v;
}

void main() {
    float fit = min(viewport.x / source_size.x, viewport.y / source_size.y);
    vec2 p = (uv * viewport - (viewport - source_size * fit) * 0.5) / fit;
    emission = vec4(0.0);
    if (any(lessThan(p, vec2(0.0))) || any(greaterThan(p, source_size))) {
        color = vec4(0.02, 0.035, 0.055, 1.0);
        return;
    }
    if (mirrored == 1) p.x = source_size.x - p.x;

    vec3 base = camera(p);
    float sh = max(shoulder, 1.0);
    vec3 primaryCol = lightning == 1 ? vec3(1.0, 0.78, 0.22) : vec3(0.38, 0.88, 1.0);
    vec3 coreCol    = lightning == 1 ? vec3(1.0, 0.97, 0.88) : vec3(0.92, 0.98, 1.0);
    vec3 accentCol  = lightning == 1 ? vec3(0.58, 0.42, 1.0)  : vec3(0.18, 0.52, 0.98);
    vec3 light = vec3(0.0);

    if (mode == 0 && visibility > 0.001) {
        vec2 q = p - center;
        float r = min(radius, min(source_size.x, source_size.y) * 0.47);

        // Compute 2.5D tilt vector from chest-to-palm / screen center offset so the array tilts with the body & arm
        vec2 aimVec = (palm - chest) / sh;
        // Pose-world shoulder yaw is an estimate; screen translation is not yaw.
        vec2 bodyTilt = vec2(sin(body_yaw) * 0.60, 0.0);
        vec2 tilt = clamp(aimVec * (0.08 + 0.18 * migration) + bodyTilt, vec2(-0.58), vec2(0.58));

        // 3 depth-staggered parallax layers even in normal mode, expanding dramatically in overdrive (migration)
        float spread = 0.35 + 0.95 * migration;
        vec2 qBack = projectPlane(q, tilt, -0.55 * spread, sh);
        vec2 qMid  = projectPlane(q, tilt,  0.00 * spread, sh);
        vec2 qFore = projectPlane(q, tilt, +0.65 * spread, sh);

        float vBack = sigilLayer(turn(-time * 0.22) * qBack, r * (1.04 - 0.12 * migration), -time * 0.3, sh, lightning);
        float vMid  = sigilLayer(turn( time * (0.32 + 0.45 * intensity)) * qMid, r * 0.78, time * 0.5, sh, lightning);
        float vFore = sigilLayer(turn(-time * (0.48 + 0.65 * migration)) * qFore, r * (0.48 + 0.18 * migration), time * 0.8, sh, lightning);

        float faceGuard = smoothstep(sh * 0.20, sh * 0.42, length(p - (chest - vec2(0.0, sh * 0.65))));
        float armPortal = smoothstep(sh * 0.06, sh * 0.16, lineDist(p, chest, palm));

        // Subtle atmospheric darkening behind the array so bright runes pop against bright rooms/clothes
        float diskMask = smoothstep(r*.35, r*.60, length(qMid)) * (1.0-smoothstep(r*.95, r*1.08, length(qMid)));
        base *= 1.0 - diskMask * visibility * 0.45 * faceGuard;

        vec3 arrayLight = accentCol * vBack * 0.85 + primaryCol * vMid * 1.35 + coreCol * vFore * (0.95 + 0.85 * migration);
        light += arrayLight * smoothstep(r*.13, r*.32, length(qMid)) * faceGuard * mix(0.62, 1.0, armPortal) * visibility * 1.20;

        // Active casting energy stream & palm focal array
        if (intensity > 0.002) {
            vec2 ep = projectPlane(p - palm, tilt, 0.45, sh);
            float d = length(ep) / sh;
            float a = atan(ep.y, ep.x);

            if (lightning == 0) {
                // Lunar vortex + radial shockwave rings
                float spiral = sin(a * 4.0 - d * 18.0 + time * (6.0 + intensity * 8.0));
                float stream = smoothstep(0.25, 0.95, spiral) * exp(-d * 2.1) * intensity;
                float pulseRing = band(fract(d * 1.8 - time * (1.2 + intensity)) - 0.5, 0.08) * exp(-d * 1.5) * intensity;
                float palmCore = band(d - 0.11, 0.035) * 1.9 + band(d, 0.09) * 1.4;
                light += (primaryCol * (stream * 1.4 + pulseRing * 1.2) + coreCol * palmCore * intensity) * visibility * 1.5;
            } else {
                // High-contrast jagged golden-violet lightning arcs
                float arcField = 0.0;
                for (int k = 0; k < 5; k++) {
                    float fk = float(k);
                    float seed = floor(time * 14.0) + fk * 7.13;
                    float targetAngle = fk * (2.0 * PI / 5.0) + time * 0.9;
                    float jitter = sin(d * 32.0 + seed * 3.7) * 0.22 + cos(d * 67.0 - seed * 5.1) * 0.11;
                    float angleDiff = abs(mod(a - targetAngle + jitter + PI, 2.0 * PI) - PI);
                    arcField += band(angleDiff * d, 0.012 + 0.008 * intensity) * exp(-d * 1.35);
                }
                float palmSpark = band(d - 0.09, 0.03) * 2.1 + band(d, 0.07) * 1.5;
                light += (accentCol * arcField * 1.3 + primaryCol * arcField * 1.8 + coreCol * palmSpark) * intensity * visibility * 1.45;
            }
        }

        // Overdrive structural transformation: Eclipse/Thunder Crown + background lens refraction
        if (migration > 0.02) {
            float wave = fract(time * 1.15);
            float shockR = r * (0.12 + wave * 1.15);
            float shockBand = band(length(qFore) - shockR, 5.5) * (1.0 - wave) * migration;
            if (quality > 0) {
                vec2 dir = normalize(qFore + vec2(0.001));
                base = mix(base, camera(p + dir * shockBand * sh * 0.045), clamp(migration, 0.0, 1.0));
            }
            // Eclipse dark core with blazing corona in Overdrive
            float eclipseCore = (1.0 - smoothstep(r * 0.08, r * 0.22, length(qFore))) * migration * clamp(intensity, 0.4, 1.5);
            base *= 1.0 - eclipseCore * 0.82;
            float corona = band(length(qFore) - r * 0.18, max(2.5, sh * 0.022)) * migration * 2.2;
            light += (coreCol * corona + primaryCol * shockBand * 2.1) * visibility;
        }
    } else if (mode == 1 && visibility > 0.001) {
        // Armed crescent indicator near the wrist
        vec2 q = p - center;
        float c1 = length(q) - radius * 1.15;
        float c2 = length(q - vec2(radius * 0.42, -radius * 0.18)) - radius * 1.05;
        float crescent = (1.0 - smoothstep(-1.0, 3.5, max(c1, -c2)));
        float rim = band(length(q) - radius * 1.15, 2.5);
        light += (vec3(0.45, 0.88, 1.0) * rim * 1.4 + vec3(0.88, 0.97, 1.0) * crescent * 1.6) * visibility;
    } else if (mode == 2 && visibility > 0.001) {
        vec2 q = turn(-mirror_angle) * (p - center);
        vec2 bounds = vec2(radius, radius * 0.66);
        // Rectangular prism frame; keep geometry identical to frozen shards
        vec2 aq = abs(q);
        float bevel = (aq.x + aq.y - (bounds.x + bounds.y) * 0.78) * 0.7071;
        vec2 edge = aq - bounds;
        float d = max(edge.x, edge.y);

        if (d < 0.0) {
            vec2 sampleq = q;
            if (folded == 1) {
                float a = atan(q.y, q.x) + mirror_angle * 0.5;
                float len = length(q);
                a = abs(mod(a + PI / 6.0, PI / 3.0) - PI / 6.0);
                sampleq = vec2(cos(a), sin(a)) * len;
            }
            sampleq.x = -sampleq.x;
            float ripple = sin(length(q) * 0.045 - mirror_time * 3.2) * 2.5;
            sampleq += normalize(q + vec2(0.001)) * ripple;

            // Prismatic chromatic aberration inside the mirror
            vec2 chromaShift = (q / max(bounds, vec2(1.0))) * sh * 0.015;
            float rCh = camera(center + sampleq + chromaShift).r;
            float gCh = camera(center + sampleq).g;
            float bCh = camera(center + sampleq - chromaShift).b;
            vec3 reflected = vec3(rCh, gCh, bCh) * vec3(0.84, 0.97, 1.10) + vec3(0.02, 0.05, 0.09);

            if (folded == 1) {
                // Kaleidoscope facet facet-lines
                float fa = atan(q.y, q.x);
                float facetLine = band(sin(fa * 3.0) * length(q), 1.8);
                reflected += vec3(0.55, 0.90, 1.0) * facetLine * 0.65;
            }
            float fresnel = pow(clamp(1.0 + d / max(12.0, radius * 0.35), 0.0, 1.0), 3.0);
            reflected += vec3(0.35, 0.78, 1.0) * fresnel * 0.42;
            base = mix(base, reflected, clamp(visibility, 0.0, 1.0));
        }
        // Double crystalline frame + corner runes
        float frameGlow = band(d, 2.6) * 2.2 + band(d + 9.0, 1.4) * 1.2 + band(d, 14.0) * 0.45;
        light += vec3(0.62, 0.92, 1.0) * frameGlow * visibility;
        // Seed slit glow when mirror is small
        light += vec3(0.85, 0.97, 1.0) * band(q.x, 2.2) * exp(-abs(q.y) / max(24.0, radius * 0.85)) * visibility * float(radius < sh * 0.38);
    }

    // Crescent Moon Blades & Spatial Rift (System B)
    for (int i = 0; i < 8; i++) {
        if (i >= slash_count) break;
        vec2 a = slashes[i].xy, b = slashes[i].zw;
        float age = slash_data[i].x, power = slash_data[i].y;
        float life = max(0.0, 1.0 - age / 0.80);
        vec2 chord = b - a;
        float spanLen = max(1.0, length(chord));
        vec2 tangent = chord / spanLen;
        vec2 normal = vec2(-tangent.y, tangent.x);

        // 1. Flying Crescent Blade Wave
        vec2 flyCenter = mix(a, b, 0.5) + normal * (age * sh * 1.15);
        vec2 rel = p - flyCenter;
        float along = dot(rel, tangent) / (spanLen * (0.58 + 0.25 * age));
        float across = dot(rel, normal);
        if (abs(along) < 1.15) {
            float arcCurve = (1.0 - along * along) * sh * (0.22 + 0.08 * power);
            float thickness = max(1.5, (1.0 - along * along) * (6.0 + 7.0 * power));
            float dBlade = abs(across - arcCurve);
            float taper = clamp(1.0 - along * along, 0.0, 1.0);
            float bladeCore = band(dBlade, thickness * 0.45) * 2.6;
            float bladeAura = band(dBlade, thickness * 2.2) * 0.85;
            light += (vec3(0.95, 0.99, 1.0) * bladeCore + vec3(0.32, 0.82, 1.0) * bladeAura) * taper * life;
        }

        // 2. Persistent Spatial Rift along the cut line with UV shear
        float riftDist = lineDist(p, a, b);
        float riftMask = band(riftDist, 2.2) * life;
        if (quality > 0 && riftDist < 18.0) {
            float side = sign(dot(p - a, normal));
            base = mix(base, camera(p + tangent * side * 6.0 * life), band(riftDist, 6.0) * life * 0.65);
        }
        light += vec3(0.55, 0.88, 1.0) * riftMask * 1.4;
    }

    if (quality > 0) light += min(light, vec3(0.65)) * 0.22;
    vec3 finalLight = light * effect_gain;
    vec3 softLight = vec3(1.0) - exp(-finalLight*.65);
    color = vec4(base + (vec3(1.0)-base)*softLight, 1.0);
    emission = vec4(max(softLight - vec3(0.45), vec3(0.0)), 1.0);
}
