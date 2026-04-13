#!/usr/bin/env python3
"""Receiver: decode mpegts/UDP H.264 via GStreamer appsink, publish Image."""

import cv2
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import Image
from cv_bridge import CvBridge


def build_pipeline(port: int) -> str:
    # Low-latency: tiny udp buffer, parse-before-decode, drop old frames,
    # appsink sync=false so we never wait on clocks.
    return (
        f"udpsrc port={port} buffer-size=65536 "
        f"caps=\"application/x-rtp, media=video\" ! "
        f"queue max-size-buffers=1 leaky=downstream ! "
        f"tsdemux ! h264parse ! avdec_h264 ! "
        f"videoconvert ! video/x-raw,format=BGR ! "
        f"appsink drop=true max-buffers=1 sync=false"
    )


class ReceiverNode(Node):
    def __init__(self):
        super().__init__('dwe_camera_receiver')

        self.declare_parameter('port', 1234)
        self.declare_parameter('topic', 'camera/image_raw')
        self.declare_parameter('frame_id', 'camera')
        self.declare_parameter('pipeline', '')

        port = self.get_parameter('port').value
        topic = self.get_parameter('topic').value
        self._frame_id = self.get_parameter('frame_id').value
        custom = self.get_parameter('pipeline').value

        # udpsrc for mpegts does not use RTP caps; override above default.
        pipeline = custom or (
            f"udpsrc port={port} buffer-size=65536 ! "
            f"queue max-size-buffers=1 leaky=downstream ! "
            f"tsdemux ! h264parse ! avdec_h264 ! "
            f"videoconvert ! video/x-raw,format=BGR ! "
            f"appsink drop=true max-buffers=1 sync=false"
        )
        self.get_logger().info(f"GStreamer pipeline:\n  {pipeline}")

        self._cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
        if not self._cap.isOpened():
            self.get_logger().fatal(
                "Failed to open GStreamer pipeline. "
                "Check OpenCV GStreamer support and that gst plugins (good/bad/libav) are installed."
            )
            raise RuntimeError("GStreamer pipeline not opened")

        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )
        self._pub = self.create_publisher(Image, topic, qos)
        self._bridge = CvBridge()

        # Tight loop — use a timer at high rate so spin can still process.
        self._timer = self.create_timer(0.0, self._tick)

    def _tick(self):
        ret, frame = self._cap.read()
        if not ret or frame is None:
            return
        msg = self._bridge.cv2_to_imgmsg(frame, encoding='bgr8')
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self._frame_id
        self._pub.publish(msg)

    def destroy_node(self):
        try:
            self._cap.release()
        except Exception:
            pass
        super().destroy_node()


def main():
    rclpy.init()
    node = ReceiverNode()
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
