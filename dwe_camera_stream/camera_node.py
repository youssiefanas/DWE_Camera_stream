#!/usr/bin/env python3
"""Direct V4L2 camera → ROS 2 Image publisher with minimal latency.

No ffmpeg, no GStreamer, no UDP — just grab frames from /dev/videoX
with OpenCV's V4L2 backend and publish them immediately.

Latency-reduction strategy
--------------------------
- V4L2 backend with 1-buffer queue (``CAP_PROP_BUFFERSIZE = 1``)
- MJPEG pixel format for maximum USB throughput
- ``BEST_EFFORT`` QoS, depth 1 so subscribers always see the newest frame
- Tight grab loop on a dedicated thread; only the most recent frame is published
"""

import threading

import cv2
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import Image
from cv_bridge import CvBridge


class CameraNode(Node):
    def __init__(self):
        super().__init__('dwe_camera_node')

        # ── parameters ──────────────────────────────────────────────
        self.declare_parameter('device',   '/dev/video0')
        self.declare_parameter('width',    1280)
        self.declare_parameter('height',   720)
        self.declare_parameter('fps',      30)
        self.declare_parameter('topic',    'camera_dwe/image_raw')
        self.declare_parameter('frame_id', 'camera')

        device   = self.get_parameter('device').value
        width    = self.get_parameter('width').value
        height   = self.get_parameter('height').value
        fps      = self.get_parameter('fps').value
        topic    = self.get_parameter('topic').value
        self._frame_id = self.get_parameter('frame_id').value

        # ── open camera (V4L2 backend) ──────────────────────────────
        self._cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
        if not self._cap.isOpened():
            self.get_logger().fatal(f'Cannot open {device}')
            raise RuntimeError(f'Cannot open {device}')

        # MJPEG = higher fps over USB; decoded by OpenCV internally
        self._cap.set(cv2.CAP_PROP_FOURCC,
                      cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH,  width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self._cap.set(cv2.CAP_PROP_FPS,          fps)
        # Minimum internal buffer → always grab the freshest frame
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE,   1)

        actual_w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = self._cap.get(cv2.CAP_PROP_FPS)
        self.get_logger().info(
            f'Opened {device}: {actual_w}x{actual_h} @ {actual_fps:.1f} fps'
        )

        # ── ROS publisher ───────────────────────────────────────────
        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )
        self._pub   = self.create_publisher(Image, topic, qos)
        self._bridge = CvBridge()

        # ── capture thread ──────────────────────────────────────────
        self._running = True
        self._thread  = threading.Thread(target=self._capture_loop,
                                         daemon=True)
        self._thread.start()

    # -----------------------------------------------------------------
    def _capture_loop(self):
        """Tight grab-and-publish loop on a background thread."""
        while self._running and rclpy.ok():
            ret, frame = self._cap.read()
            if not ret or frame is None:
                continue
            msg = self._bridge.cv2_to_imgmsg(frame, encoding='bgr8')
            msg.header.stamp    = self.get_clock().now().to_msg()
            msg.header.frame_id = self._frame_id
            self._pub.publish(msg)

    # -----------------------------------------------------------------
    def destroy_node(self):
        self._running = False
        self._thread.join(timeout=2.0)
        try:
            self._cap.release()
        except Exception:
            pass
        super().destroy_node()


def main():
    rclpy.init()
    node = CameraNode()
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
