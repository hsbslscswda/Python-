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

// True 3D foreshortening projection:
// When a circular array in 3D rotates around the vertical axis by yaw (and pitches slightly),
// its 2D projection on screen compresses along the tilt axis by cos(tiltAngle) and shifts layers along the normal.
vec2 projectPlane(vec2 q, vec2 tilt, float layerDepth, float sh) {
    vec2 normal2D = tilt * (1.0 + 0.35 * migration);
    vec2 shifted = q - normal2D * layerDepth * sh * 0.42;
    float tiltMag = clamp(length(tilt), 0.0, 0.78);
    if (tiltMag < 0.005) return shifted;
    vec2 dir = tilt / max(length(tilt), 0.0001);
    vec2 ortho = vec2(-dir.y, dir.x);
    // Multiply (divide in inverse UV space) so the circle compresses into an ellipse facing the user's heading!
    float foreshorten = clamp(1.0 - tiltMag * 0.58, 0.38, 1.0);
    float parallel = dot(shifted, dir) / foreshorten;
    float perp = dot(shifted, ortho);
    return dir * parallel + ortho * perp;
}

// Sacred Roman/Astrolabe Magic Circle Layer (distinct antique gold/silver structural geometry)
float sigilLayer(vec2 p, float r, float t, float sh, int style) {
    float d = length(p);
    float a = atan(p.y, p.x);
    float thin = max(1.8, sh * 0.012);
    float v = 0.0;

    // 1. Grand Roman Astrolabe Outer Rim & Beveled Rings
    v += band(d - r, thin * 1.35) * 1.25;
    v += band(d - r * 0.93, thin * 0.95) * 0.95;
    v += band(d - r * 0.80, thin * 0.85) * 0.85;
    v += band(d - r * 0.66, thin * 0.75) * 0.70;
    v += band(d - r, thin * 8.0) * 0.32;

    // 2. Roman Duodecimal (12-hour) & 72-degree Astrolabe Graduations
    float majorTicks = smoothstep(0.75, 0.98, cos(a * 12.0 + t * 0.4));
    float minorTicks = smoothstep(0.55, 0.92, cos(a * 72.0 - t * 1.1));
    v += band(d - r * 0.965, thin * 2.2) * majorTicks * 1.15;
    v += band(d - r * 0.965, thin * 1.3) * minorTicks * 0.85;

    // 3. Arcane Rune Script Ring (between 0.80r and 0.93r)
    float runeCells = step(0.10, sin(a * 24.0 + t * 0.6)) * smoothstep(-0.15, 0.65, cos(a * 12.0 + d * 0.25 - t * 1.2));
    float runeCross = band(abs(fract(a * 12.0 / PI) - 0.5) * r * 0.12, thin * 0.7) * step(abs(d - r * 0.865), r * 0.045);
    v += (band(d - r * 0.865, thin * 3.4) * runeCells * 0.82) + runeCross * 0.65;

    // 4. Sacred Interlocking Hexagram / Octagram Geometry
    for (int i = 0; i < 6; i++) {
        float b = float(i) * PI / 3.0 + t * 0.18;
        vec2 u = vec2(cos(b), sin(b)) * r * 0.79;
        vec2 w = vec2(cos(b + 2.0 * PI / 3.0), sin(b + 2.0 * PI / 3.0)) * r * 0.79;
        v += band(lineDist(p, u, w), thin * 0.95) * 0.72;
    }

    if (style == 0) {
        // Cardinal Moon Phases & Celestial Orbs
        float sector = mod(a + PI / 4.0, PI / 2.0) - PI / 4.0;
        vec2 moonPos = vec2(cos(sector), sin(sector)) * d - vec2(r * 0.66, 0.0);
        float m1 = length(moonPos) - r * 0.085;
        float m2 = length(moonPos - vec2(r * 0.032, 0.0)) - r * 0.076;
        v += band(max(m1, -m2), thin * 1.05) * 1.15;
    } else {
        // inscribed Solomon Square & Jagged Runic Nodes
        float oct = cos(floor(0.5 + a / (PI / 4.0)) * (PI / 4.0) - a) * d;
        v += band(oct - r * 0.68, thin * 1.2) * 1.05;
        float jag = sin(a * 16.0 + floor(time * 10.0)) * r * 0.024;
        v += band(d - (r * 0.52 + jag), thin * 1.0) * 0.90;
    }

    // 5. Inner Sanctum Ring & Compass Rose
    float rose = abs(cos(a * 4.0 - t * 0.5)) * r * 0.12;
    v += band(d - (r * 0.30 + rose), thin * 0.95) * 0.80;
    v += band(d - r * 0.32, thin * 1.25) * 0.90;
    return v;
}

void main() {
    float fit = min(viewport.x / source_size.x, viewport.y / source_size.y);
    vec2 p = (uv * viewport - (viewport - source_size * fit) * 0.5) / fit;
    emission = vec4(0.0);
    if (any(lessThan(p, vec2(0.0))) || any(greaterThan(p, source_size))) {
        color = vec4(0.03, 0.025, 0.04, 1.0);
        return;
    }
    if (mirrored == 1) p.x = source_size.x - p.x;

    vec3 base = camera(p);
    float sh = max(shoulder, 1.0);

    // CRITICAL COLOR SEPARATION:
    // The Magic Circle (Array Structure) uses Antique Roman Brass/Gold & Celestial Amber-Silver,
    // while the Released Magic Energy uses Vivid Cyan-Sapphire (Lunar) or Crimson-Violet & Blazing Gold (Thunder)!
    vec3 arrayRimCol   = lightning == 1 ? vec3(0.95, 0.42, 0.18) : vec3(0.96, 0.80, 0.42); // Antique Brass / Solar Gold
    vec3 arrayRuneCol  = lightning == 1 ? vec3(1.00, 0.72, 0.25) : vec3(1.00, 0.93, 0.75); // Warm Ivory / Parchment Gold
    vec3 spellMainCol  = lightning == 1 ? vec3(0.75, 0.28, 1.00) : vec3(0.12, 0.85, 1.00); // Arcane Violet vs Vivid Lunar Cyan
    vec3 spellCoreCol  = lightning == 1 ? vec3(1.00, 0.92, 0.55) : vec3(0.90, 0.99, 1.00); // Blazing Core

    vec3 light = vec3(0.0);

    if (mode == 0 && visibility > 0.001) {
        vec2 q = p - center;
        // Grand scale: allow up to 62% of screen height so the array looks truly magnificent
        float r = min(radius * 1.28, min(source_size.x, source_size.y) * 0.60);

        // Smooth 3D tilt driven primarily by body_yaw so turning sideways rotates the array toward your facing direction
        float yawSign = mirrored == 1 ? -1.0 : 1.0;
        vec2 bodyTilt = vec2(sin(body_yaw) * yawSign * 0.72, 0.0);
        vec2 aimOffset = clamp((palm - chest) / (sh * 2.2), vec2(-0.35), vec2(0.35));
        vec2 tilt = clamp(bodyTilt + aimOffset * (0.20 + 0.35 * migration), vec2(-0.75), vec2(0.75));

        float spread = 0.42 + 1.05 * migration;
        vec2 qBack = projectPlane(q, tilt, -0.60 * spread, sh);
        vec2 qMid  = projectPlane(q, tilt,  0.00 * spread, sh);
        vec2 qFore = projectPlane(q, tilt, +0.70 * spread, sh);

        float vBack = sigilLayer(turn(-time * 0.18) * qBack, r * (1.05 - 0.10 * migration), -time * 0.25, sh, lightning);
        float vMid  = sigilLayer(turn( time * (0.25 + 0.35 * intensity)) * qMid, r * 0.80, time * 0.40, sh, lightning);
        float vFore = sigilLayer(turn(-time * (0.38 + 0.55 * migration)) * qFore, r * (0.50 + 0.20 * migration), time * 0.65, sh, lightning);

        float faceGuard = smoothstep(sh * 0.18, sh * 0.40, length(p - (chest - vec2(0.0, sh * 0.65))));
        float armPortal = smoothstep(sh * 0.06, sh * 0.16, lineDist(p, chest, palm));

        // Obsidian shadow backing behind the runes so gold/cyan contrast sharply against any room lighting
        float diskMask = smoothstep(r * 0.28, r * 0.55, length(qMid)) * (1.0 - smoothstep(r * 0.96, r * 1.10, length(qMid)));
        base *= 1.0 - diskMask * visibility * 0.52 * faceGuard;

        // Render the Structural Array in warm Antique Gold / Ivory so it is 100% distinct from the spell discharge
        vec3 arrayLight = arrayRimCol * vBack * 0.95 + arrayRuneCol * vMid * 1.45 + mix(arrayRuneCol, spellCoreCol, 0.4) * vFore * (1.05 + 0.90 * migration);
        light += arrayLight * smoothstep(r * 0.10, r * 0.26, length(qMid)) * faceGuard * mix(0.68, 1.0, armPortal) * visibility * 1.35;

        // Render the Spell Discharge (Energy Plume, Beams, Vortex & Lightning) in contrasting Vivid Cyan or Violet-Gold
        if (intensity > 0.002) {
            vec2 ep = projectPlane(p - palm, tilt, 0.55, sh);
            float d = length(ep) / sh;
            float a = atan(ep.y, ep.x);

            // Energy conduit beam linking chest array center to caster palm
            float conduitDist = lineDist(p, center, palm);
            float conduit = band(conduitDist, sh * (0.04 + 0.05 * intensity)) * smoothstep(0.0, 0.2, intensity);
            light += spellMainCol * conduit * visibility * 1.65;

            if (lightning == 0) {
                // Magnificent Lunar Astral Vortex + Expanding Celestial Rings
                float spiral1 = sin(a * 5.0 - d * 16.0 + time * (7.0 + intensity * 7.0));
                float spiral2 = cos(a * 3.0 + d * 12.0 - time * 5.0);
                float vortex = smoothstep(0.15, 0.92, spiral1 * 0.65 + spiral2 * 0.35) * exp(-d * 1.45) * intensity;
                float shockWave = band(fract(d * 1.35 - time * (1.1 + intensity * 0.8)) - 0.5, 0.09) * exp(-d * 1.15) * intensity;
                float palmOrb = band(d - 0.14 * (0.8 + 0.5 * intensity), 0.045) * 2.4 + band(d, 0.12) * 1.8;
                light += (spellMainCol * (vortex * 1.85 + shockWave * 1.65) + spellCoreCol * palmOrb * intensity) * visibility * 1.65;
            } else {
                // Grand branching Violet-Gold Thunderbolts
                float arcField = 0.0;
                for (int k = 0; k < 6; k++) {
                    float fk = float(k);
                    float seed = floor(time * 13.0) + fk * 9.17;
                    float targetAngle = fk * (2.0 * PI / 6.0) + time * 0.8;
                    float jitter = sin(d * 28.0 + seed * 3.7) * 0.25 + cos(d * 61.0 - seed * 5.1) * 0.13;
                    float angleDiff = abs(mod(a - targetAngle + jitter + PI, 2.0 * PI) - PI);
                    arcField += band(angleDiff * d, 0.014 + 0.010 * intensity) * exp(-d * 1.10);
                }
                float palmSpark = band(d - 0.11, 0.038) * 2.5 + band(d, 0.09) * 1.9;
                light += (spellMainCol * arcField * 2.1 + spellCoreCol * (arcField * 1.4 + palmSpark)) * intensity * visibility * 1.65;
            }
        }

        // Overdrive (110%-150%): Triple Axial Projection + Reality-Bending Shockwave + Eclipse Core
        if (migration > 0.02) {
            float wave = fract(time * 1.10);
            float shockR = r * (0.10 + wave * 1.25);
            float shockBand = band(length(qFore) - shockR, 6.5) * (1.0 - wave) * migration;
            if (quality > 0) {
                vec2 dir = normalize(qFore + vec2(0.001));
                base = mix(base, camera(p + dir * shockBand * sh * 0.055), clamp(migration, 0.0, 1.0));
            }
            float eclipseCore = (1.0 - smoothstep(r * 0.09, r * 0.25, length(qFore))) * migration * clamp(intensity, 0.5, 1.5);
            base *= 1.0 - eclipseCore * 0.85;
            float corona = band(length(qFore) - r * 0.20, max(3.0, sh * 0.026)) * migration * 2.6;
            light += (spellCoreCol * corona + spellMainCol * shockBand * 2.4) * visibility;
        }
    } else if (mode == 1 && visibility > 0.001) {
        vec2 q = p - center;
        float c1 = length(q) - radius * 1.15;
        float c2 = length(q - vec2(radius * 0.42, -radius * 0.18)) - radius * 1.05;
        float crescent = (1.0 - smoothstep(-1.0, 3.5, max(c1, -c2)));
        float rim = band(length(q) - radius * 1.15, 2.5);
        light += (vec3(0.45, 0.88, 1.0) * rim * 1.4 + vec3(0.88, 0.97, 1.0) * crescent * 1.6) * visibility;
    } else if (mode == 2 && visibility > 0.001) {
        vec2 q = turn(-mirror_angle) * (p - center);
        vec2 bounds = vec2(radius, radius * 0.66);
        vec2 aq = abs(q);
        vec2 edge = aq - bounds;
        float d = max(edge.x, edge.y);

        if (d < 0.0) {
            vec2 sampleq = q;
            if (folded == 1) {
                // Multi-mode Arcane Kaleidoscope & Dimensional Portal
                float a = atan(q.y, q.x) + mirror_angle * 0.65;
                float len = length(q);
                a = abs(mod(a + PI / 6.0, PI / 3.0) - PI / 6.0);
                sampleq = vec2(cos(a), sin(a)) * len;
            }
            sampleq.x = -sampleq.x;
            float ripple = sin(length(q) * 0.045 - mirror_time * 3.2) * 2.5;
            sampleq += normalize(q + vec2(0.001)) * ripple;

            vec2 chromaShift = (q / max(bounds, vec2(1.0))) * sh * 0.016;
            float rCh = camera(center + sampleq + chromaShift).r;
            float gCh = camera(center + sampleq).g;
            float bCh = camera(center + sampleq - chromaShift).b;
            vec3 reflected = vec3(rCh, gCh, bCh) * vec3(0.86, 0.97, 1.12) + vec3(0.02, 0.05, 0.09);

            if (folded == 1) {
                float fa = atan(q.y, q.x) + mirror_angle * 0.5;
                float facetLine = band(sin(fa * 3.0) * length(q), 2.0);
                float innerRing = band(length(q) - radius * 0.42, 2.2);
                reflected += vec3(0.95, 0.78, 0.38) * (facetLine * 0.75 + innerRing * 0.85);
            }
            float fresnel = pow(clamp(1.0 + d / max(14.0, radius * 0.38), 0.0, 1.0), 2.8);
            reflected += vec3(0.45, 0.85, 1.0) * fresnel * 0.50;
            base = mix(base, reflected, clamp(visibility, 0.0, 1.0));
        }

        // Ornate Roman Mirror Frame (Gold outer trim + Silver-Cyan inner prism + Corner Astrolabe Rosettes)
        float outerGold = band(d + 5.0, 2.4) * 1.85 + band(d - 4.0, 1.8) * 1.25;
        float innerCyan = band(d, 2.8) * 2.2 + band(d, 16.0) * 0.50;
        vec2 cornerDist = aq - bounds;
        float cornerRosette = band(length(cornerDist) - sh * 0.06, 2.2) * step(length(cornerDist), sh * 0.11);
        light += (vec3(0.96, 0.78, 0.38) * (outerGold + cornerRosette * 2.0) + vec3(0.55, 0.92, 1.0) * innerCyan) * visibility;
        light += vec3(0.95, 0.88, 0.65) * band(q.x, 2.5) * exp(-abs(q.y) / max(24.0, radius * 0.85)) * visibility * float(radius < sh * 0.38);
    }

    for (int i = 0; i < 8; i++) {
        if (i >= slash_count) break;
        vec2 a = slashes[i].xy, b = slashes[i].zw;
        float age = slash_data[i].x, power = slash_data[i].y;
        float life = max(0.0, 1.0 - age / 0.80);
        vec2 chord = b - a;
        float spanLen = max(1.0, length(chord));
        vec2 tangent = chord / spanLen;
        vec2 normal = vec2(-tangent.y, tangent.x);

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

        float riftDist = lineDist(p, a, b);
        float riftMask = band(riftDist, 2.2) * life;
        if (quality > 0 && riftDist < 18.0) {
            float side = sign(dot(p - a, normal));
            base = mix(base, camera(p + tangent * side * 6.0 * life), band(riftDist, 6.0) * life * 0.65);
        }
        light += vec3(0.55, 0.88, 1.0) * riftMask * 1.4;
    }

    if (quality > 0) light += min(light, vec3(0.65)) * 0.24;
    vec3 finalLight = light * effect_gain;
    vec3 softLight = vec3(1.0) - exp(-finalLight * 0.72);
    color = vec4(base + (vec3(1.0) - base * 0.75) * softLight, 1.0);
    emission = vec4(max(softLight - vec3(0.38), vec3(0.0)), 1.0);
}
