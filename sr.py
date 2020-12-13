import multiprocessing as mp
from queue import Empty
import time
from collections import deque
import array
import random

random.seed()


class PointToPoint:
    _debug = True  # if true then outputs conversation in console

    def __init__(self, protocol_type: str, window_size, lose_prob, transfer_number=-1, seconds=-1):
        self._lose_prob = lose_prob
        self._window_size = window_size

        self._sender_queue = mp.Queue()
        self._receiver_queue = mp.Queue()

        self.pack_number = 0  # number or package that caught for session (used in number mode)

        sender = {
            'sr': {
                'number': self._sr_sender_number
            }
        }
        receiver = {
            'sr': self._sr_receiver
        }

        if transfer_number > 0:
            self._sender_process = mp.Process(target=sender[protocol_type]['number'],
                                              args=(self._sender_queue, self._receiver_queue,
                                                    window_size, lose_prob, transfer_number))
            self._receiver_process = mp.Process(target=receiver[protocol_type],
                                                args=(self._receiver_queue, self._sender_queue, lose_prob, window_size))

    def start_transmission(self):
        self._sender_process.start()
        self._receiver_process.start()

        self._sender_process.join()
        self._receiver_process.terminate()

    class SenderArgs:
        def __init__(self, window_size, lose_prob, Sb=0):
            self.Sn = 0
            self.Sm = window_size
            self.window_size = window_size
            self.need_check = False
            self.lose_prob = lose_prob
            self.Sb = Sb

    @staticmethod
    def _sr_sender_number(sender_queue, receiver_queue, window_size, lose_prob, pack_number):
        args = PointToPoint.SenderArgs(window_size, lose_prob)
        check_deque = deque()
        while args.Sn <= pack_number:
            PointToPoint._sr_sender(sender_queue, receiver_queue, check_deque, args)

    @staticmethod
    def _sr_sender(self_queue, dist_queue, check_deque, args: SenderArgs):
        print_str = 'Передатчик:'
        if args.need_check:
            if len(check_deque) == 0:
                args.need_check = False
                args.Sn = args.Sm
                args.Sm = args.Sm + args.window_size
                if PointToPoint._debug:
                    with open('Передатчик_ср.txt', 'a') as f:
                        print('Передатчик: очередь пуста, увеличить Sm = ' + str(args.Sm), file=f)
                return

            next_ack_number = check_deque.popleft()
            try:
                curr_ack = int(self_queue.get(timeout=0.1).split(':')[1])
                print_str += ' ACK' + str(curr_ack) + ' принят '
            except Empty:
                PointToPoint._send(dist_queue, str(next_ack_number), args.lose_prob)
                print_str += 'pkt' + str(next_ack_number) + ' послан '
                check_deque.append(next_ack_number)
            else:
                if curr_ack != next_ack_number:
                    try:
                        check_deque.remove(curr_ack)
                    except ValueError:
                        pass

                    PointToPoint._send(dist_queue, str(next_ack_number), args.lose_prob)
                    print_str += 'pkt' + str(next_ack_number) + ' послан'
                    check_deque.append(next_ack_number)

        else:
            PointToPoint._send(dist_queue, str(args.Sn), args.lose_prob)
            print_str += 'pkt' + str(args.Sn) + ' послан'
            check_deque.append(args.Sn)
            args.Sn += 1
            if args.Sn == args.Sm:
                args.need_check = True

        if PointToPoint._debug:
            with open('Передатчик_ср.txt', 'a') as f:
                print(print_str, file=f)

    @staticmethod
    def _send(queue: mp.Queue(), message: str, lose_prob):
        r = random.random()
        if r >= lose_prob:
            queue.put(message)

    @staticmethod
    def _sr_receiver(self_queue: mp.Queue(), dist_queue: mp.Queue(), lose_prob, window_size):
        window_i = 0
        Sb, Sm = 0, window_size
        buffer = array.array('i', window_size * [0])
        PointToPoint._arr_init(buffer)
        while True:
            message_number = self_queue.get()
            print_str = 'Ресивер: принят pkt' + message_number
            with open('Ресивер_ср.txt', 'a') as f:
                print(print_str, file=f)

            PointToPoint._send(dist_queue, 'ACK:' + str(message_number), lose_prob)
            number = int(message_number)
            buffer_ind = int(message_number) % window_size

            if buffer[buffer_ind] == -1 and Sb <= number < Sm:
                window_i += 1
                buffer[buffer_ind] = number

            if window_i == window_size:
                window_i = 0
                Sb, Sm = Sb + window_size, Sm + window_size
                if PointToPoint._debug:
                    with open('Ресивер_ср.txt', 'a') as f:
                        print("Ресивер: получено окно ", end='', file=f)
                        print([buffer[i] for i in range(0, window_size)], file=f)
                PointToPoint._arr_init(buffer)

    @staticmethod
    def _arr_init(buffer):
        for i in range(len(buffer)):
            buffer[i] = -1


if __name__ == '__main__':
    ws = 4
    lb = 0.1
    conn = PointToPoint('sr', ws, lb, transfer_number=10)
    conn.start_transmission()
