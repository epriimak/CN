import src.cmd_parser as parser
import multiprocessing as mp
from queue import Empty
from src.actions import *
import threading, time
from src.router import RouterStateType

ORANGE = (255, 150, 100)
WHITE = (255, 255, 255)
BLUE = (5, 180, 255)
GREEN = (0, 240, 10)
BLACK = (0, 0, 0)
ws = 480  # window size


def display(display_queue: mp.Queue):
    import pygame
    pygame.init()
    sc = pygame.display.set_mode((ws, ws))
    sc.fill(WHITE)
    radius_size = 20
    font = pygame.font.Font(None, 36)
    display_queue.put('init')

    while True:
        for i in pygame.event.get():
            if i.type == pygame.QUIT:
                return

        try:
            [rml, edge_list]  = display_queue.get(timeout=0.2)  # rml means routers_meta_list
            #draw lines
            for edges in edge_list:
                pygame.draw.line(sc, BLACK, (ws * rml[edges[0]].x, ws * rml[edges[0]].y),
                                 (ws * rml[edges[1]].x, ws * rml[edges[1]].y)
                )
            #draw circles
            for meta in rml:
                router_color = GREEN
                if meta.state == RouterStateType.FinishNode:
                    router_color = ORANGE
                elif meta.state == RouterStateType.Transits:
                    router_color = BLUE

                pygame.draw.circle(sc, router_color, (
                    int(meta.x * ws),
                    int(meta.y * ws)),
                    radius_size
                )
                text = font.render(str(meta.id), 1, (180, 0, 0))
                sc.blit(text, (int(meta.x * ws - radius_size // 3), int(meta.y * ws - radius_size // 2)))
        except Empty:
            pass

        pygame.display.update()

key = ''
read_input = False

def input_thread():
    global key
    global read_input
    lock = threading.Lock()
    while True:
        with lock:
            key = input()
            read_input = True
            if key.__eq__('exit'):
                break

if __name__ == "__main__":
    net = Net()
    display_queue = mp.Queue()  # for update display
    display_process = mp.Process(target=display, args=(display_queue,))
    display_process.start()
    display_queue.get()  # waiting for pygame loads in display process

    input_thread = threading.Thread(target=input_thread)
    input_thread.start()

    while True:
        if read_input and key != '':
            read_input = False
            action = parser.cmd_parse(key)
            if action.actionType == ActionType.Exit:
                break
            action.start(net)

        routers_meta_list = []
        net.update_states()
        for router in net.routers.values():
            routers_meta_list.insert(router.meta.id, router.meta)

        display_queue.put([routers_meta_list, net.edge_list])

        time.sleep(0.3)

    display_process.terminate()
    net.terminate()


from enum import Enum


class MessageType(Enum):
    Empty = 0
    Add = 1
    Ping = 2
    ACK = 3


class Message:
    def __init__(self):
        self.type: MessageType = MessageType.Empty


class AddRouterMessage(Message):
    def __init__(self, router_info):
        super().__init__()
        self.type = MessageType.Add
        self.router_info = router_info


class PingMessage(Message):
    def __init__(self, start_node_id: int, finish_node_id: int):
        super().__init__()
        self.type = MessageType.Ping
        self.start_node = start_node_id
        self.finish_node = finish_node_id
        self.previous_node = start_node_id

    def mark(self, current_node: int):
        self.previous_node = current_node


class ACKMessage(PingMessage):
    def __init__(self, start_node_id: int, finish_node_id: int, router_info):
        super().__init__(start_node_id, finish_node_id)
        self.type = MessageType.ACK
        self.router_info = router_info

    def mark(self, current_node: int):
        self.previous_node = current_node


from typing import Dict, List


class Graph:
    def __init__(self, first_node_id: int):
        self.vertices_list: Dict[int, Dict[int, float]] = {first_node_id: {}}

        # destination vertex id -> neighborhood (with which there is a connection) shorted path vertex id
        self.destination_list: Dict[int, int] = {}
        self.base_node_id = first_node_id

    def add_vertex(self, new_vertex_id: int, vertex_list: Dict[int, float]):
        # added new vertex to vertices in list
        for v_id in vertex_list.keys():
            self.vertices_list[v_id][new_vertex_id] = vertex_list[v_id]

        # added new vertex to vertices_list
        self.vertices_list[new_vertex_id] = vertex_list

        self._rebuild_track()

    def _rebuild_track(self):
        track_dict = self._dijkstra_tracks(self.base_node_id)
        track_dict.pop(self.base_node_id)
        for id_v in track_dict.keys():
            if track_dict[id_v]:  # not empty
                new_dist = track_dict[id_v][0]
            else:
                new_dist = -1
            self.destination_list[id_v] = new_dist

    def _dijkstra_tracks(self, start_vertex_id) -> Dict[int, List[int]]:  # returns tracks for each node
        # initialization
        distance_dict: Dict[int, float] = {}
        track_dict: Dict[int, List[int]] = {}
        for id_v in self.vertices_list.keys():
            distance_dict[id_v] = float("InF")
            track_dict[id_v] = []
        distance_dict[start_vertex_id] = 0

        while len(distance_dict) > 0:
            # find next node
            browsed_node_dist = min(distance_dict.values())
            browsed_node: int
            for id_v, dist in distance_dict.items():
                if dist == browsed_node_dist:
                    browsed_node = id_v
                    break
            distance_dict.pop(browsed_node)

            # find next neighborhood node
            for node in self.vertices_list[browsed_node].keys():
                if distance_dict.get(node) is None:  # visited
                    continue

                # calc new length (cost)
                new_cost = browsed_node_dist + self.vertices_list[browsed_node][node]
                if new_cost < distance_dict[node]:
                    distance_dict[node] = new_cost

                    # update track
                    track_dict[node] = track_dict[browsed_node].copy()
                    track_dict[node].append(node)

        return track_dict


import multiprocessing as mp
from typing import Dict, List
from src.ospf_graph import Graph
from src.messages import *
from queue import Empty

class RouterStateType(Enum):
    Default = 0
    Transits = 1
    FinishNode = 2

class MetaRouter:
    def __init__(self, x: float, y: float, max_range: float, id_r: int):
        self.x = x
        self.y = y
        self.max_range = max_range
        self.id = id_r
        self.state = RouterStateType.Default

    def range(self, x_r2: float, y_r2: float) -> float:
        return ((self.x - x_r2) ** 2 + (self.y - y_r2) ** 2) ** 0.5

    def define_state(self, enum_state: int):
        if enum_state == 1:
            self.state = RouterStateType.Transits
        elif enum_state == 2:
            self.state = RouterStateType.FinishNode
        else:
            self.state = RouterStateType.Default


class Router:
    def __init__(self, x: float, y: float, max_range: float, id_r: int, queue_list: [], router_states : mp.Array):
        self.meta: MetaRouter = MetaRouter(x, y, max_range, id_r)
        self._process = mp.Process(target=self.run_process, args=(self.meta, queue_list, router_states))

    @staticmethod
    def add_new_node(
            nodes: Dict[int, MetaRouter],
            new_node: MetaRouter,
            new_node_queue: mp.Queue,
            this_router_meta: MetaRouter,
            neighbor_node_queues: Dict[int, mp.Queue],
            graph: Graph
    ):
        vertex_list: Dict[int, float] = {}
        for node in nodes.values():
            dist = new_node.range(node.x, node.y)
            if dist <= new_node.max_range:
                vertex_list[node.id] = dist

        if new_node.range(this_router_meta.x, this_router_meta.y) <= this_router_meta.max_range:
            neighbor_node_queues[new_node.id] = new_node_queue

        nodes[new_node.id] = new_node
        graph.add_vertex(new_node.id, vertex_list)

    @staticmethod
    def run_process(this_router_meta: MetaRouter, queue_list: List[mp.Queue], router_states : mp.Array):
        # initialization
        this_router_queue = queue_list[this_router_meta.id]
        graph = Graph(this_router_meta.id)
        nodes: Dict[int, MetaRouter] = {this_router_meta.id: this_router_meta}
        neighbor_node_queues: Dict[int, mp.Queue] = {}
        ack_nodes: Dict[id, bool] = {}
        print('Маршрутизатор ' + str(this_router_meta.id) + ' в работе')
        # main loop
        while True:
            try:
                message: Message = this_router_queue.get(timeout=1)
            except Empty:
                router_states[this_router_meta.id] = 0  # RouterStateType.Default
            else:
                out_str = ''.join(['Вершина ', str(this_router_meta.id), " :"])
                if message.type == MessageType.Add:
                    out_str += " добавить "
                    router_states[this_router_meta.id] = 0  # RouterStateType.Default
                    new_node: AddRouterMessage = message
                    ack_nodes[new_node.router_info.id] = False  # no acknowledgment yet
                    Router.add_new_node(nodes, new_node.router_info, queue_list[new_node.router_info.id],
                                        this_router_meta, neighbor_node_queues, graph)

                    for ack_node_id in ack_nodes.keys():
                        if not ack_nodes[ack_node_id] and graph.destination_list[ack_node_id] != -1:
                            ack_nodes[ack_node_id] = True
                            out_str += ' '.join(['ACK к', str(ack_node_id), ', пробросить к',
                                                 str(graph.destination_list[ack_node_id]), ' '])
                            ack = ACKMessage(this_router_meta.id, ack_node_id, this_router_meta)
                            queue_list[graph.destination_list[ack_node_id]].put(ack)

                else: # MessageType.ACK or MessageType.Ping
                    transit_info: ACKMessage = message
                    if transit_info.finish_node == this_router_meta.id:  # this node is final destination node
                        if message.type == MessageType.ACK:
                            out_str += " ACK "
                            if nodes.get(transit_info.start_node) is None:
                                ack_nodes[transit_info.router_info.id] = True
                                Router.add_new_node(nodes, transit_info.router_info, queue_list[transit_info.router_info.id],
                                                    this_router_meta, neighbor_node_queues, graph)
                                out_str += ' '.join(['получить АСК от ', str(transit_info.start_node)])
                        router_states[this_router_meta.id] = 2  # RouterStateType.FinishNode

                    else:  # this node is just a transit node
                        if not graph.destination_list or graph.destination_list.get(transit_info.finish_node) is None:
                            #  cycling transits message put while not graph built with another messages
                            queue_list[this_router_meta.id].put(transit_info)
                        else:
                            router_states[this_router_meta.id] = 1 # RouterStateType.Transits
                            transit_info.mark(this_router_meta.id)
                            out_str += ' '.join(['переход к', str(transit_info.finish_node), ', пробросить к',
                                                 str(graph.destination_list[transit_info.finish_node])])
                            queue_list[graph.destination_list[transit_info.finish_node]].put(transit_info)
                print(out_str)


    def start(self):
        self._process.start()

    def terminate(self):
        self._process.terminate()


from src.router import Router, MetaRouter
from typing import Dict, List
from src.messages import AddRouterMessage, PingMessage
import multiprocessing as mp


class Server:
    def __init__(self, queues_list: List[mp.Queue]):
        self.routers_info: Dict[int, MetaRouter] = {}
        self.queues_list: List[mp.Queue] = queues_list

    def turn_on_router(self, router: Router):
        router.start()  # Run the process

        new_router_meta = router.meta

        message = AddRouterMessage(new_router_meta)
        for current_router_meta in self.routers_info.values():
            self.queues_list[current_router_meta.id].put(message)

        self.routers_info[new_router_meta.id] = new_router_meta

    def ping_routers(self, id_start_node: int, id_finish_node: int):
        message = PingMessage(id_start_node, id_finish_node)
        self.queues_list[id_start_node].put(message)

    def turn_out_router(self):
        pass
