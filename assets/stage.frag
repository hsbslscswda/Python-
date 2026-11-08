#version 330 core
in vec2 uv;
layout(location = 0) out vec4 frag_color;
layout(location = 1) out vec4 bloom_color;

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
uniform int mode;
uniform int mirrored;
uniform int lightning;
uniform int folded;
uniform float effect_gain;
uniform int quality;
uniform float body_yaw;
uniform float mirror_time;
uniform int mirror_closing;
uniform vec3 cast_direction;
uniform int slash_count;
uniform vec4 slashes[8];
uniform vec2 slash_data[8];
uniform int object_count;
uniform vec4 objects[12];
uniform vec4 object_motion[12];

const float PI = 3.14159265359;
const float TAU = 6.28318530718;

mat2 rot(float a) {
    float c = cos(a), s = sin(a);
    return mat2(c, -s, s, c);
}

vec3 magicColor(vec3 base) {
    vec3 violet = vec3(base.b * 0.86 + base.r * 0.14, base.g * 0.40 + base.r * 0.10, base.b);
    return lightning == 1 ? mix(base, violet, 0.90) : base;
}

float hash21(vec2 p) {
    p = fract(p * vec2(234.34, 435.345));
    p += dot(p, p + 34.23);
    return fract(p.x * p.y);
}

vec2 hash22(vec2 p) {
    float n = hash21(p);
    return vec2(n, hash21(p + n + 19.19));
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(
        mix(hash21(i), hash21(i + vec2(1.0, 0.0)), u.x),
        mix(hash21(i + vec2(0.0, 1.0)), hash21(i + vec2(1.0, 1.0)), u.x),
        u.y
    );
}

float fbm(vec2 p) {
    float v = 0.0;
    float a = 0.5;
    mat2 m = mat2(0.8, -0.6, 0.6, 0.8);
    int octaves = quality == 0 ? 3 : 4;
    for (int i = 0; i < 4; i++) {
        if (i >= octaves) break;
        v += a * noise(p);
        p = m * p * 2.03 + vec2(11.7, 7.3);
        a *= 0.5;
    }
    return v;
}

float ridgedFbm(vec2 p) {
    float v = 0.0;
    float a = 0.5;
    float weight = 1.0;
    mat2 m = mat2(0.8, -0.6, 0.6, 0.8);
    int octaves = quality == 0 ? 3 : 4;
    for (int i = 0; i < 4; i++) {
        if (i >= octaves) break;
        float n = 1.0 - abs(noise(p) * 2.0 - 1.0);
        n = n * n * weight;
        weight = clamp(n * 1.8, 0.0, 1.0);
        v += a * n;
        p = m * p * 2.12 + vec2(5.3, 13.1);
        a *= 0.5;
    }
    return v;
}

float sdSegment(vec2 p, vec2 a, vec2 b) {
    vec2 pa = p - a, ba = b - a;
    float h = clamp(dot(pa, ba) / max(1e-5, dot(ba, ba)), 0.0, 1.0);
    return length(pa - ba * h);
}

float sdRegularPolygon(vec2 p, float r, int n) {
    float an = PI / float(n);
    float bn = mod(atan(p.y, p.x) + an, 2.0 * an) - an;
    vec2 q = length(p) * vec2(cos(bn), abs(sin(bn)));
    return q.x - r * cos(an);
}

float stroke(float d, float w) {
    return 1.0 - smoothstep(w * 0.38, w * 1.05 + 0.0012, abs(d));
}

float runeGlyph(vec2 uv, float seed) {
    vec2 p = uv * 2.0 - 1.0;
    float d = 1e4;
    if (fract(seed * 1.3) > 0.22) d = min(d, sdSegment(p, vec2(0.0, -0.82), vec2(0.0, 0.82)));
    if (fract(seed * 2.7) > 0.30) d = min(d, sdSegment(p, vec2(-0.65, -0.45), vec2(0.65, 0.45)));
    if (fract(seed * 4.1) > 0.30) d = min(d, sdSegment(p, vec2(-0.65, 0.45), vec2(0.65, -0.45)));
    if (fract(seed * 5.9) > 0.40) d = min(d, abs(length(p) - 0.54));
    if (fract(seed * 7.3) > 0.35) d = min(d, abs(abs(p.x) + abs(p.y) - 0.68));
    return 1.0 - smoothstep(0.05, 0.13, d);
}

// 3 Crystal Morphologies with Independent 3D Tilt Foreshortening (大小不一、3D方向不一、形状不一的雪花: 羊齿星芒、扇形晶盘、十二芒星冠)
vec2 sdSnowflake3D(vec2 p, float s, float kind_hash, vec2 tilt_3d) {
    vec2 p_tilted = vec2(p.x / max(0.38, tilt_3d.x), (p.y + p.x * tilt_3d.y * 0.35) / max(1e-4, s));
    p_tilted.x /= max(1e-4, s);
    float r = length(p_tilted);
    if (r > 1.25) return vec2(0.0);

    float a = atan(p_tilted.y, p_tilted.x);
    float body = 0.0;
    float core_ridge = 0.0;

    if (kind_hash < 0.38) {
        // Type A: Stellar Fern Dendrite (六角羊齿分形雪花)
        float sec = PI / 3.0;
        float b = mod(a + sec * 0.5, sec) - sec * 0.5;
        vec2 q = r * vec2(cos(b), abs(sin(b)));
        float d = sdSegment(q, vec2(0.0), vec2(0.98, 0.0)) - 0.028;
        d = min(d, abs(q.x * 0.866025 + q.y * 0.5 - 0.22) - 0.022);
        d = min(d, sdSegment(q - vec2(0.28, 0.0), vec2(0.0), vec2(0.18, 0.22)) - 0.022);
        d = min(d, sdSegment(q - vec2(0.50, 0.0), vec2(0.0), vec2(0.24, 0.28)) - 0.022);
        d = min(d, sdSegment(q - vec2(0.72, 0.0), vec2(0.0), vec2(0.16, 0.19)) - 0.019);
        body = 1.0 - smoothstep(0.0, 0.038, d);
        core_ridge = 1.0 - smoothstep(0.0, 0.016, d + 0.012);
    } else if (kind_hash < 0.72) {
        // Type B: Sectored Hexagonal Crystal Plate (双环扇形晶盘雪花)
        float sec = PI / 3.0;
        float b = mod(a + sec * 0.5, sec) - sec * 0.5;
        vec2 q = r * vec2(cos(b), abs(sin(b)));
        float hex_outer = (q.x * 0.866025 + q.y * 0.5) - 0.62;
        float petal = max(hex_outer, abs(q.y) - 0.16 * (1.1 - q.x * 0.6));
        float inner_ring = abs(q.x * 0.866025 + q.y * 0.5 - 0.34) - 0.032;
        float spine = sdSegment(q, vec2(0.0), vec2(0.92, 0.0)) - 0.026;
        float d = min(min(petal, inner_ring), spine);
        body = (1.0 - smoothstep(0.0, 0.036, d)) * (0.65 + 0.35 * cos(r * 14.0));
        core_ridge = (1.0 - smoothstep(0.0, 0.022, min(inner_ring, spine))) + (1.0 - smoothstep(0.0, 0.18, r));
    } else {
        // Type C: 12-Branched Capped Star Rosette (十二芒星冠冰花)
        float sec = PI / 6.0;
        float b = mod(a + sec * 0.5, sec) - sec * 0.5;
        vec2 q = r * vec2(cos(b), abs(sin(b)));
        float d = sdSegment(q, vec2(0.0), vec2(0.94, 0.0)) - 0.025;
        d = min(d, sdSegment(q - vec2(0.58, 0.0), vec2(0.0), vec2(0.15, 0.16)) - 0.020);
        d = min(d, abs(q.x - 0.86) + abs(q.y) * 1.8 - 0.085);
        d = min(d, abs(r - 0.38) - 0.024);
        body = 1.0 - smoothstep(0.0, 0.036, d);
        core_ridge = 1.0 - smoothstep(0.0, 0.015, d + 0.010);
    }
    return vec2(clamp(body, 0.0, 1.0), clamp(core_ridge, 0.0, 1.0));
}

// 3D Faceted Polygonal Ice Shard (带亮面切面与暗部折射棱的不规则冰渣/冰刃破片)
vec2 sdFacetedIceShard(vec2 p, float s, float angle, float aspect) {
    p = rot(angle) * (p / max(1e-4, s));
    p.x *= aspect;
    float d1 = abs(p.x) * 1.9 + abs(p.y) * 0.75 - 0.52;
    float d2 = abs(p.x - 0.08) * 1.4 + abs(p.y + 0.12) * 1.1 - 0.48;
    float d = max(d1, d2);
    float body = 1.0 - smoothstep(-0.02, 0.04, d);
    float ridge = exp(-abs(p.x * 1.6 - p.y * 0.3) * 18.0) * body;
    float lit_facet = smoothstep(-0.05, 0.05, p.x + p.y * 0.25) * body;
    return vec2(body, clamp(ridge + lit_facet * 0.75, 0.0, 1.0));
}

// Fast Polar-Folded Gothic Astrolabe Plane (Warm Champagne-Platinum & Deep Sapphire, O(1) per-pixel cost!)
vec4 evaluateAstrolabePlane(vec2 q, float px_w, float t, float power, float over) {
    float r = length(q);
    if (r > 1.25) return vec4(0.0);

    float a = atan(q.y, q.x);
    float a_cw = a - t * 0.22;
    float a_ccw = a + t * 0.16;

    float metal = 0.0;
    float rune_glow = 0.0;
    float sapphire_plate = 0.0;

    metal += stroke(r - 1.000, px_w * 2.0);
    metal += stroke(r - 0.962, px_w * 1.05);
    metal += stroke(r - 0.935, px_w * 0.95);
    metal += stroke(r - 0.815, px_w * 1.5);
    metal += stroke(r - 0.780, px_w * 0.95);
    metal += stroke(r - 0.585, px_w * 1.4);
    metal += stroke(r - 0.555, px_w * 0.85);
    metal += stroke(r - 0.365, px_w * 1.25);
    metal += stroke(r - 0.175, px_w * 1.25);

    if (r > 0.935 && r < 1.000) {
        metal += smoothstep(0.94, 0.995, abs(sin(a_cw * 72.0))) * 0.52;
        metal += smoothstep(0.96, 0.999, abs(sin(a_cw * 12.0))) * 0.88;
        sapphire_plate += 0.28;
    }
    if (r > 0.56 && r < 0.80) {
        float arch1 = abs(r - (0.62 + 0.14 * abs(sin(a_ccw * 6.0))));
        float arch2 = abs(r - (0.62 + 0.14 * abs(cos(a_ccw * 6.0))));
        metal += stroke(min(arch1, arch2), px_w * 1.10) * 0.78;
    }
    if (r > 0.82 && r < 0.93) {
        float sec_i = floor((a_cw + PI) / (TAU / 32.0));
        float sec_u = fract((a_cw + PI) / (TAU / 32.0));
        float sec_v = (r - 0.825) / 0.10;
        if (sec_u > 0.12 && sec_u < 0.88 && sec_v > 0.08 && sec_v < 0.92) {
            rune_glow += runeGlyph(vec2(sec_u, sec_v), sec_i + 5.1) * 0.95;
        }
        sapphire_plate += 0.34;
    }
    for (int k = 0; k < 4; k++) {
        vec2 qk = rot(float(k) * PI / 6.0 + t * 0.10 * (k % 2 == 0 ? 1.0 : -1.0)) * q;
        metal += stroke(sdRegularPolygon(qk, 0.780, 3), px_w * 1.20) * 0.82;
    }
    for (int k = 0; k < 2; k++) {
        vec2 qh = rot(float(k) * PI / 3.0 - t * 0.14) * q;
        metal += stroke(sdRegularPolygon(qh, 0.555, 3), px_w * 1.10) * 0.75;
    }
    if (r > 0.175 && r < 0.935) {
        float sp12 = abs(sin(a_ccw * 6.0));
        metal += (1.0 - smoothstep(0.0, px_w * 2.0 / max(r, 0.18), sp12)) * 0.60;
    }
    // O(1) Polar-folded 8-node ice crystal medallions at r = 0.68 (replaces 8-loop per pixel!)
    if (r > 0.59 && r < 0.77) {
        float sec8 = mod(a_cw + PI / 8.0, PI / 4.0) - PI / 8.0;
        vec2 dq = vec2(cos(sec8), sin(sec8)) * r - vec2(0.68, 0.0);
        float mr = length(dq);
        metal += stroke(mr - 0.064, px_w * 1.10) * 0.92;
        if (mr < 0.068) {
            rune_glow += sdSnowflake3D(rot(t * 0.6) * dq, 0.056, 0.2, vec2(1.0, 0.0)).x * 0.95;
        }
    }
    if (over > 0.01) {
        metal += stroke(r - 1.11, px_w * 1.65) * over;
        metal += stroke(sdRegularPolygon(rot(t * 0.25) * q, 1.11, 12), px_w * 1.15) * over * 0.85;
    }

    vec3 deep_sapphire = vec3(0.05, 0.12, 0.28);
    vec3 champagne_gold = vec3(0.94, 0.83, 0.63);
    vec3 platinum_spec = vec3(1.00, 0.97, 0.90);

    float aniso = 0.82 + 0.18 * cos(a_cw * 8.0 - t * 2.4);
    vec3 col = deep_sapphire * (sapphire_plate + clamp(metal, 0.0, 1.0) * 0.45);
    col += champagne_gold * clamp(metal, 0.0, 1.45) * aniso;
    col += platinum_spec * clamp(rune_glow, 0.0, 1.5);

    float alpha = clamp(metal * 0.90 + rune_glow * 0.85 + sapphire_plate * 0.38, 0.0, 1.0);
    return vec4(col, alpha);
}

vec2 map_point(vec2 pt) {
    float scale = min(viewport.x / source_size.x, viewport.y / source_size.y);
    vec2 offset = (viewport - source_size * scale) * 0.5;
    float x = mirrored == 1 ? source_size.x - pt.x : pt.x;
    return offset + vec2(x, pt.y) * scale;
}

vec2 unmap_point(vec2 px) {
    float scale = min(viewport.x / source_size.x, viewport.y / source_size.y);
    vec2 offset = (viewport - source_size * scale) * 0.5;
    vec2 src = (px - offset) / max(1e-4, scale);
    if (mirrored == 1) src.x = source_size.x - src.x;
    return clamp(src / source_size, vec2(0.002), vec2(0.998));
}

void main() {
    vec2 px = uv * viewport;
    float s_scale = min(viewport.x / source_size.x, viewport.y / source_size.y);
    vec2 fitted_size = source_size * s_scale;
    vec2 offset = (viewport - fitted_size) * 0.5;
    vec2 src = (px - offset) / max(1e-4, s_scale);

    if (src.x < 0.0 || src.y < 0.0 || src.x > source_size.x || src.y > source_size.y) {
        frag_color = vec4(0.025, 0.035, 0.055, 1.0);
        bloom_color = vec4(0.0);
        return;
    }

    vec2 cam_uv = vec2(mirrored == 1 ? 1.0 - src.x / source_size.x : src.x / source_size.x, src.y / source_size.y);

    vec2 refract_offset = vec2(0.0);
    if (object_count > 0) {
        for (int i = 0; i < 12; i++) {
            if (i >= object_count) break;
            vec4 o = objects[i];
            vec4 m = object_motion[i];
            int kind = int(m.w + 0.5);
            vec2 c_px = map_point(o.xy);
            float r_px = max(2.0, o.z * s_scale);
            vec2 dp = px - c_px;
            if (kind == 4 && length(dp) < r_px * 1.85) {
                float heat = (1.0 - smoothstep(r_px * 0.2, r_px * 1.85, length(dp))) * o.w;
                refract_offset += vec2(
                    sin(dp.y * 0.11 - time * 13.0 + float(i)) * 0.0032,
                    cos(dp.x * 0.09 - time * 10.0) * 0.0024
                ) * heat;
            }
        }
    }

    vec3 color = texture(camera_tex, clamp(cam_uv + refract_offset, vec2(0.001), vec2(0.999))).rgb;
    vec3 bloom = vec3(0.0);
    float shoulder_px = max(45.0, shoulder * s_scale);

    // ═══════════════════════════════════════════════════════════════════════════
    // MODE 0: ICE MAGIC (冰魔法 — 1: 中心极寒破甲冰枪主炮与裂空冰雷核心 + 2: 环绕三道3D螺旋寒霜龙卷与震波环 + 3: 自阴影体积冰雾 + 大小/3D方向/形状不一的雪花与切面冰渣 + 4: 扇形外围与法阵边缘稀少华美连带反应)
    // ═══════════════════════════════════════════════════════════════════════════
    if (mode == 0 && visibility > 0.01 && radius > 1.0) {
        vec2 base_center_px = map_point(center);
        vec2 palm_px = map_point(palm);
        vec2 chest_px = map_point(chest);
        float R = min(radius * s_scale, viewport.y * 0.44);

        float mir_sign = mirrored == 1 ? -1.0 : 1.0;
        vec2 arm_reach = (palm_px - chest_px) / max(60.0, shoulder_px * 1.45);
        // Bounded frontal torso tracking: faces caster's front direction squarely without flipping to back/side!
        float yaw_angle = clamp(body_yaw * mir_sign * 0.65 + cast_direction.x * mir_sign * 0.25 * migration, -0.36, 0.36);
        float pitch_angle = clamp(cast_direction.y * 0.22 * migration, -0.26, 0.26);

        vec3 n3 = normalize(vec3(
            sin(yaw_angle) * cos(pitch_angle),
            sin(pitch_angle),
            -cos(yaw_angle) * cos(pitch_angle)
        ));

        vec2 plane_offset_px = n3.xy * shoulder_px * mix(0.65, 0.25, migration);
        vec2 array_center_px = base_center_px + plane_offset_px;
        vec2 p = px - array_center_px;

        float tilt_len = length(n3.xy);
        vec2 tilt_dir = tilt_len > 1e-3 ? n3.xy / tilt_len : vec2(1.0, 0.0);
        vec2 perp_dir = vec2(-tilt_dir.y, tilt_dir.x);
        float cos_tilt = max(0.78, abs(n3.z));
        float sin_tilt = sqrt(max(0.0, 1.0 - cos_tilt * cos_tilt));

        float u_scr = dot(p, tilt_dir) / R;
        float v_scr = dot(p, perp_dir) / R;
        float persp_denom = max(0.65, cos_tilt - u_scr * sin_tilt * 0.22);
        float u_plane = u_scr / persp_denom;
        float v_plane = v_scr * (1.0 + (u_plane * sin_tilt) * 0.14);
        vec2 q_front = tilt_dir * u_plane + perp_dir * v_plane;

        vec2 p_back = p + n3.xy * (R * 0.065);
        float u_scr_b = dot(p_back, tilt_dir) / R;
        float v_scr_b = dot(p_back, perp_dir) / R;
        float persp_b = max(0.65, cos_tilt - u_scr_b * sin_tilt * 0.22);
        vec2 q_back = (tilt_dir * (u_scr_b / persp_b) + perp_dir * (v_scr_b * (1.0 + (u_scr_b / persp_b) * sin_tilt * 0.14))) * 1.04;

        float power = clamp(intensity, 0.0, 1.5);
        float over = clamp(intensity - 1.0, 0.0, 0.5) * 2.0;
        float px_w = max(0.0034, 1.50 / max(90.0, R * cos_tilt));

        vec4 front_disk = evaluateAstrolabePlane(q_front, px_w, time, power, over);
        vec4 back_disk = quality >= 1 ? evaluateAstrolabePlane(q_back, px_w * 1.15, -time * 0.8, power, over) : vec4(0.0);

        vec3 array_rgb = back_disk.rgb * (0.42 * (1.0 - front_disk.a * 0.75)) + front_disk.rgb;
        float array_alpha = clamp(front_disk.a + back_disk.a * 0.38, 0.0, 1.0) * visibility;

        // Sympathetic Magic Circle Rim Frost Resonance (法阵旁边的寒霜连带反应!)
        float r_arr = length(q_front);
        if (r_arr > 0.82 && r_arr < 1.38 && power > 0.01) {
            float ang_arr = atan(q_front.y, q_front.x);
            float rim_n = fbm(q_front * 3.5 + vec2(cos(time * 0.6), sin(time * 0.6)));
            float rim_mist = exp(-pow((r_arr - 1.04) / 0.15, 2.0)) * (0.4 + 0.6 * rim_n) * min(1.0, power);
            float rim_wave = stroke(r_arr - (1.12 + 0.05 * sin(ang_arr * 6.0 - time * 2.5)), px_w * 1.2) * min(1.0, power) * 0.65;
            array_rgb += magicColor(vec3(0.35, 0.82, 1.00)) * (rim_mist * 0.65 + rim_wave);
            array_alpha = clamp(array_alpha + (rim_mist * 0.42 + rim_wave * 0.55) * visibility, 0.0, 1.0);
        }

        float metal_peak = max(array_rgb.r, max(array_rgb.g, array_rgb.b));
        vec3 metal_material = array_rgb / (1.0 + metal_peak * 0.45);
        color = mix(color, metal_material, array_alpha * clamp(effect_gain, 0.45, 1.0));
        bloom += array_rgb * visibility * (0.14 + 0.10 * over);

        if (power > 0.01) {
            vec2 raw_aim = palm_px - chest_px;
            vec2 dir_2d = length(raw_aim) > 8.0 ? normalize(raw_aim) : (tilt_len > 0.06 ? tilt_dir : normalize(vec2(mir_sign, -0.18)));
            vec2 ortho_2d = vec2(-dir_2d.y, dir_2d.x);
            vec2 rel = px - array_center_px;
            float u_ax = dot(rel, dir_2d) / R;
            float v_ax = dot(rel, ortho_2d) / R;

            float reach = 2.15 + power * 1.15 + over * 0.65;
            float start_gate = smoothstep(-0.32, 0.05, u_ax);
            float end_gate = 1.0 - smoothstep(reach * 0.65, reach, u_ax);
            float outer_half_w = 0.55 + 0.88 * clamp(u_ax * 0.45, 0.0, 1.0);

            if (u_ax > -0.45 && u_ax < reach + 0.35 && abs(v_ax) < outer_half_w * 1.75) {
                vec2 wind_uv = vec2(u_ax - time * (2.6 + power * 1.2), v_ax);
                vec2 curl = vec2(
                    fbm(wind_uv * 2.2 + vec2(0.0, time * 0.8)) - 0.5,
                    fbm(wind_uv * 2.2 + vec2(5.2, -time * 0.8)) - 0.5
                );

                // ── 1. LETHAL CENTRAL CRYO-SPEAR CANNON & SINGULARITY CORE (中心极具杀伤力的极寒破甲巨枪主炮与裂空冰雷核心!) ──
                float sing_r = length(q_front);
                float sing_ang = atan(q_front.y, q_front.x);
                float spike_burst = pow(abs(cos(sing_ang * 8.0 + time * 2.0)) * 0.6 + abs(sin(sing_ang * 12.0 - time * 3.2)) * 0.4, 2.2);
                float core_spikes = (1.0 - smoothstep(0.04, 0.28 + spike_burst * 0.28, sing_r)) * (0.7 + 0.3 * ridgedFbm(q_front * 8.0 - time * 4.0));
                float core_singularity = exp(-pow(sing_r / 0.19, 2.0) * 2.8);

                float spear_len = 1.65 + 0.55 * power + 0.35 * over;
                float spear_progress = clamp(u_ax / spear_len, 0.0, 1.0);
                float spear_half_w = mix(0.22, 0.008, pow(spear_progress, 0.82)) * (1.0 + 0.18 * sin(u_ax * 14.0 - time * 12.0));
                float spear_mask = (1.0 - smoothstep(spear_half_w * 0.15, spear_half_w, abs(v_ax))) * smoothstep(-0.15, 0.04, u_ax) * (1.0 - smoothstep(spear_len * 0.88, spear_len, u_ax));
                float spear_ridge = exp(-abs(v_ax) / max(0.006, spear_half_w * 0.22)) * spear_mask;
                float barb_wave = ridgedFbm(vec2(u_ax * 4.5 - time * 7.0, abs(v_ax) * 9.0));
                float spear_barbs = pow(clamp(barb_wave, 0.0, 1.0), 2.4) * exp(-abs(v_ax) / max(0.02, spear_half_w * 1.45)) * start_gate * (1.0 - spear_progress);

                float arc1_y = (fbm(vec2(u_ax * 6.5 - time * 14.0, 1.3)) - 0.5) * spear_half_w * 2.2;
                float arc2_y = (fbm(vec2(u_ax * 8.5 + time * 16.0, 7.9)) - 0.5) * spear_half_w * 2.4;
                float cryo_lightning = (exp(-abs(v_ax - arc1_y) * 55.0) + exp(-abs(v_ax - arc2_y) * 65.0)) * start_gate * (1.0 - spear_progress * 0.85);

                float lethal_core_energy = clamp(core_singularity * 1.15 + core_spikes * 1.05 + spear_mask * 0.85 + spear_ridge * 1.25 + spear_barbs * 0.90 + cryo_lightning * 1.20, 0.0, 1.75);

                // ── 2. SURROUNDING COMPANION EFFECTS WRAPPING THE CORE (环绕中心主炮盘旋的三道立体寒霜龙卷与破空冰环!) ──
                float helical_vortex = 0.0;
                for (int h_i = 0; h_i < 3; h_i++) {
                    float fh = float(h_i) * TAU / 3.0;
                    float h_phase = u_ax * 4.2 - time * 5.8 + fh;
                    float h_rad = (0.22 + 0.34 * clamp(u_ax * 0.55, 0.0, 1.0));
                    float h_y = sin(h_phase) * h_rad;
                    float h_z = cos(h_phase);
                    float h_dist = abs(v_ax - h_y + curl.y * 0.08);
                    float h_width = 0.055 * (0.75 + 0.35 * h_z);
                    float stream = exp(-pow(h_dist / h_width, 2.0)) * (0.55 + 0.45 * ridgedFbm(vec2(u_ax * 5.0 - time * 6.0, float(h_i))));
                    helical_vortex += stream * (h_z > 0.0 ? 1.05 : 0.48);
                }
                helical_vortex *= start_gate * end_gate;

                float shockwave_rings = 0.0;
                for (int r_i = 0; r_i < 3; r_i++) {
                    float fr = float(r_i);
                    float ring_u = mod(time * 0.95 + fr * 0.333, 1.0) * (spear_len * 0.88);
                    float ring_r = 0.28 + 0.38 * (ring_u / spear_len);
                    vec2 ring_p = vec2((u_ax - ring_u) / (ring_r * 0.28), v_ax / ring_r);
                    float r_d = abs(length(ring_p) - 1.0);
                    float r_fade = sin(clamp(ring_u / (spear_len * 0.88), 0.0, 1.0) * PI);
                    shockwave_rings += exp(-pow(r_d / 0.08, 2.0)) * r_fade * (0.65 + 0.35 * cos(atan(ring_p.y, ring_p.x) * 8.0));
                }

                // ── 3. SELF-SHADOWED VOLUMETRIC ICE FOG & VARIED 3D SNOWFLAKES / FACETED ICE SHARDS + SYMPATHETIC OUTER MOTES ──
                vec2 fog_p = vec2(u_ax * 1.6 - time * 1.6, v_ax * 1.6) + curl * 0.65;
                float f_puff1 = fbm(fog_p * 1.9);
                float f_puff2 = fbm(fog_p * 4.0 - vec2(time * 1.1, 1.3));
                float f_puff_lit = fbm((fog_p + vec2(0.08, -sign(v_ax) * 0.08)) * 2.8);
                float raw_mist = smoothstep(0.24, 0.82, f_puff1 * 0.60 + f_puff2 * 0.40);
                float flank_profile = exp(-pow(abs(v_ax) / (outer_half_w * 0.96), 2.0) * 1.55) * start_gate * end_gate;
                float mist_density = raw_mist * flank_profile * 0.72;
                float mist_light = clamp((f_puff_lit - f_puff1) * 2.8 + 0.52 + lethal_core_energy * 0.45, 0.0, 1.0);

                // Varied 3D Snowflakes (大小不一、3D方向不一、形状不一的雪花, including sparse sympathetic snowflakes outside main fan!)
                float snow_body = 0.0, snow_spec = 0.0;
                float shard_body = 0.0, shard_spec = 0.0;
                float scales[4] = float[4](1.65, 2.85, 4.65, 7.40);
                float depth_fade[4] = float[4](1.00, 0.84, 0.66, 0.48);
                int max_snow_layers = quality == 0 ? 3 : 4;
                for (int layer = 0; layer < 4; layer++) {
                    if (layer >= max_snow_layers) break;
                    float fl = float(layer);
                    float g_sc = scales[layer];
                    vec2 b_uv = rot(fl * 0.78 - 0.32) * vec2(u_ax, v_ax);
                    vec2 adv = b_uv * g_sc + curl * (0.38 + fl * 0.15) - vec2(time * (2.0 + fl * 0.95), sin(time * 0.9 + fl) * 0.3);
                    vec2 cid = floor(adv);
                    vec2 cuv = fract(adv) - 0.5;
                    vec2 rnd = hash22(cid + vec2(fl * 29.3, fl * 47.1));
                    float kind_h = hash21(cid + vec2(91.7, fl * 13.3));
                    // Inside main fan: dense blizzard; outside main fan (up to 1.68 * outer_half_w): sparse sympathetic snowflakes!
                    bool in_main_fan = abs(v_ax) < outer_half_w * (0.65 + 0.55 * rnd.y);
                    bool in_sympathetic_outer = abs(v_ax) < outer_half_w * 1.68 && rnd.x > 0.78;
                    if ((rnd.x > 0.30 && in_main_fan) || in_sympathetic_outer) {
                        vec2 loc = cuv - (rnd - 0.5) * 0.28;
                        float loc_r = length(loc);
                        if (loc_r < 0.46) {
                            float guard = 1.0 - smoothstep(0.30, 0.46, loc_r);
                            float spin = time * (1.6 + fl * 0.8) * (rnd.y > 0.5 ? 1.0 : -1.0) + rnd.x * TAU;
                            float tilt_cos = 0.42 + 0.58 * abs(cos(time * 1.6 + rnd.x * 19.0 + fl));
                            float tilt_shear = 0.65 * sin(time * 1.3 + rnd.y * 23.0);
                            float sz = mix(0.15, 0.32, pow(rnd.y, 1.35));
                            vec2 sf = sdSnowflake3D(rot(spin) * loc, sz, kind_h, vec2(tilt_cos, tilt_shear)) * guard;
                            float dw = depth_fade[layer] * start_gate * end_gate * (in_main_fan ? 1.0 : 0.78);
                            snow_body = max(snow_body, sf.x * dw);
                            snow_spec = max(snow_spec, sf.y * dw);
                        }
                    }
                }

                // 3 Layers of Flying 3D Faceted Ice Shards / Splinters (切面冰渣飞舞)
                float shard_scales[3] = float[3](2.6, 4.6, 7.8);
                int max_shard_layers = quality == 0 ? 2 : 3;
                for (int sl = 0; sl < 3; sl++) {
                    if (sl >= max_shard_layers) break;
                    float fsl = float(sl);
                    float s_sc = shard_scales[sl];
                    vec2 sb = rot(-0.48 + fsl * 0.92) * vec2(u_ax, v_ax);
                    vec2 s_adv = sb * s_sc + curl * 0.55 - vec2(time * (4.2 + fsl * 1.8), 0.0);
                    vec2 sid = floor(s_adv);
                    vec2 suv = fract(s_adv) - 0.5;
                    vec2 srnd = hash22(sid + vec2(73.1 + fsl * 31.0, 19.7));
                    bool shard_in_fan = abs(v_ax) < outer_half_w * 1.15 && srnd.x > 0.24;
                    bool shard_sympathetic = abs(v_ax) < outer_half_w * 1.62 && srnd.x > 0.82;
                    if (shard_in_fan || shard_sympathetic) {
                        vec2 sloc = suv - (srnd - 0.5) * 0.30;
                        float sloc_r = length(sloc);
                        if (sloc_r < 0.45) {
                            float sguard = 1.0 - smoothstep(0.28, 0.45, sloc_r);
                            float s_ang = (srnd.y - 0.5) * 0.75 + curl.y * 0.4;
                            float s_sz = mix(0.15, 0.30, srnd.y);
                            float s_aspect = mix(0.45, 1.15, fract(srnd.x * 7.3));
                            vec2 sh = sdFacetedIceShard(sloc, s_sz, s_ang, s_aspect) * sguard;
                            float sw = (0.98 - fsl * 0.20) * start_gate * end_gate * (shard_in_fan ? 1.0 : 0.75);
                            shard_body = max(shard_body, sh.x * sw);
                            shard_spec = max(shard_spec, sh.y * sw);
                        }
                    }
                }

                float gain_m = clamp(0.60 + 0.52 * power + 0.28 * over, 0.0, 1.50) * visibility * clamp(effect_gain, 0.45, 1.30);

                // Composite Layer A: Deep Self-Shadowed Volumetric Cryo-Fog
                vec3 mist_dark = magicColor(vec3(0.06, 0.18, 0.38));
                vec3 mist_mid = magicColor(vec3(0.28, 0.62, 0.88));
                vec3 mist_bright = magicColor(vec3(0.76, 0.92, 1.00));
                vec3 mist_col = mix(mist_dark, mist_mid, smoothstep(0.0, 0.6, mist_light));
                mist_col = mix(mist_col, mist_bright, smoothstep(0.55, 1.0, mist_light));
                color = mix(color, mist_col, clamp(mist_density * gain_m, 0.0, 0.68));

                // Composite Layer B: Surrounding Helical Vortex Ribbons, Shockwave Rings & Shrapnel Snowflakes
                float crystal_shadow = clamp(snow_body + shard_body, 0.0, 1.0);
                color = mix(color, vec3(0.05, 0.22, 0.46), crystal_shadow * 0.45);
                vec3 surround_rgb = vec3(0.12, 0.64, 0.96) * (helical_vortex * 0.85 + shockwave_rings * 0.75 + snow_body * 0.65 + shard_body * 0.75)
                                  + vec3(0.84, 0.96, 1.00) * (helical_vortex * 0.55 + shockwave_rings * 0.65 + snow_spec * 0.95 + shard_spec * 1.10);
                surround_rgb = magicColor(surround_rgb);
                float surround_peak = max(surround_rgb.r, max(surround_rgb.g, surround_rgb.b));
                color = mix(color, surround_rgb / (1.0 + surround_peak * 0.40),
                            clamp(surround_peak * gain_m * 0.65, 0.0, 0.82));

                // Composite Layer C (DOMINANT LETHAL CENTERPIECE): Giant Faceted Ice-Lance Cannon, Singularity Spikes & Cryo-Lightning!
                color = mix(color, vec3(0.04, 0.20, 0.48), clamp(spear_mask * 0.55, 0.0, 0.55));
                vec3 core_rgb = vec3(0.22, 0.82, 1.00) * (lethal_core_energy * 0.75)
                              + vec3(0.98, 1.00, 1.00) * pow(clamp(lethal_core_energy, 0.0, 1.5), 1.35) * 1.15;
                core_rgb = magicColor(core_rgb);
                float core_peak = max(core_rgb.r, max(core_rgb.g, core_rgb.b));
                vec3 core_material = core_rgb / (1.0 + core_peak * 0.55);
                color = mix(color, core_material, clamp(lethal_core_energy * gain_m * 0.58, 0.0, 0.90));
                bloom += (core_material * 0.20 + surround_rgb * 0.12) * gain_m;
            }
        }
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // MODE 2: MIRROR SPELL (镜界术 — 1px 精雕切角八角铂金蓝宝魔镜，彻底去除彩虹色与中心怪异线条!)
    // ═══════════════════════════════════════════════════════════════════════════
    if (mode == 2 && visibility > 0.001) {
        vec2 c_px = map_point(center);
        float r_px = max(0.001, radius * s_scale);
        // Restore the v0.4.2 display-to-source transform before folding/reflection.
        vec2 display_axis = vec2(mirrored == 1 ? -1.0 : 1.0, 1.0);
        vec2 local = rot(mirror_angle) * ((px - c_px) * display_axis);
        vec2 q = vec2(local.x / r_px, local.y / (r_px * 0.68));
        vec2 aq = abs(q);
        float sdf = max(max(aq.x - 1.0, aq.y - 1.0), (aq.x + aq.y - 1.68) * 0.70710678);

        if (sdf < 0.08) {
            float inside = 1.0 - smoothstep(-0.008, 0.008, sdf);
            if (inside > 0.001) {
                vec2 u_v = q * 0.5 + 0.5;
                float facet = 0.0;
                float mt = mod(mirror_time, 4096.0);
                if (folded == 1) {
                    vec2 k = q * 0.88;
                    float len = length(k);
                    float sector = PI / 6.0;
                    float a_raw = atan(k.y, k.x) + mt * 0.18;
                    float local_a = mod(a_raw, 2.0 * sector) - sector;
                    facet += smoothstep(0.76, 0.96, len) * (0.5 + 0.5 * cos(local_a * 6.0)) * 0.18;
                    u_v = clamp(vec2(cos(abs(local_a)), sin(abs(local_a))) * len * 0.72 + 0.5, 0.02, 0.98);
                }

                float bevel = smoothstep(-0.12, -0.008, sdf) * (1.0 - smoothstep(-0.008, 0.012, sdf));
                float q_norm = length(q + vec2(1e-4));
                vec2 n_dir = (q + vec2(1e-4)) / q_norm;

                float r_src = max(4.0, radius);
                vec3 factors = vec3(0.45, 0.15, -0.35);
                vec3 reflected;
                for (int ch = 0; ch < 3; ++ch) {
                    float f_ch = (ch == 0) ? factors.x : ((ch == 1) ? factors.y : factors.z);
                    vec2 s_px = center + (u_v - 0.5 + n_dir * bevel * 0.014 * f_ch) * vec2(r_src * 2.0, r_src * 2.0 * 0.68);
                    s_px = clamp(s_px, source_size * 0.002, source_size * 0.998);
                    vec2 s_uv = s_px / source_size;
                    float val = texture(camera_tex, s_uv)[ch];
                    if (ch == 0) reflected.r = val;
                    else if (ch == 1) reflected.g = val;
                    else reflected.b = val;
                }

                reflected = reflected * vec3(0.86, 0.93, 1.05) + vec3(0.015, 0.032, 0.065);
                float vig = smoothstep(0.32, 0.98, q_norm);
                reflected *= 1.0 - vig * 0.22;

                float phase = atan(q.y, q.x) * 24.0 + mt * 0.4;
                float astral_etch = smoothstep(0.45, 0.95, 0.5 + 0.5 * cos(phase)) * bevel;
                float sweep_pos = q.x * 0.65 + q.y * 0.75 - sin(mt * 0.7) * 0.35;
                float sweep = exp(-pow(sweep_pos * 5.2, 2.0)) * 0.15 + exp(-pow((sweep_pos - 0.16) * 14.0, 2.0)) * 0.22;

                reflected += astral_etch * vec3(0.88, 0.78, 0.58) * 0.32;
                reflected += (sweep + bevel * 0.22) * vec3(0.78, 0.88, 0.98);
                reflected += facet * vec3(0.82, 0.92, 1.00);
                reflected = clamp(reflected, 0.0, 1.0);

                color = mix(color, reflected, inside * visibility);
            }

            float outer_rim = stroke(sdf, 0.010);
            float inner_rim = stroke(sdf + 0.040, 0.007);
            float bevel_rim = stroke(sdf + 0.105, 0.0045);
            float inlay_band = smoothstep(-0.040, -0.002, sdf) * (1.0 - smoothstep(-0.002, 0.010, sdf));
            float scroll_pat = smoothstep(0.2, 0.85, sin(atan(q.y, q.x) * 36.0) * cos((sdf + 0.021) * 140.0)) * inlay_band;

            vec2 corners[8] = vec2[8](
                vec2(-0.68, -1.0), vec2(0.68, -1.0), vec2(1.0, -0.68), vec2(1.0, 0.68),
                vec2(0.68, 1.0), vec2(-0.68, 1.0), vec2(-1.0, 0.68), vec2(-1.0, -0.68)
            );
            float corner_gems = 0.0;
            for (int i = 0; i < 8; ++i) {
                vec2 dv = abs(q - corners[i]);
                float star_d = min(dv.x + dv.y * 2.8, dv.y + dv.x * 2.8);
                corner_gems += 1.0 - smoothstep(0.005, 0.050, star_d);
            }

            vec3 frame_col =
                vec3(0.05, 0.12, 0.28) * inlay_band * 0.85 +
                vec3(0.95, 0.84, 0.62) * (outer_rim + inner_rim * 0.90 + bevel_rim * 0.65 + scroll_pat * 0.75) +
                vec3(0.90, 0.98, 1.00) * corner_gems * 1.25;

            // Explicit closing state fades the rim as the clean interior dissolves.
            frame_col *= mirror_closing == 1 ? visibility : 1.0;
            color = mix(color, color * 0.4, inlay_band * visibility * 0.65);
            color += frame_col * visibility * clamp(effect_gain, 0.45, 1.30);
            bloom += frame_col * visibility * 0.18;
        }
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // EFFECT OBJECTS:
    // KIND 1, 2: PHOTOREALISTIC LIQUID WATER ORB + ORBITING 3D TIDAL RIBBONS + INERTIAL DEFORMATION
    // KIND 3: WATER SPLASH & DROPLET BURST
    // KIND 4: REALISTIC 3D VOLUMETRIC ROLLING FIREBALL + SPIRAL VORTEX PLUME & DARK SOOT CONTRAST
    // ═══════════════════════════════════════════════════════════════════════════
    if (object_count > 0) {
        for (int i = 0; i < 12; i++) {
            if (i >= object_count) break;
            vec4 o = objects[i];
            vec4 m = object_motion[i];
            int kind = int(m.w + 0.5);
            vec2 c = map_point(o.xy);
            float r = max(2.0, o.z * s_scale);
            vec2 p = px - c;

            if (kind == 1 || kind == 2) {
                vec2 obj_vel = m.xy;
                if (mirrored == 1) obj_vel.x = -obj_vel.x;
                float speed = length(obj_vel);
                vec2 v_dir = (speed > 4.0) ? (obj_vel / speed) : vec2(1.0, 0.0);
                vec2 v_ort = vec2(-v_dir.y, v_dir.x);
                float stretch = clamp(speed / 620.0, 0.0, 0.28);

                vec2 u_raw = p / r;
                float proj_par = dot(u_raw, v_dir);
                float proj_perp = dot(u_raw, v_ort);
                vec2 u = v_dir * (proj_par / (1.0 + stretch * (proj_par < 0.0 ? 1.2 : 0.65)))
                       + v_ort * (proj_perp * sqrt(1.0 + stretch * 0.75));

                float u_len = length(u);
                float ang = atan(u.y, u.x);

                // 3D Orbiting Refractive Tidal Water Ribbons (两道 3D 环绕潮汐水绸带!)
                if (u_len < 1.60) {
                    for (int rib = 0; rib < 2; rib++) {
                        float fr = float(rib);
                        vec2 u_rot = rot(0.48 * (rib == 0 ? 1.0 : -1.0) + sin(time * 0.7 + fr) * 0.15) * u;
                        vec2 ell = vec2(u_rot.x / 1.28, u_rot.y / 0.44);
                        float er = length(ell);
                        float ea = atan(ell.y, ell.x) + time * (2.2 + fr * 0.6) * (rib == 0 ? 1.0 : -1.0);
                        bool in_front = (rib == 0 ? u_rot.y > 0.0 : u_rot.y < 0.0);
                        if (in_front || u_len > 0.98) {
                            float rib_w = 0.045 * (0.5 + 0.5 * sin(ea * 2.0));
                            float rib_d = abs(er - 1.0);
                            if (rib_d < rib_w) {
                                float nz_rib = sqrt(max(0.0, 1.0 - (rib_d / rib_w) * (rib_d / rib_w)));
                                vec2 r_uv = clamp(cam_uv - normalize(u_rot + 1e-4) * 0.018 * nz_rib, vec2(0.002), vec2(0.998));
                                vec3 r_bg = texture(camera_tex, r_uv).rgb;
                                float r_spec = pow(nz_rib, 16.0);
                                float r_fres = pow(1.0 - nz_rib, 2.5);
                                vec3 rib_col = r_bg * vec3(0.88, 0.98, 1.04) + vec3(0.55, 0.90, 1.0) * r_fres * 0.7 + vec3(1.0) * r_spec * 0.95;
                                color = mix(color, rib_col, (1.0 - smoothstep(rib_w * 0.2, rib_w, rib_d)) * o.w * (in_front ? 0.85 : 0.45));
                            }
                        }
                    }
                }

                float slosh = 0.026 * sin(ang * 3.0 - time * 4.0 + m.z)
                            + 0.016 * cos(ang * 5.0 + time * 5.8)
                            + 0.009 * sin(ang * 8.0 - time * 7.5);
                vec2 u_liq = u * (1.0 - slosh);
                float d2 = dot(u_liq, u_liq);

                if (d2 < 1.0) {
                    float z = sqrt(max(0.0, 1.0 - d2));
                    vec2 wp = u_liq * 2.2 + vec2(time * 1.2, -time * 0.95);
                    float h0 = fbm(wp);
                    float hx = fbm(wp + vec2(0.07, 0.0)) - h0;
                    float hy = fbm(wp + vec2(0.0, 0.07)) - h0;
                    vec3 N = normalize(vec3(u_liq.x + hx * 1.85, u_liq.y + hy * 1.85, z));

                    vec3 R_vec = refract(vec3(0.0, 0.0, -1.0), N, 1.0 / 1.333);
                    vec2 refr_uv = clamp(cam_uv + R_vec.xy * (0.092 * (1.0 - z * 0.28)), vec2(0.002), vec2(0.998));
                    vec3 refracted_bg = vec3(
                        texture(camera_tex, clamp(refr_uv + N.xy * 0.003 * (1.0 - z), vec2(0.002), vec2(0.998))).r,
                        texture(camera_tex, refr_uv).g,
                        texture(camera_tex, clamp(refr_uv - N.xy * 0.003 * (1.0 - z), vec2(0.002), vec2(0.998))).b
                    );

                    float focus_grad = clamp(dot(u_liq, normalize(vec2(0.55, 0.60))) * 0.65 + 0.35, 0.0, 1.0);
                    vec3 absorption = exp(-vec3(0.26, 0.045, 0.01) * (1.0 - z * 0.65) * 1.2);
                    vec3 clear_water = refracted_bg * absorption + vec3(0.04, 0.22, 0.34) * pow(focus_grad, 2.2) * z;

                    float c_flow = sin(u_liq.x * 7.5 + u_liq.y * 5.5 + h0 * 5.0 - time * 2.8) * cos(u_liq.x * 5.0 - u_liq.y * 8.0 + time * 2.2);
                    float smooth_caustic = pow(smoothstep(0.35, 0.95, c_flow * 0.5 + 0.5), 3.0) * z * (0.4 + 0.6 * focus_grad);
                    float tir_crescent = pow(max(0.0, dot(N, normalize(vec3(0.55, 0.62, 0.56)))), 11.0) * pow(1.0 - z, 1.3);

                    float fresnel = 0.02 + 0.98 * pow(1.0 - max(0.0, N.z), 4.4);
                    vec2 ref_uv = N.xy - vec2(-0.38, -0.44);
                    vec2 win_p = rot(-0.52) * ref_uv;
                    float win_box = max(abs(win_p.x) - 0.16, abs(win_p.y) - 0.095);
                    float win_pane = (1.0 - smoothstep(-0.012, 0.025, win_box)) * smoothstep(0.004, 0.018, abs(win_p.x)) * smoothstep(0.004, 0.016, abs(win_p.y));
                    vec3 H_sun = normalize(vec3(-0.42, -0.48, 1.75));
                    float spec_pin = pow(max(0.0, dot(N, H_sun)), 220.0);

                    float pearl_bubbles = 0.0;
                    for (int b_i = 0; b_i < 4; b_i++) {
                        float fb = float(b_i);
                        float by = 0.55 - mod(time * (0.35 + fb * 0.08) + fb * 0.37, 1.10);
                        float bx = sin(time * 1.8 + fb * 2.4) * 0.28 + (fb - 1.5) * 0.15;
                        vec2 bp = u_liq - vec2(bx, by);
                        float br = 0.032 + 0.012 * sin(fb * 3.1);
                        float bd = length(bp);
                        if (bd < br && d2 < 0.72) {
                            float bz = sqrt(max(0.0, 1.0 - (bd / br) * (bd / br)));
                            pearl_bubbles += pow(1.0 - bz, 2.2) * 0.75 + (1.0 - smoothstep(0.0, br * 0.45, length(bp + vec2(br * 0.3, br * 0.3)))) * 1.35;
                        }
                    }

                    vec3 water_rgb = clear_water
                                   + vec3(0.42, 0.88, 1.00) * (smooth_caustic * 0.42 + tir_crescent * 0.82)
                                   + vec3(0.80, 0.95, 1.00) * fresnel * 0.96
                                   + vec3(0.98, 1.00, 1.00) * (win_pane * 0.92 + spec_pin * 1.50 + pearl_bubbles);

                    float edge_aa = (1.0 - smoothstep(0.935, 1.0, d2)) * o.w;
                    color = mix(color, water_rgb, edge_aa);
                    bloom += (vec3(0.65, 0.92, 1.0) * (fresnel * 0.32 + tir_crescent * 0.40) + vec3(1.0) * (win_pane * 0.55 + spec_pin)) * edge_aa;
                }
            }
            else if (kind == 3) {
                float age = m.z;
                float fade = clamp(1.0 - age / 1.05, 0.0, 1.0);
                vec2 u = p / r;
                float dist = length(u);
                float mist_r = 0.30 + age * 1.90;
                float mist_ring = exp(-pow((dist - mist_r) * 3.4, 2.0)) * fbm(u * 4.0 + time * 2.2) * fade;
                float splash_spec = 0.0, splash_body = 0.0;
                for (int k = 0; k < 28; k++) {
                    float fk = float(k);
                    float a = fk * 2.39996 + o.w;
                    float spd = 0.80 + 1.05 * fract(sin(fk * 43.17) * 197.3);
                    vec2 pos = vec2(cos(a), sin(a)) * (0.15 + age * spd * 1.70) + vec2(0.0, age * age * 1.10);
                    float dr = mix(0.032, 0.082, fract(fk * 0.37)) * fade;
                    float d_drop = length(u - pos);
                    if (d_drop < dr) {
                        float dz = sqrt(max(0.0, 1.0 - (d_drop / dr) * (d_drop / dr)));
                        splash_body += 0.45 + 0.55 * (1.0 - dz);
                        splash_spec += pow(dz, 8.0);
                    }
                }
                vec3 sp_col = vec3(0.68, 0.92, 1.00) * (mist_ring * 0.65 + splash_body * 0.75) + vec3(1.0) * splash_spec * 1.25;
                color += sp_col * fade * clamp(effect_gain, 0.45, 1.30);
                bloom += sp_col * fade * 0.35;
            }
            // ── KIND 4: REALISTIC 3D VOLUMETRIC ROLLING FIREBALL + SPIRAL VORTEX PLUME & DARK SOOT CONTRAST ──
            else if (kind == 4) {
                vec2 obj_vel = m.xy;
                if (mirrored == 1) obj_vel.x = -obj_vel.x;
                float shear_x = clamp(-obj_vel.x / 420.0, -0.45, 0.45);

                vec2 u = vec2(p.x / r, (p.y + r * 0.42) / (r * 1.55));
                if (abs(u.x) < 1.45 && u.y > -1.15 && u.y < 0.85) {
                    float raw_h = (0.52 - u.y) / 1.48;
                    float h = clamp(raw_h, 0.0, 1.0);
                    float phase_seed = m.z * 3.7;
                    u.x -= shear_x * pow(h, 1.25) * 0.55;

                    // Upward swirling fluid domain warp (genuine rolling Kelvin-Helmholtz billows!)
                    vec2 flow_p = vec2(u.x * 2.2, u.y * 2.2 + time * 4.8 + phase_seed);
                    vec2 warp1 = vec2(
                        fbm(flow_p * 1.3 + vec2(0.0, time * 1.5)) - 0.5,
                        fbm(flow_p * 1.3 + vec2(4.7, -time * 1.5)) - 0.5
                    );
                    vec2 warp2 = vec2(
                        fbm((flow_p + warp1 * 0.85) * 2.6 - vec2(time * 2.2, 0.0)) - 0.5,
                        fbm((flow_p + warp1 * 0.85) * 2.6 + vec2(0.0, time * 2.2)) - 0.5
                    );
                    vec2 p_warped = u + warp1 * (0.28 + 0.42 * h) + warp2 * (0.14 + 0.25 * h);

                    // Rounded 3D Fireball Base + Spiraling Upward Plume Envelope (NO flat bottom cut!)
                    vec2 orb_center = vec2(0.0, 0.16);
                    float d_orb = length((p_warped - orb_center) / vec2(0.58, 0.48));
                    float sway_plume = sin(h * 4.5 - time * 5.5 + phase_seed) * 0.16 * pow(h, 1.2);
                    float plume_w = mix(0.56, 0.06, pow(h, 1.15));
                    float d_plume = length(vec2((p_warped.x - sway_plume) / max(0.06, plume_w), max(0.0, abs(raw_h - 0.48) - 0.32) / 0.28));
                    d_plume += (1.0 - smoothstep(-0.03, 0.12, raw_h)) * 1.4;
                    float vessel_d = min(d_orb, d_plume);

                    float billow = fbm(flow_p * 1.8 + warp1 * 1.4);
                    float sharp_sheet = ridgedFbm(flow_p * 2.4 + warp2 * 1.6);
                    float dark_soot_turbulence = fbm(flow_p * 3.2 - warp1 * 1.8 + vec2(2.3, -time * 3.5));

                    // Turbulent Helical Fire-Dragon Vortex Streams wrapping around the fireball
                    float spiral_tongues = 0.0;
                    for (int st = 0; st < 2; st++) {
                        float fst = float(st) * PI;
                        float s_x = sin(h * 6.2 - time * 6.5 + fst + phase_seed) * mix(0.54, 0.12, h);
                        float s_d = abs(p_warped.x - s_x);
                        float s_w = mix(0.18, 0.04, h) * (0.6 + 0.6 * billow);
                        spiral_tongues += exp(-pow(s_d / max(0.03, s_w), 2.0)) * smoothstep(0.02, 0.20, h) * (1.0 - smoothstep(0.75, 0.98, h));
                    }

                    float radial_contain = 1.0 - smoothstep(0.55, 1.32, vessel_d);
                    float raw_density = clamp((1.15 - vessel_d * 0.85) * 0.72 + sharp_sheet * 0.48 + billow * 0.35 + spiral_tongues * 0.55, 0.0, 1.6) * radial_contain;

                    // Carve dark, rolling smoke/soot pockets into the outer & upper flame billows for photorealistic 3D depth!
                    float soot_carve = smoothstep(0.42, 0.82, dark_soot_turbulence) * smoothstep(0.35, 0.95, vessel_d) * (0.35 + 0.65 * h);
                    float temp = clamp(raw_density - soot_carve * 0.52, 0.0, 1.45);
                    float soot_smoke = clamp(raw_density * soot_carve * 1.35, 0.0, 0.85);

                    float sparks = 0.0;
                    if (vessel_d < 1.38) {
                        for (int e_i = 0; e_i < 2; e_i++) {
                            float fe = float(e_i);
                            vec2 s_uv = vec2(
                                u.x * (5.5 + fe * 2.5) + warp1.x * 2.2,
                                u.y * (4.5 + fe * 2.0) + time * (6.8 + fe * 2.6) + phase_seed
                            );
                            vec2 sid = floor(s_uv);
                            vec2 sf = fract(s_uv) - 0.5;
                            vec2 srnd = hash22(sid + vec2(47.1 + fe * 23.0, 89.3));
                            if (srnd.x > 0.56) {
                                vec2 sj = (srnd - 0.5) * 0.40;
                                vec2 sd = rot(warp1.x * 0.8) * (sf - sj) * vec2(1.6, 0.62);
                                sparks += (1.0 - smoothstep(0.012, 0.11, length(sd))) * (1.0 - smoothstep(0.65, 1.38, vessel_d));
                            }
                        }
                    }

                    if (temp > 0.02 || soot_smoke > 0.03 || sparks > 0.01) {
                        vec3 c_soot = vec3(0.06, 0.02, 0.02);
                        vec3 c_crimson = vec3(0.68, 0.05, 0.01);
                        vec3 c_vermilion = vec3(0.98, 0.26, 0.01);
                        vec3 c_gold = vec3(1.00, 0.72, 0.10);
                        vec3 c_white_core = vec3(1.00, 0.99, 0.92);

                        vec3 fire_rgb = mix(c_soot, c_crimson, smoothstep(0.02, 0.28, temp));
                        fire_rgb = mix(fire_rgb, c_vermilion, smoothstep(0.24, 0.54, temp));
                        fire_rgb = mix(fire_rgb, c_gold, smoothstep(0.50, 0.82, temp));
                        fire_rgb = mix(fire_rgb, c_white_core, smoothstep(0.78, 1.20, temp));

                        fire_rgb = mix(fire_rgb, c_soot, clamp(soot_smoke * (1.0 - smoothstep(0.55, 0.95, temp)), 0.0, 0.72));
                        fire_rgb += vec3(1.0, 0.82, 0.32) * sparks * 1.50;

                        float bounds_fade = (1.0 - smoothstep(1.20, 1.45, abs(u.x)))
                                          * smoothstep(-1.15, -0.95, u.y)
                                          * (1.0 - smoothstep(0.65, 0.85, u.y));
                        float alpha = clamp(smoothstep(0.02, 0.22, temp + soot_smoke * 0.5) * 0.95 + sparks, 0.0, 1.0) * o.w * bounds_fade;
                        float gain_f = clamp(effect_gain, 0.45, 1.30);
                        color = mix(color, color * 0.28, alpha * 0.68);
                        color += fire_rgb * alpha * gain_f;
                        bloom += (fire_rgb * smoothstep(0.45, 1.15, temp) * 0.50 + vec3(1.0, 0.72, 0.22) * sparks * 0.65) * o.w * gain_f * bounds_fade;
                    }
                }
            }
        }
    }

    for (int i = 0; i < 8; i++) {
        if (i >= slash_count) break;
        vec4 s = slashes[i];
        vec2 info = slash_data[i];
        float age = info.x;
        float fade = clamp(1.0 - age / 0.80, 0.0, 1.0);
        vec2 a = map_point(s.xy);
        vec2 b = map_point(s.zw);
        vec2 ba = b - a;
        vec2 pa = px - a;
        float t = clamp(dot(pa, ba) / max(1.0, dot(ba, ba)), 0.0, 1.0);
        vec2 normal = normalize(vec2(-ba.y, ba.x));
        float arc = sin(t * PI) * max(16.0, length(ba) * 0.08);
        vec2 curve = a + ba * t + normal * arc;
        float d = length(px - curve);
        float w = (8.0 + info.y * 10.0) * sin(t * PI);
        float blade = (exp(-d / max(2.0, w * 0.32)) + 0.35 * exp(-d / max(8.0, w * 1.4))) * fade;
        vec3 slash_col = vec3(0.62, 0.88, 1.0) * blade;
        color += slash_col * clamp(effect_gain, 0.35, 1.2);
        bloom += slash_col * 0.20;
    }

    frag_color = vec4(clamp(color, 0.0, 1.0), 1.0);
    bloom_color = vec4(clamp(bloom, 0.0, 1.0), 1.0);
}
