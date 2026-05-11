import pygame
import sys
import os
import math
import random

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
FPS = 60
TITLE = "PATCHWORK"

# Colour palette  (warm amber / teal / dark fabric)
C_BG        = (18,  14,  24)
C_DARK      = (28,  22,  38)
C_AMBER     = (255, 180,  60)
C_AMBER2    = (255, 130,  30)
C_TEAL      = ( 60, 210, 190)
C_TEAL2     = ( 30, 160, 150)
C_CREAM     = (240, 230, 210)
C_WHITE     = (255, 255, 255)
C_GREY      = (120, 110, 130)
C_BTN_IDLE  = ( 35,  28,  50)
C_BTN_HOVER = ( 55,  45,  75)
C_BTN_BORD  = (100,  85, 130)
C_BTN_BORD2 = (255, 180,  60)

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")


# ──────────────────────────────────────────────
#  FLOATING STITCH PARTICLE
# ──────────────────────────────────────────────
class StitchParticle:
    def __init__(self):
        self.reset(random.randint(0, SCREEN_H))

    def reset(self, y=None):
        self.x  = random.uniform(0, SCREEN_W)
        self.y  = y if y is not None else SCREEN_H + 10
        self.vx = random.uniform(-0.3, 0.3)
        self.vy = random.uniform(-0.6, -0.2)
        self.size   = random.randint(2, 5)
        self.life   = random.uniform(0.4, 1.0)
        self.max_life = self.life
        # alternating amber / teal
        self.color  = random.choice([C_AMBER, C_TEAL, C_CREAM])

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.life -= 0.003
        if self.life <= 0 or self.y < -20:
            self.reset()

    def draw(self, surf):
        alpha = int(255 * (self.life / self.max_life))
        r, g, b = self.color
        # draw a tiny cross / stitch shape
        s = self.size
        pygame.draw.line(surf, (r, g, b, alpha), (self.x - s, self.y), (self.x + s, self.y), 1)
        pygame.draw.line(surf, (r, g, b, alpha), (self.x, self.y - s), (self.x, self.y + s), 1)


# ──────────────────────────────────────────────
#  MENU BUTTON
# ──────────────────────────────────────────────
class MenuButton:
    def __init__(self, rect, label, font, action=None):
        self.rect    = pygame.Rect(rect)
        self.label   = label
        self.font    = font
        self.action  = action
        self.hovered = False
        self.scale   = 1.0          # for bounce animation
        self._hover_t = 0.0         # 0 → 1 lerp progress

    def update(self, mouse_pos, dt):
        self.hovered = self.rect.collidepoint(mouse_pos)
        target = 1.0 if self.hovered else 0.0
        self._hover_t += (target - self._hover_t) * 0.15
        self.scale = 1.0 + self._hover_t * 0.04

    def draw(self, surf):
        cx, cy = self.rect.centerx, self.rect.centery
        w  = int(self.rect.width  * self.scale)
        h  = int(self.rect.height * self.scale)
        r  = pygame.Rect(cx - w // 2, cy - h // 2, w, h)

        # shadow
        shadow_r = r.inflate(4, 4).move(3, 4)
        shadow_surf = pygame.Surface((shadow_r.width, shadow_r.height), pygame.SRCALPHA)
        shadow_surf.fill((0, 0, 0, 80))
        surf.blit(shadow_surf, shadow_r.topleft)

        # body
        body_color = C_BTN_HOVER if self.hovered else C_BTN_IDLE
        pygame.draw.rect(surf, body_color, r, border_radius=10)

        # border glow
        border_color = C_BTN_BORD2 if self.hovered else C_BTN_BORD
        pygame.draw.rect(surf, border_color, r, width=2, border_radius=10)

        # stitch decoration on border
        if self.hovered:
            dash = 8
            for i in range(r.left + 8, r.right - 8, dash * 2):
                pygame.draw.line(surf, C_AMBER, (i, r.top + 4), (i + dash, r.top + 4), 1)
                pygame.draw.line(surf, C_AMBER, (i, r.bottom - 4), (i + dash, r.bottom - 4), 1)

        # label
        col  = C_AMBER if self.hovered else C_CREAM
        text = self.font.render(self.label, True, col)
        tr   = text.get_rect(center=r.center)
        surf.blit(text, tr)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                return self.action
        return None


# ──────────────────────────────────────────────
#  TITLE RENDERER  (gradient + glow shimmer)
# ──────────────────────────────────────────────
def draw_title(surf, font_big, font_sub, t):
    # subtle vertical shimmer offset
    shimmer = math.sin(t * 1.5) * 4

    # shadow layers
    for ox, oy, a in [(4,6,60),(2,3,90)]:
        shadow = font_big.render(TITLE, True, (0,0,0))
        shadow.set_alpha(a)
        sr = shadow.get_rect(centerx=SCREEN_W // 2 + ox, centery=200 + oy + shimmer)
        surf.blit(shadow, sr)

    # main text – render once then tint with amber gradient via per-pixel blend
    title_surf = font_big.render(TITLE, True, C_CREAM)
    tr = title_surf.get_rect(centerx=SCREEN_W // 2, centery=int(200 + shimmer))
    surf.blit(title_surf, tr)

    # glow overlay (amber)
    glow = font_big.render(TITLE, True, C_AMBER)
    glow_alpha = int(120 + 60 * math.sin(t * 2.0))
    glow.set_alpha(glow_alpha)
    surf.blit(glow, tr)

    # subtitle
    pulse = 0.6 + 0.4 * math.sin(t * 1.2)
    sub   = font_sub.render("A World Stitched Together", True, C_TEAL)
    sub.set_alpha(int(200 * pulse))
    sr = sub.get_rect(centerx=SCREEN_W // 2, centery=270)
    surf.blit(sub, sr)


# ──────────────────────────────────────────────
#  DECORATIVE THREAD LINES
# ──────────────────────────────────────────────
def draw_thread_lines(surf, t):
    for i in range(6):
        phase = t * 0.4 + i * 1.05
        y_base = 350 + i * 60
        pts = []
        for x in range(0, SCREEN_W + 10, 8):
            y = y_base + math.sin(x * 0.015 + phase) * 6
            pts.append((x, y))
        col_a = int(30 + 20 * math.sin(phase))
        pygame.draw.lines(surf, (*C_TEAL2, col_a) if i % 2 == 0 else (*C_AMBER2, col_a), False, pts, 1)


# ──────────────────────────────────────────────
#  MAIN MENU STATE
# ──────────────────────────────────────────────
class MainMenu:
    def __init__(self, screen):
        self.screen = screen
        self.clock  = pygame.time.Clock()
        self.t      = 0.0               # elapsed seconds

        # ---- fonts ----
        pygame.font.init()
        self._load_fonts()

        # ---- background image ----
        self.bg = None
        self._load_bg()

        # ---- cinema bars overlay ----
        self.cinema = None
        self._load_cinema()

        # ---- particles ----
        self.particles = [StitchParticle() for _ in range(80)]

        # ---- particle surface (SRCALPHA for per-pixel alpha) ----
        self.particle_surf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)

        # ---- buttons ----
        btn_w, btn_h = 280, 54
        cx = SCREEN_W // 2
        self.buttons = [
            MenuButton((cx - btn_w//2, 340, btn_w, btn_h), "START GAME",   self.font_btn, "start"),
            MenuButton((cx - btn_w//2, 408, btn_w, btn_h), "SETTINGS",     self.font_btn, "settings"),
            MenuButton((cx - btn_w//2, 476, btn_w, btn_h), "CREDITS",      self.font_btn, "credits"),
            MenuButton((cx - btn_w//2, 544, btn_w, btn_h), "QUIT",         self.font_btn, "quit"),
        ]

        # ---- vignette ----
        self.vignette = self._make_vignette()

        # ---- overlay dim surf ----
        self.dim = pygame.Surface((SCREEN_W, SCREEN_H))
        self.dim.fill(C_BG)

    # ── loaders ──────────────────────────────
    def _load_fonts(self):
        # Try system fonts that look good; fall back gracefully
        def try_font(names, size, bold=False):
            for n in names:
                try:
                    f = pygame.font.SysFont(n, size, bold=bold)
                    return f
                except Exception:
                    continue
            return pygame.font.SysFont(None, size, bold=bold)

        self.font_title = try_font(["Georgia", "Palatino", "Times New Roman", "serif"], 96, bold=True)
        self.font_sub   = try_font(["Garamond","Georgia","Palatino","serif"], 28)
        self.font_btn   = try_font(["Consolas","Courier New","monospace"], 26, bold=True)
        self.font_ver   = try_font(["Consolas","Courier New","monospace"], 18)

    def _load_bg(self):
        # Try the generated background first, then fallback to procedural
        candidates = [
            os.path.join(ASSETS, "menu_bg.png"),
            os.path.join(ASSETS, "background.png"),
        ]
        for p in candidates:
            if os.path.exists(p):
                try:
                    img = pygame.image.load(p).convert()
                    self.bg = pygame.transform.smoothscale(img, (SCREEN_W, SCREEN_H))
                    return
                except Exception:
                    pass
        # procedural gradient fallback
        self.bg = self._make_gradient_bg()

    def _make_gradient_bg(self):
        surf = pygame.Surface((SCREEN_W, SCREEN_H))
        for y in range(SCREEN_H):
            ratio = y / SCREEN_H
            r = int(18  + ratio * 10)
            g = int(14  + ratio * 8)
            b = int(24  + ratio * 30)
            pygame.draw.line(surf, (r, g, b), (0, y), (SCREEN_W, y))
        return surf

    def _load_cinema(self):
        path = os.path.join(ASSETS, "map", "Cinema-Bars-PNG-Images.png")
        if os.path.exists(path):
            try:
                img = pygame.image.load(path).convert_alpha()
                self.cinema = pygame.transform.smoothscale(img, (SCREEN_W, SCREEN_H))
                return
            except Exception:
                pass
        # fallback: black bars
        self.cinema = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        bar_h = 70
        self.cinema.fill((0, 0, 0, 220), (0, 0, SCREEN_W, bar_h))
        self.cinema.fill((0, 0, 0, 220), (0, SCREEN_H - bar_h, SCREEN_W, bar_h))

    def _make_vignette(self):
        surf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        cx, cy = SCREEN_W / 2, SCREEN_H / 2
        max_d  = math.hypot(cx, cy)
        # sample-based vignette (fast enough for once-off creation)
        for y in range(0, SCREEN_H, 4):
            for x in range(0, SCREEN_W, 4):
                d = math.hypot(x - cx, y - cy) / max_d
                a = int(min(255, d ** 1.8 * 200))
                if a > 0:
                    pygame.draw.rect(surf, (0, 0, 0, a), (x, y, 4, 4))
        return surf

    # ── main loop ────────────────────────────
    def run(self):
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            self.t += dt

            action = self._handle_events()
            if action:
                return action

            self._update(dt)
            self._draw()
            pygame.display.flip()

    # ── events ───────────────────────────────
    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return "quit"
            for btn in self.buttons:
                result = btn.handle_event(event)
                if result:
                    return result
        return None

    # ── update ───────────────────────────────
    def _update(self, dt):
        mouse = pygame.mouse.get_pos()
        for btn in self.buttons:
            btn.update(mouse, dt)
        for p in self.particles:
            p.update()

    # ── draw ─────────────────────────────────
    def _draw(self):
        surf = self.screen

        # 1. Background
        surf.blit(self.bg, (0, 0))

        # 2. Dark overlay (breathing)
        dim_alpha = int(90 + 20 * math.sin(self.t * 0.5))
        self.dim.set_alpha(dim_alpha)
        surf.blit(self.dim, (0, 0))

        # 3. Animated thread lines
        draw_thread_lines(surf, self.t)

        # 4. Particles
        self.particle_surf.fill((0, 0, 0, 0))
        for p in self.particles:
            p.draw(self.particle_surf)
        surf.blit(self.particle_surf, (0, 0))

        # 5. Vignette
        surf.blit(self.vignette, (0, 0))

        # 6. Decorative horizontal seam lines around button area
        self._draw_seam_box(surf)

        # 7. Title
        draw_title(surf, self.font_title, self.font_sub, self.t)

        # 8. Buttons
        for btn in self.buttons:
            btn.draw(surf)

        # 9. Cinema bars
        surf.blit(self.cinema, (0, 0))

        # 10. Version / footer
        ver = self.font_ver.render("v0.1.0  |  PATCHWORK  |  2026", True, C_GREY)
        surf.blit(ver, ver.get_rect(centerx=SCREEN_W // 2, bottom=SCREEN_H - 12))

    def _draw_seam_box(self, surf):
        # decorative stitched border around the button panel
        pad  = 30
        bx   = SCREEN_W // 2 - 180
        by   = 318
        bw   = 360
        bh   = 300
        rect = pygame.Rect(bx - pad, by - pad, bw + pad * 2, bh + pad * 2)
        # faint fill
        panel = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        panel.fill((20, 15, 35, 120))
        surf.blit(panel, rect.topleft)
        # stitched border
        pygame.draw.rect(surf, C_BTN_BORD, rect, 1, border_radius=14)
        dash = 12
        for i in range(rect.left + 12, rect.right - 12, dash * 2):
            pygame.draw.line(surf, C_GREY, (i, rect.top + 5), (i + dash, rect.top + 5), 1)
            pygame.draw.line(surf, C_GREY, (i, rect.bottom - 5), (i + dash, rect.bottom - 5), 1)
        for j in range(rect.top + 12, rect.bottom - 12, dash * 2):
            pygame.draw.line(surf, C_GREY, (rect.left + 5, j), (rect.left + 5, j + dash), 1)
            pygame.draw.line(surf, C_GREY, (rect.right - 5, j), (rect.right - 5, j + dash), 1)


# ──────────────────────────────────────────────
#  PLACEHOLDER SCREENS  (stubs for later)
# ──────────────────────────────────────────────
def placeholder_screen(screen, clock, label):
    font = pygame.font.SysFont("Consolas", 40, bold=True)
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

    # try to set an icon
    icon_path = os.path.join(ASSETS, "icon.png")
    if os.path.exists(icon_path):
        try:
            pygame.display.set_icon(pygame.image.load(icon_path))
        except Exception:
            pass

    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    clock  = pygame.time.Clock()

    state = "menu"
    while True:
        if state == "menu":
            state = MainMenu(screen).run()

        elif state == "start":
            state = placeholder_screen(screen, clock, "GAME  —  Coming Soon")

        elif state == "settings":
            state = placeholder_screen(screen, clock, "SETTINGS")

        elif state == "credits":
            state = placeholder_screen(screen, clock, "CREDITS")

        elif state == "quit":
            pygame.quit()
            sys.exit()

        else:
            state = "menu"


if __name__ == "__main__":
    main()
