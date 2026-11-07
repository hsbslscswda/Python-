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
uniform vec3 cast_direction;
uniform int object_count;
uniform vec4 objects[12];
uniform vec4 object_motion[12];
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
const float TAU = 6.28318530718;

float band(float d, float w) {
    return exp(-d * d / max(0.00005, w * w));
}

float sharpLine(float d, float w) {
    return (1.0 - smoothstep(w * 0.2, w * 1.4, abs(d))) + exp(-abs(d) / max(0.001, w * 2.2)) * 0.45;
}

float lineDist(vec2 p, vec2 a, vec2 b) {
    vec2 ab = b - a;
    return length(p - a - clamp(dot(p - a, ab) / max(0.0001, dot(ab, ab)), 0.0, 1.0) * ab);
}

mat2 turn(float a) {
    float c = cos(a), s = sin(a);
    return mat2(c, s, -s, c);
}

vec3 camera(vec2 p) {
    return texture(camera_tex, clamp(p / source_size, vec2(0.0), vec2(1.0))).rgb;
}

float hash21(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

float noise2D(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = hash21(i);
    float b = hash21(i + vec2(1.0, 0.0));
    float c = hash21(i + vec2(0.0, 1.0));
    float d = hash21(i + vec2(1.0, 1.0));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

float fbm(vec2 p) {
    float v = 0.0;
    float amp = 0.5;
    mat2 rot = turn(0.58);
    for (int i = 0; i < 4; i++) {
        v += amp * noise2D(p);
        p = rot * p * 2.07 + vec2(17.3, 9.2);
        amp *= 0.5;
    }
    return v;
}

// 3D perspective foreshortening projection
vec2 projectPlane(vec2 q, vec2 tilt, float layerDepth, float sh) {
    vec2 normal2D = tilt * (1.0 + 0.35 * migration);
    vec2 shifted = q - normal2D * layerDepth * sh * 0.42;
    float tiltMag = clamp(length(tilt), 0.0, 0.78);
    if (tiltMag < 0.005) return shifted;
    vec2 dir = tilt / max(length(tilt), 0.0001);
    vec2 ortho = vec2(-dir.y, dir.x);
    float foreshorten = clamp(1.0 - tiltMag * 0.58, 0.38, 1.0);
    float parallel = dot(shifted, dir) / foreshorten;
    float perp = dot(shifted, ortho);
    return dir * parallel + ortho * perp;
}

// Procedural Arcane Alchemical Glyph inside a polar cell:
// Draws actual multi-stroke geometric runes (stems, crescents, diamonds, crossbars, circles)
float arcaneGlyph(vec2 uvCell, float id) {
    vec2 g = uvCell * 2.0 - 1.0;
    if (max(abs(g.x), abs(g.y)) > 0.88) return 0.0;
    float h1 = fract(id * 0.371 + 0.13);
    float h2 = fract(id * 0.719 + 0.47);
    float h3 = fract(id * 0.531 + 0.89);
    float d = 10.0;

    // Central vertical or diagonal staff
    if (h1 > 0.25) {
        d = min(d, lineDist(g, vec2(0.0, -0.72), vec2(0.0, 0.72)));
    } else {
        d = min(d, lineDist(g, vec2(-0.55, -0.65), vec2(0.55, 0.65)));
    }
    // Alchemical circle or crescent head
    vec2 cPos = vec2(0.0, (h2 - 0.5) * 0.55);
    d = min(d, abs(length(g - cPos) - 0.34));
    // Diagonal rune branches
    float side = h3 > 0.5 ? 1.0 : -1.0;
    d = min(d, lineDist(g, vec2(-0.52, -0.25 * side), vec2(0.52, 0.35 * side)));
    if (h2 > 0.45) {
        d = min(d, lineDist(g, vec2(-0.45, 0.48), vec2(0.45, 0.48)));
    }
    if (h3 > 0.35) {
        vec2 rg = abs(g - vec2(0.0, -0.2 * side));
        d = min(d, abs(rg.x + rg.y - 0.42) * 0.7071);
    }
    return 1.0 - smoothstep(0.04, 0.16, d);
}

// High-detail Gothic / Ptolemaic Armillary Astrolabe Layer
// Returns vec2(structuralFiligree, luminescentEnergy) so we can color the intricate filigree and glowing runes distinctly!
vec2 grandAstrolabe(vec2 p, float r, float t, float sh, int style) {
    float d = length(p);
    if (d > r * 1.22) return vec2(0.0);
    float a = atan(p.y, p.x);
    float w = max(1.15, sh * 0.0055);
    float metal = 0.0;
    float glow = 0.0;

    // 1. Outer Guilloché / Spirograph Rose Lacework (24-fold harmonic hypotrochoid weave)
    float lace1 = r * (0.955 + 0.028 * cos(a * 24.0 + t * 0.6) + 0.014 * sin(a * 48.0 - t * 1.2));
    float lace2 = r * (0.955 - 0.028 * cos(a * 24.0 - t * 0.6) + 0.014 * cos(a * 72.0 + t * 0.8));
    metal += sharpLine(d - lace1, w * 0.85) * 0.85;
    metal += sharpLine(d - lace2, w * 0.85) * 0.75;
    metal += sharpLine(d - r, w * 1.35) * 1.25;
    metal += sharpLine(d - r * 0.915, w * 1.1) * 1.05;

    // 2. Precision 360-degree Vernier Astrolabe Graduations (72 minor, 24 medium, 12 zodiacal major)
    if (d > r * 0.89 && d < r * 1.02) {
        float tick72 = smoothstep(0.72, 0.98, cos(a * 72.0));
        float tick24 = smoothstep(0.82, 0.99, cos(a * 24.0));
        float tick12 = smoothstep(0.90, 0.998, cos(a * 12.0));
        float inMinor = step(r * 0.982, d) * step(d, r * 1.00);
        float inMed   = step(r * 0.968, d) * step(d, r * 1.00);
        float inMaj   = step(r * 0.915, d) * step(d, r * 1.008);
        metal += (tick72 * inMinor * 0.75 + tick24 * inMed * 0.95 + tick12 * inMaj * 1.35);
    }

    // 3. Outer Inscribed Alchemical Script Band (36 distinct procedural runes between 0.81r and 0.90r)
    if (d > r * 0.805 && d < r * 0.905) {
        float numCells = 36.0;
        float aRot = a + t * 0.14;
        float cellId = floor((aRot + PI) / TAU * numCells);
        float cellU = fract((aRot + PI) / TAU * numCells);
        float cellV = (d - r * 0.812) / (r * 0.086);
        float glyph = arcaneGlyph(vec2(cellU, cellV), cellId);
        glow += glyph * 1.25;
        // Delicate divider pillars between runes
        float divider = 1.0 - smoothstep(0.01, 0.06, min(cellU, 1.0 - cellU));
        metal += divider * 0.55;
    }
    metal += sharpLine(d - r * 0.808, w * 1.05) * 1.0;

    // 4. Gothic Rose Cathedral Tracery (12 pointed lancet arches + trefoil cusps between 0.52r and 0.808r)
    float sector12 = mod(a + PI / 12.0, PI / 6.0) - PI / 12.0;
    vec2 lp12 = vec2(cos(sector12), sin(sector12)) * d;
    // Two intersecting circular arcs forming a pointed Gothic ogive arch in each of the 12 sectors
    float arch1 = abs(length(lp12 - vec2(r * 0.54, -r * 0.14)) - r * 0.27);
    float arch2 = abs(length(lp12 - vec2(r * 0.54,  r * 0.14)) - r * 0.27);
    float gothicArch = min(arch1, arch2);
    float archMask = step(r * 0.50, d) * step(d, r * 0.808);
    metal += sharpLine(gothicArch, w * 0.95) * archMask * 0.95;
    // Foil rosette inside the upper cusp of each Gothic arch
    float rosette = abs(length(lp12 - vec2(r * 0.71, 0.0)) - r * 0.048);
    float rosetteDot = length(lp12 - vec2(r * 0.71, 0.0));
    metal += sharpLine(rosette, w * 0.8) * 0.85;
    glow  += band(rosetteDot, w * 2.2) * 1.1;

    // 5. Continuous Sacred Polygram Curve (24-pointed Dodecagram + Rhodonea Rose Curve)
    float roseCurve1 = r * (0.64 + 0.155 * cos(a * 6.0 - t * 0.25) * cos(a * 2.0 + t * 0.1));
    float roseCurve2 = r * (0.64 + 0.155 * sin(a * 6.0 + t * 0.25) * sin(a * 2.0 - t * 0.1));
    glow  += sharpLine(d - roseCurve1, w * 0.90) * 0.85;
    metal += sharpLine(d - roseCurve2, w * 0.85) * 0.80;

    // 6. Ptolemaic Eccentric Ecliptic Ring & 8 Planetary / Moon-Phase Astrolabe Medallions
    vec2 eclipticOffset = vec2(cos(t * 0.35), sin(t * 0.35)) * r * 0.085;
    float dEcliptic = abs(length(p - eclipticOffset) - r * 0.58);
    metal += sharpLine(dEcliptic, w * 1.1) * 0.95;

    float sector8 = mod(a + PI / 8.0 - t * 0.2, PI / 4.0) - PI / 8.0;
    vec2 nodePos = vec2(cos(sector8), sin(sector8)) * d - vec2(r * 0.50, 0.0);
    float outerMedal = abs(length(nodePos) - r * 0.068);
    float innerCrescent = max(length(nodePos) - r * 0.052, -(length(nodePos - vec2(r * 0.022, 0.0)) - r * 0.045));
    metal += sharpLine(outerMedal, w * 0.85) * 1.05;
    glow  += (1.0 - smoothstep(-w * 0.5, w * 1.2, innerCrescent)) * 1.35;

    // 7. Inner Sanctum Rune Ring (24 micro-runes between 0.34r and 0.42r) & 16-Ray Astrolabe Compass Star
    metal += sharpLine(d - r * 0.425, w * 1.0) * 0.95;
    metal += sharpLine(d - r * 0.335, w * 1.0) * 0.95;
    if (d > r * 0.335 && d < r * 0.425) {
        float aInner = a - t * 0.28;
        float id2 = floor((aInner + PI) / TAU * 24.0) + 19.0;
        float u2 = fract((aInner + PI) / TAU * 24.0);
        float v2 = (d - r * 0.34) / (r * 0.08);
        glow += arcaneGlyph(vec2(u2, v2), id2) * 1.15;
    }

    // 16-ray astrolabe star needle in the center
    float star16 = r * (0.16 + 0.16 * pow(abs(cos(a * 8.0 + t * 0.4)), 3.0));
    metal += sharpLine(d - star16, w * 0.9) * 0.95;
    glow  += band(d - r * 0.14, w * 2.5) * 0.95;

    if (style == 1) {
        // Additional High-Frequency Runic Circuit Traces for Thunder Mode
        float circuit = abs(sin(a * 16.0 + floor(d / (r * 0.06)) * 1.7)) * d;
        glow += sharpLine(circuit, w * 0.75) * step(r * 0.32, d) * step(d, r * 0.92) * 0.55;
    }

    return vec2(metal, glow);
}

void main() {
    float fit = min(viewport.x / source_size.x, viewport.y / source_size.y);
    vec2 p = (uv * viewport - (viewport - source_size * fit) * 0.5) / fit;
    emission = vec4(0.0);
    if (any(lessThan(p, vec2(0.0))) || any(greaterThan(p, source_size))) {
        color = vec4(0.025, 0.02, 0.04, 1.0);
        return;
    }
    if (mirrored == 1) p.x = source_size.x - p.x;

    vec3 base = camera(p);
    float sh = max(shoulder, 1.0);

    // Non-emissive warm metal is deliberately separate from the cold discharge.
    vec3 filigreeCol = vec3(0.68, 0.48, 0.23);
    vec3 runeGlowCol = vec3(0.86, 0.64, 0.32);
    vec3 spellMainCol = lightning == 1 ? vec3(0.42, 0.12, 0.95) : vec3(0.02, 0.38, 0.82);
    vec3 spellCoreCol = lightning == 1 ? vec3(0.72, 0.36, 1.0) : vec3(0.24, 0.72, 1.0);
    vec3 light = vec3(0.0);

    if (mode == 0 && visibility > 0.001) {
        vec2 q = p - center;
        float r = min(radius * 1.28, min(source_size.x, source_size.y) * 0.60);

        float yawSign = mirrored == 1 ? -1.0 : 1.0;
        vec2 bodyTilt = vec2(sin(body_yaw) * yawSign * 0.72, 0.0);
        vec2 aimOffset = clamp((palm - chest) / (sh * 2.2), vec2(-0.35), vec2(0.35));
        vec2 tilt = clamp(bodyTilt + aimOffset * (0.20 + 0.35 * migration), vec2(-0.75), vec2(0.75));

        float spread = 0.42 + 1.05 * migration;
        vec2 qBack = projectPlane(q, tilt, -0.60 * spread, sh);
        vec2 qMid  = projectPlane(q, tilt,  0.00 * spread, sh);
        vec2 qFore = projectPlane(q, tilt, +0.70 * spread, sh);

        vec2 layerBack = grandAstrolabe(turn(-time * 0.14) * qBack, r * (1.05 - 0.08 * migration), -time * 0.25, sh, lightning);
        vec2 layerMid  = grandAstrolabe(turn( time * (0.20 + 0.30 * intensity)) * qMid, r * 0.79, time * 0.40, sh, lightning);
        vec2 layerFore = grandAstrolabe(turn(-time * (0.32 + 0.48 * migration)) * qFore, r * (0.50 + 0.18 * migration), time * 0.60, sh, lightning);

        float faceGuard = smoothstep(sh * 0.18, sh * 0.40, length(p - (chest - vec2(0.0, sh * 0.65))));
        float armPortal = smoothstep(sh * 0.06, sh * 0.16, lineDist(p, chest, palm));

        // Mystical Abyssal Vignette & FBM Star-Nebula inside the Astrolabe
        float rNorm = length(qMid) / max(r, 1.0);
        float diskMask = smoothstep(0.18, 0.45, rNorm) * (1.0 - smoothstep(0.96, 1.12, rNorm));
        float nebula = fbm(qMid / (sh * 0.35) + vec2(time * 0.18, -time * 0.12));
        base *= 1.0 - diskMask * visibility * 0.16 * faceGuard;
        // Array remains a material, not another energy cloud.

        // Combine Brushed Champagne-Silver Filigree with Luminous Cyan/Violet Engraved Runes
        float engraving = layerBack.x * 0.28 + layerMid.x * 0.42 + layerFore.x * 0.20;
        float runes = layerBack.y * 0.18 + layerMid.y * 0.30 + layerFore.y * 0.14;
        float mask = clamp((engraving + runes) * visibility * faceGuard, 0.0, 0.82);
        vec3 metalColor = filigreeCol * (0.55 + 0.30 * sin(qMid.y * 0.03)) + runeGlowCol * min(runes, 0.45);
        base = mix(base, metalColor, mask);

        // A directed stream with travelling dense packets, wake and a narrow core.
        // Forward-facing palms use a foreground-biased screen trajectory; depth is estimated.
        if (intensity > 0.002) {
            vec2 aim = cast_direction.xy;
            if (length(aim) < 0.20) aim = (palm - chest) / sh + vec2(0.0, -0.12);
            aim = normalize(aim + vec2(0.001));
            vec2 normal = vec2(-aim.y, aim.x);
            vec2 delta = p - palm;
            float along = dot(delta, aim);
            float across = dot(delta, normal);
            float reach = sh * (3.2 + migration);
            if (along >= -sh * 0.10 && along < reach) {
                float u = clamp(along / reach, 0.0, 1.0);
                float width = sh * (0.035 + 0.065 * intensity + migration * 0.08) * (1.0 + u * 0.55);
                float turbulence = (fbm(vec2(along/sh*4.0-time*6.0, across/sh*5.0)) - 0.5) * width;
                float core = band(across + turbulence * 0.25, width * 0.30);
                float sheath = band(across + turbulence, width);
                float packets = pow(max(0.0, cos(u * 35.0 - time * 18.0)), 12.0);
                float envelope = smoothstep(-sh*0.1, sh*0.12, along) * (1.0-smoothstep(0.80, 1.0, u));
                light += (spellMainCol * sheath * 0.65 + spellCoreCol * core * (0.7 + packets*1.5)) * envelope * intensity * visibility;
                if (migration > 0.05) {
                    float flank = abs(across) - width * (1.5 + 0.18*sin(along/sh*9.0-time*8.0));
                    light += spellMainCol * band(flank, width*0.23) * envelope * migration * 0.9;
                }
                for (int k=0; k<4; k++) {
                    float head = fract(time*1.5+float(k)*0.25)*reach;
                    float dx = (along-head)/max(1.0, sh*0.17);
                    float dy = across/max(1.0, width*0.7);
                    float packet = exp(-dx*dx-dy*dy);
                    light += spellCoreCol * packet * envelope * intensity * 0.8;
                }
            }
        }

        if (migration > 0.02) {
            float wave = fract(time * 0.8);
            float shockR = r * (0.15 + wave * 0.85);
            float shock = band(length(qFore)-shockR, 2.0) * (1.0-wave) * migration;
            light += spellMainCol * shock * 0.28 * visibility;
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
                float facetLine = sharpLine(sin(fa * 3.0) * length(q), 1.5);
                float innerRosette = sharpLine(length(q) - radius * (0.42 + 0.08 * cos(fa * 12.0)), 1.6);
                reflected += vec3(0.82, 0.88, 1.0) * (facetLine * 0.70 + innerRosette * 0.85);
            }
            float fresnel = pow(clamp(1.0 + d / max(14.0, radius * 0.38), 0.0, 1.0), 2.8);
            reflected += vec3(0.45, 0.82, 1.0) * fresnel * 0.52;
            base = mix(base, reflected, clamp(visibility, 0.0, 1.0));
        }

        // Intricate Engraved Silver-Champagne & Astral-Cyan Mirror Frame with Filigree Corner Rosettes
        float scrollWave = sin((q.x + q.y) * 0.18) * 1.8;
        float outerFiligree = sharpLine(d + 5.5 + scrollWave, 1.4) * 1.35 + sharpLine(d - 4.5, 1.2) * 1.10;
        float innerPrism = sharpLine(d, 2.0) * 1.85 + band(d, 14.0) * 0.45;
        vec2 cornerDist = aq - bounds;
        float cornerAngle = atan(cornerDist.y, cornerDist.x);
        float cornerLace = sharpLine(length(cornerDist) - sh * (0.065 + 0.018 * cos(cornerAngle * 8.0)), 1.4) * step(length(cornerDist), sh * 0.12);
        light += (filigreeCol * (outerFiligree + cornerLace * 1.8) + vec3(0.52, 0.90, 1.0) * innerPrism) * visibility;
        light += vec3(0.85, 0.94, 1.0) * band(q.x, 2.4) * exp(-abs(q.y) / max(24.0, radius * 0.85)) * visibility * float(radius < sh * 0.38);
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

    // Bounded object list: persistent water, ballistic water, splashes and per-hand flame.
    for (int i=0; i<12; i++) {
        if (i >= object_count) break;
        vec2 c = objects[i].xy;
        float r = max(2.0, objects[i].z), opacity=objects[i].w;
        vec2 velocity=object_motion[i].xy;
        float age=object_motion[i].z;
        int kind=int(object_motion[i].w+0.5);
        vec2 q=(p-c)/r;
        if (kind == 1 || kind == 2) {
            float a=atan(q.y,q.x);
            float wobble=0.025*sin(a*5.0+time*3.5)+0.018*sin(a*9.0-time*5.0);
            vec2 v=q/(1.0+wobble);
            float d=length(v);
            if(d<1.0) {
                vec3 n=vec3(v,sqrt(max(0.0,1.0-dot(v,v))));
                vec2 offset=n.xy*r*(0.16+0.12*n.z);
                vec3 refracted=camera(p+offset)*vec3(0.65,0.90,1.0);
                float fresnel=pow(1.0-n.z,3.0);
                float spec=pow(max(0.0,dot(n,normalize(vec3(-0.4,-0.6,0.9)))),70.0);
                float caustic=pow(max(0.0,sin(v.x*17.0+sin(v.y*13.0+time*2.5)+time*1.8)),14.0)*(1.0-n.z*0.5);
                float diffuse=max(0.0,dot(n,normalize(vec3(-0.45,-0.65,0.9))));
                vec3 sky=mix(vec3(0.025,0.08,0.14),vec3(0.22,0.52,0.68),clamp(0.5-n.y*0.6,0.0,1.0));
                vec3 water=refracted*0.72+sky*(0.25+fresnel*0.50)+vec3(0.05,0.16,0.23)*diffuse+vec3(0.75,0.90,0.98)*spec+vec3(0.04,0.10,0.13)*caustic;
                base=mix(base,water,opacity*(1.0-smoothstep(0.94,1.0,d))*0.92);
            }
            if(kind==2) {
                vec2 dir=normalize(velocity+vec2(0.001));
                float tail=max(0.0,-dot(q,dir));
                float side=abs(q.x*dir.y-q.y*dir.x);
                float trail=exp(-side*side*12.0-tail*1.7)*step(0.2,tail)*step(tail,4.0);
                base=mix(base,vec3(0.08,0.38,0.56),trail*0.35*opacity);
            }
        } else if(kind==3) {
            float fade=max(0.0,1.0-age/1.1);
            for(int j=0;j<18;j++) {
                float fj=float(j), a=fj*2.39996;
                vec2 pos=vec2(cos(a),sin(a))*(0.15+age*(1.2+fract(fj*0.37)))+vec2(0.0,age*age*0.85);
                float size=(0.03+fract(fj*0.27)*0.05)*fade;
                float drop=1.0-smoothstep(size*0.5,size,length(q-pos));
                base=mix(base,vec3(0.22,0.57,0.76),drop*fade*0.75);
                light+=vec3(0.12,0.28,0.32)*drop*fade*0.2;
            }
            float ring=band(length(q)-(0.2+age*1.8),0.025)*fade;
            base=mix(base,vec3(0.16,0.38,0.50),ring*0.35);
        } else if(kind==4) {
            vec2 uvf=q;
            float height=-uvf.y;
            if(height> -0.2 && height<3.8 && abs(uvf.x)<1.5) {
                float n=fbm(vec2(uvf.x*3.8,height*2.4-time*5.0));
                float width=(0.88-height*0.20)*(0.65+0.7*n);
                float sway=sin(height*2.4-time*6.0)*0.12*height;
                float body=1.0-smoothstep(width*0.35,width,abs(uvf.x+sway));
                float tongues=1.0-smoothstep(2.0+n*1.6,3.8,height);
                float density=body*tongues*smoothstep(-0.2,0.1,height);
                float hot=pow(clamp(1.0-height/3.0,0.0,1.0),1.4)*body;
                vec3 flame=mix(vec3(0.80,0.08,0.005),vec3(1.0,0.62,0.08),hot);
                base=mix(base,flame,density*opacity*0.86);
                light+=vec3(0.35,0.08,0.005)*density*opacity*0.35;
            }
            for(int j=0;j<6;j++) {
                float u=fract(time*(0.5+float(j)*0.04)+float(j)*0.17);
                vec2 pos=vec2(sin(float(j)*8.1+u*4.0)*u*0.9,-u*4.5);
                float ember=band(length(q-pos),0.018)*(1.0-u);
                light+=vec3(0.7,0.22,0.01)*ember*opacity;
            }
        }
    }
    vec3 finalLight = max(vec3(0.0),light) * effect_gain;
    vec3 softLight = finalLight/(vec3(1.0)+finalLight);
    color = vec4(base + (vec3(1.0)-base)*softLight,1.0);
    emission = vec4(max(softLight-vec3(0.70),vec3(0.0))*0.25,1.0);
}
