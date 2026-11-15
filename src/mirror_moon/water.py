"""Owner-session water magic with palm-normal attachment and ray/palm resizing.

Inter-hand translation and centimeter scale are monocular estimates.
"""
import math
from dataclasses import dataclass, replace
from .config import DEFAULTS
from .domain import EffectObject, Shape, SpellView
from .geometry import Hold, arm_lowered, fingertip_polygon, open_over_90


def fresh(a):
    return a.hand_valid and a.shape_age <= DEFAULTS.gesture_max_age


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def sub(a, b):
    return tuple(x-y for x, y in zip(a, b))


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


@dataclass
class Shot:
    position: list
    velocity: list
    radius: float
    born: float
    seed: int


class Water:
    def __init__(self, cfg=DEFAULTS):
        self.cfg, self.hold = cfg, Hold()
        self.enabled = self.has_orb = self.scaling = False
        self.fist_started = {}
        self.owner = None
        self.support = None
        self.magic_running = False
        self.session_depth = None
        self.ray_origin = None
        self.owner_palm = None
        self.ray_direction = None
        self.position = [0.0, 0.0, 2.0]
        self.radius = 0.075
        self.display_radius = 48.0
        self.shots, self.splashes = [], []
        self.last_t = None
        self.seed = 0
        self.opened = False
        self.first_fist_released = False
        self.resize_span = None
        self.resize_radius = self.radius
        self.normal_last_t = None
        self.normal_pending = None
        self.normal_pending_since = None
        self.last_hand_time = -1e9
        self.palm_wrist_offset = (0.0,0.0)
        self.resize_ray_t = None
        self.resize_hit = None
        self.support_palm = None
        self.intersection_status = 'unknown'
        self.opened_at = 0.0
        self.tracking_status = '等待手部'


    @staticmethod
    def camera(f):
        return f.width * 0.9

    def project(self, p, f):
        k = self.camera(f) / max(0.18, p[2])
        return (f.width/2 + p[0]*k, f.height/2 + p[1]*k), k

    def palm_origin(self, a, f):
        focal = self.camera(f)
        if self.session_depth is None:
            z = focal*0.40/max(50.0, f.scale) if f.valid else focal*0.08/max(15.0, a.palm_scale)
            self.session_depth = max(0.4, min(6.0, z))
        z = self.session_depth
        palm = a.palm or a.wrist
        return ((palm[0]-f.width/2)*z/focal, (palm[1]-f.height/2)*z/focal, z)

    def observed_normal(self, a):
        if a.palm_normal_quality is None:
            return a.normal  # Explicit synthetic fixtures / legacy recordings.
        return a.palm_normal if a.palm_normal_quality >= 0.2 else None

    def update_ray(self, a, f):
        self.ray_origin = self.palm_origin(a, f)
        normal=self.observed_normal(a)
        if normal is None:
            self.normal_pending=self.normal_pending_since=None
            return False
        length=math.sqrt(dot(normal,normal))
        if not math.isfinite(length) or length<1e-6:
            return False
        normal=tuple(v/length for v in normal)
        # Direct attachment: accept the current measured palm direction now.
        self.ray_direction=normal
        self.normal_pending=self.normal_pending_since=None
        return True

    def target(self, a, f):
        # The caller has already updated the observed ray once this frame.
        # Solve r = screen_radius * center_depth / focal, keeping the visible
        # radius invariant while the palm normal rotates. Surface gap is 0.08m.
        n, origin = self.ray_direction, self.ray_origin
        r = self.display_radius*(origin[2]+n[2]*0.08)/(self.camera(f)-self.display_radius*n[2])
        self.radius = max(0.001, r)
        return [x+v*(self.radius+0.08) for x,v in zip(origin,n)]

    def palm_intersection(self, a, b, f):
        self.intersection_status = 'unknown'
        # Opening is a prerequisite, checked BEFORE any ray/region geometry.
        if not self.scaling and (not fresh(b) or not open_over_90(b)):
            return None
        if not (fresh(a) and fresh(b) and len(b.landmarks)==21 and self.ray_direction):
            return None
        origin, n = self.ray_origin, self.ray_direction
        start, _ = self.project(origin,f)
        end, _ = self.project([x+v*0.15 for x,v in zip(origin,n)],f)
        dx,dy=end[0]-start[0],end[1]-start[1]
        length=math.hypot(dx,dy)
        if length<1.0:
            return None  # Facing the camera belongs to launch, not resizing.
        dx,dy=dx/length,dy/length
        polygon=fingertip_polygon(b.landmarks)
        if len(polygon)<3:
            return None
        intersections=[]
        # A ray starting inside the tip boundary has only one positive edge hit.
        inside=all((polygon[(i+1)%len(polygon)][0]-p[0])*(start[1]-p[1])-
                   (polygon[(i+1)%len(polygon)][1]-p[1])*(start[0]-p[0])>=-1e-6
                   for i,p in enumerate(polygon))
        if inside:intersections.append(0.0)
        for j,p0 in enumerate(polygon):
            p1=polygon[(j+1)%len(polygon)]
            ex,ey=p1[0]-p0[0],p1[1]-p0[1]
            det=dx*ey-dy*ex
            if abs(det)<1e-8:
                continue
            qx,qy=p0[0]-start[0],p0[1]-start[1]
            along=(qx*ey-qy*ex)/det
            edge=(qx*dy-qy*dx)/det
            if along>0 and -1e-6<=edge<=1+1e-6:
                intersections.append(along)
        # A collapsed side-view palm is unobservable, not proof of departure.
        area=abs(sum(polygon[i][0]*polygon[(i+1)%len(polygon)][1]-polygon[(i+1)%len(polygon)][0]*polygon[i][1] for i in range(len(polygon))))*0.5
        if area<max(4.0,b.palm_scale*b.palm_scale*0.025):
            return None
        if len(intersections)<2:
            self.intersection_status='miss'
            return None
        lo,hi=min(intersections),max(intersections)
        # Closed region: both boundary and interior count. For an origin already
        # inside, use the middle of the positive interior interval, avoiding a zero-length segment.
        along=lo if lo>1e-5 else hi*0.5
        hit=(start[0]+dx*along,start[1]+dy*along)
        axis=0 if abs(dx)>abs(dy) else 1
        q=(hit[axis]-(f.width if axis==0 else f.height)/2)/self.camera(f)
        denom=n[axis]-q*n[2]
        if abs(denom)<1e-8:
            return None
        ray_t=(q*origin[2]-origin[axis])/denom
        if ray_t<=0 or origin[2]+ray_t*n[2]<0.20:
            return None
        self.intersection_status='hit'
        self.current_ray_t=ray_t
        midpoint=((start[0]+hit[0])*0.5,(start[1]+hit[1])*0.5)
        # Boundary crossing governs membership only. Radius must respond to
        # palm separation, not a moving edge hit when the normal trembles.
        if b.palm is None:
            self.intersection_status='unknown'
            return None
        span=math.dist(start,b.palm)
        if span<max(8.0,min(a.palm_scale,b.palm_scale)*0.25):
            self.intersection_status='unknown'
            return None
        return span, self.point_on_ray(midpoint,f)

    def point_on_ray(self, pixel, f):
        """Back-project a screen point on the ray without leaving its 3D line."""
        origin,n=self.ray_origin,self.ray_direction
        q=((pixel[0]-f.width*0.5)/self.camera(f),(pixel[1]-f.height*0.5)/self.camera(f))
        denominators=(n[0]-q[0]*n[2],n[1]-q[1]*n[2])
        axis=0 if abs(denominators[0])>=abs(denominators[1]) else 1
        if abs(denominators[axis])<1e-9:
            return list(self.position)
        t=(q[axis]*origin[2]-origin[axis])/denominators[axis]
        return [x+v*t for x,v in zip(origin,n)]

    def scaling_position(self,f,b):
        # The ray is ONLY the geometric lifecycle test. Never aim it at b.
        self.resize_hit=tuple(x+n*self.resize_ray_t for x,n in zip(self.ray_origin,self.ray_direction))
        if fresh(b) and b.palm is not None:
            self.support_palm=tuple(b.palm)
        start,_=self.project(self.ray_origin,f)
        end=self.support_palm
        midpoint=((start[0]+end[0])*0.5,(start[1]+end[1])*0.5)
        # Use the session's shared estimated depth so both palms and their
        # midpoint have consistent screen projection; do NOT project onto the ray.
        z=self.ray_origin[2]
        return [(midpoint[0]-f.width*.5)*z/self.camera(f),
                (midpoint[1]-f.height*.5)*z/self.camera(f),z]

    def pause(self, timestamp):
        delta = max(0.0, timestamp-self.last_t) if self.last_t is not None else 0.0
        self.last_t = timestamp
        for shot in self.shots:
            shot.born += delta
        self.splashes = [(t+delta, c, r, seed) for t, c, r, seed in self.splashes]
        self.hold.clear()
        self.fist_started.clear()

    def end_session(self, f):
        self.enabled = self.has_orb = self.scaling = self.opened = False
        self.owner = self.support = None
        self.magic_running = False
        self.session_depth = None
        self.ray_origin = self.ray_direction = None
        self.owner_palm = None
        self.resize_span = None
        self.hold.clear()
        self.fist_started.clear()
        self.resize_ray_t=None
        self.resize_hit=None
        self.support_palm=None
        self.normal_pending=self.normal_pending_since=None
        self.last_hand_time=-1e9

    def update(self, f):
        t, events = f.timestamp, []
        dt = min(0.20, max(0.0, t-self.last_t)) if self.last_t is not None else 0.0
        if self.last_t is not None and (t-self.last_t > 0.5 or t < self.last_t):
            self.hold.clear()
            self.fist_started.clear()
        self.last_t = t
        if not self.magic_running:
            ready = []
            for a in f.arms:
                eligible = fresh(a) and a.shape == Shape.FIST and not open_over_90(a) and not (f.valid and arm_lowered(a, f))
                if not eligible:
                    self.fist_started.pop(a.side,None)
                    continue
                began=self.fist_started.setdefault(a.side,t)
                deadline=began+2.0
                if t>=deadline-1e-8:
                    ready.append((deadline,a.side))
            if ready:
                # Both may become observable as ready in one delayed frame;
                # compare their actual observed deadlines, not arm iteration order.
                earliest=min(deadline for deadline,side in ready)
                tied=[side for deadline,side in ready if abs(deadline-earliest)<=1e-8]
                self.owner = 'right' if 'right' in tied else tied[0]
                self.support = 'left' if self.owner == 'right' else 'right'
                self.magic_running = self.enabled = True
                self.opened = self.first_fist_released = False
                self.session_depth = None
                self.ray_origin = self.ray_direction = None
                self.owner_palm = None
                self.radius = 0.075
                self.display_radius = f.height * 0.10
                self.hold.clear()
                self.fist_started.clear()
        if self.magic_running:
            a = f.arm(self.owner)
            b = f.arm(self.support)
            # Once locked, lowering the owner must not freeze tracking or transfer ownership.
            usable = fresh(a) and a.palm is not None
            # Screen palm anchors update independently of normal validity.
            if usable:
                self.ray_origin = self.palm_origin(a,f)
            if self.scaling and fresh(b) and b.palm is not None:
                self.support_palm = tuple(b.palm)
            open_enough = usable and open_over_90(a)
            if open_enough:
                self.first_fist_released = True
            # The first opening has no deadline and need not pass the stricter OPEN classifier.
            # A closed fist has no reliable open-palm orientation. Establish the first
            # ray only from an opening observation, then track normally while held.
            normal_observed = self.update_ray(a,f) if usable and (self.opened or open_enough) else False
            if usable:
                self.last_hand_time=t
                self.palm_wrist_offset=tuple(x-y for x,y in zip(a.palm or a.wrist,a.wrist))
            if not self.opened and open_enough and normal_observed:
                self.opened = self.has_orb = True
                self.opened_at=t
                events.append(('water_open', (a.palm or a.wrist,), 1.0))
            tight_fist = usable and not open_enough and a.shape == Shape.FIST and (a.openness is None or a.openness < 0.22)
            cancel = self.first_fist_released and self.hold.ready('second_fist', tight_fist, t, 0.15)
            if cancel:
                center, k = self.project(self.position, f)
                self.seed += 1
                if self.has_orb:
                    self.splashes.append((t, center, max(45.0, self.radius*k*1.45), self.seed))
                events.append(('water_close', (center,), 1.0))
                self.end_session(f)
            elif self.has_orb:
                # Missing observations retain the last measured 2D palm; no
                # body-wrist replacement for either palm anchor.
                bridge=False
                self.tracking_status='二维掌心实测' if usable else '掌心遮挡，保留最后实测点'
                intersection=self.palm_intersection(a,b,f) if usable and normal_observed else None
                if not (usable and normal_observed):
                    self.intersection_status='unknown'
                if self.scaling:
                    if self.intersection_status=='miss':
                        self.scaling=False
                        self.resize_span=self.resize_ray_t=None
                        self.resize_hit=None
                        self.support_palm=None
                        self.hold.ready('resize',False,t,0.10)
                    elif intersection is not None:
                        span,_=intersection
                        self.resize_ray_t=self.current_ray_t
                        desired=max(3.0,min(f.height*0.7,self.resize_radius*span/self.resize_span))
                        # Deadband suppresses measurement tremor, never changes size outside resizing.
                        if abs(desired-self.display_radius)>0.5:
                            self.display_radius=desired
                else:
                    if self.hold.ready('resize',intersection is not None and b.palm is not None,t,0.10):
                        span,_=intersection
                        self.resize_span,self.resize_radius=span,self.display_radius
                        self.resize_ray_t=self.current_ray_t
                        self.support_palm=tuple(b.palm)
                        self.scaling=True
                if usable or (self.scaling and fresh(b) and b.palm is not None):
                    if self.scaling:
                        # Never overwrite the midpoint with a palm target during a scaling session.
                        self.position=self.scaling_position(f,b)
                    else:
                        self.position=self.target(a,f)
                # Scaling owns the orb until an observed miss. A noisy normal must not launch it.
                aimed=(usable and normal_observed and not self.scaling and
                       self.ray_direction[2]<=-math.cos(math.radians(15)))
                if self.hold.ready('aim',aimed,t,0.10):
                    center,_=self.project(self.position,f)
                    self.seed+=1
                    self.shots.append(Shot(list(self.position),[n*self.cfg.water_launch_speed for n in self.ray_direction],self.display_radius*self.position[2]/self.camera(f),t,self.seed))
                    self.shots=self.shots[-8:]
                    events.append(('water_launch',(center,),1.0))
                    self.end_session(f)
        previous_positions = {id(shot): list(shot.position) for shot in self.shots}
        for shot in self.shots:
            for i in range(3):
                shot.position[i] += shot.velocity[i]*dt
        objects = []
        if self.has_orb:
            center, k = self.project(self.position, f)
            objects.append(EffectObject(1, center, self.display_radius, t-self.opened_at, depth=self.position[2]))
        alive = []
        for shot in self.shots:
            center, scale = self.project(shot.position, f)
            hit = shot.position[2] < 0.25
            before = previous_positions[id(shot)]
            hit_position = list(shot.position)
            if hit:
                alpha = max(0.0, min(1.0, (before[2] - 0.25) / max(1e-6, before[2] - shot.position[2])))
                hit_position = [x + (y - x) * alpha for x, y in zip(before, shot.position)]
            for left, top, right, bottom, shoulder in f.people:
                target_z = self.camera(f) * 0.4 / max(30.0, shoulder)
                low, high = sorted((before[2], shot.position[2]))
                if low - shot.radius - 0.30 <= target_z <= high + shot.radius + 0.30:
                    dz = shot.position[2] - before[2]
                    if abs(dz) > 1e-6:
                        candidates_alpha = (max(0.0, min(1.0, (target_z - before[2]) / dz)),)
                    else:
                        candidates_alpha = (0.0, 0.5, 1.0)
                    for alpha in candidates_alpha:
                        contact = [x + (y - x) * alpha for x, y in zip(before, shot.position)]
                        pixel, k = self.project(contact, f)
                        pad = shot.radius * k
                        if left - pad <= pixel[0] <= right + pad and top - pad <= pixel[1] <= bottom + pad:
                            hit = True
                            hit_position = contact
                            break
                    if hit:
                        break
            if hit or t - shot.born > 4.0:
                center, scale = self.project(hit_position, f)
                impact_center = (max(0.0, min(f.width, center[0])), max(0.0, min(f.height, center[1])))
                radius = min(f.height * 0.7, max(45.0, shot.radius * scale * 1.5))
                self.splashes.append((t, impact_center, radius, shot.seed))
                events.append(("water_hit", (impact_center,), 1.0))
            else:
                alive.append(shot)
                objects.append(
                    EffectObject(
                        2,
                        center,
                        shot.radius * scale,
                        t - shot.born,
                        velocity=(shot.velocity[0] * scale, shot.velocity[1] * scale),
                        depth=shot.position[2],
                        seed=shot.seed,
                    )
                )
        self.shots = alive
        self.splashes = [s for s in self.splashes if t - s[0] < 1.1][-8:]
        for stamp, center, radius, seed in self.splashes:
            objects.append(EffectObject(3, center, radius, t - stamp, seed=seed))
        center, k = self.project(self.position, f)
        ray_start=ray_end=None
        if self.magic_running and self.ray_origin is not None and self.ray_direction is not None:
            ray_start,_=self.project(self.ray_origin,f)
            length=self.resize_ray_t if self.scaling else self.radius+0.12
            ray_end,_=self.project([x+n*length for x,n in zip(self.ray_origin,self.ray_direction)],f)
        return SpellView(
            mode='water', state='SCALING' if self.scaling else 'HELD' if self.has_orb else 'ARMED' if self.enabled else 'FLYING' if self.shots else 'OFF',
            visibility=1.0 if objects else 0.0, intensity=1.0 if objects else 0.0,
            center=center, radius=self.display_radius, caster=self.owner,
            support=self.support, ray_start=ray_start, ray_end=ray_end,
            palm_line_start=ray_start if self.scaling else None,
            palm_line_end=self.support_palm if self.scaling else None,
            objects=tuple(objects[-12:]),
            hint='掌心朝屏幕发射；副手挡住掌心准线缩放；主人手再次握紧收起' if self.has_orb else '主人手张开即可召唤，无等待时限' if self.enabled else '任意一手握拳保持2秒，开始水球术',
            quality=(f'魔法运行中 | 主人手：{self.owner} | 副手：{self.support} | ' + ('缩放中' if self.scaling else '准线锁定掌心') + ' | ' + self.tracking_status) if self.magic_running else '魔法结束；双手自由，重新握拳2秒开始',
        ), events
