import cv2
import threading
import collections
import socket
import time

import argparse


class VideoCamera(object):

    def __init__(self, videofile):
        # Using OpenCV to capture from device 0. If you have trouble capturing
        # from a webcam, comment the line below out and use a video file
        # instead.
        print 'videofile: ', videofile
        self.video = cv2.VideoCapture(videofile)
        self._frame_count = 0
        # If you decide to use video.mp4, you must have this file in the folder
        # as the main.py.
        # self.video = cv2.VideoCapture('video.mp4')

    def __del__(self):
        self.video.release()

    def get_frame(self):
        success, image = self.video.read()
        self._frame_count += 1
        if self._frame_count == self.video.get(cv2.CAP_PROP_FRAME_COUNT):
            self._frame_count=0
            self.video.set(cv2.CAP_PROP_POS_FRAMES, 0)
            print 'restart video'

        # We are using Motion JPEG, but OpenCV defaults to capture raw images,
        # so we must encode it into JPEG in order to correctly display the
        # video stream.
        if success:
            ret, jpeg = cv2.imencode('.jpg', image)
            return jpeg.tobytes()
        else:
            return None


class HttpVideoStreamer(threading.Thread):

    def __init__(self, name='data_processor', host='localhost', port=9800):
        threading.Thread.__init__(self)
        self._stop_event = threading.Event()
        self.name = name
        self.host = host
        self.port = port

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.settimeout(1)
        self.server_socket.bind((host, port))
        self.server_socket.listen(5)
        self.connections = {}
        print 'starting http video streamer {} on port: {}'.format(self.name, port)

    def run(self):
        while not self._stop_event.is_set():
            try:
                (client_socket, client_address) = self.server_socket.accept()
                address = client_address[0] + ':' + str(client_address[1])

                if address not in self.connections:
                    print 'http video streamer {} is connected with client: {}'.format(self.name, address)
                    self.connections[address] = RemoteClient(self, client_socket, address)
                    self.connections[address].start()
                    print 'http video streamer {} has: {} clients'.format(self.name, len(self.connections))
            except socket.timeout:
                pass

    def broadcast(self, message):

        for client_id in self.connections.keys():
            if self.connections[client_id].isAlive():
                self.connections[client_id].say(message)

    def remove_client(self, client_id):
        if client_id in self.connections.keys():
            print '\nremoving client: {}'.format(client_id)
            self.connections[client_id].stop()
            del self.connections[client_id]
            print 'client: {} is removed'.format(client_id)
            print 'http video streamer {} has: {} clients'.format(self.name, len(self.connections))

    def stop(self):
        print 'http video streamer {} is stopping'.format(self.name)
        # stopping all connection threads.
        for client_id in self.connections.keys():
            self.connections[client_id].stop()
        self.connections = {}

        if self.isAlive():
            self._stop_event.set()
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((self.host, self.port))
            self.server_socket.close()
        print 'http video streamer {} is stopped'.format(self.name)


class RemoteClient(threading.Thread):

    """Wraps a remote client socket."""

    def __init__(self, host, socket, client_id):
        threading.Thread.__init__(self)
        self.setName(str(client_id))
        self.daemon = True
        self._stop_event = threading.Event()
        self.socket = socket
        self.host = host
        self.client_id = client_id
        self.frame_buffer = collections.deque(maxlen=50)
        self.is_first_call = True
        self._last_print = time.time()

    @staticmethod
    def get_frame_header(frame):
        return b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n' + b'\r\n--" + "BoundaryString" + "\r\n'

    @staticmethod
    def get_boundary_header():
        return "\r\n--" + "BoundaryString" + "\r\n"

    @staticmethod
    def get_mjpeg_header():
        return "HTTP/1.0 200 OK\r\n" + \
        "Server: AdxVideoServer \r\n" + \
        "Connection: close\r\n" + \
        "Max-Age: 0\r\n" + \
        "Expires: 0\r\n" + \
        "Cache-Control: no-store, no-cache, must-revalidate, pre-check=0, post-check=0, max-age=0\r\n" + \
        "Pragma: no-cache\r\n" + \
        "Content-Type: multipart/x-mixed-replace; " + "boundary=--" + "BoundaryString" + "\r\n" + "\r\n"

    def say(self, message):
        self.frame_buffer.append(message)

    def run(self):
        while not self._stop_event.is_set():
            if len(self.frame_buffer) > 0:
                try:
                    if self.is_first_call:
                        self.socket.sendall(RemoteClient.get_mjpeg_header())
                        self.is_first_call = False
                    else:
                        frame = self.frame_buffer.popleft()
                        self.socket.sendall(RemoteClient.get_frame_header(frame))
                        self.socket.sendall(RemoteClient.get_boundary_header())
                except socket.error, e:
                    print 'client {} socket error: {}'.format(self.client_id, e)
                    self._stop_event.set()
                except IOError, e:
                    if e.errno == e.errno.EPIPE:
                        print 'client {} socket EPIPE error'.format(self.client_id)
                        self._stop_event.set()
                    else:
                        print 'client {} unknown error'.format(self.client_id)
                        self._stop_event.set()

        self.host.remove_client(self.client_id)

    def stop(self):
        if self.isAlive():
            self._stop_event.set()
            self.socket.close()


import signal


class GracefulKiller:

  kill_now = False

  def __init__(self):
    signal.signal(signal.SIGINT, self.exit_gracefully)
    signal.signal(signal.SIGTERM, self.exit_gracefully)

  def exit_gracefully(self, signum, frame):
    self.kill_now = True


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description="publish a video to a url.")
    parser.add_argument("-v", required=True, help="Input video.")
    parser.add_argument("-n", default=3)
    parser.add_argument("-url", default="localhost:8000", help="url to which the video will be streamed to.")

    args = parser.parse_args()

    video_file = args.v
    num_stream = int(args.n)
    url = args.url
    host, port = url.split(':')

    video = VideoCamera(video_file)

    http_video_streamers = []
    for i in range(num_stream):
        http_video_streamers.append(HttpVideoStreamer(host=host, port=int(port)+i) )

    for http_video_streamer in http_video_streamers:
        http_video_streamer.start()

    killer = GracefulKiller()
    last_print = time.time()
    while True:
        frame = video.get_frame()
        time.sleep(0.04)
        if frame is not None:
            for http_video_streamer in http_video_streamers:
                http_video_streamer.broadcast(frame)
        else:
            if (time.time() - last_print) > 2.0:
                last_print = time.time()
                print 'frame is not valid'

        if killer.kill_now:
            break

    for http_video_streamer in http_video_streamers:
        http_video_streamer.stop()



