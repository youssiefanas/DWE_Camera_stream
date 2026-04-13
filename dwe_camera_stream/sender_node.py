#!/usr/bin/env python3
"""Sender: grab DWE USB cam via V4L2, encode H.264, stream mpegts/UDP.

Runs ffmpeg as a subprocess with zero-latency tuning. No ROS topics are
published — this node just manages the encoder process lifecycle.
"""

import os
import shlex
import signal
import subprocess

import rclpy
from rclpy.node import Node


class SenderNode(Node):
    def __init__(self):
        super().__init__('dwe_camera_sender')

        self.declare_parameter('device', '/dev/video0')
        self.declare_parameter('width', 1280)
        self.declare_parameter('height', 720)
        self.declare_parameter('fps', 30)
        self.declare_parameter('input_format', 'mjpeg')  # mjpeg or yuyv422
        self.declare_parameter('receiver_ip', '127.0.0.1')
        self.declare_parameter('port', 1234)
        self.declare_parameter('bitrate', '4M')
        self.declare_parameter('gop', 15)

        g = lambda k: self.get_parameter(k).value
        device = g('device')
        width, height, fps = g('width'), g('height'), g('fps')
        in_fmt = g('input_format')
        ip, port = g('receiver_ip'), g('port')
        bitrate = g('bitrate')
        gop = g('gop')

        cmd = (
            f"ffmpeg -hide_banner -loglevel warning "
            f"-fflags nobuffer -flags low_delay "
            f"-probesize 32 -analyzeduration 0 "
            f"-f v4l2 -input_format {in_fmt} "
            f"-framerate {fps} -video_size {width}x{height} "
            f"-i {device} "
            f"-c:v libx264 -preset ultrafast -tune zerolatency "
            f"-g {gop} -bf 0 -refs 1 -b:v {bitrate} -maxrate {bitrate} "
            f"-bufsize {bitrate} -pix_fmt yuv420p "
            f"-flush_packets 1 -muxdelay 0 -muxpreload 0 "
            f"-f mpegts udp://{ip}:{port}?pkt_size=1316"
        )
        self.get_logger().info(f"Launching encoder:\n  {cmd}")
        self._proc = subprocess.Popen(
            shlex.split(cmd),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            preexec_fn=os.setsid,
        )

        self._timer = self.create_timer(1.0, self._watchdog)

    def _watchdog(self):
        if self._proc.poll() is not None:
            self.get_logger().error(
                f"ffmpeg exited with code {self._proc.returncode}; shutting down."
            )
            rclpy.shutdown()

    def destroy_node(self):
        if self._proc and self._proc.poll() is None:
            try:
                os.killpg(os.getpgid(self._proc.pid), signal.SIGINT)
                self._proc.wait(timeout=3)
            except Exception:
                self._proc.kill()
        super().destroy_node()


def main():
    rclpy.init()
    node = SenderNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
