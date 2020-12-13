import multiprocessing as mp
from queue import Empty
import time
import random

random.seed()


class PointToPoint:
    _debug = True  # if true then outputs conversation in console

    def __init__(self, protocol_type: str, window_size, lose_prob, transfer_number=-1):
        self._lose_prob = lose_prob
        self._window_size = window_size

        self._sender_queue = mp.Queue()
        self._receiver_queue = mp.Queue()

        self.pack_number = 0  # number or package that caught for session (used in number mode)

        sender = {
            'gbn': {
                'number': self._gbn_sender_number,
            }
        }
        receiver = {
            'gbn': self._gbn_receiver
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
    def _send(queue: mp.Queue(), message: str, lose_prob):
        r = random.random()
        if r >= lose_prob:
            queue.put(message)

    @staticmethod
    def _gbn_sender_number(sender_queue, receiver_queue, window_size, lose_prob, pack_number):
        args = PointToPoint.SenderArgs(window_size, lose_prob)
        while args.Sn <= pack_number:
            PointToPoint._gbn_sender(sender_queue, receiver_queue, args)

    @staticmethod
    def _gbn_sender_time(sender_queue, receiver_queue, window_size, lose_prob, work_time, pack_number):
        args = PointToPoint.SenderArgs(window_size, lose_prob)

        start_time = time.time()
        while time.time() < start_time + work_time:
            PointToPoint._gbn_sender(sender_queue, receiver_queue, args)

        pack_number[0] = args.Sb

    @staticmethod
    def _gbn_sender(self_queue: mp.Queue(), dist_queue: mp.Queue(), args: SenderArgs):
        repeat = False
        print_str = 'Передатчик:'
        if args.Sn < args.Sm:
            PointToPoint._send(dist_queue, str(args.Sn), args.lose_prob)
            args.Sn += 1
            print_str += ' послан pkt' + str(args.Sn - 1)
        else:
            try:
                message_number = self_queue.get(timeout=0.1).split(':')[1]
                print_str += ' принят ACK' + message_number + ' Sb = ' + str(args.Sb)
                if int(message_number) == args.Sb:
                    PointToPoint._send(dist_queue, str(args.Sn), args.lose_prob)
                    args.Sn, args.Sb, args.Sm = args.Sn + 1, args.Sb + 1, args.Sm + 1
                elif int(message_number) > args.Sb:
                    repeat = True
            except Empty:
                repeat = True

        if repeat:
            args.Sn = args.Sb
            print_str += ' повтор с Sn = ' + str(args.Sn)

        if PointToPoint._debug:
            with open('передатчик_гбн2.txt', 'a') as f:
                print(print_str, file=f)

    @staticmethod
    def _gbn_receiver(self_queue: mp.Queue(), dist_queue: mp.Queue(), lose_prob, window_size=1):
        Rn = 0
        while True:
            message_number = self_queue.get()
            print_str = 'Ресивер: принят pkt' + message_number
            if Rn == int(message_number):
                print_str += ' доставлен '
                PointToPoint._send(dist_queue, 'ACK:' + str(Rn), lose_prob)
                Rn += 1
            elif Rn < int(message_number):
                PointToPoint._send(dist_queue, 'ACK:' + str(Rn - 1), lose_prob)
            else:
                print_str += ' сброшен '
                PointToPoint._send(dist_queue, 'ACK:' + message_number, lose_prob)

            if PointToPoint._debug:
                with open('ресивер_гбн2.txt', 'a') as f:
                    print(print_str, file=f)


if __name__ == '__main__':
    ws = 4
    lb = 0.2
    conn = PointToPoint('gbn', ws, lb, transfer_number=5 + ws)
    conn.start_transmission()
