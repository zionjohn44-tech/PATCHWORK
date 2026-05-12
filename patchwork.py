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
SCREEN_W, SCREEN_H = 1280, 720
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

    def __init__(self, image_path, center_x, center_y, action):
        self.action   = action
        self.hovered  = False
        self._hover_t = 0.0

        raw = pygame.image.load(image_path).convert_alpha()
        iw, ih = raw.get_size()
        aspect = ih / iw
        self.base_w = self.BASE_W
        self.base_h = int(self.BASE_W * aspect)
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
            pygame.draw.ellipse(glow, (255, 180, 60, int(60 * self._hover_t)),
                                (0, 0, self.rect.width + 20, self.rect.height + 20))
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
#  TMX MAP RENDERER
# ──────────────────────────────────────────────
class TiledMap:
    """Loads a .tmx file and pre-renders all tile layers onto a surface."""

    def __init__(self, tmx_path):
        self.tmx_path = tmx_path
        self.tmx_data = pytmx.load_pygame(tmx_path, pixelalpha=True)
        self.tw = self.tmx_data.tilewidth
        self.th = self.tmx_data.tileheight
        self.map_w = self.tmx_data.width  * self.tw
        self.map_h = self.tmx_data.height * self.th
        self._surface = self._render()

    def _render(self):
        surf = pygame.Surface((self.map_w, self.map_h))
        surf.fill(C_BG)
        td = self.tmx_data
        for layer in td.visible_layers:
            if isinstance(layer, pytmx.TiledTileLayer):
                for x, y, gid in layer:
                    tile = td.get_tile_image_by_gid(gid)
                    if tile:
                        surf.blit(tile, (x * self.tw, y * self.th))
        return surf

    @property
    def surface(self):
        return self._surface


# ──────────────────────────────────────────────
#  GAME SCREEN  (renders the TMX map with camera)
# ──────────────────────────────────────────────
class GameScreen:
    def __init__(self, screen, clock):
        self.screen = screen
        self.clock  = clock

        tmx_path = os.path.join(MAP_DIR, "try.tmx")
        self.tiled = TiledMap(tmx_path)

        # Camera offset (simple — follows centre of map for now)
        self.cam_x = 0
        self.cam_y = max(0, self.tiled.map_h - SCREEN_H)

        # Font for ESC hint
        self.font = pygame.font.SysFont("Consolas", 20)

    def draw_frame(self, surf):
        surf.blit(self.tiled.surface, (-self.cam_x, -self.cam_y))
        hint = self.font.render("ESC — Main Menu   ← → scroll", True, C_CREAM)
        hint.set_alpha(160)
        surf.blit(hint, (12, 12))

    def run(self):
        scroll_speed = 200  # px/s
        while True:
            dt = self.clock.tick(FPS) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "quit"
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return "menu"

            keys = pygame.key.get_pressed()
            if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                self.cam_x -= scroll_speed * dt
            if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                self.cam_x += scroll_speed * dt

            # Clamp camera
            max_x = max(0, self.tiled.map_w - SCREEN_W)
            max_y = max(0, self.tiled.map_h - SCREEN_H)
            self.cam_x = max(0, min(self.cam_x, max_x))
            self.cam_y = max(0, min(self.cam_y, max_y))

            self.draw_frame(self.screen)
            pygame.display.flip()


# ──────────────────────────────────────────────
#  PLACEHOLDER SCREENS
# ──────────────────────────────────────────────
def placeholder_screen(screen, clock, label):
    font  = pygame.font.SysFont("Consolas", 40, bold=True)
    small = pygame.font.SysFont("Consolas", 24)
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                    return "menu"
        screen.fill(C_BG)
        t = font.render(label, True, C_AMBER)
        screen.blit(t, t.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2 - 30)))
        h = small.render("Press ESC to return to Main Menu", True, C_GREY)
        screen.blit(h, h.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2 + 30)))
        pygame.display.flip()
        clock.tick(FPS)


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
    game_screen = GameScreen(screen, clock)

    state = "menu"
    menu  = None   # built lazily / re-built after returning from game

    while True:
        # ── MENU ──────────────────────────────
        if state == "menu":
            menu  = MainMenu(screen)
            action = menu.run()

            if action == "start":
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
                # Transfer to full menu loop
                state = "menu"
            else:
                state = action

        # ── SETTINGS ──────────────────────────
        elif state == "settings":
            state = placeholder_screen(screen, clock, "SETTINGS")

        # ── QUIT ──────────────────────────────
        elif state == "quit":
            pygame.quit()
            sys.exit()

        else:
            state = "menu"


if __name__ == "__main__":
    main()
