import pygame
import sys
import os
import math
import random
import cv2
import numpy as np
import pytmx

# ──────────────────────────────────────────────
#  PATH HELPER (works both in dev & PyInstaller)
# ──────────────────────────────────────────────
def resource_path(relative_path):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative_path)

# ──────────────────────────────────────────────
#  CONSTANTS
# ──────────────────────────────────────────────
SCREEN_W, SCREEN_H = 1366, 768
FPS   = 60
TITLE = "PATCHWORK"

FADE_DURATION = 0.8   # seconds for each half of the cross-fade

# Palette
C_BG    = (18,  14,  24)
C_AMBER = (255, 180,  60)
C_AMBER2= (255, 130,  30)
C_TEAL  = ( 60, 210, 190)
C_TEAL2 = ( 30, 160, 150)
C_CREAM = (240, 230, 210)
C_GREY  = (120, 110, 130)
C_WHITE = (255, 255, 255)

ASSETS   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
MENU_DIR = os.path.join(ASSETS, "menu")
MAP_DIR  = os.path.join(ASSETS, "map", "patchwork-maps")

# ──────────────────────────────────────────────
#  SOUND HELPER
# ──────────────────────────────────────────────
GLOBAL_VOLUME = 1.0
SFX = {}
SFX_BASE_VOL = {}

def update_volumes():
    """Applies the GLOBAL_VOLUME to all loaded sounds and current BGM."""
    for key, sound in SFX.items():
        if sound:
            sound.set_volume(SFX_BASE_VOL.get(key, 0.6) * GLOBAL_VOLUME)
    pygame.mixer.music.set_volume(0.5 * GLOBAL_VOLUME)

def load_game_sounds():
    global SFX, SFX_BASE_VOL
    names = {
        'jump': 'JUMP.mp3',
        'patched': 'PATCHED.mp3',
        'select': 'SELECT.mp3',
        'walk': 'WALK (TRY).mp3',
        'zoom': 'ZOOM IN AND ZOOM OUT.mp3'
    }
    sounds_dir = os.path.join(ASSETS, "sounds")
    for key, filename in names.items():
        try:
            path = os.path.join(sounds_dir, filename)
            SFX[key] = pygame.mixer.Sound(path)
            if key == 'walk':
                SFX_BASE_VOL[key] = 0.1
            else:
                SFX_BASE_VOL[key] = 0.6
            SFX[key].set_volume(SFX_BASE_VOL[key] * GLOBAL_VOLUME)
        except:
            SFX[key] = None

def play_sfx(key):
    if key in SFX and SFX[key]:
        SFX[key].play()

def play_bgm(filename):
    try:
        path = os.path.join(ASSETS, "sounds", filename)
        pygame.mixer.music.load(path)
        pygame.mixer.music.set_volume(0.5 * GLOBAL_VOLUME)
        pygame.mixer.music.play(-1)
    except Exception as e:
        print(f"[WARN] Could not play BGM {filename}: {e}")


# ──────────────────────────────────────────────
#  FADE TRANSITION  (black overlay, 0→1→0 alpha)
# ──────────────────────────────────────────────
def fade_transition(screen, clock, from_draw, to_draw, duration=FADE_DURATION):
    """
    Crossfade between two draw callables.
    from_draw(surf) / to_draw(surf) are called with the screen surface.
    Blocks until the full fade-out + fade-in is done.
    """
    overlay = pygame.Surface((SCREEN_W, SCREEN_H))
    overlay.fill((0, 0, 0))
    total = duration * 2

    elapsed = 0.0
    while elapsed < total:
        dt = clock.tick(FPS) / 1000.0
        elapsed += dt

        # First half → fade OUT (alpha 0 → 255)
        # Second half → fade IN  (alpha 255 → 0)
        if elapsed < duration:
            alpha = int(255 * (elapsed / duration))
            from_draw(screen)
        else:
            alpha = int(255 * (1.0 - (elapsed - duration) / duration))
            to_draw(screen)

        alpha = max(0, min(255, alpha))
        overlay.set_alpha(alpha)
        screen.blit(overlay, (0, 0))
        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()


# ──────────────────────────────────────────────
#  VIDEO BACKGROUND  (OpenCV → pygame surface)
# ──────────────────────────────────────────────
class VideoBackground:
    """Reads an MP4 frame-by-frame, converts to pygame Surface, loops."""

    def __init__(self, path):
        self.cap    = cv2.VideoCapture(path)
        self.ok     = self.cap.isOpened()
        self.fps    = self.cap.get(cv2.CAP_PROP_FPS) or 30
        self._accum = 0.0
        self._surface = None
        if self.ok:
            self._read_next()

    def _read_next(self):
        ret, frame = self.cap.read()
        if not ret:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.cap.read()
        if ret:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = cv2.resize(frame, (SCREEN_W, SCREEN_H))
            self._surface = pygame.surfarray.make_surface(np.transpose(frame, (1, 0, 2)))

    def update(self, dt):
        if not self.ok:
            return
        self._accum += dt
        frame_dur = 1.0 / self.fps
        while self._accum >= frame_dur:
            self._accum -= frame_dur
            self._read_next()

    def draw(self, surf):
        if self._surface:
            surf.blit(self._surface, (0, 0))
        else:
            surf.fill(C_BG)

    def release(self):
        if self.ok:
            self.cap.release()


# ──────────────────────────────────────────────
#  IMAGE BUTTON
# ──────────────────────────────────────────────
class ImageButton:
    """Button rendered from a PNG asset. Scales up on hover."""

    BASE_W = 272   # 15% smaller than original 320

    def __init__(self, image_path, center_x, center_y, action, scale_override=None):
        self.action   = action
        self.hovered  = False
        self._hover_t = 0.0

        raw = pygame.image.load(image_path).convert_alpha()
        iw, ih = raw.get_size()
        aspect = ih / iw
        self.base_w = int(self.BASE_W * scale_override) if scale_override else self.BASE_W
        self.base_h = int(self.base_w * aspect)
        self._img_normal = pygame.transform.smoothscale(raw, (self.base_w, self.base_h))

        self._img_hover = self._img_normal.copy()
        bright = pygame.Surface(self._img_hover.get_size(), pygame.SRCALPHA)
        bright.fill((255, 220, 120, 45))
        self._img_hover.blit(bright, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

        self.cx = center_x
        self.cy = center_y
        self._update_rect(1.0)

    def _update_rect(self, scale):
        w = int(self.base_w * scale)
        h = int(self.base_h * scale)
        self.rect = pygame.Rect(self.cx - w // 2, self.cy - h // 2, w, h)

    def update(self, mouse_pos, dt):
        base_rect = pygame.Rect(self.cx - self.base_w // 2,
                                self.cy - self.base_h // 2,
                                self.base_w, self.base_h)
        self.hovered = base_rect.collidepoint(mouse_pos)
        target = 1.0 if self.hovered else 0.0
        self._hover_t += (target - self._hover_t) * 0.12
        self._update_rect(1.0 + self._hover_t * 0.06)

    def draw(self, surf):
        img    = self._img_hover if self.hovered else self._img_normal
        scaled = pygame.transform.smoothscale(img, (self.rect.width, self.rect.height))
        if self._hover_t > 0.05:
            glow = pygame.Surface((self.rect.width + 20, self.rect.height + 20), pygame.SRCALPHA)
            pygame.draw.rect(glow, (255, 180, 60, int(60 * self._hover_t)),
                             (0, 0, self.rect.width + 20, self.rect.height + 20), border_radius=15)
            surf.blit(glow, (self.rect.x - 10, self.rect.y - 10))
        surf.blit(scaled, self.rect.topleft)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            base_rect = pygame.Rect(self.cx - self.base_w // 2,
                                    self.cy - self.base_h // 2,
                                    self.base_w, self.base_h)
            if base_rect.collidepoint(event.pos):
                return self.action
        return None


# ──────────────────────────────────────────────
#  FLOATING STITCH PARTICLE
# ──────────────────────────────────────────────
class StitchParticle:
    def __init__(self):
        self.reset(random.randint(0, SCREEN_H))

    def reset(self, y=None):
        self.x       = random.uniform(0, SCREEN_W)
        self.y       = y if y is not None else SCREEN_H + 10
        self.vx      = random.uniform(-0.3, 0.3)
        self.vy      = random.uniform(-0.5, -0.15)
        self.size    = random.randint(2, 5)
        self.life    = random.uniform(0.4, 1.0)
        self.max_life= self.life
        self.color   = random.choice([C_AMBER, C_TEAL, C_CREAM])

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.life -= 0.002
        if self.life <= 0 or self.y < -20:
            self.reset()

    def draw(self, surf):
        alpha = int(255 * (self.life / self.max_life))
        r, g, b = self.color
        s = self.size
        pygame.draw.line(surf, (r, g, b, alpha), (self.x - s, self.y), (self.x + s, self.y), 1)
        pygame.draw.line(surf, (r, g, b, alpha), (self.x, self.y - s), (self.x, self.y + s), 1)
        
class SnowParticle:
    def __init__(self):
        self.reset()
        
    def reset(self):
        self.x = random.randint(0, SCREEN_W)
        self.y = random.randint(-100, 0)
        self.vx = random.uniform(-0.5, 0.5)
        self.vy = random.uniform(1, 2)
        self.size = random.randint(1, 3)
        self.alpha = random.randint(100, 255)
        
    def update(self, dt):
        self.x += self.vx
        self.y += self.vy
        if self.y > SCREEN_H:
            self.reset()
            
    def draw(self, surf):
        pygame.draw.circle(surf, (255, 255, 255, self.alpha), (int(self.x), int(self.y)), self.size)



# ──────────────────────────────────────────────
#  MAIN MENU STATE
# ──────────────────────────────────────────────
class MainMenu:
    def __init__(self, screen):
        self.screen = screen
        self.clock  = pygame.time.Clock()
        self.t      = 0.0

        # Video background
        vid_path = os.path.join(MENU_DIR, "main menu.mp4")
        self.video = VideoBackground(vid_path)
        if not self.video.ok:
            print(f"[WARN] Could not open video: {vid_path}")

        # Background music
        music_path = os.path.join(ASSETS, "sounds", "main_menu_bg.mp3")
        try:
            pygame.mixer.music.load(music_path)
            pygame.mixer.music.set_volume(0.5)
            pygame.mixer.music.play(-1)
        except Exception as e:
            print(f"[WARN] Could not load music: {e}")

        # Particles
        self.particles     = [StitchParticle() for _ in range(60)]
        self.particle_surf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)

        # Vignette (pre-baked)
        self.vignette = self._make_vignette()

        # Image buttons
        cx    = SCREEN_W // 2
        btn_y = [390, 505, 620]
        names = ["PLAY_BUTTON.png", "SETTINGS_BUTTON.png", "QUIT_BUTTON.png"]
        acts  = ["start",           "settings",             "quit"]
        self.buttons = []
        for fname, act, y in zip(names, acts, btn_y):
            path = os.path.join(MENU_DIR, fname)
            self.buttons.append(ImageButton(path, cx, y, act))
            
        # Add tutorial button
        tut_path = os.path.join(MENU_DIR, "TUTORIAL_BUTTON.png")
        self.buttons.append(ImageButton(tut_path, SCREEN_W - 120, SCREEN_H - 60, "tutorial", scale_override=0.6))

    # ── helpers ──────────────────────────────
    def _make_vignette(self):
        surf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        cx, cy = SCREEN_W / 2, SCREEN_H / 2
        max_d  = math.hypot(cx, cy)
        for y in range(0, SCREEN_H, 4):
            for x in range(0, SCREEN_W, 4):
                d = math.hypot(x - cx, y - cy) / max_d
                a = int(min(255, d ** 1.8 * 190))
                if a > 0:
                    pygame.draw.rect(surf, (0, 0, 0, a), (x, y, 4, 4))
        return surf

    def draw_frame(self, surf):
        """Draw one menu frame onto surf (used by fade_transition too)."""
        self.video.draw(surf)
        self.particle_surf.fill((0, 0, 0, 0))
        for p in self.particles:
            p.draw(self.particle_surf)
        surf.blit(self.particle_surf, (0, 0))
        surf.blit(self.vignette, (0, 0))
        for btn in self.buttons:
            btn.draw(surf)

    # ── main loop ────────────────────────────
    def run(self):
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            self.t += dt

            action = self._handle_events()
            if action:
                self.video.release()
                pygame.mixer.music.stop()
                return action

            self._update(dt)
            self.draw_frame(self.screen)
            pygame.display.flip()

    # ── events ───────────────────────────────
    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return "quit"
            for btn in self.buttons:
                result = btn.handle_event(event)
                if result:
                    return result
        return None

    # ── update ───────────────────────────────
    def _update(self, dt):
        self.video.update(dt)
        mouse = pygame.mouse.get_pos()
        for btn in self.buttons:
            btn.update(mouse, dt)
        for p in self.particles:
            p.update()

# ──────────────────────────────────────────────
#  TUTORIAL SCREEN
# ──────────────────────────────────────────────
class TutorialScreen:
    def __init__(self, screen):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.page = 1
        self.max_pages = 5
        self.images = {}
        for i in range(1, 6):
            path = os.path.join(ASSETS, "tutorial", f"{i}.png")
            try:
                img = pygame.image.load(path).convert_alpha()
                self.images[i] = pygame.transform.smoothscale(img, (SCREEN_W, SCREEN_H))
            except Exception as e:
                print(f"[WARN] Error loading tutorial page {i}: {e}")
                surf = pygame.Surface((SCREEN_W, SCREEN_H))
                surf.fill(C_BG)
                self.images[i] = surf
                
        self.btn_size = 60
        self.left_rect = pygame.Rect(20, SCREEN_H//2 - self.btn_size//2, self.btn_size, self.btn_size)
        self.right_rect = pygame.Rect(SCREEN_W - 20 - self.btn_size, SCREEN_H//2 - self.btn_size//2, self.btn_size, self.btn_size)
        
        self.font = pygame.font.SysFont("Consolas", 24, bold=True)

    def draw_frame(self, surf):
        surf.blit(self.images[self.page], (0, 0))
        
        mouse_pos = pygame.mouse.get_pos()
        
        # Left button
        if self.page > 1:
            color = C_AMBER if self.left_rect.collidepoint(mouse_pos) else C_WHITE
            surf_alpha = pygame.Surface((self.btn_size, self.btn_size), pygame.SRCALPHA)
            pygame.draw.circle(surf_alpha, (0, 0, 0, 150), (self.btn_size//2, self.btn_size//2), self.btn_size//2)
            surf.blit(surf_alpha, self.left_rect.topleft)
            pygame.draw.polygon(surf, color, [
                (self.left_rect.right - 15, self.left_rect.top + 15),
                (self.left_rect.right - 15, self.left_rect.bottom - 15),
                (self.left_rect.left + 15, self.left_rect.centery)
            ])
            
        # Right button
        if self.page < self.max_pages:
            color = C_AMBER if self.right_rect.collidepoint(mouse_pos) else C_WHITE
            surf_alpha = pygame.Surface((self.btn_size, self.btn_size), pygame.SRCALPHA)
            pygame.draw.circle(surf_alpha, (0, 0, 0, 150), (self.btn_size//2, self.btn_size//2), self.btn_size//2)
            surf.blit(surf_alpha, self.right_rect.topleft)
            pygame.draw.polygon(surf, color, [
                (self.right_rect.left + 15, self.right_rect.top + 15),
                (self.right_rect.left + 15, self.right_rect.bottom - 15),
                (self.right_rect.right - 15, self.right_rect.centery)
            ])

        # Draw "Press ESC to return"
        esc_text = self.font.render("Press ESC to return", True, C_WHITE)
        esc_rect = esc_text.get_rect(topleft=(30, 30))
        bg_rect = esc_rect.inflate(20, 10)
        bg_surf = pygame.Surface(bg_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(bg_surf, (0, 0, 0, 150), bg_surf.get_rect(), border_radius=5)
        surf.blit(bg_surf, (esc_rect.x - 10, esc_rect.y - 5))
        surf.blit(esc_text, esc_rect)

    def run(self):
        while True:
            self.clock.tick(FPS)
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "quit"
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        play_sfx('select')
                        return "menu"
                    elif event.key == pygame.K_LEFT or event.key == pygame.K_a:
                        if self.page > 1:
                            self.page -= 1
                            play_sfx('select')
                    elif event.key == pygame.K_RIGHT or event.key == pygame.K_d:
                        if self.page < self.max_pages:
                            self.page += 1
                            play_sfx('select')
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.page > 1 and self.left_rect.collidepoint(event.pos):
                        self.page -= 1
                        play_sfx('select')
                    elif self.page < self.max_pages and self.right_rect.collidepoint(event.pos):
                        self.page += 1
                        play_sfx('select')
            
            self.draw_frame(self.screen)
            pygame.display.flip()

# ──────────────────────────────────────────────
#  VICTORY SCREEN
# ──────────────────────────────────────────────
class VictoryScreen:
    def __init__(self, screen):
        self.screen = screen
        self.clock = pygame.time.Clock()
        
        # Video background
        vid_path = os.path.join(ASSETS, "VICTORY SCREEN.mp4")
        self.video = VideoBackground(vid_path)
        
        self.font = pygame.font.SysFont("Consolas", 48, bold=True)
        self.small_font = pygame.font.SysFont("Consolas", 24)
        
        # Buttons
        cx = SCREEN_W // 2
        names = ["RESTART_BUTTON.png", "MENU_BUTTON.png"]
        acts = ["restart", "menu"]
        self.buttons = []
        for i, (fname, act) in enumerate(zip(names, acts)):
            path = os.path.join(MENU_DIR, fname)
            self.buttons.append(ImageButton(path, cx, 450 + i * 115, act))

    def draw_frame(self, surf):
        self.video.draw(surf)
        
        pass
        
        for btn in self.buttons:
            btn.draw(surf)

    def run(self):
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            self.video.update(dt)
            mouse = pygame.mouse.get_pos()
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "quit"
                for btn in self.buttons:
                    act = btn.handle_event(event)
                    if act:
                        self.video.release()
                        return act
            
            for btn in self.buttons:
                btn.update(mouse, dt)
                
            self.draw_frame(self.screen)
            pygame.display.flip()


# ──────────────────────────────────────────────
#  PLAYER (Sprite)
# ──────────────────────────────────────────────
class Player(pygame.sprite.Sprite):
    def __init__(self, pos, groups, collision_sprites):
        super().__init__(groups)
        
        self.import_assets()
        self.frame_index = 0
        self.animation_speed = 8
        self.status = 'idle'
        self.flip = False
        self.image = self.animations[self.status][self.frame_index]
        
        self.rect = self.image.get_rect(topleft=pos)
        self.hitbox = self.rect.inflate(-12, -18) 
        
        self.moving_left = False
        self.moving_right = False
        
        self.speed = 100 
        self.pos = pygame.math.Vector2(self.rect.topleft)
        self.direction = pygame.math.Vector2()
        self.gravity = 800
        self.jump_speed = -300
        self.in_air = False
        self.collision_sprites = collision_sprites
        self.active = True
        self.walk_timer = 0
        self.walk_freq = 0.35

    def import_assets(self):
        self.animations = {'idle': [], 'run': [], 'jump': []}
        
        def get_frames(path, frame_width):
            try:
                full_surf = pygame.image.load(path).convert_alpha()
                frames = []
                for i in range(full_surf.get_width() // frame_width):
                    x = i * frame_width
                    frame = pygame.Surface((frame_width, full_surf.get_height()), pygame.SRCALPHA)
                    frame.blit(full_surf, (0, 0), (x, 0, frame_width, full_surf.get_height()))
                    frames.append(frame)
                return frames
            except Exception as e:
                print(f"[WARN] Error loading {path}: {e}")
                fallback = pygame.Surface((32, 32))
                fallback.fill((255, 0, 255))
                return [fallback]

        base = os.path.join(ASSETS, "map", "spritesheet", "Player")
        self.animations['idle'] = get_frames(os.path.join(base, "Idle.png"), 32)
        self.animations['run'] = get_frames(os.path.join(base, "Run.png"), 32)
        self.animations['jump'] = get_frames(os.path.join(base, "Jump.png"), 32)

    def get_status(self):
        if self.in_air:
            self.status = 'jump'
        elif self.moving_left or self.moving_right:
            self.status = 'run'
        else:
            self.status = 'idle'

    def animate(self, dt):
        old_frame = int(self.frame_index)
        self.frame_index += self.animation_speed * dt
        if self.frame_index >= len(self.animations[self.status]):
            self.frame_index = 0
            
        new_frame = int(self.frame_index)
        # Sync footsteps with animation frames (typically frames 1 and 4 in a standard run cycle)
        if self.status == 'run' and not self.in_air:
            if old_frame != new_frame and new_frame in [0, 1.]:
                play_sfx('walk')
                
        image = self.animations[self.status][int(self.frame_index)]
        if self.flip:
            self.image = pygame.transform.flip(image, True, False)
        else:
            self.image = image

    def jump(self):
        if not self.in_air and getattr(self, 'active', True):
            self.direction.y = self.jump_speed
            self.in_air = True
            play_sfx('jump')

    def update(self, dt):
        if not getattr(self, 'active', True):
            self.get_status()
            self.animate(dt)
            return

        dx = 0
        if self.moving_right: dx = 1; self.flip = False
        elif self.moving_left: dx = -1; self.flip = True
        
        self.pos.x += dx * self.speed * dt
        self.hitbox.centerx = round(self.pos.x + self.rect.width / 2)
        self.horizontal_collision()
        self.rect.centerx = self.hitbox.centerx

        self.apply_gravity(dt)
        self.vertical_collision()
        self.rect.centery = self.hitbox.centery

        self.get_status()
        self.animate(dt)

    def horizontal_collision(self):
        for sprite in self.collision_sprites:
            if sprite.rect.colliderect(self.hitbox):
                if self.hitbox.centerx < sprite.rect.centerx: 
                    self.hitbox.right = sprite.rect.left
                else: 
                    self.hitbox.left = sprite.rect.right
                self.pos.x = self.hitbox.left - (self.rect.width - self.hitbox.width) / 2

    def apply_gravity(self, dt):
        self.direction.y += self.gravity * dt
        self.pos.y += self.direction.y * dt
        self.hitbox.centery = round(self.pos.y + self.rect.height / 2)

    def vertical_collision(self):
        self.in_air = True
        for sprite in self.collision_sprites:
            if sprite.rect.colliderect(self.hitbox):
                if self.direction.y > 0: 
                    self.hitbox.bottom = sprite.rect.top
                    self.direction.y = 0
                    self.in_air = False 
                elif self.direction.y < 0: 
                    self.hitbox.top = sprite.rect.bottom
                    self.direction.y = 0
                self.pos.y = self.hitbox.top - (self.rect.height - self.hitbox.height) / 2


# ──────────────────────────────────────────────
#  MAP OBJECTS
# ──────────────────────────────────────────────
class Tile(pygame.sprite.Sprite):
    def __init__(self, pos, groups):
        super().__init__(groups)
        self.image = pygame.Surface((16, 16))
        self.image.fill((255,0,0))
        self.image.set_alpha(0) # Invisible collision
        self.rect = self.image.get_rect(topleft=pos)

class Tree(pygame.sprite.Sprite):
    def __init__(self, pos, surf, groups, tree_type):
        super().__init__(groups)
        self.image = surf
        self.rect = self.image.get_rect(topleft=pos)
        self.tree_type = tree_type 

class MissingPiece(pygame.sprite.Sprite):
    def __init__(self, pos, tmx_data, start_tx, end_tx, groups):
        super().__init__(groups)
        
        tw = tmx_data.tilewidth
        th = tmx_data.tileheight
        width = (end_tx - start_tx + 1) * tw
        height = tmx_data.height * th
        
        self.image = pygame.Surface((width, height), pygame.SRCALPHA)
        
        for layer in tmx_data.visible_layers:
            if isinstance(layer, pytmx.TiledTileLayer):
                for x, y, gid in layer:
                    if start_tx <= x <= end_tx:
                        tile = tmx_data.get_tile_image_by_gid(gid)
                        if tile:
                            self.image.blit(tile, ((x - start_tx) * tw, y * th))

        self.rect = self.image.get_rect(topleft=pos)
        self.dragging = False
        self.offset_x = 0
        self.offset_y = 0
        self.particles = []

    def get_alpha_at(self, world_x, world_y):
        local_x = int(world_x - self.rect.x)
        local_y = int(world_y - self.rect.y)
        if 0 <= local_x < self.rect.width and 0 <= local_y < self.rect.height:
            return self.image.get_at((local_x, local_y))[3] > 0
        return False

    def update(self, dt):
        if random.random() < 0.5:
            for _ in range(5):
                px = random.randint(self.rect.left, self.rect.right - 1)
                py = random.randint(self.rect.top, self.rect.bottom - 1)
                if self.get_alpha_at(px, py):
                    self.particles.append([px, py, random.uniform(2, 5)])
                    break
            
        for p in self.particles[:]:
            p[2] -= 3 * dt
            p[1] -= 30 * dt
            if p[2] <= 0:
                self.particles.remove(p)

class NPC(pygame.sprite.Sprite):
    def __init__(self, pos, groups, hint_text):
        super().__init__(groups)
        self.image = pygame.Surface((32, 32), pygame.SRCALPHA)
        self.rect = self.image.get_rect(center=pos)
        self.hint_text = hint_text
        self.time = random.uniform(0, 10)
        self.base_y = self.rect.y
        
    def update(self, dt):
        self.time += dt * 3
        self.image.fill((0,0,0,0))
        # Draw a simple pulsing glowing orb
        pulse = int(math.sin(self.time) * 5)
        pygame.draw.circle(self.image, (100, 200, 255), (16, 16), 10 + pulse // 2)
        pygame.draw.circle(self.image, (255, 255, 255), (16, 16), 6)
        
        self.rect.y = self.base_y + int(math.sin(self.time * 2) * 4) # hover effect

class CameraGroup(pygame.sprite.Group):
    def __init__(self, internal_surf):
        super().__init__()
        self.display_surface = internal_surf
        self.offset = pygame.math.Vector2()
        self.internal_w = internal_surf.get_width()
        self.internal_h = internal_surf.get_height()
        
        self.has_gap = False
        self.gap_start_tx = 0
        self.gap_end_tx = 0

    def custom_draw(self, center_sprite, tmx_data, mode="PLAY", manual_offset=None):
        if mode == "PLAY" and center_sprite:
            self.offset.x = center_sprite.rect.centerx - self.internal_w // 2
            self.offset.y = center_sprite.rect.centery - self.internal_h // 2
            
            map_width = tmx_data.width * tmx_data.tilewidth
            map_height = tmx_data.height * tmx_data.tileheight
            self.offset.x = max(0, min(self.offset.x, map_width - self.internal_w))
            self.offset.y = max(0, min(self.offset.y, map_height - self.internal_h))
            
        elif mode == "CREATOR" and manual_offset:
            self.offset.x = manual_offset.x
            self.offset.y = manual_offset.y
            # Camera freely pans!

        for layer in tmx_data.visible_layers:
            if isinstance(layer, pytmx.TiledTileLayer):
                for x, y, gid in layer:
                    if self.has_gap and self.gap_start_tx <= x <= self.gap_end_tx:
                        continue # Skip drawing gap tiles
                        
                    tile = tmx_data.get_tile_image_by_gid(gid)
                    if tile:
                        pos = (x * tmx_data.tilewidth - self.offset.x, y * tmx_data.tileheight - self.offset.y)
                        self.display_surface.blit(tile, pos)

        for sprite in sorted(self.sprites(), key=lambda sprite: sprite.rect.bottom):
            if not isinstance(sprite, Tile):
                # Hide missing piece in PLAY mode
                if mode == "PLAY" and isinstance(sprite, MissingPiece):
                    continue
                offset_pos = sprite.rect.topleft - self.offset
                self.display_surface.blit(sprite.image, offset_pos)

# ──────────────────────────────────────────────


# ──────────────────────────────────────────────
#  GAME SCREEN  (patchwork 2.py logic)
# ──────────────────────────────────────────────
class GameScreen:
    def __init__(self, screen, clock):
        self.screen = screen
        self.clock  = clock

        self.zoom = 3.0
        self.target_zoom = 3.0
        self.internal_w = int(SCREEN_W / self.zoom)
        self.internal_h = int(SCREEN_H / self.zoom)
        self.internal_surf = pygame.Surface((self.internal_w, self.internal_h))

        tmx_path = os.path.join(MAP_DIR, "lvl1.tmx")
        try:
            self.tmx_data = pytmx.load_pygame(tmx_path, pixelalpha=True)
        except Exception as e:
            print(f"[WARN] Error loading map: {e}")
            self.tmx_data = pytmx.load_pygame(os.path.join(MAP_DIR, "try.tmx"), pixelalpha=True)

        self.loop_count = 0 # Start at 0 for exploration stage
        self.current_world = 1
        self.mode = "PLAY"
        
        self.camera_manual_offset = pygame.math.Vector2()
        self.is_dragging_camera = False
        
        self.missing_piece = None
        self.npcs = pygame.sprite.Group()
        self.active_npc_hint = None
        
        self.font = pygame.font.SysFont("Consolas", 14)
        self.big_font = pygame.font.SysFont("Consolas", 20, bold=True)
        self.notify_font = pygame.font.SysFont("Consolas", 32, bold=True)
        
        self.game_msg = "Welcome to the Plains World"
        self.game_msg_timer = 5.0
        
        self.snow_particles = [SnowParticle() for _ in range(50)]
        
        try:
            self.sky_img = pygame.image.load(os.path.join(ASSETS, "map", "SKY (MAP 1).png")).convert()
        except Exception as e:
            print(f"[WARN] Error loading sky image: {e}")
            self.sky_img = pygame.Surface((SCREEN_W, SCREEN_H))
            self.sky_img.fill('#333333')
            
        # Pause state
        self.is_paused = False
        pause_path = os.path.join(MENU_DIR, "PAUSE_BUTTON.png")
        self.pause_btn = ImageButton(pause_path, SCREEN_W - 80, SCREEN_H - 60, "pause", scale_override=0.4)
        
        cx = SCREEN_W // 2
        p_names = ["RESSUME_BUTTON.png", "RESTART_BUTTON.png", "SETTINGS_BUTTON.png", "QUIT_BUTTON.png"]
        p_acts = ["resume", "restart", "settings_game", "menu"]
        self.pause_menu_btns = []
        for i, (fname, act) in enumerate(zip(p_names, p_acts)):
            path = os.path.join(MENU_DIR, fname)
            self.pause_menu_btns.append(ImageButton(path, cx, 200 + i * 115, act))
        
        self._build_map()

    def _build_map(self):
        self.visible_sprites = CameraGroup(self.internal_surf)
        self.collision_sprites = pygame.sprite.Group()
        self.missing_piece = None
        self.npcs = pygame.sprite.Group()
        self.active_npc_hint = None
        self.gap_patched = False
        
        has_gap = (1 <= self.loop_count <= 5)
        self.visible_sprites.has_gap = has_gap
        
        spawn_x, spawn_y = 100, 100
        if self.loop_count == 1:
            self.gap_start_tx, self.gap_end_tx = 40, 45
            spawn_x = random.randint(100, 1000)
            spawn_y = random.randint(0, 200)
        elif self.loop_count == 2:
            self.gap_start_tx, self.gap_end_tx = 30, 35
            spawn_x = random.randint(100, 1000)
            spawn_y = random.randint(-300, 500)
        elif self.loop_count == 3:
            self.gap_start_tx, self.gap_end_tx = 50, 55
            spawn_x = random.randint(100, 1000)
            spawn_y = random.randint(-600, 800)
        elif self.loop_count == 4:
            self.gap_start_tx, self.gap_end_tx = 20, 25
            spawn_x = random.randint(100, 1000)
            spawn_y = random.randint(-1000, 1200)
        elif self.loop_count == 5:
            self.gap_start_tx, self.gap_end_tx = 60, 65
            spawn_x = random.randint(100, 1000)
            spawn_y = random.randint(-1500, 1800)
        else:
            self.gap_start_tx, self.gap_end_tx = 40, 45

        self.gap_rect = pygame.Rect(self.gap_start_tx * 16, 0, (self.gap_end_tx - self.gap_start_tx + 1) * 16, self.tmx_data.height * 16)
        self.visible_sprites.gap_start_tx = self.gap_start_tx
        self.visible_sprites.gap_end_tx = self.gap_end_tx

        for layer in self.tmx_data.visible_layers:
            if isinstance(layer, pytmx.TiledTileLayer) and layer.name in ["Collisions", "Collision"]:
                for x, y, gid in layer:
                    if has_gap and self.gap_start_tx <= x <= self.gap_end_tx:
                        continue # No collision in the gap
                    if gid != 0:
                        Tile((x * 16, y * 16), [self.collision_sprites])

        self.player = None
        try:
            entities_layer = self.tmx_data.get_layer_by_name("Entities")
            for obj in entities_layer:
                if obj.name == "PlayerSpawn":
                    self.player = Player((obj.x, obj.y), [self.visible_sprites], self.collision_sprites)
                elif obj.name and obj.name.strip().startswith("Tree"):
                    tree_image = self.tmx_data.get_tile_image_by_gid(obj.gid)
                    if tree_image:
                        Tree((obj.x, obj.y), tree_image, [self.visible_sprites], obj.name.strip())
        except ValueError:
            pass

        if not self.player:
            self.player = Player((100, 100), [self.visible_sprites], self.collision_sprites)
            
        if has_gap:
            self.missing_piece = MissingPiece((spawn_x, spawn_y), self.tmx_data, self.gap_start_tx, self.gap_end_tx, [self.visible_sprites])
            
            # Spawn NPCs
            if spawn_y < 0:
                hint = "I saw it fly high into the sky!"
            elif spawn_y > 320:
                hint = "It's buried deep underground..."
            elif spawn_x < 640:
                hint = "Try looking towards the beginning of the path..."
            else:
                hint = "It's hidden further down the trail..."
                
            NPC((300, 200), [self.npcs], hint)
            NPC((800, 200), [self.npcs], hint)

    def loop_map(self):
        self.loop_count += 1
        
        # World Transition logic
        if self.loop_count > 5:
            if self.current_world == 2:
                # VICTORY!
                return "victory"
            
            self.loop_count = 0
            if self.current_world == 1:
                self.current_world = 2
                tmx_path = os.path.join(MAP_DIR, "lvl2.tmx")
                play_bgm('BGM (SNOW MAP).mp3')
            else:
                self.current_world = 1
                tmx_path = os.path.join(MAP_DIR, "lvl1.tmx")
                play_bgm('BGM (PLAIN).mp3')
                
            try:
                self.tmx_data = pytmx.load_pygame(tmx_path, pixelalpha=True)
            except Exception as e:
                print(f"[WARN] Error transitioning world: {e}")

        self.mode = "PLAY"
        self._build_map()
        
        # Notification logic
        if self.loop_count == 0:
            w_name = "Plains World" if self.current_world == 1 else "Snow World"
            self.game_msg = f"Welcome to the {w_name}"
        else:
            self.game_msg = f"Level {self.loop_count}"
        
        self.game_msg_timer = 5.0

    def draw_frame(self, surf):
        # Smooth zoom interpolation
        dt = self.clock.get_time() / 1000.0
        lerp_speed = 4.0
        if abs(self.zoom - self.target_zoom) > 0.01:
            self.zoom += (self.target_zoom - self.zoom) * dt * lerp_speed
            
            # Optimization: Only recreate surface if dimensions actually change
            nw = int(SCREEN_W / self.zoom)
            nh = int(SCREEN_H / self.zoom)
            if nw != self.internal_w or nh != self.internal_h:
                self.internal_w, self.internal_h = nw, nh
                self.internal_surf = pygame.Surface((self.internal_w, self.internal_h))
                # Update CameraGroup with new surface dimensions
                self.visible_sprites.display_surface = self.internal_surf
                self.visible_sprites.internal_w = self.internal_w
                self.visible_sprites.internal_h = self.internal_h

        # Draw Sky with parallax and tile horizontally, extending edge colors vertically
        parallax_x = -(self.visible_sprites.offset.x * 0.2)
        parallax_y = -(self.visible_sprites.offset.y * 0.2)
        
        sky_w = self.sky_img.get_width()
        sky_h = self.sky_img.get_height()
        
        top_color = self.sky_img.get_at((0, 0))
        bottom_color = self.sky_img.get_at((0, sky_h - 1))
        
        # Fill surface with the bottom color
        self.internal_surf.fill(bottom_color)
        
        # Extend top color if sky is pulled down
        if parallax_y > 0:
            pygame.draw.rect(self.internal_surf, top_color, (0, 0, self.internal_w, int(parallax_y)))
        
        # Tile sky image ONLY horizontally
        start_x = int(parallax_x % sky_w)
        if start_x > 0: start_x -= sky_w
        
        for x in range(start_x, self.internal_w, sky_w):
            self.internal_surf.blit(self.sky_img, (x, parallax_y))
        
        self.visible_sprites.custom_draw(self.player, self.tmx_data, self.mode, self.camera_manual_offset)
        
        # Draw NPCs (only in Creator Mode)
        if self.mode == "CREATOR":
            for npc in self.npcs:
                offset_pos = npc.rect.topleft - self.visible_sprites.offset
                self.internal_surf.blit(npc.image, offset_pos)
        
        # Draw clues and particles in CREATOR mode
        if self.mode == "CREATOR":
            if self.missing_piece:
                # Draw glow particles for the missing piece
                for p in self.missing_piece.particles:
                    px = int(p[0] - self.camera_manual_offset.x)
                    py = int(p[1] - self.camera_manual_offset.y)
                    pygame.draw.circle(self.internal_surf, (255, 215, 0), (px, py), int(p[2]))
                    
            mx, my = pygame.mouse.get_pos()
            world_x = (mx / self.zoom) + self.camera_manual_offset.x
            world_y = (my / self.zoom) + self.camera_manual_offset.y
            
            if self.active_npc_hint:
                hint = self.font.render(f"Wisp: '{self.active_npc_hint}'", True, C_TEAL)
                self.internal_surf.blit(hint, (mx / self.zoom + 15, my / self.zoom + 15))
            else:
                if self.loop_count <= 2 and self.missing_piece:
                    piece_center_x = self.missing_piece.rect.centerx
                    piece_center_y = self.missing_piece.rect.centery
                    dist = math.hypot(world_x - piece_center_x, world_y - piece_center_y)
                    
                    if dist < 80:
                        text = "HOT! Right here!"
                        color = C_AMBER
                    elif dist < 250:
                        text = "Warm... getting closer"
                        color = C_TEAL
                    else:
                        text = "Cold. Pan around to find it!"
                        color = C_GREY
                else:
                    text = "Find Wisps to get clues!"
                    color = C_GREY
                    
                hint = self.font.render(text, True, color)
                self.internal_surf.blit(hint, (mx / self.zoom + 15, my / self.zoom + 15))
            
            mode_text = self.big_font.render(f"CREATOR MODE (Level {self.loop_count}) - Right click to pan!", True, C_AMBER)
            self.internal_surf.blit(mode_text, (10, 10))

        scaled_surface = pygame.transform.scale(self.internal_surf, (SCREEN_W, SCREEN_H))
        surf.blit(scaled_surface, (0, 0))
        
        # Draw game notifications
        if self.game_msg_timer > 0:
            self.game_msg_timer -= dt
            msg_surf = self.notify_font.render(self.game_msg, True, C_WHITE)
            msg_rect = msg_surf.get_rect(midtop=(SCREEN_W // 2, 40))
            
            # Draw a subtle background for readability
            bg_rect = msg_rect.inflate(40, 20)
            bg_surf = pygame.Surface(bg_rect.size, pygame.SRCALPHA)
            pygame.draw.rect(bg_surf, (0, 0, 0, 150), bg_surf.get_rect(), border_radius=10)
            surf.blit(bg_surf, bg_rect)
            
            surf.blit(msg_surf, msg_rect)
            
        # Draw Snow (only in Snow World)
        if self.current_world == 2:
            for p in self.snow_particles:
                p.update(dt)
                p.draw(surf)
                
        # Draw Pause menu or button
        if self.is_paused:
            overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 150))
            surf.blit(overlay, (0, 0))
            for btn in self.pause_menu_btns:
                btn.draw(surf)
        else:
            self.pause_btn.draw(surf)

    def run(self):
        while True:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.1)
            
            if not self.is_paused:
                # Check for map end
                map_width = self.tmx_data.width * self.tmx_data.tilewidth
                if self.player.pos.x > map_width - 32:
                    res = self.loop_map()
                    if res == "victory":
                        return "victory"
                    
                # Check for falling into gap
                if self.mode == "PLAY" and 1 <= self.loop_count <= 5 and not self.gap_patched:
                    if self.gap_rect.colliderect(self.player.rect):
                        self.mode = "CREATOR"
                        self.target_zoom = 2.2
                        play_sfx('zoom')
                        self.player.active = False
                        self.player.moving_left = False
                        self.player.moving_right = False
                        self.camera_manual_offset.x = self.visible_sprites.offset.x
                        self.camera_manual_offset.y = self.visible_sprites.offset.y

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "quit"
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        if self.is_paused:
                            self.is_paused = False
                            play_sfx('select')
                        else:
                            self.is_paused = True
                            play_sfx('select')
                            
                if self.is_paused:
                    for btn in self.pause_menu_btns:
                        act = btn.handle_event(event)
                        if act == "resume":
                            self.is_paused = False
                            play_sfx('select')
                        elif act == "restart":
                            play_sfx('select')
                            return "restart"
                        elif act == "settings_game":
                            play_sfx('select')
                            return "settings_game"
                        elif act == "menu":
                            play_sfx('select')
                            return "menu"
                else:
                    act = self.pause_btn.handle_event(event)
                    if act == "pause":
                        self.is_paused = True
                        play_sfx('select')
                        
                    if self.mode == "PLAY":
                        if event.type == pygame.KEYDOWN:
                            if event.key == pygame.K_LEFT or event.key == pygame.K_a:
                                self.player.moving_left = True
                            if event.key == pygame.K_RIGHT or event.key == pygame.K_d:
                                self.player.moving_right = True
                            if event.key == pygame.K_SPACE or event.key == pygame.K_w or event.key == pygame.K_UP:
                                self.player.jump()
                        
                        if event.type == pygame.KEYUP:
                            if event.key == pygame.K_LEFT or event.key == pygame.K_a:
                                self.player.moving_left = False
                            if event.key == pygame.K_RIGHT or event.key == pygame.K_d:
                                self.player.moving_right = False
                                
                    elif self.mode == "CREATOR":
                        if event.type == pygame.MOUSEBUTTONDOWN:
                            if event.button == 1:
                                # Translate mouse pos to scaled internal pos, then to world pos
                                mx, my = event.pos
                                world_x = (mx / self.zoom) + self.camera_manual_offset.x
                                world_y = (my / self.zoom) + self.camera_manual_offset.y
                                
                                if self.missing_piece and self.missing_piece.rect.collidepoint(world_x, world_y) and self.missing_piece.get_alpha_at(world_x, world_y):
                                    self.missing_piece.dragging = True
                                    self.missing_piece.offset_x = self.missing_piece.rect.x - world_x
                                    self.missing_piece.offset_y = self.missing_piece.rect.y - world_y
                                    play_sfx('select')
                                
                                # Check NPC click
                                for npc in self.npcs:
                                    if npc.rect.collidepoint(world_x, world_y):
                                        play_sfx('select')
                            elif event.button == 3:
                                self.is_dragging_camera = True
                                
                        if event.type == pygame.MOUSEBUTTONUP:
                            if event.button == 3:
                                self.is_dragging_camera = False
                            elif event.button == 1:
                                if self.missing_piece and self.missing_piece.dragging:
                                    self.missing_piece.dragging = False
                                    # Check if dropped in gap
                                    if self.gap_rect.colliderect(self.missing_piece.rect):
                                        # Correct piece!
                                        for layer in self.tmx_data.visible_layers:
                                            if isinstance(layer, pytmx.TiledTileLayer) and layer.name in ["Collisions", "Collision"]:
                                                for x, y, gid in layer:
                                                    if self.gap_start_tx <= x <= self.gap_end_tx and gid != 0:
                                                        Tile((x * 16, y * 16), [self.collision_sprites])
                                        
                                        self.visible_sprites.has_gap = False
                                        self.gap_patched = True
                                        self.game_msg = "World Patched! Proceed to Next Level"
                                        self.game_msg_timer = 5.0
                                        play_sfx('patched')
                                        
                                        if self.missing_piece:
                                            self.missing_piece.kill()
                                            self.missing_piece = None
                                        
                                        for npc in self.npcs:
                                            npc.kill()
                                            
                                        self.mode = "PLAY"
                                        self.target_zoom = 3.0
                                        play_sfx('zoom')
                                        self.player.active = True
                                        self.player.pos.x = self.gap_rect.left - 64
                                        self.player.pos.y = 100
                                        self.player.hitbox.topleft = self.player.pos
                                        self.player.rect.center = self.player.hitbox.center
                        
                        if event.type == pygame.MOUSEMOTION:
                            if self.is_dragging_camera:
                                dx, dy = event.rel
                                self.camera_manual_offset.x -= dx / self.zoom
                                self.camera_manual_offset.y -= dy / self.zoom
                            elif self.missing_piece and self.missing_piece.dragging:
                                mx, my = event.pos
                                world_x = (mx / self.zoom) + self.camera_manual_offset.x
                                world_y = (my / self.zoom) + self.camera_manual_offset.y
                                self.missing_piece.rect.x = world_x + self.missing_piece.offset_x
                                self.missing_piece.rect.y = world_y + self.missing_piece.offset_y
                                
                            # Handle NPC hovering
                            mx, my = pygame.mouse.get_pos()
                            world_x = (mx / self.zoom) + self.camera_manual_offset.x
                            world_y = (my / self.zoom) + self.camera_manual_offset.y
                            
                            hovered_npc = None
                            for npc in self.npcs:
                                if npc.rect.collidepoint(world_x, world_y):
                                    hovered_npc = npc
                                    break
                                    
                            if hovered_npc:
                                self.active_npc_hint = hovered_npc.hint_text
                            else:
                                self.active_npc_hint = None
            
            mouse = pygame.mouse.get_pos()
            if self.is_paused:
                for btn in self.pause_menu_btns:
                    btn.update(mouse, dt)
            else:
                self.pause_btn.update(mouse, dt)
                self.npcs.update(dt)
                self.visible_sprites.update(dt)
                
            self.draw_frame(self.screen)
            pygame.display.flip()

# ──────────────────────────────────────────────
#  SETTINGS SCREEN
# ──────────────────────────────────────────────
class SettingsScreen:
    def __init__(self, screen, return_state="menu"):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.return_state = return_state
        
        self.font = pygame.font.SysFont("Consolas", 48, bold=True)
        self.small_font = pygame.font.SysFont("Consolas", 24)
        
        cx = SCREEN_W // 2
        self.slider_bar = pygame.Rect(cx - 150, 250, 300, 20)
        
        self.buttons = []
        cred_path = os.path.join(MENU_DIR, "CREDITS_BUTTON.png")
        self.buttons.append(ImageButton(cred_path, cx, 400, "credits"))
        
        back_img = "RESSUME_BUTTON.png" if return_state == "game" else "MENU_BUTTON.png"
        back_path = os.path.join(MENU_DIR, back_img)
        self.buttons.append(ImageButton(back_path, cx, 515, return_state))
        
        self.dragging_slider = False

    def draw_frame(self, surf):
        surf.fill(C_BG)
        
        title = self.font.render("SETTINGS", True, C_AMBER)
        tr = title.get_rect(center=(SCREEN_W // 2, 100))
        surf.blit(title, tr)
        
        vol_text = self.small_font.render(f"Global Volume: {int(GLOBAL_VOLUME * 100)}%", True, C_WHITE)
        vr = vol_text.get_rect(center=(SCREEN_W // 2, 210))
        surf.blit(vol_text, vr)
        
        pygame.draw.rect(surf, (100, 100, 100), self.slider_bar, border_radius=10)
        
        handle_x = self.slider_bar.left + int(GLOBAL_VOLUME * self.slider_bar.width)
        handle_rect = pygame.Rect(0, 0, 20, 40)
        handle_rect.center = (handle_x, self.slider_bar.centery)
        pygame.draw.rect(surf, C_AMBER, handle_rect, border_radius=5)
        
        for btn in self.buttons:
            btn.draw(surf)

    def run(self):
        global GLOBAL_VOLUME
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            mouse = pygame.mouse.get_pos()
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "quit"
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                        return self.return_state
                        
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    handle_x = self.slider_bar.left + int(GLOBAL_VOLUME * self.slider_bar.width)
                    handle_rect = pygame.Rect(0, 0, 40, 60)
                    handle_rect.center = (handle_x, self.slider_bar.centery)
                    
                    if handle_rect.collidepoint(event.pos) or self.slider_bar.collidepoint(event.pos):
                        self.dragging_slider = True
                        play_sfx('select')
                        
                if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    self.dragging_slider = False
                    
                if event.type == pygame.MOUSEMOTION:
                    if self.dragging_slider:
                        rel_x = event.pos[0] - self.slider_bar.left
                        GLOBAL_VOLUME = max(0.0, min(1.0, rel_x / self.slider_bar.width))
                        update_volumes()
                        
                for btn in self.buttons:
                    act = btn.handle_event(event)
                    if act:
                        play_sfx('select')
                        if act == "credits":
                            CreditsScreen(self.screen).run()
                        else:
                            return act
                        
            for btn in self.buttons:
                btn.update(mouse, dt)
                
            self.draw_frame(self.screen)
            pygame.display.flip()

# ──────────────────────────────────────────────
#  CREDITS SCREEN
# ──────────────────────────────────────────────
class CreditsScreen:
    def __init__(self, screen):
        self.screen = screen
        self.clock = pygame.time.Clock()
        try:
            self.credits_img = pygame.image.load(os.path.join(ASSETS, "PATCHWORK CREDITS.png")).convert_alpha()
            iw, ih = self.credits_img.get_size()
            scale = min(SCREEN_W / iw, SCREEN_H / ih)
            new_w, new_h = int(iw * scale), int(ih * scale)
            self.credits_img = pygame.transform.smoothscale(self.credits_img, (new_w, new_h))
            self.img_rect = self.credits_img.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2))
        except:
            self.credits_img = None
            self.img_rect = None

    def run(self):
        while True:
            self.clock.tick(FPS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    import sys
                    sys.exit()
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE, pygame.K_SPACE, pygame.K_RETURN):
                        return "back"
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    return "back"
                    
            self.screen.fill((20, 20, 20))
            if self.credits_img:
                self.screen.blit(self.credits_img, self.img_rect)
            else:
                font = pygame.font.SysFont("Consolas", 48, bold=True)
                t = font.render("CREDITS IMAGE NOT FOUND", True, C_AMBER)
                self.screen.blit(t, t.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2)))
                
            pygame.display.flip()


# ──────────────────────────────────────────────
#  ENTRY POINT
# ──────────────────────────────────────────────
def main():
    pygame.init()
    pygame.display.set_caption(TITLE)

    icon_path = os.path.join(ASSETS, "icon.png")
    if os.path.exists(icon_path):
        try:
            pygame.display.set_icon(pygame.image.load(icon_path))
        except Exception:
            pass

    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    clock  = pygame.time.Clock()

    # Pre-load game screen once (avoids re-parsing TMX on every play)
    load_game_sounds()
    game_screen = GameScreen(screen, clock)

    state = "menu"
    menu  = None   # built lazily / re-built after returning from game

    while True:
        # ── MENU ──────────────────────────────
        if state == "menu":
            menu  = MainMenu(screen)
            action = menu.run()

            if action == "start":
                play_bgm('BGM (PLAIN).mp3')
                # Fade out menu → fade in game
                fade_transition(
                    screen, clock,
                    from_draw=lambda s: menu.draw_frame(s),
                    to_draw  =lambda s: game_screen.draw_frame(s),
                )
                state = "game"
            else:
                state = action

        # ── GAME ──────────────────────────────
        elif state == "game":
            action = game_screen.run()

            if action == "menu":
                # Fade out game → fade in menu (re-build so video restarts)
                new_menu = MainMenu(screen)
                fade_transition(
                    screen, clock,
                    from_draw=lambda s: game_screen.draw_frame(s),
                    to_draw  =lambda s: new_menu.draw_frame(s),
                )
                state = "menu"
            elif action == "victory":
                state = "victory"
            elif action == "restart":
                game_screen = GameScreen(screen, clock)
                state = "game"
            else:
                state = action

        # ── VICTORY ───────────────────────────
        elif state == "victory":
            vic = VictoryScreen(screen)
            action = vic.run()
            if action == "restart":
                game_screen = GameScreen(screen, clock)
                state = "game"
            elif action == "menu":
                state = "menu"
            else:
                state = action

        # ── SETTINGS ──────────────────────────
        elif state == "settings":
            settings = SettingsScreen(screen, return_state="menu")
            state = settings.run()

        # ── SETTINGS_GAME ─────────────────────
        elif state == "settings_game":
            settings = SettingsScreen(screen, return_state="game")
            state = settings.run()

        # ── TUTORIAL ──────────────────────────
        elif state == "tutorial":
            tut = TutorialScreen(screen)
            action = tut.run()
            if action == "menu":
                # Fade out tutorial -> fade in menu
                new_menu = MainMenu(screen)
                fade_transition(
                    screen, clock,
                    from_draw=lambda s: tut.draw_frame(s),
                    to_draw  =lambda s: new_menu.draw_frame(s),
                )
                state = "menu"
            else:
                state = action

        # ── QUIT ──────────────────────────────
        elif state == "quit":
            pygame.quit()
            sys.exit()

        else:
            state = "menu"


if __name__ == "__main__":
    main()
