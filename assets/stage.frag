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

    // Refined Mystical Palette (Never garish yellow! Uses Moonlight Platinum-Champagne, Astral Cyan-Sapphire, and Amethyst-Starlight)
    vec3 filigreeCol = lightning == 1 ? vec3(0.92, 0.76, 0.58) : vec3(0.86, 0.80, 0.68); // Brushed Champagne Silver-Brass
    vec3 runeGlowCol = lightning == 1 ? vec3(1.00, 0.64, 0.92) : vec3(0.62, 0.92, 1.00); // Luminous Lilac-Rose vs Ice-Cyan Runes
    vec3 spellMainCol = lightning == 1 ? vec3(0.62, 0.24, 1.00) : vec3(0.12, 0.72, 1.00); // Deep Astral Violet vs Celestial Azure
    vec3 spellCoreCol = lightning == 1 ? vec3(1.00, 0.92, 0.78) : vec3(0.92, 0.98, 1.00); // Starlight Core

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
        base *= 1.0 - diskMask * visibility * 0.54 * faceGuard;
        light += spellMainCol * diskMask * nebula * 0.38 * (0.5 + 0.8 * intensity) * faceGuard * visibility;

        // Combine Brushed Champagne-Silver Filigree with Luminous Cyan/Violet Engraved Runes
        vec3 backCol = filigreeCol * layerBack.x * 0.55 + spellMainCol * layerBack.y * 0.75;
        vec3 midCol  = filigreeCol * layerMid.x  * 1.05 + runeGlowCol  * layerMid.y  * 1.35;
        vec3 foreCol = mix(filigreeCol, spellCoreCol, 0.5) * layerFore.x * (0.85 + 0.75 * migration)
                     + spellCoreCol * layerFore.y * (0.95 + 0.90 * migration);

        vec3 arrayLight = backCol + midCol + foreCol;
        light += arrayLight * smoothstep(r * 0.08, r * 0.22, length(qMid)) * faceGuard * mix(0.68, 1.0, armPortal) * visibility * 1.18;

        // Active Spell Discharge: Swirling Nebula Streams, Orbiting Star-Motes & Fractal Lightning
        if (intensity > 0.002) {
            vec2 ep = projectPlane(p - palm, tilt, 0.55, sh);
            float d = length(ep) / sh;
            float a = atan(ep.y, ep.x);

            // Ethereal braided energy conduit between chest and palm
            float conduitDist = lineDist(p, center, palm);
            float braid = sin(length(p - center) * 0.12 - time * 9.0) * sh * 0.025;
            float conduit = band(conduitDist + braid, sh * (0.028 + 0.035 * intensity)) * smoothstep(0.0, 0.2, intensity);
            light += mix(spellMainCol, spellCoreCol, 0.45) * conduit * visibility * 1.45;

            if (lightning == 0) {
                // Organic FBM Nebula Vortex + Orbiting Starlight Motes
                vec2 swirlUV = turn(d * 2.8 - time * (1.8 + intensity * 1.5)) * ep / (sh * 0.28);
                float cloud = fbm(swirlUV + vec2(time * 0.6, -time * 0.4));
                float spiralRibbon = smoothstep(0.32, 0.88, sin(a * 3.0 - d * 14.0 + time * 7.0 + cloud * 3.5)) * exp(-d * 1.45);
                float nebulaAura = pow(cloud, 1.6) * exp(-d * 1.25) * 1.6;
                float palmRing = sharpLine(d - 0.16 * (0.85 + 0.35 * intensity), 0.012) * 1.8 + band(d, 0.08) * 1.5;
                light += (spellMainCol * (spiralRibbon + nebulaAura) * 1.55 + spellCoreCol * palmRing) * intensity * visibility * 1.45;
            } else {
                // Multi-branching Fractal Noise Plasma Arcs
                float arcs = 0.0;
                for (int k = 0; k < 6; k++) {
                    float fk = float(k);
                    float tSlot = floor(time * 14.0) + fk * 11.3;
                    float baseAng = fk * (TAU / 6.0) + time * 0.7;
                    float fbmJitter = (fbm(vec2(d * 6.5, tSlot * 0.37)) - 0.5) * 0.95;
                    float microJitter = sin(d * 48.0 + tSlot * 5.1) * 0.08;
                    float aDiff = abs(mod(a - baseAng + fbmJitter + microJitter + PI, TAU) - PI);
                    arcs += sharpLine(aDiff * d, 0.008 + 0.006 * intensity) * exp(-d * 1.15);
                }
                float palmCore = band(d - 0.10, 0.028) * 2.2 + band(d, 0.07) * 1.7;
                light += (spellMainCol * arcs * 1.8 + spellCoreCol * (arcs * 0.95 + palmCore)) * intensity * visibility * 1.55;
            }
        }

        // Overdrive (110%-150%): Celestial Eclipse Singularity + Reality-Refracting Shockwave
        if (migration > 0.02) {
            float wave = fract(time * 1.05);
            float shockR = r * (0.10 + wave * 1.25);
            float shockBand = band(length(qFore) - shockR, 6.0) * (1.0 - wave) * migration;
            if (quality > 0) {
                vec2 dir = normalize(qFore + vec2(0.001));
                base = mix(base, camera(p + dir * shockBand * sh * 0.055), clamp(migration, 0.0, 1.0));
            }
            float eclipseCore = (1.0 - smoothstep(r * 0.08, r * 0.24, length(qFore))) * migration * clamp(intensity, 0.5, 1.5);
            base *= 1.0 - eclipseCore * 0.88;
            float corona = sharpLine(length(qFore) - r * 0.18, max(2.2, sh * 0.018)) * migration * 2.4;
            light += (spellCoreCol * corona + runeGlowCol * shockBand * 2.2) * visibility;
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

    if (quality > 0) light += min(light, vec3(0.65)) * 0.24;
    vec3 finalLight = light * effect_gain;
    vec3 softLight = vec3(1.0) - exp(-finalLight * 0.72);
    color = vec4(base + (vec3(1.0) - base * 0.72) * softLight, 1.0);
    emission = vec4(max(softLight - vec3(0.36), vec3(0.0)), 1.0);
}
