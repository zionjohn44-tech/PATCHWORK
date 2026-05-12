import pygame
import pytmx
import sys

# Configuration
SCREEN_WIDTH = 640
SCREEN_HEIGHT = 320
SCALE = 2 # Scale factor
TILE_SIZE = 16
FPS = 60

class Player(pygame.sprite.Sprite):
    def __init__(self, pos, groups, collision_sprites):
        super().__init__(groups)
        
        # Animation
        self.import_assets()
        self.frame_index = 0
        self.animation_speed = 8
        self.status = 'idle'
        self.flip = False
        self.image = self.animations[self.status][self.frame_index]
        
        self.rect = self.image.get_rect(topleft=pos)
        self.hitbox = self.rect.inflate(-12, -18) 
        
        # Movement flags
        self.moving_left = False
        self.moving_right = False
        
        # Movement attributes
        self.speed = 100 
        self.pos = pygame.math.Vector2(self.rect.topleft)
        self.direction = pygame.math.Vector2()
        self.gravity = 800
        self.jump_speed = -300
        self.in_air = False
        self.collision_sprites = collision_sprites

    def import_assets(self):
        self.animations = {'idle': [], 'run': [], 'jump': []}
        
        # Slicer helper
        def get_frames(path, frame_width):
            full_surf = pygame.image.load(path).convert_alpha()
            frames = []
            for i in range(full_surf.get_width() // frame_width):
                x = i * frame_width
                frame = pygame.Surface((frame_width, full_surf.get_height()), pygame.SRCALPHA)
                frame.blit(full_surf, (0, 0), (x, 0, frame_width, full_surf.get_height()))
                frames.append(frame)
            return frames

        self.animations['idle'] = get_frames('spritesheet/Player/Idle.png', 32)
        self.animations['run'] = get_frames('spritesheet/Player/Run.png', 32)
        self.animations['jump'] = get_frames('spritesheet/Player/Jump.png', 32)

    def get_status(self):
        if self.in_air:
            self.status = 'jump'
        elif self.moving_left or self.moving_right:
            self.status = 'run'
        else:
            self.status = 'idle'

    def animate(self, dt):
        self.frame_index += self.animation_speed * dt
        if self.frame_index >= len(self.animations[self.status]):
            self.frame_index = 0
            
        image = self.animations[self.status][int(self.frame_index)]
        if self.flip:
            self.image = pygame.transform.flip(image, True, False)
        else:
            self.image = image

    def jump(self):
        if not self.in_air:
            self.direction.y = self.jump_speed
            self.in_air = True

    def update(self, dt):
        # Horizontal
        dx = 0
        if self.moving_right: dx = 1; self.flip = False
        elif self.moving_left: dx = -1; self.flip = True
        
        self.pos.x += dx * self.speed * dt
        self.hitbox.centerx = round(self.pos.x + self.rect.width / 2)
        self.horizontal_collision()
        self.rect.centerx = self.hitbox.centerx

        # Vertical
        self.apply_gravity(dt)
        self.vertical_collision()
        self.rect.centery = self.hitbox.centery

        self.get_status()
        self.animate(dt)

    def horizontal_collision(self):
        for sprite in self.collision_sprites:
            if sprite.rect.colliderect(self.hitbox):
                if self.hitbox.centerx < sprite.rect.centerx: # Right
                    self.hitbox.right = sprite.rect.left
                else: # Left
                    self.hitbox.left = sprite.rect.right
                self.pos.x = self.hitbox.left - (self.rect.width - self.hitbox.width) / 2

    def apply_gravity(self, dt):
        self.direction.y += self.gravity * dt
        self.pos.y += self.direction.y * dt
        self.hitbox.centery = round(self.pos.y + self.rect.height / 2)

    def vertical_collision(self):
        # We start by assuming the player is in the air
        self.in_air = True
        for sprite in self.collision_sprites:
            if sprite.rect.colliderect(self.hitbox):
                if self.direction.y > 0: # Falling
                    self.hitbox.bottom = sprite.rect.top
                    self.direction.y = 0
                    self.in_air = False # Hit ground
                elif self.direction.y < 0: # Jumping
                    self.hitbox.top = sprite.rect.bottom
                    self.direction.y = 0
                self.pos.y = self.hitbox.top - (self.rect.height - self.hitbox.height) / 2

class Tile(pygame.sprite.Sprite):
    def __init__(self, pos, groups):
        super().__init__(groups)
        # Invisible collision tile (strictly for the 'Collisions' layer)
        self.image = pygame.Surface((TILE_SIZE, TILE_SIZE))
        self.rect = self.image.get_rect(topleft=pos)

class Tree(pygame.sprite.Sprite):
    def __init__(self, pos, surf, groups, tree_type):
        super().__init__(groups)
        self.image = surf
        self.rect = self.image.get_rect(topleft=pos)
        self.tree_type = tree_type 

class CameraGroup(pygame.sprite.Group):
    def __init__(self, internal_surf):
        super().__init__()
        self.display_surface = internal_surf
        self.offset = pygame.math.Vector2()

    def custom_draw(self, center_sprite, tmx_data):
        # Calculate camera offset to center on the player/spawn point
        if center_sprite:
            self.offset.x = center_sprite.rect.centerx - SCREEN_WIDTH // 2
            self.offset.y = center_sprite.rect.centery - SCREEN_HEIGHT // 2
        
        # Keep camera within map bounds
        map_width = tmx_data.width * tmx_data.tilewidth
        map_height = tmx_data.height * tmx_data.tileheight
        self.offset.x = max(0, min(self.offset.x, map_width - SCREEN_WIDTH))
        self.offset.y = max(0, min(self.offset.y, map_height - SCREEN_HEIGHT))

        # 1. Draw Map Background
        for layer in tmx_data.visible_layers:
            if isinstance(layer, pytmx.TiledTileLayer):
                for x, y, gid in layer:
                    tile = tmx_data.get_tile_image_by_gid(gid)
                    if tile:
                        pos = (x * tmx_data.tilewidth - self.offset.x, y * tmx_data.tileheight - self.offset.y)
                        self.display_surface.blit(tile, pos)

        # 2. Draw Sprites (Sorted by bottom Y for depth)
        for sprite in sorted(self.sprites(), key=lambda sprite: sprite.rect.bottom):
            # We don't draw the invisible collision tiles and definitely NO collisions for trees
            if not isinstance(sprite, Tile):
                offset_pos = sprite.rect.topleft - self.offset
                self.display_surface.blit(sprite.image, offset_pos)

def main():
    pygame.init()
    # The actual window is scaled up
    window = pygame.display.set_mode((SCREEN_WIDTH * SCALE, SCREEN_HEIGHT * SCALE))
    # We render everything to this internal surface first
    display_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    
    pygame.display.set_caption("Patchwork - Map Assets View (2x Scale)")
    clock = pygame.time.Clock()

    # Load Tiled map
    try:
        tmx_data = pytmx.util_pygame.load_pygame('patchwork-maps/lvl1.tmx')
    except Exception as e:
        print(f"Error loading map: {e}")
        pygame.quit()
        sys.exit()

    # Groups
    visible_sprites = CameraGroup(display_surface)
    # This group ONLY contains the 'Collisions' layer tiles
    collision_sprites = pygame.sprite.Group()

    # Create map collisions from 'Collisions' layer
    for layer in tmx_data.visible_layers:
        if isinstance(layer, pytmx.TiledTileLayer) and layer.name == "Collisions":
            for x, y, gid in layer:
                if gid != 0:
                    Tile((x * TILE_SIZE, y * TILE_SIZE), [collision_sprites])

    # Create objects from Entities layer
    player = None
    entities_layer = tmx_data.get_layer_by_name("Entities")
    
    for obj in entities_layer:
        if obj.name == "PlayerSpawn":
            player = Player((obj.x, obj.y), [visible_sprites], collision_sprites)
        elif obj.name in ["Tree1", "Tree2", "Tree3", "Tree4"]:
            tree_image = tmx_data.get_tile_image_by_gid(obj.gid)
            # Trees are added to visible_sprites ONLY, not collision_sprites
            Tree((obj.x, obj.y), tree_image, [visible_sprites], obj.name)

    # Game Loop
    while True:
        # Cap delta time to prevent huge jumps
        dt = min(clock.tick(FPS) / 1000, 0.1)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            
            # Input handling
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_LEFT or event.key == pygame.K_a:
                    player.moving_left = True
                if event.key == pygame.K_RIGHT or event.key == pygame.K_d:
                    player.moving_right = True
                if event.key == pygame.K_SPACE or event.key == pygame.K_w:
                    player.jump()
            
            if event.type == pygame.KEYUP:
                if event.key == pygame.K_LEFT or event.key == pygame.K_a:
                    player.moving_left = False
                if event.key == pygame.K_RIGHT or event.key == pygame.K_d:
                    player.moving_right = False

        # 1. Update sprites
        visible_sprites.update(dt)

        # 2. Render everything to the small surface
        display_surface.fill('#333333')
        visible_sprites.custom_draw(player, tmx_data)
        
        # 3. Scale the small surface and blit it to the main window
        scaled_surface = pygame.transform.scale(display_surface, (SCREEN_WIDTH * SCALE, SCREEN_HEIGHT * SCALE))
        window.blit(scaled_surface, (0, 0))
        
        pygame.display.update()

if __name__ == '__main__':
    main()
