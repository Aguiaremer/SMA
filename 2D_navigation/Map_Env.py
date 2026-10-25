from maspy import *
from maspy.learning import *
from collections import deque
from random import randint
import random

def generate_map_with_walls(width, height, target, wall_prob=0.1, max_attempts=2000):
    def neighbors(x, y):
        for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
            nx, ny = x+dx, y+dy
            if 0 <= nx < width and 0 <= ny < height:
                yield nx, ny

    for _ in range(max_attempts):
        walls = {(x, y) for x in range(width) for y in range(height)
                 if random.random() < wall_prob and (x, y) != target}

        queue = deque([target])
        reachable = {target}
        while queue:
            cx, cy = queue.popleft()
            for nx, ny in neighbors(cx, cy):
                if (nx, ny) not in walls and (nx, ny) not in reachable:
                    reachable.add((nx, ny))
                    queue.append((nx, ny))

        total_open = width * height - len(walls)
        if len(reachable) == total_open:
            available = sorted(reachable)
            return walls, available

    raise RuntimeError("Failed to generate a valid map.")

class Map(Environment):
    def __init__(self, map_size=(10, 10), walls_prob=0.1):
        super().__init__()
        self.moves = {
            "up": (0, -1),"down": (0, 1), 
            "right": (1, 0), "left": (-1, 0),
        }
        self.map_size = map_size

        #Criação de dois alvos aleatórios
        target1 = (randint(0, self.map_size[0]-1), randint(0, self.map_size[1]-1))
        target2 = (randint(0, self.map_size[0]-1), randint(0, self.map_size[1]-1))

        # Garante que os alvos sejam diferentes
        while target2 == target1:
            target2 = (randint(0, self.map_size[0]-1),randint(0, self.map_size[1]-1))

        self.print(f"Target 1 is at {target1}")
        self.print(f"Target 2 is at {target2}")

        # Gera um mapa conectado considerando os dois alvos
        walls, available = generate_map_with_walls(map_size[0],map_size[1],target1,walls_prob)

        # Remove o segundo alvo das paredes, se ele tiver sido sorteado como parede
        walls.discard(target2)

        self.create(Percept("target1", target1))
        self.create(Percept("target2", target2))

        for wall in walls:
            self.create(Percept("wall", wall))

        self.create(Percept("position", available, listed))
        self.possible_starts = "off-policy"
    
    def reset_positions(self, og_pos):
        for name in ("arrived_target", "arrived_target_name"):
            found = self.get(Percept(name, Any, Any), all=True)
            if isinstance(found, list):
                self.delete(found)

        positions = self.get(
            Percept("agt_position", (Any, Any)), all=True
        )
        assert isinstance(positions, list)

        for position in positions:
            position.change(values=og_pos[position.group])

    def on_connect(self, agt):
        target1 = self.get(Percept("target1", (Any, Any))).values
        target2 = self.get(Percept("target2", (Any, Any))).values
        while True:
            start_pos = (randint(0, self.map_size[0]-1),randint(0, self.map_size[1]-1))
            if (not self.has(Percept("wall", start_pos))
                and start_pos not in (target1, target2)
                and min(abs(start_pos[0] - target1[0]) + abs(start_pos[1] - target1[1]),abs(start_pos[0] - target2[0]) + abs(start_pos[1] - target2[1])) > self.map_size[0] / 2):
                break
        self.create(Percept("agt_position", start_pos, agt))
        #print(f"MAP> Agent {agt} starts at {start_pos}")
    
    def moviment(self, position, direction):
        dx, dy = self.moves[direction]
        new_x = max(0, min(position[0] + dx, self.map_size[0] - 1))
        new_y = max(0, min(position[1] + dy, self.map_size[1] - 1)) 
        return new_x, new_y
    
    def move_transition(self, position, direction):
        reward = -1
        terminated = False
        
        new_position = self.moviment(position, direction)
        target1 = self.get(Percept("target1", (Any, Any))).values
        target2 = self.get(Percept("target2", (Any, Any))).values

        if new_position == target1:
            reward = 10
            terminated = True
        elif new_position == target2:
            reward = 50
            terminated = True
        elif self.has(Percept("wall", new_position)) or position == new_position:
            reward = -10

        return new_position, reward, terminated
    
    @action(listed, ["up", "down", "left", "right"], move_transition)
    def move(self, agt, direction):
        position = self.get(Percept("agt_position", (Any, Any), agt), ck_group=True)
        assert isinstance(position, Percept)
        
        wall_flag = False
        pos = position.values
        if direction == "stay":
            new_pos = pos
        else:
            new_pos = self.moviment(pos, direction)
            if self.has(Percept("wall", new_pos)):
                wall_flag = True
                new_pos = pos
            else:
                position.change(values=new_pos)
        
        n_pos = self.get(Percept("agt_position", (Any, Any), agt), ck_group=True).values

        targets = {"target1": self.get(Percept("target1", (Any, Any))).values,"target2": self.get(Percept("target2", (Any, Any))).values}
        arrived = next((name for name, target_pos in targets.items() if n_pos == target_pos), None)

        if arrived:
            self.print(
                f"{agt} chegou ao {arrived} na posição {n_pos}"
            )

            self.create(Percept("arrived_target", n_pos, agt))
            self.create(Percept("arrived_target_name", arrived, agt))
        elif wall_flag:
            self.print(f"{agt} em {pos} tentou {direction}, mas bateu em uma parede")
        else:
            self.print(f"{agt} em {pos} moveu {direction} para {n_pos}")